"""Regressões das falhas reais, sem dados pessoais nem credenciais."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
import requests
import ficha_cadastral_vendas_rj_streamlit as app
import salesforce_integracao as i

CPF = '52998224725'  # Vetor público de validação, usado somente em memória.


def erro(code, message='', fields=None, **kw):
    e = RuntimeError(code)
    e.content = [dict(errorCode=code, message=message, fields=fields or [], **kw)]
    return e


class RobustezTests(unittest.TestCase):
    def schema(self):
        specs = [('LastName','string',80), ('FirstName','string',40), ('CPF__c','string',14),
                 ('OwnerId','reference',18), ('AccountId','reference',18), ('RecordTypeId','reference',18),
                 ('Atividade__c','picklist',255), ('Status_CRECI__c','picklist',255),
                 ('Conta_Banc_ria__c','string',20), ('Ag_ncia_Banc_ria__c','string',10)]
        fields=[dict(name=k,label=k,type=t,length=l,createable=True,nillable=k!='LastName',defaultedOnCreate=False,restrictedPicklist=t=='picklist') for k,t,l in specs]
        next(f for f in fields if f['name']=='Status_CRECI__c')['controllerName']='Atividade__c'
        sf=SimpleNamespace(Contact=Mock(),restful=Mock())
        sf.Contact.describe.return_value={'fields':fields,'recordTypeInfos':[{'name':'Corretor','recordTypeId':'012CORRETOR','available':True}]}
        sf.restful.return_value={'picklistFieldValues':{
            'Atividade__c':{'values':[{'value':'Corretor Parceiro'},{'value':'Corretor'}]},
            'Status_CRECI__c':{'controllerValues':{'Corretor Parceiro':0,'Corretor':1},'values':[{'value':'Definitivo','validFor':[0,1]}]}}}
        return sf

    def test_cpf_verificadores_e_repeticoes(self):
        self.assertTrue(i.cpf_valido(CPF))
        self.assertFalse(i.cpf_valido(CPF[:-1]+'6'))
        self.assertFalse(i.cpf_valido('11111111111'))

    def test_cpf_api_sem_mascara_e_controller_antes_dependente(self):
        p=i.normalizar_payload(self.schema(),{'LastName':'Exemplo','CPF__c':'529.982.247-25','Status_CRECI__c':'Definitivo','Atividade__c':'Autônomo Parceiro'},[])
        self.assertEqual(p['CPF__c'],CPF)
        self.assertEqual(p['Atividade__c'],'Corretor Parceiro')
        self.assertEqual(p['Status_CRECI__c'],'Definitivo')

    def test_cpf_invalido_bloqueado_antes_de_create(self):
        sf=self.schema()
        with self.assertRaisesRegex(ValueError,'CPF inválido'):
            i.normalizar_payload(sf,{'LastName':'Exemplo','CPF__c':'11111111111'},[])
        sf.Contact.create.assert_not_called()

    def test_schema_limites_reais_e_banco_sem_corte(self):
        avisos=[]
        p=i.normalizar_payload(self.schema(),{'LastName':'A'*90,'Ag_ncia_Banc_ria__c':'1234567890'},avisos)
        self.assertEqual(len(p['LastName']),80)
        self.assertEqual(p['Ag_ncia_Banc_ria__c'],'1234567890')
        self.assertTrue(avisos)
        for v in ['alguem1234@example.org','123456789012345678901']:
            with self.assertRaises(ValueError): i.normalizar_payload(self.schema(),{'LastName':'Exemplo','Conta_Banc_ria__c':v},[])

    def test_campo_dinamico_nao_vira_coluna_salesforce(self):
        with self.assertRaisesRegex(ValueError,'Campo Salesforce inexistente'):
            i.normalizar_payload(self.schema(),{'LastName':'Exemplo','NOME DE PESSOA':'x'},[])

    def test_picklist_apenas_opcoes_tipo_corretor(self):
        with self.assertRaisesRegex(ValueError,'opção não aceita'):
            i.normalizar_payload(self.schema(),{'LastName':'Exemplo','Atividade__c':'Diretor de Outra Regional'},[])

    def test_naturalidade_nao_e_alterada_para_contornar_erro(self):
        sf=SimpleNamespace(Contact=Mock())
        sf.Contact.create.side_effect=erro('FIELD_CUSTOM_VALIDATION_EXCEPTION','Naturalidade inválida')
        p={'LastName':'Exemplo','Naturalidade__c':'Cidade informada'}
        cid,e,used=app.criar_contato_payload_com_fallback_naturalidade(sf,p,[])
        self.assertIsNone(cid)
        self.assertEqual(used['Naturalidade__c'],'Cidade informada')
        self.assertEqual(sf.Contact.create.call_count,1)

    def test_cpf_ambiguo_e_consulta_sem_permissao_nao_criam(self):
        sf=SimpleNamespace(query=Mock(return_value={'records':[{'Id':'003A'},{'Id':'003B'}]}),Contact=Mock())
        cid,e,_=app.criar_contato_salesforce_preparado(sf,{'CPF__c':CPF},{},[])
        self.assertIsNone(cid)
        self.assertIn('Mais de um',str(e))
        sf.query.side_effect=erro('INSUFFICIENT_ACCESS_OR_READONLY')
        cid,e,_=app.criar_contato_salesforce_preparado(sf,{'CPF__c':CPF},{},[])
        self.assertIsNone(cid)
        sf.Contact.create.assert_not_called()

    def test_novo_proprietario_e_integracao(self):
        sf=SimpleNamespace(query=Mock(return_value={'records':[{'Id':'005ATIVO','IsActive':True}]}))
        with patch.object(app,'_aplicar_enriquecimentos_payload_sf'),patch.object(app,'normalizar_payload',side_effect=lambda sf,p,a:p),patch.dict(app.os.environ,{'SALESFORCE_USER':'integracao'}):
            p=app._preparar_payload_insert_salesforce({'OwnerId':'005ANTIGO','LastName':'Exemplo'},{},sf,[])
        self.assertEqual(p['OwnerId'],'005ATIVO')

    def test_owner_inativo_bloqueia_apenas_nova_criacao(self):
        sf=SimpleNamespace(query=Mock(return_value={'records':[{'Id':'005INATIVO','IsActive':False}]}))
        with self.assertRaisesRegex(ValueError,'usuário ativo'):
            i.usuario_integracao(sf,'integracao')

    def test_resposta_perdida_consulta_cpf_sem_repetir_post(self):
        sf=SimpleNamespace(Contact=Mock())
        p={'CPF__c':CPF,'LastName':'Exemplo','AccountId':'001A','OwnerId':'005A'}
        sf.Contact.get.return_value=dict(p)
        with patch.object(app,'_buscar_contact_id_existente',side_effect=[(None,None),('003A','CPF')]),patch.object(app,'_preparar_payload_insert_salesforce',return_value=p),patch.object(app,'criar_contato_payload_com_fallback_naturalidade',return_value=(None,requests.Timeout(),p)) as create:
            cid,e,_=app.criar_contato_salesforce_preparado(sf,p,{},[])
        self.assertEqual(cid,'003A')
        self.assertIsNone(e)
        self.assertEqual(create.call_count,1)
        sf.Contact.update.assert_not_called()

    def test_apelido_repetido_gera_novo_sem_reutilizar_outra_pessoa(self):
        sf=SimpleNamespace(Contact=Mock())
        p={'CPF__c':CPF,'LastName':'Exemplo','AccountId':'001A','OwnerId':'005A','Apelido__c':'EXEMPLO_RJ01'}
        sf.Contact.get.return_value=dict(p)
        with patch.object(app,'_buscar_contact_id_existente',return_value=(None,None)),patch.object(app,'_preparar_payload_insert_salesforce',return_value=p),patch.object(app,'_proximo_apelido_disponivel',return_value='EXEMPLO_RJ02'),patch.object(app,'criar_contato_payload_com_fallback_naturalidade',side_effect=[(None,erro('DUPLICATE_VALUE','Apelido__c'),p),('003A',None,p)]) as create:
            cid,e,_=app.criar_contato_salesforce_preparado(sf,p,{},[])
        self.assertEqual(cid,'003A')
        self.assertIsNone(e)
        self.assertEqual(create.call_count,2)
        sf.Contact.update.assert_not_called()

    def test_duplicidade_email_nao_reutiliza_outro_cpf(self):
        sf=SimpleNamespace(Contact=Mock())
        p={'CPF__c':CPF,'LastName':'Exemplo'}
        e=erro('DUPLICATES_DETECTED','Email já registrado',duplicateResult={'duplicateRule':'Email_Contato','matchResults':[{'matchRecords':[{'record':{'Id':'003OUTRO'}}]}]})
        with patch.object(app,'_buscar_contact_id_existente',return_value=(None,None)),patch.object(app,'_preparar_payload_insert_salesforce',return_value=p),patch.object(app,'criar_contato_payload_com_fallback_naturalidade',return_value=(None,e,p)):
            cid,returned,_=app.criar_contato_salesforce_preparado(sf,p,{},[])
        self.assertIsNone(cid)
        self.assertIs(returned,e)
        sf.Contact.get.assert_not_called()

    def test_header_preserva_posicao_historica_e_separa_email_api(self):
        headers,row=i.alinhar_cabecalhos_existentes(['CPF *','E-mail *','Email'],['Email','Regional de Cadastro *','CPF *','E-mail *'],['api@example.org','MG',CPF,'humano@example.org'])
        self.assertEqual(headers,['CPF *','E-mail *','Email','Regional de Cadastro *'])
        self.assertEqual(row,[CPF,'humano@example.org','api@example.org','MG'])
        headers=app.cabecalho_planilha()
        self.assertEqual(i.alinhar_cabecalhos_existentes(headers,headers,['']*len(headers))[0],headers)

    def test_header_realmente_duplicado_e_recusado(self):
        with self.assertRaisesRegex(ValueError,'duplicado'):
            i.alinhar_cabecalhos_existentes(['Email','Email'],['Email'],['x'])

    def test_falha_parcial_sheets_reusa_linha_na_sessao(self):
        state={}
        with patch.object(app.st,'session_state',state),patch.object(app,'anexar_linha',return_value=42) as append,patch.object(app,'atualizar_status_envio_salesforce',side_effect=[RuntimeError('temporário'),None]) as update,patch.object(app,'_registrar_debug_envio'),patch.object(app._LOG_FICHA,'exception'):
            kwargs=dict(envio='OK',coluna_link='https://sf/003A',payload_final={'CPF__c':CPF})
            self.assertIsNone(app._gravar_cadastro_planilha([],[],'sid','Corretores Nova Base',{}, {},**kwargs))
            self.assertEqual(app._gravar_cadastro_planilha([],[],'sid','Corretores Nova Base',{}, {},**kwargs),42)
            self.assertEqual(append.call_count,1)
            self.assertEqual(update.call_count,2)

    def test_timeout_login_e_rest_limitado_sem_retry_post(self):
        session=i.SessaoSalesforceLimitada()
        with patch.object(requests.Session,'request',return_value='ok') as req:
            self.assertEqual(session.request('POST','https://example.org'), 'ok')
        self.assertEqual(req.call_args.kwargs['timeout'],(10,30))
        self.assertEqual(req.call_count,1)

    def test_senha_expirada_e_permissoes_tem_diagnostico(self):
        e=RuntimeError('Your password has expired')
        self.assertIn('expirada',i.resumo_erro(e))
        self.assertIn('permissão',i.resumo_erro(erro('INSUFFICIENT_ACCESS_OR_READONLY')))

class LegadoTests(unittest.TestCase):
    def linha(self):
        headers=app.cabecalho_planilha()
        cells=['']*len(headers)
        data={'Nome completo *':'PESSOA EXEMPLO','Data de Nascimento *':'01/01/1990','Estado Civil *':'Solteiro','CPF *':CPF,'Nacionalidade *':'Brasileiro','Tratamento':'Sr.','Apelido':'PESSOA_RJ01','Regional de Cadastro *':'RJ','CPF__c':CPF,'FirstName':'PESSOA','LastName':'EXEMPLO','Email':'exemplo@example.org','Regional__c':'RJ'}
        # Os rótulos refletem o esquema oficial; ancore posições pelo cadastro.
        for c in app.CAMPOS:
            if c['key'] in {'nome_completo','birthdate','estado_civil','cpf','nacionalidade'}:
                value={'nome_completo':'PESSOA EXEMPLO','birthdate':'01/01/1990','estado_civil':'Solteiro','cpf':CPF,'nacionalidade':'Brasileiro'}[c['key']]
                if c['label'] in headers: cells[headers.index(c['label'])]=value
        for key,value in data.items():
            if key in headers:cells[headers.index(key)]=value
        return headers,cells

    def test_api_deslocada_independente_do_bloco_pessoal(self):
        h,c=self.linha()
        index=h.index('Regional de Cadastro *')
        del c[index]
        aligned,info=i.alinhar_linha_legada(h,c)
        self.assertEqual(aligned[h.index('CPF *')],CPF)
        self.assertEqual(aligned[h.index('FirstName')],'PESSOA')
        self.assertEqual(aligned[h.index('LastName')],'EXEMPLO')
        self.assertEqual(info['api_shift'],-1)

    def test_identidade_api_divergente_recusa_alinhamento(self):
        h,c=self.linha()
        c[h.index('FirstName')]='OUTRA'
        with self.assertRaisesRegex(ValueError,'ambígua'):
            i.alinhar_linha_legada(h,c)

    def test_linha_atual_preserva_cpf_nome_api(self):
        h,c=self.linha()
        aligned,info=i.alinhar_linha_legada(h,c)
        self.assertEqual(aligned[h.index('CPF *')],CPF)
        self.assertEqual(aligned[h.index('LastName')],'EXEMPLO')
        self.assertEqual(info['api_shift'],0)

if __name__=='__main__': unittest.main()
