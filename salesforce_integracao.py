"""Validação e tratamento de integração, sem credenciais ou dados de produção."""
from __future__ import annotations

import re
import time
import unicodedata
from datetime import date, datetime
from typing import Any

import requests
from salesforce_regras import validar_valor, esquema_local


class SessaoSalesforceLimitada(requests.Session):
    """Limita login e chamadas REST; não repete POST de criação automaticamente."""
    def request(self, method, url, **kwargs):
        kwargs.setdefault('timeout', (10, 30))
        return super().request(method, url, **kwargs)


def digitos(valor: Any) -> str:
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        if float(valor).is_integer():
            return str(int(valor))
    return re.sub(r'\D', '', str(valor or ''))


def canonico(valor: Any) -> str:
    txt = unicodedata.normalize('NFKD', str(valor or '')).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]', '', txt.lower())


def cpf_valido(valor: Any) -> bool:
    cpf = digitos(valor)
    if len(cpf) != 11 or len(set(cpf)) == 1:
        return False
    for n in (9, 10):
        resto = sum(int(cpf[i]) * (n + 1 - i) for i in range(n)) % 11
        esperado = 0 if resto < 2 else 11 - resto
        if int(cpf[n]) != esperado:
            return False
    return True


def cpf_formatado(valor: Any) -> str:
    if not cpf_valido(valor):
        raise ValueError('CPF inválido: confira os 11 dígitos e os dígitos verificadores.')
    cpf = digitos(valor)
    return f'{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}'


def validar_dados_integracao(dados: dict) -> list[str]:
    erros = []
    cpf = dados.get('cpf')
    if cpf and not cpf_valido(cpf):
        erros.append('CPF inválido: confira os dígitos verificadores.')
    for chave, label, limite in [('conta_bancaria', 'Conta Bancária', esquema_local()['fields']['Conta_Banc_ria__c']['length']), ('agencia_bancaria', 'Agência Bancária', esquema_local()['fields']['Ag_ncia_Banc_ria__c']['length'])]:
        valor = str(dados.get(chave) or '').strip().replace(' ', '')
        if not valor:
            continue
        if not re.fullmatch(r'[0-9xX.\-]+', valor) or not digitos(valor):
            erros.append(f'{label}: informe o número da conta/agência, não e-mail ou chave PIX.')
        elif len(valor) > limite:
            erros.append(f'{label}: máximo de {limite} caracteres, sem cortar o número informado.')
    return erros


def erros_salesforce(erro: Any) -> list[dict]:
    content = getattr(erro, 'content', None)
    if isinstance(content, list):
        return [x for x in content if isinstance(x, dict)]
    return []


def apelido_duplicado(erro: Any) -> bool:
    for item in erros_salesforce(erro):
        if item.get('errorCode') == 'DUPLICATE_VALUE' and (
            'Apelido__c' in item.get('fields', []) or 'Apelido__c' in str(item.get('message', ''))
        ):
            return True
    texto = str(erro)
    return 'DUPLICATE_VALUE' in texto and 'Apelido__c' in texto


def ids_duplicados_cpf(erro: Any) -> set[str]:
    ids = set()
    for item in erros_salesforce(erro):
        dup = item.get('duplicateResult') or {}
        if item.get('errorCode') != 'DUPLICATES_DETECTED' or dup.get('duplicateRule') != 'CPF_Contato':
            continue
        for match in dup.get('matchResults', []):
            for rec in match.get('matchRecords', []):
                value = (rec.get('record') or {}).get('Id')
                if value and re.fullmatch(r'003[A-Za-z0-9]{12}(?:[A-Za-z0-9]{3})?', value):
                    ids.add(value)
    return ids


def mesma_identidade(contato: dict, payload: dict) -> bool:
    if not isinstance(contato, dict):
        return False
    cpf = digitos(payload.get('CPF__c'))
    if cpf and digitos(contato.get('CPF__c')) != cpf:
        return False
    nome = canonico(str(payload.get('FirstName') or '') + ' ' + str(payload.get('LastName') or ''))
    email = str(payload.get('Email') or '').strip().lower()
    nome_sf = canonico(contato.get('Name') or (str(contato.get('FirstName') or '') + ' ' + str(contato.get('LastName') or '')))
    email_sf = str(contato.get('Email') or '').strip().lower()
    if not nome and not email:
        return bool(cpf)
    return bool((nome and nome == nome_sf) or (email and email == email_sf))


def resumo_erro(erro: Any) -> str:
    codigo = str(getattr(erro, 'code', '') or '')
    texto = str(erro or '')
    if 'EXPIRED_PASSWORD' in codigo or 'password has expired' in texto.lower():
        return 'Senha Salesforce expirada. Atualize a senha e o token nos Secrets antes de reenviar.'
    if codigo in {'INVALID_LOGIN', 'LOGIN_MUST_USE_SECURITY_TOKEN', 'AUTHENTICATION_FAILURE'}:
        return f'Autenticação Salesforce recusada ({codigo}). Confira usuário, senha, token e política de login por API.'
    if isinstance(erro, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
        return 'Conexão Salesforce interrompida. O contato será procurado por CPF antes de qualquer nova tentativa de criação.'
    itens = erros_salesforce(erro)
    if itens:
        codes = {x.get('errorCode') for x in itens}
        if 'INSUFFICIENT_ACCESS_OR_READONLY' in codes:
            return 'O usuário da integração não tem permissão para esta operação no Salesforce. O cadastro não será repetido como novo.'
        if 'CANNOT_REPARENT_RECORD' in codes:
            return 'O contato já existe e não pode ser movido por causa do proprietário inativo. Nenhum novo contato será criado para contornar a restrição.'
        return '; '.join(f"{x.get('errorCode', 'ERRO_SF')}: {x.get('message', 'Falha na integração')}" for x in itens)[:1500]
    if isinstance(erro, ValueError):
        return str(erro)
    return ''


def usuario_integracao(sf: Any, username: str) -> str:
    cache = vars(sf).get('_ficha_usuario_integracao')
    if cache and cache[0] == username:
        return cache[1]
    if not username:
        raise ValueError('Usuário Salesforce da integração não configurado.')
    escaped = username.replace('\\', '\\\\').replace("'", "\\'")
    records = (sf.query("SELECT Id, IsActive FROM User WHERE Username = '" + escaped + "' LIMIT 2") or {}).get('records', [])
    if len(records) != 1 or not records[0].get('IsActive'):
        raise ValueError('O proprietário dos novos contatos deve ser o usuário ativo da integração.')
    uid = records[0]['Id']
    vars(sf)['_ficha_usuario_integracao'] = (username, uid)
    return uid


def _texto_celula(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, (int, float)) and not isinstance(value, bool) and float(value).is_integer():
        return str(int(value))
    return str(value).strip()


def _data_celula(value: Any) -> str | None:
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10]
    text = _texto_celula(value)
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d/%m/%y'):
        try:
            return datetime.strptime(text[:10], fmt).date().isoformat()
        except ValueError:
            continue
    return None


def alinhar_linha_legada(headers: list, cells: list) -> tuple[list, dict]:
    """Alinha blocos independentemente, exigindo concordância de nome e CPF.

    Nunca altera a planilha original e nunca preenche dados pessoais por palpite.
    """
    cells = list(cells) + [''] * max(0, len(headers) - len(cells))
    indexes = {str(h): i for i, h in enumerate(headers) if h}
    at = lambda i: cells[i] if 0 <= i < len(cells) else None
    required = {'Nome completo *', 'CPF *', 'Email', 'CPF__c', 'FirstName', 'LastName'}
    if not required.issubset(indexes):
        # Planilhas com rótulos próprios continuam no parser de cabeçalhos do formulário.
        return cells, {'legacy': False}
    candidates = []
    civil_prefix = ('solteir', 'casad', 'divorciad', 'viuv', 'separad', 'uniao')
    for i in range(7):
        name = _texto_celula(at(i))
        if len(name) > 3 and '@' not in name and 'http' not in name.lower() and _data_celula(at(i+1)) and canonico(at(i+2)).startswith(civil_prefix):
            candidates.append((i, name))
    if len(candidates) != 1:
        raise ValueError('Linha histórica ambígua: nome, nascimento e estado civil não coincidem com os cabeçalhos. Corrija a linha antes de importar.')
    ni, name = candidates[0]
    cpf_candidates = []
    for ci in range(ni+3, ni+6):
        value = at(ci)
        candidate = digitos(value)
        if isinstance(value, (int, float)) and len(candidate) < 11:
            candidate = candidate.zfill(11)
        if len(candidate) == 11 and re.search(r'[A-Za-zÀ-ÿ]', _texto_celula(at(ci+1))) and '@' not in _texto_celula(at(ci+1)):
            cpf_candidates.append((ci, candidate))
    if len(cpf_candidates) != 1:
        raise ValueError('Linha histórica ambígua: CPF e nacionalidade não puderam ser alinhados com segurança.')
    ci, cpf = cpf_candidates[0]
    scored = []
    for shift in range(-7, 8):
        api = lambda k: at(indexes[k] + shift)
        api_cpf = digitos(api('CPF__c'))
        if isinstance(api('CPF__c'), (int, float)) and len(api_cpf) < 11:
            api_cpf = api_cpf.zfill(11)
        api_name = canonico(_texto_celula(api('FirstName')) + ' ' + _texto_celula(api('LastName')))
        name_match = api_name == canonico(name) or (len(name.split()) == 1 and canonico(api('FirstName')) == canonico(name) and canonico(api('LastName')) == canonico(name))
        score = (8 if api_cpf == cpf else 0) + (8 if name_match else 0) + (3 if re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', _texto_celula(api('Email'))) else 0)
        scored.append((score, shift))
    scored.sort(reverse=True)
    score, api_shift = scored[0]
    if score < 16 or scored[1][0] == score:
        current = ni == indexes['Nome completo *'] and ci == indexes['CPF *']
        no_api = not any(at(indexes[k]) for k in ('CPF__c', 'FirstName', 'LastName'))
        if current and no_api:
            return cells, {'legacy': False}
        raise ValueError('Linha histórica ambígua: o bloco de API deve coincidir com nome e CPF, sem selecionar a primeira hipótese.')
    aligned = list(cells)
    personal_delta = ni - indexes['Nome completo *']
    spouse_delta = ci - (indexes['CPF *'] + personal_delta)
    start, end = indexes['Nome completo *'], indexes.get('Tipo de Conta', 32)
    for i in range(start, end + 1):
        if headers[i] == 'Nome do Cônjuge' and spouse_delta == -1:
            aligned[i] = ''
        else:
            aligned[i] = at(i + personal_delta + (spouse_delta if i >= indexes['CPF *'] else 0))
    aligned[indexes['CPF *']] = cpf
    # Tratamento, apelido e status ancoram o bloco comercial das versões anteriores.
    salutation_idx = indexes.get('Tratamento')
    business_shift = api_shift
    if salutation_idx is not None:
        anchors = [i for i in range(max(0, salutation_idx-7), min(len(cells)-2, salutation_idx+8))
                   if _texto_celula(at(i)) in {'Sr.', 'Sra.'} and re.search(r'_(RJ|MG)\d+$', _texto_celula(at(i+1)), re.I)]
        if len(anchors) == 1:
            business_shift = anchors[0] - salutation_idx
        for i in range(salutation_idx, indexes.get('AccountId', salutation_idx)):
            aligned[i] = at(i + business_shift)
    if 'Regional de Cadastro *' in indexes:
        reg = _texto_celula(at(2)) if ni == 4 else _texto_celula(at(indexes['Regional de Cadastro *']))
        if reg not in {'RJ', 'MG'}:
            reg = _texto_celula(at(indexes.get('Regional__c', 99999) + api_shift))
        aligned[indexes['Regional de Cadastro *']] = reg if reg in {'RJ', 'MG'} else ''
    api_start = indexes.get('AccountId', len(headers))
    api_end = indexes.get('Envio?', len(headers))
    for i in range(api_start, api_end):
        aligned[i] = at(i + api_shift)
    return aligned, {'legacy': bool(personal_delta or spouse_delta or business_shift or api_shift), 'personal_shift': personal_delta, 'business_shift': business_shift, 'api_shift': api_shift}


def alinhar_cabecalhos_existentes(existing: list, incoming: list, values: list) -> tuple[list, list]:
    """Mantém a ordem histórica; colunas novas são adicionadas ao fim, nunca renomeadas."""
    # Rótulos humanos (E-mail *) e nomes de API (Email) são colunas distintas.
    chave = lambda h: re.sub(r"\s+", " ", str(h).strip()).casefold()
    headers = list(existing)
    positions = {}
    for i, h in enumerate(headers):
        if not h:
            continue
        key = chave(h)
        if key in positions:
            raise ValueError('Cabeçalho duplicado na planilha: ' + str(h))
        positions[key] = i
    seen = set()
    for h in incoming:
        key = chave(h)
        if not key or key in seen:
            raise ValueError('Cabeçalho de integração vazio ou duplicado: ' + str(h))
        seen.add(key)
        if key not in positions:
            positions[key] = len(headers)
            headers.append(h)
    result = [''] * len(headers)
    for i, h in enumerate(incoming):
        result[positions[chave(h)]] = values[i] if i < len(values) else ''
    return headers, result


def _schema(sf: Any, record_type: str | None) -> tuple[dict, str, dict]:
    cache = vars(sf).get('_ficha_schema_cache')
    if not cache or time.monotonic() - cache['time'] > 120:
        desc = sf.Contact.describe()
        if not isinstance(desc, dict) or not isinstance(desc.get('fields'), list):
            raise ValueError('Não foi possível validar os campos e permissões do Contact no Salesforce.')
        if desc.get('createable') is False:
            raise ValueError('O usuário da integração não tem permissão para criar contatos no Salesforce.')
        cache = {'time': time.monotonic(), 'desc': desc, 'picklists': {}}
        vars(sf)['_ficha_schema_cache'] = cache
    desc = cache['desc']
    tipos = desc.get('recordTypeInfos', [])
    if record_type:
        matches = [r for r in tipos if str(r.get('recordTypeId', ''))[:15] == record_type[:15] and r.get('available') and r.get('name') == 'Corretor']
    else:
        matches = [r for r in tipos if r.get('name') == 'Corretor' and r.get('available')]
    if len(matches) != 1:
        raise ValueError('Tipo de registro Corretor não disponível ou RecordTypeId configurado sem permissão. Confira a configuração Salesforce.')
    rt = matches[0]['recordTypeId']
    if rt not in cache['picklists']:
        try:
            values = sf.restful('ui-api/object-info/Contact/picklist-values/' + rt)
            cache['picklists'][rt] = values.get('picklistFieldValues', {})
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            raise
        except Exception as exc:
            raise ValueError('Não foi possível consultar as opções permitidas do tipo Corretor. O cadastro não foi criado; confira a permissão da UI API.') from exc
    return {f['name']: f for f in desc['fields']}, rt, cache['picklists'][rt]


def normalizar_payload(sf: Any, payload: dict, avisos: list[str]) -> dict:
    fields, rt, picklists = _schema(sf, str(payload.get('RecordTypeId') or '') or None)
    out = dict(payload, RecordTypeId=rt)
    if out.get('CPF__c'):
        cpf_formatado(out['CPF__c'])  # Valida os dígitos; esta organização recebe CPF sem máscara.
        out['CPF__c'] = digitos(out['CPF__c'])
    ordered, visiting, done = [], set(), set()
    def visit(key):
        if key in done:
            return
        if key in visiting:
            raise ValueError('Dependência circular nos metadados de picklist Salesforce.')
        visiting.add(key)
        controller = fields.get(key, {}).get('controllerName')
        if controller in out:
            visit(controller)
        visiting.remove(key)
        done.add(key)
        ordered.append(key)
    for key in list(out):
        visit(key)
    for key in ordered:
        value = out[key]
        meta = fields.get(key)
        if not meta:
            raise ValueError(f'Campo Salesforce inexistente no Contact: {key}. Confira o mapeamento de integração.')
        if not meta.get('createable'):
            del out[key]
            avisos.append(f'{key}: campo de sistema não gravável, omitido do insert.')
            continue
        if value is None or value == '':
            del out[key]
            continue
        typ = meta.get('type')
        if typ in {'picklist', 'multipicklist'}:
            ui = picklists.get(key) or {}
            values = ui.get('values')
            if values is not None:
                controller = meta.get('controllerName')
                controllers = ui.get('controllerValues') or {}
                if controller and controllers:
                    selected = out.get(controller)
                    index = controllers.get(str(selected))
                    values = [x for x in values if index in x.get('validFor', [])] if index is not None else []
                allowed = [x['value'] for x in values]
            else:
                allowed = [x['value'] for x in meta.get('picklistValues', []) if x.get('active')]
            vals = str(value).split(';') if typ == 'multipicklist' else [str(value).strip()]
            cleaned = []
            for v in vals:
                v = v.strip()
                if key == 'Atividade__c' and v == 'Autônomo Parceiro': v = 'Corretor Parceiro'
                if key == 'Unidade_Negocio__c' and v == 'Outra imobiliária (parceira)': v = 'Direcional'
                if v not in allowed:
                    matches = [x for x in allowed if canonico(x) == canonico(v)]
                    # Bancos são identificados pelo código COMPE; descrições históricas variam.
                    if key == 'Banco__c' and not matches:
                        code = re.match(r'^\s*(\d{3})\b', v)
                        if code:
                            matches = [x for x in allowed if re.match(r'^\s*' + code.group(1) + r'\b', x)]
                    if len(matches) == 1:
                        v = matches[0]
                    elif meta.get('restrictedPicklist') or values is not None:
                        label = meta.get('label') or key
                        raise ValueError(f'{label}: opção não aceita para o tipo Corretor. Opções permitidas: ' + ', '.join(allowed))
                cleaned.append(v)
            out[key] = ';'.join(cleaned)
            value = out[key]
        if key in {'Conta_Banc_ria__c', 'Ag_ncia_Banc_ria__c'}:
            value = str(value).replace(' ', '')
            if not re.fullmatch(r'[0-9xX.\-]+', value) or not digitos(value):
                raise ValueError(f"{meta.get('label', key)}: informe o número bancário, não e-mail ou chave PIX.")
            out[key] = value
        problemas = validar_valor(meta, value, esquema_local()['reference_prefixes'])
        if problemas:
            raise ValueError("; ".join(problemas))
    required = [f.get('label') or k for k, f in fields.items() if f.get('createable') and not f.get('nillable') and not f.get('defaultedOnCreate') and out.get(k) in (None, '')]
    if required:
        raise ValueError('Campos obrigatórios Salesforce ausentes: ' + ', '.join(required))
    return out
