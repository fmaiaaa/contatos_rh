"""Regressões de integração sem acessar Salesforce, Sheets ou SMTP."""
import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import ficha_cadastral_vendas_rj_streamlit as app


class IntegracaoTests(unittest.TestCase):
    def setUp(self):
        self.sf = SimpleNamespace(Contact=Mock(), query=Mock())
        self.aid = '001000000000001AAA'
        self.cid = '003U6000013mV9OIAU'

    def test_payload_descarta_nome_de_pessoa_como_campo_e_normaliza_email(self):
        payload = app._filtrar_payload_contact_insert({
            'YNARA AZEVEDO DA SILVA': 'invalido', 'Gerente_de_Vendas__c': 'x',
            'Email': 'nome.direcionalvendas@.gmail.com', 'LastName': 'Teste',
        })
        self.assertEqual(payload, {'Email': 'nome.direcionalvendas@gmail.com', 'LastName': 'Teste'})
        with self.assertRaises(ValueError):
            app._filtrar_payload_contact_insert({'Email': 'email-invalido'})

    def test_conta_obrigatoria_rj_e_mg_ignora_gerente_e_id_antigos(self):
        for regional in ('RJ', 'MG'):
            with self.subTest(regional=regional), patch.object(app, '_resolver_account_id_por_nome', return_value=self.aid) as resolver, patch.object(app, '_proximo_apelido_disponivel', return_value='TESTE01'):
                dados = {'regional_cadastro': regional, 'gerente_vendas': 'Outra equipe'}
                payload = {'AccountId': '001OUTRA', 'FirstName': 'Teste'}
                app._aplicar_enriquecimentos_payload_sf(payload, dados, self.sf, [])
                self.assertEqual(payload['AccountId'], self.aid)
                resolver.assert_called_once_with(self.sf, 'COORDENADORES DV - RJ')
        self.assertFalse(any(c['key'] == 'gerente_vendas' for c in app.campos_por_secao_visiveis('Informações para contato')))
        self.assertNotIn('gerente_vendas', app._CHAVES_FORA_FORM_INFO_CONTATO)
        self.assertTrue(any(c['key'] == 'gerente_vendas' for c in app.campos_planilha_corretor()))

    def test_conta_ausente_nao_cria_contato_desvinculado(self):
        with patch.object(app, '_resolver_account_id_por_nome', return_value=None):
            cid, err, _ = app.criar_contato_salesforce_preparado(self.sf, {}, {}, [])
        self.assertIsNone(cid)
        self.assertIn('Conta obrigatória', err)
        self.sf.Contact.create.assert_not_called()

    def test_cpf_mascarado_sem_reutilizar_celular_compartilhado(self):
        self.sf.query.side_effect = [{'records': []}, {'records': [{'Id': self.cid}]}]
        cid, campo = app._buscar_contact_id_existente(self.sf, {'CPF__c': '12345678901', 'MobilePhone': '21999999999'})
        self.assertEqual((cid, campo), (self.cid, 'CPF'))
        self.assertIn('123.456.789-01', self.sf.query.call_args.args[0])
        self.sf.query.reset_mock()
        self.assertEqual(app._buscar_contact_id_existente(self.sf, {'MobilePhone': '21999999999', 'CRECI__c': 1}), (None, None))
        self.sf.query.assert_not_called()

    def test_duplicata_cpf_retorna_contato_e_atualiza_arvore(self):
        payload = {'AccountId': self.aid, 'CPF__c': '12345678901'}
        err = f"DUPLICATES_DETECTED CPF_Contato /Contact/{self.cid}"
        with patch.object(app, '_preparar_payload_insert_salesforce', return_value=payload), patch.object(app, '_buscar_contact_id_existente', return_value=(None, None)), patch.object(app, 'criar_contato_payload_com_fallback_naturalidade', return_value=(None, err, payload)):
            cid, erro, _ = app.criar_contato_salesforce_preparado(self.sf, payload, {}, [])
        self.assertEqual(cid, self.cid)
        self.assertIsNone(erro)
        self.sf.Contact.update.assert_called_once_with(self.cid, {'AccountId': self.aid})

    def test_falha_ao_mover_existente_nao_indica_sucesso(self):
        self.sf.Contact.update.side_effect = RuntimeError('sem permissão')
        with patch.object(app, '_preparar_payload_insert_salesforce', return_value={'AccountId': self.aid}), patch.object(app, '_buscar_contact_id_existente', return_value=(self.cid, 'CPF')):
            cid, err, _ = app.criar_contato_salesforce_preparado(self.sf, {}, {}, [])
        self.assertIsNone(cid)
        self.assertIn('sem permissão', err)

    def test_token_opcional(self):
        with patch.dict(os.environ, {'SALESFORCE_USER': 'teste', 'SALESFORCE_PASSWORD': 'teste', 'SALESFORCE_TOKEN': ''}):
            self.assertTrue(app._credenciais_salesforce_ok())

    def test_conexao_repete_so_falha_transitoria_de_rede(self):
        with patch.dict(os.environ, {'SALESFORCE_USER': 'teste', 'SALESFORCE_PASSWORD': 'teste'}), patch.object(app, '_SF_SDK_DISPONIVEL', True), patch.object(app, 'Salesforce', side_effect=[app.requests.exceptions.ConnectionError(), self.sf], create=True) as login, patch.object(app.time, 'sleep'):
            sf, erro = app.conectar_salesforce_diagnostico()
        self.assertIs(sf, self.sf)
        self.assertIsNone(erro)
        self.assertEqual(login.call_count, 2)


if __name__ == '__main__':
    unittest.main()
