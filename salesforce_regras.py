"""Limites auditados de Contact e regras de criação; não executa fórmulas arbitrárias."""
from __future__ import annotations
import json
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path

@lru_cache(maxsize=1)
def esquema_local():
    return json.loads(Path(__file__).with_name('salesforce_contact_schema.json').read_text(encoding='utf-8'))

def tamanho_texto(value):
    return len(str(value).encode('utf-16-le')) // 2

def canon(value):
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD',str(value or '')).encode('ascii','ignore').decode().lower())

def numero(value):
    if isinstance(value,bool): raise ValueError('Informe um número, não um valor lógico.')
    try: n=Decimal(str(value).strip().replace(',','.'))
    except InvalidOperation: raise ValueError('Informe um número válido.') from None
    if not n.is_finite(): raise ValueError('Informe um número finito.')
    return n

def validar_valor(meta, value, prefixes=None):
    if value is None or value == '': return []
    label=meta.get('label') or meta['name']; typ=meta.get('type'); errors=[]
    if typ in {'string','textarea','email','phone','url','encryptedstring','picklist','multipicklist','reference','id'}:
        if not isinstance(value,str): return [f'{label}: informe um texto.']
        maximum=meta.get('length')
        if maximum and tamanho_texto(value)>maximum: errors.append(f'{label}: máximo de {maximum} caracteres; informado {tamanho_texto(value)}. O valor não será cortado.')
        if meta.get('byteLength') and len(value.encode('utf-8'))>meta['byteLength']:
            errors.append(f'{label}: o texto excede o limite de armazenamento do campo.')
    if typ in {'int','long','double','currency','percent'}:
        try:
            n=numero(value); scale=meta.get('scale') or 0; precision=meta.get('precision') or (10 if typ=='int' else 18)
            normalized=n.normalize(); decimals=max(0,-normalized.as_tuple().exponent) if n else 0
            integers=max(0,n.adjusted()+1) if n else 0
            if decimals>scale: errors.append(f'{label}: máximo de {scale} casas decimais.')
            if integers>precision-scale: errors.append(f'{label}: máximo de {precision-scale} dígitos antes da vírgula.')
        except ValueError as e: errors.append(f'{label}: {e}')
    if typ=='boolean' and not isinstance(value,bool): errors.append(f'{label}: informe verdadeiro ou falso.')
    if typ=='date':
        try:
            if isinstance(value,datetime): raise ValueError()
            text=value.isoformat() if isinstance(value,date) else value
            if not isinstance(text,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',text):raise ValueError()
            date.fromisoformat(text)
        except (ValueError,TypeError): errors.append(f'{label}: informe uma data válida no formato AAAA-MM-DD.')
    if typ=='datetime':
        try:
            d=value if isinstance(value,datetime) else datetime.fromisoformat(str(value).replace('Z','+00:00'))
            if d.tzinfo is None: raise ValueError()
        except (ValueError,TypeError): errors.append(f'{label}: informe data, hora e fuso horário válidos.')
    if typ=='email' and (not isinstance(value,str) or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value)):
        errors.append(f'{label}: endereço de e-mail inválido.')
    if typ in {'reference','id'} and isinstance(value,str):
        if not re.fullmatch(r'[A-Za-z0-9]{15}(?:[A-Za-z0-9]{3})?',value): errors.append(f'{label}: ID Salesforce deve conter 15 ou 18 caracteres.')
        elif prefixes:
            allowed={prefixes[x] for x in meta.get('referenceTo',[]) if prefixes.get(x)}
            if allowed and value[:3] not in allowed: errors.append(f'{label}: ID não pertence ao objeto relacionado permitido.')
    return list(dict.fromkeys(errors))

def opcoes_permitidas(api,payload,fields=None,picklists=None):
    schema=esquema_local();fields=fields if fields is not None else schema['fields'];picklists=picklists if picklists is not None else schema['picklists']
    meta=fields.get(api,{})
    ui=picklists.get(api)
    if ui is None: return [p['value'] for p in meta.get('picklistValues',[]) if p.get('active')]
    values=ui.get('values',[]); controller=meta.get('controllerName')
    if controller and ui.get('controllerValues'):
        selected=payload.get(controller); selected=normalizar_opcao(controller,selected,payload,fields,picklists)
        idx=ui['controllerValues'].get(str(selected))
        values=[v for v in values if idx in v.get('validFor',[])] if idx is not None else []
    return [v['value'] for v in values]

def normalizar_opcao(api,value,payload,fields=None,picklists=None):
    aliases={('Atividade__c','Autônomo Parceiro'):'Corretor Parceiro',('Unidade_Negocio__c','Outra imobiliária (parceira)'):'Direcional',('Tipo_do_PIX__c','Telefone'):'Celular'}
    value=aliases.get((api,str(value)),value)
    allowed=opcoes_permitidas(api,payload,fields,picklists)
    if value in allowed:return value
    matches=[x for x in allowed if canon(x)==canon(value)]
    if api=='Banco__c' and not matches:
        code=re.match(r'^(\d{3})\b',str(value).strip())
        if code:matches=[x for x in allowed if re.match(r'^'+code.group(1)+r'\b',x)]
    return matches[0] if len(matches)==1 else value

def validar_regras_criacao(payload):
    """Espelha as 16 regras ativas aplicáveis à criação de Corretor, auditadas em 10/11/2026.

    As quatro regras com ISCHANGED são de atualização e não se aplicam: o app não atualiza contatos.
    """
    enabled={r['name']:r for r in esquema_local()['validation_rules'] if r['creation']}
    errors=[]
    blank=lambda k:payload.get(k) is None or str(payload.get(k)).strip()==''
    def add(rule,condition):
        if condition and rule in enabled:errors.append(f"{enabled[rule]['message']} ({rule})")
    cpf=re.sub(r'\D','',str(payload.get('CPF__c') or '')); cnpj=re.sub(r'\D','',str(payload.get('CNPJ__c') or ''))
    add('BlackList_CPF',bool(cpf) and len(set(cpf))==1)
    add('BlackList_CNPJ',bool(cnpj) and len(set(cnpj))==1)
    add('CNPJ_Obrigatorio',payload.get('Corretor_Associado__c')=='PJ / Empresa Própria' and blank('CNPJ__c'))
    add('CRECICoretor',payload.get('Atividade__c')=='Corretor' and blank('CRECI__c'))
    add('Campo_origem_indicacao',payload.get('Origem__c')=='Indicação' and blank('Indicado_por__c'))
    add('Celular_obrigatorio',blank('MobilePhone'))
    add('Data_de_saida_obrigatorio',payload.get('Status_Corretor__c')=='Inativo' and blank('Data_de_Saida__c'))
    add('Informar_Motivo_Antecedente',payload.get('Pesquisa_cadastral__c')=='Não recomendado' and blank('Nao_recomendado_Motivo__c'))
    trainee=payload.get('Atividade__c')=='Estagiário' or payload.get('Status_CRECI__c')=='Estágio'
    add('MatriculaTTI_Estagiario',trainee and blank('Data_Matricula_TTI__c'))
    add('Obrigatorio_Casado',payload.get('EstadoCivil__c')=='Casado' and blank('Nome_do_Conjuge__c'))
    add('Responsavel_obrigatorio_estagiario',trainee and blank('Nome_do_Responsavel__c'))
    add('Validade_CRECI',payload.get('Atividade__c') in {'Corretor','Estagiário'} and blank('Validade_CRECI__c'))
    from salesforce_integracao import cpf_valido
    add('Verifica_CPF',not cpf_valido(cpf))
    add('Reativacao_corretor',payload.get('Status_Corretor__c')=='Reativado' and blank('Data_Reativacao__c'))
    uf=str(payload.get('EnderecoResidencialEstado__c') or '')
    add('Verifica_UF',bool(uf) and uf not in {'AC','AL','AM','AP','BA','CE','DF','ES','GO','MA','MG','MS','MT','PA','PB','PE','PI','PR','RJ','RN','RO','RR','RS','SC','SE','SP','TO'})
    add('Valida_CPF_CNPJ',blank('CPF__c') and blank('CNPJ__c'))
    return errors

def payload_formulario(dados,campos):
    payload={}
    for c in campos:
        api=c.get('sf');value=dados.get(c['key'])
        if not api or value is None or value=='':continue
        if isinstance(value,list):value=';'.join(value)
        if isinstance(value,(date,datetime)):value=value.isoformat()[:10]
        if c['tipo']=='date' and isinstance(value,str):
            for fmt in ('%Y-%m-%d','%d/%m/%Y','%d-%m-%Y'):
                try:value=datetime.strptime(value,fmt).date().isoformat();break
                except ValueError:pass
        payload[api]=value
    if dados.get('nome_completo'):
        parts=str(dados['nome_completo']).strip().upper().split(None,1)
        if parts:payload.update(FirstName=parts[0],LastName=parts[-1])
    for k in list(payload):
        if esquema_local()['fields'].get(k,{}).get('type') in {'picklist','multipicklist'}:
            vals=str(payload[k]).split(';');payload[k]=';'.join(str(normalizar_opcao(k,v,payload)) for v in vals)
    if payload.get('CPF__c'):payload['CPF__c']=re.sub(r'\D','',str(payload['CPF__c']))
    if dados.get('unidade_negocio')=='Outra imobiliária (parceira)':payload['Atividade__c']='Corretor Parceiro'
    return payload

def validar_formulario(dados,campos,sec=None):
    fields=esquema_local()['fields'];payload=payload_formulario(dados,campos);errors=[]
    targets={c.get('sf') for c in campos if sec is None or c['sec']==sec}
    if sec is None or any(c['key']=='nome_completo' and c['sec']==sec for c in campos):targets|={'FirstName','LastName'}
    for api,value in payload.items():
        meta=fields.get(api)
        if not meta or not meta.get('createable') or api not in targets:continue
        errors.extend(validar_valor(meta,value,esquema_local()['reference_prefixes']))
        if meta.get('type') in {'picklist','multipicklist'} and meta.get('restrictedPicklist'):
            allowed=opcoes_permitidas(api,payload)
            if any(v not in allowed for v in str(value).split(';')):errors.append(f"{meta['label']}: opção não permitida para a atividade e o tipo de cadastro selecionados.")
    return list(dict.fromkeys(errors))

def limite_campo(c):
    if c['key']=='nome_completo':return 121
    meta=esquema_local()['fields'].get(c.get('sf'),{})
    return meta.get('length') or None if meta.get('type') in {'string','textarea','email','phone','url','encryptedstring'} else None
