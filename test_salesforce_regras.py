"""Regressões a partir dos metadados e das fórmulas auditadas de Contact."""
import unittest
from unittest.mock import patch
from datetime import date
import ficha_cadastral_vendas_rj_streamlit as app
from salesforce_regras import *
import salesforce_integracao as integration

VALID={'CPF__c':'52998224725','MobilePhone':'21999999999','LastName':'EXEMPLO','Atividade__c':'Captador','EstadoCivil__c':'Solteiro','EnderecoResidencialEstado__c':'RJ','Status_Corretor__c':'Pré credenciado'}

class RegrasContactTests(unittest.TestCase):
    def test_esquema_213_campos_20_regras_ativas_16_criacao(self):
        schema=esquema_local()
        self.assertEqual(len(schema['fields']),213)
        self.assertEqual(sum(r['active'] for r in schema['validation_rules']),20)
        self.assertEqual(sum(r['creation'] for r in schema['validation_rules']),16)
        self.assertEqual(sum(r['active'] for r in schema['duplicate_rules']),2)

    def test_limites_verificados_que_divergiam(self):
        expected={'Ag_ncia_Banc_ria__c':4,'Email':80,'Observacoes__c':500,'FirstName':40,'LastName':80,'Naturalidade__c':50,'Nome_do_Conjuge__c':50,'Conta_Banc_ria__c':20,'RG__c':25,'EnderecoResidencialCEP__c':9,'EnderecoResidencialEstado__c':2}
        for api,maximum in expected.items():
            with self.subTest(api=api):self.assertEqual(esquema_local()['fields'][api]['length'],maximum)

    def test_todos_textos_gravaveis_recusam_limite_mais_um(self):
        tested=0
        for f in esquema_local()['fields'].values():
            if f['createable'] and f['type'] in {'string','textarea','email','phone','url','encryptedstring'} and f['length']:
                with self.subTest(api=f['name']):
                    errors=validar_valor(f,'A'*(f['length']+1))
                    self.assertTrue(any('máximo de' in e for e in errors))
                    tested+=1
        self.assertGreater(tested,30)

    def test_agencia_falha_na_secao_antes_do_envio(self):
        errors=app.validar_obrigatorios_secao('Dados Bancários Pessoa Física',{'agencia_bancaria':'1234213'})
        self.assertTrue(any('4 caracteres' in e for e in errors),str(errors))
        self.assertEqual(limite_campo(next(c for c in app.CAMPOS if c['key']=='agencia_bancaria')),4)

    def test_18_digitos_sem_arredondar_e_19_recusados(self):
        f=esquema_local()['fields']['CRECI__c']
        self.assertEqual(validar_valor(f,'123456789012345678'),[])
        self.assertTrue(validar_valor(f,'1234567890123456789'))
        self.assertTrue(validar_valor(f,'1.5'))
        self.assertEqual(numero('123456789012345678'),Decimal('123456789012345678'))

    def test_precisao_8_escala_6(self):
        f=esquema_local()['fields']['Multiplicador__c']
        self.assertEqual(validar_valor(f,'99.999999'),[])
        for value in ['100','0.0000001','NaN','Infinity',True]:
            with self.subTest(value=value):self.assertTrue(validar_valor(f,value))

    def test_datas_e_booleanos_validos(self):
        f=esquema_local()['fields']['Birthdate']
        self.assertTrue(validar_valor(f,'2026-02-30'))
        self.assertEqual(validar_valor(f,'2000-02-29'),[])
        boolean={'name':'Teste','type':'boolean'}
        self.assertTrue(validar_valor(boolean,'false'))
        self.assertEqual(validar_valor(boolean,False),[])

    def test_referencias_validam_objeto_alvo(self):
        schema=esquema_local();f=schema['fields']['AccountId'];prefix=schema['reference_prefixes']
        self.assertEqual(validar_valor(f,'001000000000001',prefix),[])
        self.assertTrue(validar_valor(f,'005000000000001',prefix))
        self.assertTrue(validar_valor(f,'001INCOMPLETO',prefix))

    def test_email_de_80_aceito_81_recusado(self):
        f=esquema_local()['fields']['Email']
        email='a'*68+'@example.org'
        self.assertEqual(len(email),80)
        self.assertEqual(validar_valor(f,email),[])
        self.assertTrue(validar_valor(f,'a'+email))

    def test_nome_nao_e_cortado_antes_da_validacao(self):
        p={};app._aplicar_nome_completo(p,{'nome_completo':'A'*41+' '+'B'*81})
        self.assertEqual(len(p['FirstName']),41)
        self.assertEqual(len(p['LastName']),81)
        errors=validar_formulario({'nome_completo':'A'*41+' '+'B'*81},app.CAMPOS)
        self.assertGreaterEqual(len(errors),2)

    def test_as_16_regras_de_criacao_tem_cenario_de_bloqueio(self):
        cases={
            'BlackList_CNPJ':{'CNPJ__c':'11.111.111/1111-11'},
            'BlackList_CPF':{'CPF__c':'111.111.111-11'},
            'CNPJ_Obrigatorio':{'Corretor_Associado__c':'PJ / Empresa Própria'},
            'CRECICoretor':{'Atividade__c':'Corretor'},
            'Campo_origem_indicacao':{'Origem__c':'Indicação'},
            'Celular_obrigatorio':{'MobilePhone':''},
            'Data_de_saida_obrigatorio':{'Status_Corretor__c':'Inativo'},
            'Informar_Motivo_Antecedente':{'Pesquisa_cadastral__c':'Não recomendado'},
            'MatriculaTTI_Estagiario':{'Status_CRECI__c':'Estágio'},
            'Obrigatorio_Casado':{'EstadoCivil__c':'Casado'},
            'Responsavel_obrigatorio_estagiario':{'Atividade__c':'Estagiário'},
            'Validade_CRECI':{'Atividade__c':'Corretor','CRECI__c':12345},
            'Verifica_CPF':{'CPF__c':'52998224726'},
            'Reativacao_corretor':{'Status_Corretor__c':'Reativado'},
            'Verifica_UF':{'EnderecoResidencialEstado__c':'XX'},
            'Valida_CPF_CNPJ':{'CPF__c':''},
        }
        self.assertEqual(set(cases),{r['name'] for r in esquema_local()['validation_rules'] if r['creation']})
        for rule,change in cases.items():
            with self.subTest(rule=rule):self.assertTrue(any('('+rule+')' in e for e in validar_regras_criacao(dict(VALID,**change))))

    def test_validos_captador_corretor_estagiario(self):
        self.assertEqual(validar_regras_criacao(VALID),[])
        corretor=dict(VALID,Atividade__c='Corretor',CRECI__c=12345,Validade_CRECI__c='2027-01-01')
        self.assertEqual(validar_regras_criacao(corretor),[])
        trainee=dict(VALID,Atividade__c='Estagiário',Validade_CRECI__c='2027-01-01',Data_Matricula_TTI__c='2026-01-01',Nome_do_Responsavel__c='RESPONSÁVEL INFORMADO')
        self.assertEqual(validar_regras_criacao(trainee),[])

    def test_casado_inativo_reativado_podem_ter_dados_condicionais(self):
        p=dict(VALID,EstadoCivil__c='Casado',Nome_do_Conjuge__c='CÔNJUGE')
        self.assertEqual(validar_regras_criacao(p),[])
        self.assertEqual(validar_regras_criacao(dict(VALID,Status_Corretor__c='Inativo',Data_de_Saida__c='2026-11-10')),[])
        self.assertEqual(validar_regras_criacao(dict(VALID,Status_Corretor__c='Reativado',Data_Reativacao__c='2026-11-10')),[])

    def test_creci_obrigatorio_nao_fica_oculto_quando_nao(self):
        d={'possui_creci':'Não','atividade':'Corretor'}
        self.assertTrue(app._formulario_exibe_creci_detalhado(d))
        errors=app._erros_preenchimento_creci_se_sim(d)
        self.assertTrue(any('CRECI:' in e for e in errors))
        self.assertTrue(any('Validade CRECI' in e for e in errors))
        p={};app._aplicar_defaults_creci_campos_vazios_salesforce(p,d)
        self.assertEqual(p,{})

    def test_creci_informado_e_preservado_mesmo_flag_nao(self):
        p={'CRECI__c':12345,'Validade_CRECI__c':'2027-01-01'}
        app._ajustar_payload_creci_conforme_possui(p,{'possui_creci':'Não','atividade':'Corretor'})
        self.assertEqual(p['CRECI__c'],12345)

    def test_status_creci_filtrado_pela_atividade(self):
        self.assertIn('Definitivo',opcoes_permitidas('Status_CRECI__c',{'Atividade__c':'Corretor'}))
        self.assertNotIn('Pendente Prova',opcoes_permitidas('Status_CRECI__c',{'Atividade__c':'Corretor'}))
        self.assertEqual(opcoes_permitidas('Status_CRECI__c',{'Atividade__c':'Outra Atividade Inexistente'}),[])

    def test_origem_rh_nao_e_descartada(self):
        self.assertEqual(app._filtrar_payload_contact_insert({'Origem__c':'RH'}),{'Origem__c':'RH'})
        self.assertIn('RH',opcoes_permitidas('Origem__c',{}))

    def test_mensagem_de_validacao_preserva_detalhe(self):
        e=ValueError('Agência Bancária: máximo de 4 caracteres.')
        self.assertEqual(app._mensagem_erro_sf_amigavel(e),str(e))

    def test_sem_permissao_contact_nao_tenta_criar(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        sf=SimpleNamespace(Contact=Mock())
        sf.Contact.describe.return_value={'createable':False,'fields':[],'recordTypeInfos':[]}
        with self.assertRaisesRegex(ValueError,'permissão para criar'):
            integration.normalizar_payload(sf,{'LastName':'Exemplo'},[])
        sf.Contact.create.assert_not_called()

    def test_sem_picklists_do_tipo_nao_usa_opcoes_globais(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        sf=SimpleNamespace(Contact=Mock(),restful=Mock(side_effect=RuntimeError('sem acesso')))
        sf.Contact.describe.return_value={'fields':[],'recordTypeInfos':[{'name':'Corretor','recordTypeId':'012000000000001','available':True}]}
        with self.assertRaisesRegex(ValueError,'UI API'):
            integration.normalizar_payload(sf,{'LastName':'Exemplo'},[])
        sf.Contact.create.assert_not_called()

    def test_email_de_outro_contato_bloqueia_sem_mudar_ninguem(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        sf=SimpleNamespace(Contact=Mock(),query=Mock(return_value={'records':[{'Id':'003OUTRO'}]}))
        p=dict(VALID,Email='exemplo@example.org')
        with patch.object(app,'_buscar_contact_id_existente',return_value=(None,None)),patch.object(app,'_preparar_payload_insert_salesforce',return_value=p):
            cid,error,_=app.criar_contato_salesforce_preparado(sf,p,{},[])
        self.assertIsNone(cid)
        self.assertIn('e-mail já está cadastrado',str(error))
        sf.Contact.create.assert_not_called()
        sf.Contact.update.assert_not_called()

if __name__=='__main__':unittest.main()
