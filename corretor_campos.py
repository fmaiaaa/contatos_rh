# -*- coding: utf-8 -*-
"""
Definição dos campos do layout "Novo Contato: Corretor" (Salesforce Contact)
+ mapeamento para API (nomes reais do org Direcional) e ordem das colunas na planilha Google.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

# Record Type Corretor (ajuste se mudar no org)
RECORD_TYPE_CORRETOR = "012f1000000n6nN"

# Campos de fórmula / somente leitura / não createable — não enviar no INSERT
SF_OMIT_INSERT = frozenset(
    {
        "Blacklist__c",
        "RetornoIntegracaoContaBancaria__c",
        "C_digo_Pessoa_UAU__c",
        "Corretor_Associado__c",
        "MultiplicadorFinal__c",
        "Contact_ID__c",
        "ErroIntegracaoUAU__c",
        "RetornoIntegracaoPessoa__c",
        "Data_Descredenciamento__c",
    }
)

REGIONAIS = [
    "AC",
    "AL",
    "AM",
    "AP",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MG",
    "MS",
    "MT",
    "PA",
    "PE",
    "PI",
    "PR",
    "RJ",
    "RN",
    "RO",
    "RR",
    "RS",
    "SC",
    "SE",
    "SP",
    "TO",
]

ORIGENS = [
    "RH",
    "Indicação",
    "Gerente",
    "Diretor",
    "DiRi Talent",
    "Coordenador",
    "Gupy",
    "MARINHA",
    "Creci",
    "Parceria Estácio",
]

STATUS_CORRETOR = ["Ativo", "Inativo", "Pré credenciado", "Reativado"]

SALUTATIONS = ["", "Sr.", "Sra.", "Dr.", "Dra."]

SEXOS = ["", "Masculino", "Feminino"]

CAMISETAS = ["", "PP", "P", "M", "G", "GG", "XGG"]

UNIDADES_NEGOCIO = [
    "",
    "Direcional",
    "Parceiros (Externo)",
    # completar conforme org
]

TIPO_PIX = [
    "",
    "CPF",
    "CNPJ",
    "E-mail",
    "Telefone",
    "Chave aleatória",
]

ESTADOS_UF = [
    "",
    "AC",
    "AL",
    "AM",
    "AP",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MG",
    "MS",
    "MT",
    "PA",
    "PE",
    "PI",
    "PR",
    "RJ",
    "RN",
    "RO",
    "RR",
    "RS",
    "SC",
    "SE",
    "SP",
    "TO",
]

POSSUI_FILHOS = ["", "Sim", "Não"]

TIPO_CONTA_BANCARIA = ["", "Corrente", "Poupança"]

PREFERRED_METHOD_OPTS = [
    "Work phone",
    "Home phone",
    "Mobile phone",
    "Work Email",
    "Personal Email",
    "No preference",
    "***",
    "Telefone de Trabalho",
    "Telefone residencial",
    "Celular",
    "Email de trabalho",
    "Email pessoal",
    "Sem preferência",
]

# Cada entrada: chave interna, rótulo na planilha/UI, seção, tipo (text|date|number|textarea|id|multiselect),
# nome API Salesforce (None = só planilha / vai para Observacoes), obrigatório, opções (lista ou None)
Campo = Dict[str, Any]


def _campos_def() -> List[Campo]:
    """Lista ordenada de campos (espelha o formulário Salesforce)."""
    z = lambda **kw: kw  # noqa
    return [
        # Informações para contato
        z(
            key="account_id",
            label="Nome da conta (Id Salesforce 18 caracteres)",
            sec="Informações para contato",
            tipo="id",
            sf="AccountId",
            req=False,
            help="Cole o Id da Conta (Account). Obrigatório enviar Id **ou** nome abaixo.",
        ),
        z(
            key="account_name",
            label="Nome da conta (texto livre) *",
            sec="Informações para contato",
            tipo="text",
            sf=None,
            req=False,
            help="Obrigatório se não informar o Id da conta acima.",
        ),
        z(
            key="owner_id",
            label="Proprietário do contato (Id User)",
            sec="Informações para contato",
            tipo="id",
            sf="OwnerId",
            req=False,
        ),
        z(key="first_name", label="Primeiro Nome", sec="Informações para contato", tipo="text", sf="FirstName", req=False),
        z(key="last_name", label="Sobrenome *", sec="Informações para contato", tipo="text", sf="LastName", req=True),
        z(
            key="salutation",
            label="Tratamento",
            sec="Informações para contato",
            tipo="select",
            sf="Salutation",
            opcoes=SALUTATIONS,
            req=False,
        ),
        z(key="apelido", label="Apelido *", sec="Informações para contato", tipo="text", sf="Apelido__c", req=True),
        z(
            key="status_corretor",
            label="Status Corretor *",
            sec="Informações para contato",
            tipo="select",
            sf="Status_Corretor__c",
            opcoes=STATUS_CORRETOR,
            req=True,
        ),
        z(
            key="regional",
            label="Regional *",
            sec="Informações para contato",
            tipo="select",
            sf="Regional__c",
            opcoes=[""] + REGIONAIS,
            req=True,
        ),
        z(
            key="origem",
            label="Origem *",
            sec="Informações para contato",
            tipo="select",
            sf="Origem__c",
            opcoes=[""] + ORIGENS,
            req=True,
        ),
        z(
            key="sexo",
            label="Sexo *",
            sec="Informações para contato",
            tipo="select",
            sf="Sexo__c",
            opcoes=SEXOS,
            req=True,
        ),
        z(
            key="indicado_por_id",
            label="Indicado por (Id User — Pesquisar Pessoas)",
            sec="Informações para contato",
            tipo="id",
            sf="Indicado_por__c",
            req=False,
        ),
        z(
            key="camiseta",
            label="Camiseta *",
            sec="Informações para contato",
            tipo="select",
            sf="Camiseta__c",
            opcoes=CAMISETAS,
            req=True,
        ),
        z(
            key="atividade",
            label="Atividade *",
            sec="Informações para contato",
            tipo="text",
            sf="Atividade__c",
            req=True,
            help="Ex.: Corretor N1 (valores conforme lista de atividades no Salesforce).",
        ),
        z(
            key="escolaridade",
            label="Escolaridade",
            sec="Informações para contato",
            tipo="text",
            sf="Escolaridade__c",
            req=False,
        ),
        z(
            key="data_entrevista",
            label="Data da Entrevista * (dd/mm/aaaa)",
            sec="Informações para contato",
            tipo="date",
            sf="Data_da_Entrevista__c",
            req=True,
        ),
        z(
            key="unidade_negocio",
            label="Unidade Negócio",
            sec="Informações para contato",
            tipo="select",
            sf="Unidade_Negocio__c",
            opcoes=UNIDADES_NEGOCIO,
            req=False,
        ),
        z(
            key="data_transferencia_parceiro",
            label="Data Transferência Corretor Parceiro (dd/mm/aaaa)",
            sec="Informações para contato",
            tipo="date",
            sf="Data_Transferencia_Corretor_Parceiro__c",
            req=False,
        ),
        # Dados pessoais
        z(
            key="birthdate",
            label="Data de nascimento * (dd/mm/aaaa)",
            sec="Dados pessoais",
            tipo="date",
            sf="Birthdate",
            req=True,
        ),
        z(
            key="estado_civil",
            label="Estado Civil *",
            sec="Dados pessoais",
            tipo="text",
            sf="EstadoCivil__c",
            req=True,
        ),
        z(key="cpf", label="CPF *", sec="Dados pessoais", tipo="text", sf="CPF__c", req=True),
        z(key="pis", label="PIS", sec="Dados pessoais", tipo="text", sf="PIS__c", req=False),
        z(
            key="nacionalidade",
            label="Nacionalidade *",
            sec="Dados pessoais",
            tipo="text",
            sf="Nacionalidade__c",
            req=True,
        ),
        z(
            key="naturalidade",
            label="Naturalidade *",
            sec="Dados pessoais",
            tipo="text",
            sf="Naturalidade__c",
            req=True,
        ),
        z(key="rg", label="RG *", sec="Dados pessoais", tipo="text", sf="RG__c", req=True),
        z(
            key="uf_naturalidade",
            label="UF Naturalidade *",
            sec="Dados pessoais",
            tipo="select",
            sf="UF_Naturalidade__c",
            opcoes=ESTADOS_UF,
            req=True,
        ),
        z(
            key="uf_rg",
            label="UF RG *",
            sec="Dados pessoais",
            tipo="select",
            sf="UF_RG__c",
            opcoes=ESTADOS_UF,
            req=True,
        ),
        z(
            key="tipo_pix",
            label="Tipo do PIX *",
            sec="Dados pessoais",
            tipo="select",
            sf="Tipo_do_PIX__c",
            opcoes=TIPO_PIX,
            req=True,
        ),
        z(
            key="dados_pix",
            label="Dados para PIX *",
            sec="Dados pessoais",
            tipo="text",
            sf="Dados_para_PIX__c",
            req=True,
        ),
        # Dados de usuário (multiplicadores)
        z(
            key="multiplicador_nivel",
            label="Multiplicador de Nível",
            sec="Dados de usuário",
            tipo="number",
            sf="Multiplicador__c",
            req=False,
        ),
        z(
            key="usuario_uau",
            label="Usuário UAU",
            sec="Dados de usuário",
            tipo="text",
            sf="Usu_rio_UAU__c",
            req=False,
        ),
        z(
            key="multiplicador_regime",
            label="Multiplicador de Regime",
            sec="Dados de usuário",
            tipo="number",
            sf="Multiplicador_de_Regime__c",
            req=False,
        ),
        # Dados para contato
        z(key="phone", label="Telefone", sec="Dados para contato", tipo="text", sf="Phone", req=False),
        z(
            key="email_direcional",
            label="E-mail Direcional",
            sec="Dados para contato",
            tipo="text",
            sf="E_mail_Direcional__c",
            req=False,
        ),
        z(key="email", label="E-mail *", sec="Dados para contato", tipo="text", sf="Email", req=True),
        z(
            key="mobile",
            label="Celular",
            sec="Dados para contato",
            tipo="text",
            sf="MobilePhone",
            req=False,
        ),
        z(
            key="celular_2",
            label="Celular 2",
            sec="Dados para contato",
            tipo="text",
            sf="Celular_2__c",
            req=False,
        ),
        z(
            key="other_phone",
            label="Outro telefone",
            sec="Dados para contato",
            tipo="text",
            sf="OtherPhone",
            req=False,
        ),
        # Dados familiares
        z(
            key="nome_pai",
            label="Nome do Pai *",
            sec="Dados familiares",
            tipo="text",
            sf="Nome_do_Pai__c",
            req=True,
        ),
        z(
            key="possui_filhos",
            label="Possui Filho(s)?",
            sec="Dados familiares",
            tipo="select",
            sf="Possui_Filho__c",
            opcoes=POSSUI_FILHOS,
            req=False,
        ),
        z(
            key="nome_mae",
            label="Nome da Mãe *",
            sec="Dados familiares",
            tipo="text",
            sf="Nome_da_Mae__c",
            req=True,
        ),
        z(
            key="qtd_filhos",
            label="Quantidade de Filhos",
            sec="Dados familiares",
            tipo="number",
            sf="Quantidade_de_Filhos__c",
            req=False,
        ),
        z(
            key="nome_conjuge",
            label="Nome do Cônjuge",
            sec="Dados familiares",
            tipo="text",
            sf="Nome_do_Conjuge__c",
            req=False,
        ),
        # Dados bancários
        z(key="banco", label="Banco *", sec="Dados bancários PF", tipo="text", sf="Banco__c", req=True),
        z(
            key="conta_bancaria",
            label="Conta Bancária *",
            sec="Dados bancários PF",
            tipo="text",
            sf="Conta_Banc_ria__c",
            req=True,
        ),
        z(
            key="agencia_bancaria",
            label="Agência Bancária *",
            sec="Dados bancários PF",
            tipo="text",
            sf="Ag_ncia_Banc_ria__c",
            req=True,
        ),
        z(
            key="retorno_integracao_bancaria",
            label="Retorno integração conta bancária",
            sec="Dados bancários PF",
            tipo="textarea",
            sf="RetornoIntegracaoContaBancaria__c",
            req=False,
            help="Campo somente leitura no Salesforce — preenchido pela integração.",
        ),
        z(
            key="tipo_conta",
            label="Tipo de Conta",
            sec="Dados bancários PF",
            tipo="select",
            sf="Tipo_de_Conta__c",
            opcoes=TIPO_CONTA_BANCARIA,
            req=False,
        ),
        # CRECI / TTI
        z(
            key="data_matricula_tti",
            label="Data Matrícula - TTI (dd/mm/aaaa)",
            sec="CRECI / TTI",
            tipo="date",
            sf="Data_Matricula_TTI__c",
            req=False,
        ),
        z(
            key="tti",
            label="TTI",
            sec="CRECI / TTI",
            tipo="text",
            sf="TTI__c",
            req=False,
        ),
        z(
            key="status_creci",
            label="Status CRECI",
            sec="CRECI / TTI",
            tipo="text",
            sf="Status_CRECI__c",
            req=False,
        ),
        z(
            key="data_conclusao",
            label="Data de conclusão (dd/mm/aaaa)",
            sec="CRECI / TTI",
            tipo="date",
            sf="Data_de_conclusao__c",
            req=False,
        ),
        z(key="creci", label="CRECI", sec="CRECI / TTI", tipo="text", sf="CRECI__c", req=False),
        z(
            key="observacoes_creci",
            label="Observações (CRECI)",
            sec="CRECI / TTI",
            tipo="textarea",
            sf="Observacoes__c",
            req=False,
        ),
        z(
            key="validade_creci",
            label="Validade CRECI (dd/mm/aaaa)",
            sec="CRECI / TTI",
            tipo="date",
            sf="Validade_CRECI__c",
            req=False,
        ),
        z(
            key="nome_responsavel",
            label="Nome do Responsável",
            sec="CRECI / TTI",
            tipo="text",
            sf="Nome_do_Responsavel__c",
            req=False,
        ),
        z(
            key="creci_responsavel",
            label="CRECI do Responsável",
            sec="CRECI / TTI",
            tipo="number",
            sf="CRECI_do_Responsavel__c",
            req=False,
        ),
        z(
            key="tipo_comissionamento",
            label="Tipo de Comissionamento",
            sec="CRECI / TTI",
            tipo="text",
            sf=None,
            req=False,
            help="Se o campo customizado existir no org, ajuste em corretor_campos.py",
        ),
        z(
            key="tipo_corretor",
            label="Tipo Corretor *",
            sec="CRECI / TTI",
            tipo="text",
            sf="Tipo_Corretor__c",
            req=True,
            help="Ex.: Direcional Vendas - Autônomos",
        ),
        z(
            key="faturamento_comissao",
            label="Faturamento Comissão (ordem)",
            sec="Contrato / PJ",
            tipo="text",
            sf=None,
            req=False,
            help="Campo dependente no SF — gravado na planilha; pode ir para Observações.",
        ),
        z(
            key="faturamento_comissao_obs",
            label="Faturamento Comissão (observação / CNPJ contexto)",
            sec="Contrato / PJ",
            tipo="text",
            sf=None,
            req=False,
        ),
        z(key="cnpj", label="CNPJ", sec="Contrato / PJ", tipo="text", sf="CNPJ__c", req=False),
        z(
            key="razao_social",
            label="Razão Social",
            sec="Contrato / PJ",
            tipo="text",
            sf="Razao_Social__c",
            req=False,
        ),
        z(
            key="fornecedor_uau",
            label="Cadastrado como Fornecedor no UAU?",
            sec="Contrato / PJ",
            tipo="text",
            sf="Cadastrado_como_Fornecedor_no_UAU__c",
            req=False,
            help="Sim/Não ou valor exato do picklist no Salesforce.",
        ),
        z(
            key="contrato_texto",
            label="Contrato (texto)",
            sec="Contrato / PJ",
            tipo="textarea",
            sf="Contrato__c",
            req=False,
        ),
        z(
            key="data_contrato",
            label="Data Contrato * (dd/mm/aaaa)",
            sec="Contrato / PJ",
            tipo="date",
            sf="Data_Contrato__c",
            req=True,
        ),
        z(
            key="data_credenciamento",
            label="Data Credenciamento * (dd/mm/aaaa)",
            sec="Contrato / PJ",
            tipo="date",
            sf="Data_Credenciamento__c",
            req=True,
        ),
        # Histórico / equipe
        z(
            key="historico_equipe",
            label="Histórico Equipe",
            sec="Histórico equipe",
            tipo="textarea",
            sf=None,
            req=False,
        ),
        z(
            key="produto_atuacao_id",
            label="Produto de Atuação (Id Empreendimento)",
            sec="Histórico equipe",
            tipo="id",
            sf="Produto_de_Atuacao__c",
            req=False,
        ),
        z(
            key="nao_recomendado_motivo",
            label="Não recomendado - Motivo",
            sec="Histórico equipe",
            tipo="textarea",
            sf=None,
            req=False,
        ),
        z(
            key="gerente_anterior_id",
            label="Gerente anterior (Id User)",
            sec="Histórico equipe",
            tipo="id",
            sf="GerenteAnterior__c",
            req=False,
        ),
        z(
            key="motivo_inatividade",
            label="Motivo Inatividade",
            sec="Histórico equipe",
            tipo="text",
            sf="Motivo_Inatividade__c",
            req=False,
        ),
        z(
            key="solicitante_descredenciamento_id",
            label="Solicitante Descredenciamento (Id User)",
            sec="Histórico equipe",
            tipo="id",
            sf="Solicitantedescredenciamento__c",
            req=False,
        ),
        z(
            key="tipo_desligamento",
            label="Tipo de desligamento",
            sec="Histórico equipe",
            tipo="text",
            sf="Tipo_de_desligamento__c",
            req=False,
        ),
        z(
            key="motivo_descredenciamento",
            label="Motivo Descredenciamento",
            sec="Histórico equipe",
            tipo="text",
            sf="Motivo_Descredenciamento__c",
            req=False,
        ),
        z(
            key="blacklist_flag",
            label="Blacklist (informação)",
            sec="Histórico equipe",
            tipo="text",
            sf=None,
            req=False,
            help="Campo Blacklist no SF é controlado pelo sistema — use para notas na planilha.",
        ),
        z(
            key="falso_blacklist",
            label="FalsoBlacklist / observação",
            sec="Histórico equipe",
            tipo="text",
            sf=None,
            req=False,
        ),
        # Datas adicionais
        z(
            key="data_descredenciamento",
            label="Data Descredenciamento (dd/mm/aaaa)",
            sec="Datas",
            tipo="date",
            sf="Data_Descredenciamento__c",
            req=False,
        ),
        z(
            key="data_saida",
            label="Data de Saída (dd/mm/aaaa)",
            sec="Datas",
            tipo="date",
            sf="Data_de_Saida__c",
            req=False,
        ),
        z(
            key="data_transferencia",
            label="Data de Transferência (dd/mm/aaaa)",
            sec="Datas",
            tipo="date",
            sf="Data_de_Transferencia__c",
            req=False,
        ),
        z(
            key="data_reativacao",
            label="Data Reativação (dd/mm/aaaa)",
            sec="Datas",
            tipo="date",
            sf="Data_Reativacao__c",
            req=False,
        ),
        z(
            key="data_entrada_recruita",
            label="Data Entrada Recruta+ (dd/mm/aaaa)",
            sec="Datas",
            tipo="date",
            sf="Data_Entrada_Recruta__c",
            req=False,
        ),
        z(
            key="data_saida_recruita",
            label="Data Saída Recruta+ (dd/mm/aaaa)",
            sec="Datas",
            tipo="date",
            sf="Data_Sai_da_Recruta__c",
            req=False,
        ),
        # Integração
        z(
            key="codigo_pessoa_uau",
            label="Código Pessoa UAU",
            sec="Dados integração",
            tipo="text",
            sf="C_digo_Pessoa_UAU__c",
            req=False,
        ),
        z(
            key="erro_integracao_uau",
            label="Erro Integração UAU",
            sec="Dados integração",
            tipo="textarea",
            sf="ErroIntegracaoUAU__c",
            req=False,
        ),
        z(
            key="retorno_integracao_pessoa",
            label="Retorno Integração Pessoa",
            sec="Dados integração",
            tipo="textarea",
            sf="RetornoIntegracaoPessoa__c",
            req=False,
        ),
        z(key="anexos", label="Anexos (notas)", sec="Anexos", tipo="textarea", sf=None, req=False),
        z(
            key="preferred_contact_method",
            label="Preferred Contact Method (múltiplos)",
            sec="Preferred Contact Method",
            tipo="multiselect",
            sf="Preferred_Contact_Method__c",
            opcoes=PREFERRED_METHOD_OPTS,
            req=False,
        ),
    ]


CAMPOS: List[Campo] = _campos_def()

_ID_RE = re.compile(r"^[a-zA-Z0-9]{15}(?:[a-zA-Z0-9]{3})?$")


def parse_data_br(val: Any) -> Optional[str]:
    """Converte dd/mm/aaaa ou aaaa-mm-dd para ISO date string (YYYY-MM-DD)."""
    if val is None or (isinstance(val, float) and str(val) == "nan"):
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, datetime):
        return val.date().isoformat()
    s = str(val).strip()
    if not s:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _limpa_id(sf_field: str, val: Any) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    if sf_field in ("AccountId", "OwnerId", "Indicado_por__c", "GerenteAnterior__c", "Solicitantedescredenciamento__c"):
        if _ID_RE.match(s):
            return s
    if sf_field == "Produto_de_Atuacao__c" and _ID_RE.match(s):
        return s
    return None


def validar_obrigatorios(dados: Dict[str, Any]) -> List[str]:
    erros = []
    for c in CAMPOS:
        if not c.get("req"):
            continue
        k = c["key"]
        v = dados.get(k)
        if c["tipo"] == "multiselect":
            if not v or (isinstance(v, list) and len(v) == 0):
                erros.append(c["label"])
            continue
        if v is None or (isinstance(v, str) and not str(v).strip()):
            erros.append(c["label"])
    # Nome da conta: Id OU nome
    aid = (dados.get("account_id") or "").strip()
    aname = (dados.get("account_name") or "").strip()
    if not aid and not aname:
        erros.append("Nome da conta (Id Salesforce ou texto)")
    return erros


def montar_payload_salesforce(dados: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """
    Monta dict para Contact.create. Acrescenta RecordTypeId.
    Devolve (payload, avisos) — avisos = campos ignorados ou texto extra para Description.
    """
    payload: Dict[str, Any] = {"RecordTypeId": RECORD_TYPE_CORRETOR}
    avisos: List[str] = []
    extras_obs: List[str] = []

    for c in CAMPOS:
        key = c["key"]
        sf = c.get("sf")
        raw = dados.get(key)
        if sf is None:
            if raw and str(raw).strip():
                extras_obs.append(f"{c['label']}: {raw}")
            continue

        if sf in SF_OMIT_INSERT:
            if raw and str(raw).strip():
                extras_obs.append(f"{c['label']}: {raw}")
            continue

        tipo = c["tipo"]
        val: Any = raw

        if tipo == "date":
            iso = parse_data_br(raw)
            if iso:
                payload[sf] = iso
            continue

        if tipo == "id":
            lid = _limpa_id(sf, raw)
            if lid:
                payload[sf] = lid
            elif raw and str(raw).strip():
                avisos.append(f"{c['label']}: valor não parece Id Salesforce — omitido.")
            continue

        if tipo == "number":
            if raw is None or raw == "":
                continue
            try:
                payload[sf] = float(str(raw).replace(",", "."))
            except ValueError:
                avisos.append(f"{c['label']}: número inválido — omitido.")
            continue

        if tipo == "multiselect":
            if isinstance(raw, list) and raw:
                payload[sf] = ";".join(raw)
            continue

        if tipo == "textarea":
            s = (str(raw).strip() if raw is not None else "") or ""
            if s:
                if sf == "Observacoes__c":
                    extras_obs.insert(0, s)
                else:
                    payload[sf] = s
            continue

        # text / select
        s = (str(raw).strip() if raw is not None else "") or ""
        if not s:
            continue
        payload[sf] = s

    # Nome da conta (texto) se não tiver AccountId
    acc = dados.get("account_id")
    acc_txt = dados.get("account_name")
    if (not acc or not str(acc).strip()) and acc_txt and str(acc_txt).strip():
        extras_obs.append(f"Nome da conta (referência): {acc_txt}")

    obs_final = (payload.get("Observacoes__c") or "").strip()
    extra_block = "\n".join(extras_obs)
    if extra_block:
        payload["Observacoes__c"] = (obs_final + "\n" + extra_block).strip() if obs_final else extra_block

    # Remove chaves vazias / None
    payload = {k: v for k, v in payload.items() if v is not None and v != ""}

    return payload, avisos


def linha_planilha(dados: Dict[str, Any], timestamp_iso: str) -> List[str]:
    """Uma linha na ordem das colunas + carimbo de data."""
    row: List[str] = []
    for c in CAMPOS:
        k = c["key"]
        v = dados.get(k)
        if c["tipo"] == "multiselect" and isinstance(v, list):
            row.append("; ".join(v))
        elif v is None:
            row.append("")
        else:
            row.append(str(v))
    row.append(timestamp_iso)
    return row


def cabecalho_planilha() -> List[str]:
    return [c["label"] for c in CAMPOS] + ["Carimbo de data/hora"]


def secoes_ordenadas() -> List[str]:
    seen = []
    for c in CAMPOS:
        s = c["sec"]
        if s not in seen:
            seen.append(s)
    return seen


def campos_por_secao(sec: str) -> List[Campo]:
    return [c for c in CAMPOS if c["sec"] == sec]
