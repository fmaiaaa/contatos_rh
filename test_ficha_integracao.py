"""Regressões de integração sem acessar Salesforce, Sheets ou SMTP."""
import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from contextlib import ExitStack

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

    def test_videos_usam_apenas_regional_enviada(self):
        for reg, esperado in [('RJ', True), ('MG', False), ('', False), (None, False)]:
            with patch.object(app.st, 'session_state', {'ficha_dados_enviados': {'regional_cadastro': reg}, 'fld_regional_cadastro': 'RJ'}):
                self.assertEqual(app._regional_cadastro_enviada_rj(), esperado)

    def test_dimensoes_fixas_e_sem_quebra_de_texto(self):
        ws = SimpleNamespace(id=10, spreadsheet=Mock())
        app._fixar_dimensoes_aba_corretores(ws)
        reqs = ws.spreadsheet.batch_update.call_args.args[0]['requests']
        self.assertEqual(reqs[0]['updateDimensionProperties']['properties']['pixelSize'], 32)
        self.assertEqual(reqs[1]['updateDimensionProperties']['properties']['pixelSize'], 180)
        self.assertEqual(reqs[2]['repeatCell']['cell']['userEnteredFormat']['wrapStrategy'], 'CLIP')

    def test_append_usa_linha_confirmada_pela_api_em_envios_simultaneos(self):
        ws = Mock(id=10)
        ws.get_all_values.return_value = [['A']]
        ws.append_row.return_value = {'updates': {'updatedRange': "'Corretores'!A42:B42"}}
        sh = Mock()
        cliente = Mock()
        cliente.open_by_key.return_value = sh
        with patch.object(app, '_cliente_gspread', return_value=cliente), patch.object(app, '_resolver_worksheet_planilha', return_value=ws), patch.object(app, '_garantir_aba_valores_fixos'), patch.object(app, '_garantir_aba_dicionario'), patch.object(app, '_cabecalho_planilha_desalinhado', return_value=False):
            self.assertEqual(app.anexar_linha(['00123'], ['A'], 'planilha-associada', 'Corretores', {}), 42)
        cliente.open_by_key.assert_called_once_with('planilha-associada')
        ws.append_row.assert_called_once_with(['00123'], value_input_option='RAW')
        self.assertEqual(ws.get_all_values.call_count, 1)

    def test_confirmacao_exige_salesforce_e_planilha(self):
        for cid, linha, esperado in [(None, 42, False), (self.cid, None, False), (self.cid, 42, True)]:
            with self.subTest(cid=cid, linha=linha), ExitStack() as stack:
                state = {'fld_lgpd_ficha': True}
                stack.enter_context(patch.object(app.st, 'session_state', state))
                stack.enter_context(patch.object(app.st, 'secrets', {'google_sheets': {'SPREADSHEET_ID': 'associada'}}))
                stack.enter_context(patch.object(app.st, 'caption'))
                stack.enter_context(patch.object(app.st, 'rerun'))
                funcs = {
                    'verificar_antes_envio': (True, ''), 'secoes_com_campos_visiveis': ['Dados Pessoais'],
                    '_snapshot_persistir_secao_atual': None, '_snapshot_mesclar_todos_fld_do_session_state': None,
                    '_coletar_dados_formulario_completo': {'regional_cadastro': 'MG'},
                    'enriquecer_derivados_vendas_rj': {'regional_cadastro': 'MG'},
                    'validar_obrigatorios': [], '_credenciais_google_sheets': {'cred': True},
                    'montar_payload_salesforce': ({}, []), '_enriquecer_mobile_phone': [],
                    'linha_planilha': [], 'cabecalho_planilha': [], '_aplicar_secrets_sf': None,
                    '_credenciais_salesforce_ok': True, 'conectar_salesforce_diagnostico': (self.sf, None),
                    'criar_contato_salesforce_preparado': (cid, 'falha SF' if not cid else None, {}),
                    '_gravar_cadastro_planilha': linha,
                }
                mocks = {name: stack.enter_context(patch.object(app, name, return_value=value)) for name, value in funcs.items()}
                stack.enter_context(patch.object(app, '_SF_SDK_DISPONIVEL', True))
                email = stack.enter_context(patch.object(app, '_tentar_enviar_email_boas_vindas'))
                app._processar_envio_cadastro_impl()
                self.assertEqual(bool(state.get('ficha_sucesso')), esperado)
                self.assertEqual(email.called, esperado)
                self.assertEqual(mocks['_gravar_cadastro_planilha'].call_args.args[2], 'associada')

    def test_status_na_planilha_deve_ser_confirmado_por_leitura(self):
        ws = Mock()
        ws.row_values.side_effect = [['Link do contato', 'Envio?', 'Log / erro'], ['', '', ''], ['', 'Erro', '']]
        with patch.object(app, '_cliente_gspread'), patch.object(app, '_resolver_worksheet_planilha', return_value=ws):
            with self.assertRaisesRegex(RuntimeError, 'não confirmou'):
                app.atualizar_status_envio_salesforce('associada', 'Corretores', {}, 42, 'Ok', '', 'https://contato')


if __name__ == '__main__':
    unittest.main()
