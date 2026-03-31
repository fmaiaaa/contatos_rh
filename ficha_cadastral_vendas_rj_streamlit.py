# -*- coding: utf-8 -*-
"""
Ficha de credenciamento — Direcional Vendas RJ (corretores).

Arquivo único para deploy (ex.: Streamlit Cloud): campos, planilha Google, segurança e app.
Dependências: streamlit, gspread, google-auth, simple_salesforce (requirements.txt).
"""
from __future__ import annotations

import base64
import html
import io
import json
import os
import platform
import re
import smtplib
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape as _xml_escape_para_pdf
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

_DIR_APP = Path(__file__).resolve().parent

# --- Salesforce (simple_salesforce; antes: salesforce_api.py) ---
try:
    from simple_salesforce import Salesforce, SalesforceAuthenticationFailed
except ImportError:
    Salesforce = None  # type: ignore[misc, assignment]
    SalesforceAuthenticationFailed = Exception  # type: ignore[misc, assignment]

_SF_SDK_DISPONIVEL = Salesforce is not None


def conectar_salesforce():
    if not _SF_SDK_DISPONIVEL:
        return None
    username = (os.environ.get("SALESFORCE_USER") or "").strip()
    password = (os.environ.get("SALESFORCE_PASSWORD") or "").strip()
    token = (os.environ.get("SALESFORCE_TOKEN") or "").strip()
    if not username or not password:
        return None
    try:
        if token:
            return Salesforce(
                username=username,
                password=password,
                security_token=token,
                domain="login",
            )
        return Salesforce(username=username, password=password, domain="login")
    except SalesforceAuthenticationFailed:
        return None
    except Exception:
        return None


def criar_contato_payload(sf, payload: dict) -> tuple[Any, Any]:
    try:
        res = sf.Contact.create(payload)
        return res.get("id"), None
    except Exception as e:
        return None, str(e)


def _explicacao_erro_record_type_se_aplicavel(err: Any) -> str:
    """
    INVALID_CROSS_REFERENCE_KEY em RecordTypeId: o Id 012… costuma estar certo; o usuário da API
    frequentemente não tem esse tipo de registro no perfil (mensagem em PT: «ID do tipo de registro»).
    """
    base = (str(err).strip() if err is not None else "") or "Erro desconhecido"
    u = base.upper()
    compact = u.replace(" ", "")
    if "INVALID_CROSS_REFERENCE_KEY" not in compact:
        return base
    if "RECORDTYPE" not in compact and "TIPODEREGISTRO" not in compact.replace("_", ""):
        if "REGISTRO" not in u:
            return base
    return (
        base
        + "\n\n▸ O Id na URL (prefixo **012**) em geral está correto. Este erro indica que o **usuário da integração** "
        "(login em [salesforce] **USER** nos Secrets) **não pode usar esse Record Type** no objeto Contact.\n"
        "  • Ajuste no org: **Setup → Profiles** (ou **Permission Sets**) do usuário da API → **Object Settings** → "
        "**Contact** → **Record Types** → inclua o tipo desejado (ex.: o da URL que você copiou).\n"
        "  • **Enquanto isso:** nos Secrets use **RECORD_TYPE_ID = \"omit\"** ou remova a chave — o insert deixa de enviar "
        "**RecordTypeId** e o Salesforce usa um tipo que o usuário já tenha como padrão (confira depois no registro)."
    )


def _html_erro_salesforce_multilinha(msg: Any) -> str:
    """Escape HTML e preserva quebras para _alert_vermelho_html."""
    return html.escape(str(msg)).replace("\n", "<br/>")


# =============================================================================
# INTEGRADO: corretor_campos
# =============================================================================
# Opcional: Id do Record Type Contact (URL Setup → Object Manager → Contact → Record Types → …/012…/view).
# Só é usado se [salesforce] RECORD_TYPE_ID estiver vazio. Ex. de org: 012f1000000n6nNAAQ.
# INVALID_CROSS_REFERENCE_KEY em RecordTypeId com Id 012 válido → veja _explicacao_erro_record_type_se_aplicavel (perfil).
RECORD_TYPE_CORRETOR = ""

_SF_ID_15_18 = re.compile(r"^[a-zA-Z0-9]{15}(?:[a-zA-Z0-9]{3})?$")


def _id_e_record_type_plausivel(rid: str) -> bool:
    """Record Type Id no Salesforce usa prefixo de chave 012 (005 = usuário, não serve em RecordTypeId)."""
    if not rid or len(rid) < 3 or not _SF_ID_15_18.match(rid):
        return False
    return rid[:3] == "012"


_EMAIL_CONTATO_RE = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)


def email_contato_formato_valido(val: Any) -> bool:
    """Validação simples de e-mail para formulário e SMTP (evita destinos como «K»)."""
    s = (str(val).strip() if val is not None else "") or ""
    if not s or len(s) > 254:
        return False
    return bool(_EMAIL_CONTATO_RE.match(s))


def record_type_id_contato_payload_e_aviso() -> Tuple[str, str]:
    """
    Record Type Id de Contact começa com **012**. **005…** é Id de **usuário** → INVALID_CROSS_REFERENCE_KEY.
    Retorna (id_ou_vazio, aviso_se_config_incorreta).
    """
    for candidate in (
        (os.environ.get("SF_RECORD_TYPE_ID") or "").strip(),
        (RECORD_TYPE_CORRETOR or "").strip(),
    ):
        if not candidate:
            continue
        if not _SF_ID_15_18.match(candidate):
            continue
        if _id_e_record_type_plausivel(candidate):
            return candidate, ""
        return (
            "",
            "Secrets **[salesforce] RECORD_TYPE_ID** está incorreto: o valor não é um **Record Type Id** de Contact "
            "(no Salesforce ele começa com **012**). **005…** é Id de **usuário**, não de tipo de registro. "
            "Ajuste em **Setup → Object Manager → Contact → Record Types** (abra o tipo, ex.: Corretor, e copie o Id da URL) "
            "ou remova a chave nos Secrets para usar o tipo padrão da integração.",
        )
    return "", ""


def record_type_id_contato_payload() -> str:
    rid, _ = record_type_id_contato_payload_e_aviso()
    return rid

# Ordem das seções no Salesforce (não alterar sem checar o layout no org)
SEC_ORDER: Tuple[str, ...] = (
    "Informações para contato",
    "Dados Pessoais",
    "Dados de Usuário",
    "Dados para Contato",
    "Dados Familiares",
    "Dados Bancários Pessoa Física",
    "CRECI/TTI",
    "Dados Integração",
    "Preferência de contato",
)

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
        # Evita falha de picklist restrita em orgs onde "Indicação" não existe para Origem__c.
        "Origem__c",
        # Evita DUPLICATE_VALUE em orgs com restrição de unicidade no apelido.
        "Apelido__c",
    }
)

REGIONAIS = [
    "--Nenhum--",
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
    "--Nenhum--",
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

STATUS_CORRETOR = ["--Nenhum--", "Ativo", "Inativo", "Pré credenciado", "Reativado"]

SALUTATIONS = ["--Nenhum--", "Sr.", "Sra.", "Dr.", "Dra."]

SEXOS = ["--Nenhum--", "Masculino", "Feminino"]

CAMISETAS = ["--Nenhum--", "PP", "P", "M", "G", "GG", "XGG"]

# Valores exibidos no formulário Vendas RJ (mapeados para o picklist SF em `montar_payload_salesforce`).
UNIDADE_REDE_OUTRA_IMOBILIARIA = "Outra imobiliária (parceira)"
UNIDADES_NEGOCIO = [
    "--Nenhum--",
    "Direcional",
    "Riva",
    UNIDADE_REDE_OUTRA_IMOBILIARIA,
]

# Atividade restrita ao fluxo Vendas RJ (picklist SF: Corretor Parceiro, Corretor, Captador).
ATIVIDADE_VENDAS_RJ_OPTS = ["--Nenhum--", "Corretor Parceiro", "Corretor", "Captador"]

TIPO_PIX = ["--Nenhum--", "CPF", "CNPJ", "E-mail", "Telefone", "Chave aleatória"]

ESTADOS_UF = [
    "--Nenhum--",
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

POSSUI_FILHOS = ["--Nenhum--", "Sim", "Não"]

TIPO_CONTA_BANCARIA = ["--Nenhum--", "Corrente", "Poupança"]

# Picklists Contact (fonte: salesforce_objetos_describe.json — alinhar ao org ao atualizar o describe)
_ESTADO_CIVIL = ["Solteiro", "Casado", "Divorciado", "Viúvo"]
_ESCOLARIDADE = [
    "Ensino Fundamental",
    "Ensino Médio",
    "Superior em Andamento",
    "Superior Completo",
    "Mestrado em Andamento",
    "Mestrado Concluído",
    "Doutorado em Andamento",
    "Doutorado Concluído",
]
_NACIONALIDADE = ["Brasileiro", "Estrangeira", "Espanhola"]
_ATIVIDADE = [
    "Captador",
    "Estagiário",
    "Corretor",
    "Coordenador",
    "Gerente de Vendas",
    "Gerente Regional",
    "Diretor",
    "Gerente",
    "Captador Recruta+",
    "Gerente Recruta+",
    "Corretor N1",
    "Gerente de Vendas N1",
    "Diretor de Vendas",
    "Analista",
    "Assistente",
    "Cliente",
    "Coordenador de Produto",
    "Coordenador de Vendas",
    "Diretor de Incorporação",
    "Gerente Comercial",
    "Gerente de Parcerias",
    "Imobiliária Parceira",
    "Pasteiro (a)",
    "Superintendente",
    "Supervisor",
    "Autônomo Parceiro",
    "Corretor Parceiro",
    "Recepção",
    "Coordenador de Parcerias",
]
_TIPO_CORRETOR = [
    "Direcional Vendas – GRI (CLT)",
    "Direcional Vendas – Autônomos",
    "Parceiros (Externo)",
]
_STATUS_CRECI = [
    "Concluído Provas",
    "Definitivo",
    "Estágio",
    "Matriculado",
    "Pendente",
    "Protocolo Definitivo",
    "Protocolo Estágio",
    "Pendente Prova",
]
_MOTIVO_INATIVIDADE = [
    "Solicitação do Corretor",
    "Solicitação do Gerente de Vendas",
    "Solicitação do Gerente Regional",
    "Solicitação do Diretor",
]
_MOTIVO_DESCREDENCIAMENTO = [
    "Falta de recurso financeiro",
    "Oportunidade CLT",
    "Distância",
    "Relacionamento com o Gestor",
    "Baixa performance",
    "Abandono",
    "Desistente da Incubadora",
    "Mudança de Cidade / Estado",
    "Problemas de Saúde",
    "Concorrência",
    "Comportamento Inadequado",
    "Promoção Interna",
    "Corretor Parceiro",
]
_TIPO_DESLIGAMENTO = ["Ativo", "Passivo"]
_FORNECEDOR_UAU = ["Não", "Sim"]
_BANCO = [
    "001 – Banco do Brasil S.A.",
    "004 - BANCO DO NORDESTE DO BRASIL S.A.",
    "033 – Banco Santander (Brasil) S.A.",
    "070 - BCO BRB SA - BRASILIA",
    "104 – Caixa Econômica Federal",
    "121 - Banco Agiplan",
    "197 – Stone Pagamentos S.A.",
    "208 – Banco BTG Pactual",
    "212 - Banco Original S.A.",
    "218 – Banco Bonsucesso SA",
    "237 – Banco Bradesco S.A.",
    "246 - Banco ABC Brasil S.A.",
    "260 – Banco Nubank",
    "290 – PagSeguro Internt SA",
    "318 - BCO BMG COMERCIAL S.A",
    "323 – Mercado Pago",
    "336 - BANCO C6 S.A.",
    "340 – Super digital",
    "341 – Banco Itaú S.A.",
    "356 – Banco Real S.A. (antigo)",
    "364 - Gerencianet",
    "380 – PicPay",
    "389 – Banco Mercantil do Brasil S.A.",
    "399 – HSBC Bank Brasil S.A. – Banco Múltiplo",
    "403 – CORA SOCIEDADE DE CR",
    "413 – BV",
    "422 – Banco Safra S.A.",
    "453 – Banco Rural S.A.",
    "473 - Banco Caixa Geral - Brasil S.A.",
    "623 – Banco Panamericano S.A",
    "633 – Banco Rendimento S.A.",
    "637 - Bco Sofisa SA.",
    "652 – Itaú Unibanco Holding S.A.",
    "655 – Banco Votorantim S.A.",
    "735 - BANCO POTTENCIAL S.A.",
    "745 – Banco Citibank S.A.",
    "746 - BCO MODAL SA.",
    "748 – BCO COOP. SICREDI SA",
    "756 – Banco SICCOB S.A",
    "77 - BCO INTERMEDIUM SA",
    "79 - Banco Original Agro",
    "92 - BANCO BRK",
    "348 - BANCO XP S.A",
    "679 - CloudWalk Instituição de Pagamento",
    "536 – NEON PAGAMENTOS",
    "335 -  Banco Digio S.A.",
]

ESTADO_CIVIL_OPTS = ["--Nenhum--"] + _ESTADO_CIVIL
ESCOLARIDADE_OPTS = ["--Nenhum--"] + _ESCOLARIDADE
NACIONALIDADE_OPTS = ["--Nenhum--"] + _NACIONALIDADE
ATIVIDADE_OPTS = ["--Nenhum--"] + _ATIVIDADE
TIPO_CORRETOR_OPTS = ["--Nenhum--"] + _TIPO_CORRETOR
STATUS_CRECI_OPTS = ["--Nenhum--"] + _STATUS_CRECI
MOTIVO_INATIVIDADE_OPTS = ["--Nenhum--"] + _MOTIVO_INATIVIDADE
MOTIVO_DESCREDENCIAMENTO_OPTS = ["--Nenhum--"] + _MOTIVO_DESCREDENCIAMENTO
TIPO_DESLIGAMENTO_OPTS = ["--Nenhum--"] + _TIPO_DESLIGAMENTO
FORNECEDOR_UAU_OPTS = ["--Nenhum--"] + _FORNECEDOR_UAU
BANCO_OPTS = ["--Nenhum--"] + _BANCO

# Valores alinhados ao picklist do Salesforce (somente opções em português).
PREFERRED_METHOD_OPTS = [
    "Telefone de Trabalho",
    "Telefone residencial",
    "Celular",
    "Email de trabalho",
    "Email pessoal",
    "Sem preferência",
]

# Fallback se [ficha_defaults] não tiver account_names — substitua ou use Secrets.
NOMES_CONTA_FIXOS: Tuple[str, ...] = ("Ajuste em ficha_defaults.account_names",)

Campo = Dict[str, Any]


def _z(**kw) -> Campo:
    return kw


def _campos_def() -> List[Campo]:
    """
    Ordem idêntica ao formulário Salesforce (Novo Contato: Corretor).
    * = obrigatório no layout (req=True), salvo quando combinado com outro campo.
    """
    return [
        # ——— Informações para contato ———
        _z(
            key="account_name",
            label="Nome da conta *",
            sec="Informações para contato",
            tipo="select",
            sf=None,
            opcoes=list(NOMES_CONTA_FIXOS),
            req=True,
            help="Opções: coluna «Nome da Conta» na aba «Gerentes» da planilha Google ([google_sheets]); senão [ficha_defaults].",
        ),
        _z(
            key="account_id",
            label="Nome da conta — Id (Account)",
            sec="Informações para contato",
            tipo="id",
            sf="AccountId",
            req=False,
            help="Id Salesforce da conta (18 caracteres).",
        ),
        _z(
            key="owner_id",
            label="Proprietário do contato",
            sec="Informações para contato",
            tipo="id",
            sf="OwnerId",
            req=False,
            help="Id do usuário proprietário (opcional).",
        ),
        _z(
            key="nome_completo",
            label="Nome completo *",
            sec="Informações para contato",
            tipo="text",
            sf=None,
            req=True,
            help="Primeira palavra = nome (Primeiro Nome no Salesforce); o restante = sobrenome. Apelido gerado automaticamente.",
        ),
        _z(
            key="salutation",
            label="Tratamento",
            sec="Informações para contato",
            tipo="select",
            sf="Salutation",
            opcoes=SALUTATIONS,
            req=False,
        ),
        _z(
            key="apelido",
            label="Apelido",
            sec="Informações para contato",
            tipo="text",
            sf="Apelido__c",
            req=False,
            help="Preenchido automaticamente: primeiro nome + _RJ01",
        ),
        _z(
            key="status_corretor",
            label="Status Corretor *",
            sec="Informações para contato",
            tipo="select",
            sf="Status_Corretor__c",
            opcoes=STATUS_CORRETOR,
            req=True,
        ),
        _z(
            key="regional",
            label="Regional *",
            sec="Informações para contato",
            tipo="select",
            sf="Regional__c",
            opcoes=REGIONAIS,
            req=True,
        ),
        _z(
            key="origem",
            label="Origem *",
            sec="Informações para contato",
            tipo="select",
            sf="Origem__c",
            opcoes=ORIGENS,
            req=True,
        ),
        _z(
            key="sexo",
            label="Sexo *",
            sec="Informações para contato",
            tipo="select",
            sf="Sexo__c",
            opcoes=SEXOS,
            req=True,
        ),
        _z(
            key="camiseta",
            label="Camiseta *",
            sec="Informações para contato",
            tipo="select",
            sf="Camiseta__c",
            opcoes=CAMISETAS,
            req=True,
        ),
        _z(
            key="unidade_negocio",
            label="Fará parte de qual rede? *",
            sec="Informações para contato",
            tipo="select",
            sf="Unidade_Negocio__c",
            opcoes=UNIDADES_NEGOCIO,
            req=True,
            help="Direcional, Riva ou imobiliária parceira (externa).",
        ),
        _z(
            key="atividade",
            label="Função na operação *",
            sec="Informações para contato",
            tipo="select",
            sf="Atividade__c",
            opcoes=ATIVIDADE_OPTS,
            req=True,
            help="No fluxo Vendas RJ o formulário restringe a Corretor Parceiro, Corretor (próprio) e Captador. Corretor = corretor próprio. Parceira externa: gravado como Corretor Parceiro.",
        ),
        _z(
            key="escolaridade",
            label="Escolaridade",
            sec="Informações para contato",
            tipo="select",
            sf="Escolaridade__c",
            opcoes=ESCOLARIDADE_OPTS,
            req=False,
        ),
        _z(
            key="data_entrevista",
            label="Data da Entrevista",
            sec="Informações para contato",
            tipo="date",
            sf="Data_da_Entrevista__c",
            req=False,
            help="Definida automaticamente na data do envio.",
        ),
        # ——— Dados Pessoais ———
        _z(
            key="birthdate",
            label="Data de nascimento *",
            sec="Dados Pessoais",
            tipo="date",
            sf="Birthdate",
            req=True,
            help="Formato: 31/12/2024",
        ),
        _z(
            key="estado_civil",
            label="Estado Civil *",
            sec="Dados Pessoais",
            tipo="select",
            sf="EstadoCivil__c",
            opcoes=ESTADO_CIVIL_OPTS,
            req=True,
        ),
        _z(key="cpf", label="CPF *", sec="Dados Pessoais", tipo="text", sf="CPF__c", req=True),
        _z(key="pis", label="PIS", sec="Dados Pessoais", tipo="text", sf="PIS__c", req=False),
        _z(
            key="nacionalidade",
            label="Nacionalidade *",
            sec="Dados Pessoais",
            tipo="select",
            sf="Nacionalidade__c",
            opcoes=NACIONALIDADE_OPTS,
            req=True,
        ),
        _z(
            key="naturalidade",
            label="Naturalidade *",
            sec="Dados Pessoais",
            tipo="text",
            sf="Naturalidade__c",
            req=True,
        ),
        _z(key="rg", label="RG *", sec="Dados Pessoais", tipo="text", sf="RG__c", req=True),
        _z(
            key="uf_naturalidade",
            label="UF Naturalidade *",
            sec="Dados Pessoais",
            tipo="select",
            sf="UF_Naturalidade__c",
            opcoes=ESTADOS_UF,
            req=True,
        ),
        _z(
            key="uf_rg",
            label="UF RG *",
            sec="Dados Pessoais",
            tipo="select",
            sf="UF_RG__c",
            opcoes=ESTADOS_UF,
            req=True,
        ),
        _z(
            key="tipo_pix",
            label="Tipo do PIX *",
            sec="Dados Pessoais",
            tipo="select",
            sf="Tipo_do_PIX__c",
            opcoes=TIPO_PIX,
            req=True,
        ),
        _z(
            key="dados_pix",
            label="Dados para PIX *",
            sec="Dados Pessoais",
            tipo="text",
            sf="Dados_para_PIX__c",
            req=True,
        ),
        # ——— Dados de Usuário ———
        _z(
            key="multiplicador_nivel",
            label="Multiplicador de Nível",
            sec="Dados de Usuário",
            tipo="number",
            sf="Multiplicador__c",
            req=False,
        ),
        _z(
            key="usuario_uau",
            label="Usuário UAU",
            sec="Dados de Usuário",
            tipo="text",
            sf="Usu_rio_UAU__c",
            req=False,
        ),
        _z(
            key="multiplicador_regime",
            label="Multiplicador de Regime",
            sec="Dados de Usuário",
            tipo="number",
            sf="Multiplicador_de_Regime__c",
            req=False,
        ),
        # ——— Dados para Contato ———
        _z(key="phone", label="Telefone", sec="Dados para Contato", tipo="text", sf="Phone", req=False),
        _z(key="mobile", label="Celular *", sec="Dados para Contato", tipo="text", sf="MobilePhone", req=True),
        _z(key="email", label="E-mail *", sec="Dados para Contato", tipo="text", sf="Email", req=True),
        # ——— Dados Familiares ———
        _z(
            key="nome_pai",
            label="Nome do Pai *",
            sec="Dados Familiares",
            tipo="text",
            sf="Nome_do_Pai__c",
            req=True,
        ),
        _z(
            key="possui_filhos",
            label="Possui Filho(s)?",
            sec="Dados Familiares",
            tipo="select",
            sf="Possui_Filho__c",
            opcoes=POSSUI_FILHOS,
            req=False,
        ),
        _z(
            key="nome_mae",
            label="Nome da Mãe *",
            sec="Dados Familiares",
            tipo="text",
            sf="Nome_da_Mae__c",
            req=True,
        ),
        _z(
            key="qtd_filhos",
            label="Quantidade de Filhos",
            sec="Dados Familiares",
            tipo="number",
            sf="Quantidade_de_Filhos__c",
            req=False,
        ),
        _z(
            key="nome_conjuge",
            label="Nome do Cônjuge",
            sec="Dados Familiares",
            tipo="text",
            sf="Nome_do_Conjuge__c",
            req=False,
        ),
        # ——— Dados Bancários Pessoa Física ———
        _z(
            key="banco",
            label="Banco *",
            sec="Dados Bancários Pessoa Física",
            tipo="select",
            sf="Banco__c",
            opcoes=BANCO_OPTS,
            req=True,
        ),
        _z(
            key="conta_bancaria",
            label="Conta Bancária *",
            sec="Dados Bancários Pessoa Física",
            tipo="text",
            sf="Conta_Banc_ria__c",
            req=True,
        ),
        _z(
            key="agencia_bancaria",
            label="Agência Bancária *",
            sec="Dados Bancários Pessoa Física",
            tipo="text",
            sf="Ag_ncia_Banc_ria__c",
            req=True,
        ),
        _z(
            key="retorno_integracao_bancaria",
            label="Retorno integração conta bancária",
            sec="Dados Bancários Pessoa Física",
            tipo="textarea",
            sf="RetornoIntegracaoContaBancaria__c",
            req=False,
            help="Somente leitura no Salesforce — uso informativo na planilha.",
        ),
        _z(
            key="tipo_conta",
            label="Tipo de Conta",
            sec="Dados Bancários Pessoa Física",
            tipo="select",
            sf="Tipo_de_Conta__c",
            opcoes=TIPO_CONTA_BANCARIA,
            req=False,
        ),
        # ——— CRECI/TTI ———
        _z(
            key="possui_creci",
            label="Possui CRECI? *",
            sec="CRECI/TTI",
            tipo="select",
            sf=None,
            opcoes=["Sim", "Não"],
            req=True,
            help="Se sim, os campos de CRECI aparecem abaixo. Se não, avance para a próxima etapa.",
        ),
        _z(
            key="data_matricula_tti",
            label="Data Matrícula - TTI",
            sec="CRECI/TTI",
            tipo="date",
            sf="Data_Matricula_TTI__c",
            req=False,
            help="Formato: 31/12/2024",
        ),
        _z(key="tti", label="TTI", sec="CRECI/TTI", tipo="text", sf="TTI__c", req=False),
        _z(
            key="status_creci",
            label="Status CRECI",
            sec="CRECI/TTI",
            tipo="select",
            sf="Status_CRECI__c",
            opcoes=STATUS_CRECI_OPTS,
            req=False,
        ),
        _z(
            key="data_conclusao",
            label="Data de conclusão",
            sec="CRECI/TTI",
            tipo="date",
            sf="Data_de_conclusao__c",
            req=False,
            help="Formato: 31/12/2024",
        ),
        _z(key="creci", label="CRECI", sec="CRECI/TTI", tipo="text", sf="CRECI__c", req=False),
        _z(
            key="observacoes_creci",
            label="Observações",
            sec="CRECI/TTI",
            tipo="textarea",
            sf="Observacoes__c",
            req=False,
        ),
        _z(
            key="validade_creci",
            label="Validade CRECI",
            sec="CRECI/TTI",
            tipo="date",
            sf="Validade_CRECI__c",
            req=False,
            help="Formato: 31/12/2024",
        ),
        _z(
            key="nome_responsavel",
            label="Nome do Responsável",
            sec="CRECI/TTI",
            tipo="text",
            sf="Nome_do_Responsavel__c",
            req=False,
        ),
        _z(
            key="creci_responsavel",
            label="CRECI do Responsável",
            sec="CRECI/TTI",
            tipo="number",
            sf="CRECI_do_Responsavel__c",
            req=False,
        ),
        _z(
            key="tipo_comissionamento",
            label="Tipo de Comissionamento",
            sec="CRECI/TTI",
            tipo="text",
            sf=None,
            req=False,
        ),
        # ——— Dados Integração (campos ocultos: tipo/datas preenchidos pelo enriquecedor Vendas RJ) ———
        _z(
            key="tipo_corretor",
            label="Tipo Corretor *",
            sec="Dados Integração",
            tipo="select",
            sf="Tipo_Corretor__c",
            opcoes=TIPO_CORRETOR_OPTS,
            req=False,
        ),
        _z(
            key="data_contrato",
            label="Data Contrato",
            sec="Dados Integração",
            tipo="date",
            sf="Data_Contrato__c",
            req=False,
            help="Definida automaticamente na data do envio.",
        ),
        _z(
            key="data_credenciamento",
            label="Data Credenciamento",
            sec="Dados Integração",
            tipo="date",
            sf="Data_Credenciamento__c",
            req=False,
            help="Definida automaticamente na data do envio.",
        ),
        # ——— Dados Integração ———
        _z(
            key="codigo_pessoa_uau",
            label="Código Pessoa UAU",
            sec="Dados Integração",
            tipo="text",
            sf="C_digo_Pessoa_UAU__c",
            req=False,
        ),
        _z(
            key="erro_integracao_uau",
            label="Erro Integração UAU",
            sec="Dados Integração",
            tipo="textarea",
            sf="ErroIntegracaoUAU__c",
            req=False,
        ),
        _z(
            key="retorno_integracao_pessoa",
            label="Retorno Integração Pessoa",
            sec="Dados Integração",
            tipo="textarea",
            sf="RetornoIntegracaoPessoa__c",
            req=False,
        ),
        # ——— Preferência de contato ———
        _z(
            key="preferred_contact_method",
            label="Preferência de contato",
            sec="Preferência de contato",
            tipo="multiselect",
            sf="Preferred_Contact_Method__c",
            opcoes=PREFERRED_METHOD_OPTS,
            req=False,
        ),
    ]


CAMPOS: List[Campo] = _campos_def()

# Ocultos no Streamlit: integração/sistema (preenchidos por processos ou planilha) e
# valores fixos via Secrets → [ficha_defaults] (regional, origem, status, ids opcionais).
# tipo_corretor / multiplicadores / apelido / datas: enriquecer_derivados_vendas_rj.
CAMPOS_OCULTOS_FORMULARIO: frozenset[str] = frozenset(
    {
        "codigo_pessoa_uau",
        "erro_integracao_uau",
        "retorno_integracao_pessoa",
        "retorno_integracao_bancaria",
        "status_corretor",
        "regional",
        "origem",
        "account_id",
        "owner_id",
        "tipo_corretor",
        "apelido",
        "data_entrevista",
        "data_contrato",
        "data_credenciamento",
        "multiplicador_nivel",
        "multiplicador_regime",
    }
)

# Campos da seção CRECI/TTI exibidos só quando «Possui CRECI?» = Sim.
CAMPOS_CRECI_DETALHES: frozenset[str] = frozenset(
    {
        "data_matricula_tti",
        "tti",
        "status_creci",
        "data_conclusao",
        "creci",
        "observacoes_creci",
        "validade_creci",
        "nome_responsavel",
        "creci_responsavel",
        "tipo_comissionamento",
    }
)


def campos_por_secao_visiveis(
    sec: str, dados: Optional[Dict[str, Any]] = None
) -> List[Campo]:
    cols = [
        c
        for c in CAMPOS
        if c["sec"] == sec and c["key"] not in CAMPOS_OCULTOS_FORMULARIO
    ]
    if sec == "CRECI/TTI":
        d = dados or {}
        if (str(d.get("possui_creci") or "").strip()) != "Sim":
            cols = [c for c in cols if c["key"] == "possui_creci"]
    if sec == "Informações para contato":
        d = dados or {}
        if _norm_picklist(d.get("unidade_negocio")) == UNIDADE_REDE_OUTRA_IMOBILIARIA:
            cols = [c for c in cols if c["key"] != "atividade"]
    return cols


def secoes_com_campos_visiveis() -> List[str]:
    presentes = {
        c["sec"] for c in CAMPOS if c["key"] not in CAMPOS_OCULTOS_FORMULARIO
    }
    return [s for s in SEC_ORDER if s in presentes]


_ID_RE = re.compile(r"^[a-zA-Z0-9]{15}(?:[a-zA-Z0-9]{3})?$")


def _norm_picklist(val: Any) -> str:
    """Remove marcador '--Nenhum--' como vazio."""
    s = (str(val).strip() if val is not None else "") or ""
    if s in ("--Nenhum--", "Nenhum"):
        return ""
    return s


def parse_data_br(val: Any) -> Optional[str]:
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


def _erros_preenchimento_creci_se_sim(dados: Dict[str, Any]) -> List[str]:
    """Se «Possui CRECI?» = Sim, exige status, número e validade."""
    if (str(dados.get("possui_creci") or "").strip()) != "Sim":
        return []
    er: List[str] = []
    if not _norm_picklist(dados.get("status_creci")):
        er.append("Status CRECI *")
    if not (str(dados.get("creci") or "").strip()):
        er.append("CRECI *")
    if not (str(dados.get("validade_creci") or "").strip()):
        er.append("Validade CRECI *")
    return er


def _limpa_id(sf_field: str, val: Any) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    if sf_field in ("AccountId", "OwnerId", "GerenteAnterior__c", "Solicitantedescredenciamento__c"):
        if _ID_RE.match(s):
            return s
    if sf_field == "Produto_de_Atuacao__c" and _ID_RE.match(s):
        return s
    return None


def validar_obrigatorios(dados: Dict[str, Any]) -> List[str]:
    erros: List[str] = []
    for c in CAMPOS:
        if c["key"] in CAMPOS_OCULTOS_FORMULARIO:
            continue
        if c["key"] == "atividade" and _norm_picklist(
            dados.get("unidade_negocio")
        ) == UNIDADE_REDE_OUTRA_IMOBILIARIA:
            continue
        if not c.get("req"):
            continue
        k = c["key"]
        v = dados.get(k)
        if c["tipo"] == "multiselect":
            if not v or (isinstance(v, list) and len(v) == 0):
                erros.append(c["label"])
            continue
        if c["tipo"] == "select":
            if not _norm_picklist(v):
                erros.append(c["label"])
            continue
        if v is None or (isinstance(v, str) and not str(v).strip()):
            erros.append(c["label"])
    aid = (dados.get("account_id") or "").strip()
    aname = (dados.get("account_name") or "").strip()
    if not aid and not aname:
        erros.append(
            "Conta Salesforce: defina account_id em [ficha_defaults] nos Secrets "
            "(ou selecione Nome da conta)."
        )
    nc = (dados.get("nome_completo") or "").strip()
    if not nc:
        erros.append("Nome completo *")
    em = (dados.get("email") or "").strip()
    if em and not email_contato_formato_valido(em):
        erros.append("E-mail * (use um endereço válido, ex.: nome@empresa.com.br)")
    erros.extend(_erros_preenchimento_creci_se_sim(dados))
    return list(dict.fromkeys(erros))


def validar_obrigatorios_secao(sec: str, dados: Dict[str, Any]) -> List[str]:
    """
    Valida apenas campos obrigatórios da seção atual (para bloquear «Avançar» no formulário por etapas).
    Replica a lógica de `validar_obrigatorios` para `c['sec'] == sec` e, na seção
    «Informações para contato», as regras de conta + nome/sobrenome.
    """
    erros: List[str] = []
    for c in CAMPOS:
        if c["key"] in CAMPOS_OCULTOS_FORMULARIO:
            continue
        if (
            c["key"] == "atividade"
            and sec == "Informações para contato"
            and _norm_picklist(dados.get("unidade_negocio"))
            == UNIDADE_REDE_OUTRA_IMOBILIARIA
        ):
            continue
        if c["sec"] != sec or not c.get("req"):
            continue
        k = c["key"]
        v = dados.get(k)
        if c["tipo"] == "multiselect":
            if not v or (isinstance(v, list) and len(v) == 0):
                erros.append(c["label"])
            continue
        if c["tipo"] == "select":
            if not _norm_picklist(v):
                erros.append(c["label"])
            continue
        if v is None or (isinstance(v, str) and not str(v).strip()):
            erros.append(c["label"])
    if sec == "Informações para contato":
        aid = (dados.get("account_id") or "").strip()
        aname = (dados.get("account_name") or "").strip()
        if not aid and not aname:
            erros.append(
                "Conta Salesforce: defina account_id em [ficha_defaults] nos Secrets "
                "(ou selecione Nome da conta)."
            )
        nc = (dados.get("nome_completo") or "").strip()
        if not nc:
            erros.append("Nome completo *")
    if sec == "Dados para Contato":
        em = (dados.get("email") or "").strip()
        if em and not email_contato_formato_valido(em):
            erros.append("E-mail * (use um endereço válido, ex.: nome@empresa.com.br)")
    if sec == "CRECI/TTI":
        erros.extend(_erros_preenchimento_creci_se_sim(dados))
    return list(dict.fromkeys(erros))


def _aplicar_nome_completo(payload: Dict[str, Any], dados: Dict[str, Any]) -> None:
    """Primeira palavra → FirstName; restante → LastName (sem campos separados no formulário)."""
    nc = (dados.get("nome_completo") or "").strip()
    if not nc:
        return
    partes = nc.split(None, 1)
    payload["FirstName"] = partes[0][:40]
    payload["LastName"] = (partes[1] if len(partes) > 1 else partes[0])[:80]


def montar_payload_salesforce(dados: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    payload: Dict[str, Any] = {}
    rt, rt_aviso = record_type_id_contato_payload_e_aviso()
    if rt:
        payload["RecordTypeId"] = rt
    avisos: List[str] = []
    if rt_aviso:
        avisos.append(rt_aviso)
    extras_obs: List[str] = []

    for c in CAMPOS:
        key = c["key"]
        sf = c.get("sf")
        raw = dados.get(key)

        if key == "nome_completo":
            continue

        if sf is None:
            if raw and str(raw).strip() and key not in ("nome_completo",):
                extras_obs.append(f"{c['label']}: {raw}")
            continue

        if sf in SF_OMIT_INSERT:
            if raw and str(raw).strip():
                extras_obs.append(f"{c['label']}: {raw}")
            continue

        tipo = c["tipo"]

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

        if tipo == "select":
            s = _norm_picklist(raw)
            if key == "unidade_negocio":
                smap = {
                    "Direcional": "Direcional",
                    "Riva": "Direcional",
                    UNIDADE_REDE_OUTRA_IMOBILIARIA: "Parceiros (Externo)",
                }
                s2 = smap.get(s)
                if s2:
                    payload[sf] = s2
                elif s:
                    payload[sf] = s
                if s == "Riva":
                    extras_obs.append("Rede de atuação informada: Riva")
                continue
            if key == "origem" and s == "Indicação":
                # Compatibilidade com orgs que não possuem "Indicação" na picklist restrita.
                s = "RH"
            if s:
                payload[sf] = s
            continue

        s = (str(raw).strip() if raw is not None else "") or ""
        if not s:
            continue
        payload[sf] = s

    _aplicar_nome_completo(payload, dados)

    acc = dados.get("account_id")
    acc_txt = dados.get("account_name")
    if (not acc or not str(acc).strip()) and acc_txt and str(acc_txt).strip():
        extras_obs.append(f"Nome da conta (referência): {acc_txt}")

    obs_final = (payload.get("Observacoes__c") or "").strip()
    extra_block = "\n".join(extras_obs)
    if extra_block:
        payload["Observacoes__c"] = (obs_final + "\n" + extra_block).strip() if obs_final else extra_block

    payload = {k: v for k, v in payload.items() if v is not None and v != ""}

    return payload, avisos


def enriquecer_derivados_vendas_rj(dados: Dict[str, Any]) -> Dict[str, Any]:
    """
    Regras Vendas RJ: rede (Direcional/Riva/parceira) → tipo de corretor e Unidade SF;
    parceira → Atividade Corretor Parceiro e Origem RH; função → multiplicadores;
    apelido e datas automáticos.
    """
    out = dict(dados)
    rede = _norm_picklist(out.get("unidade_negocio"))

    if rede == UNIDADE_REDE_OUTRA_IMOBILIARIA:
        out["atividade"] = "Corretor Parceiro"
        out["origem"] = "RH"
    else:
        act = _norm_picklist(out.get("atividade"))
        out["atividade"] = act if act else "Corretor"

    if rede in ("Direcional", "Riva"):
        out["tipo_corretor"] = "Direcional Vendas – Autônomos"
    elif rede:
        out["tipo_corretor"] = "Parceiros (Externo)"
    else:
        out["tipo_corretor"] = ""

    act_final = out.get("atividade") or ""
    if act_final == "Captador":
        out["multiplicador_nivel"] = 0.9
        out["multiplicador_regime"] = 1.0
    elif act_final in ("Corretor", "Corretor Parceiro"):
        out["multiplicador_nivel"] = 1.0
        out["multiplicador_regime"] = 1.0
    else:
        out["multiplicador_nivel"] = 1.0
        out["multiplicador_regime"] = 1.0

    nc = (out.get("nome_completo") or "").strip()
    primeiro = nc.split(None, 1)[0] if nc else ""
    out["apelido"] = f"{primeiro}_RJ01" if primeiro else ""
    hoje = date.today().strftime("%d/%m/%Y")
    out["data_entrevista"] = hoje
    out["data_contrato"] = hoje
    out["data_credenciamento"] = hoje
    if (str(out.get("possui_creci") or "").strip()) != "Sim":
        for k in CAMPOS_CRECI_DETALHES:
            out[k] = ""
    return out


def _agora_envio_brasilia() -> tuple[str, str]:
    """Data/hora legível em Brasília e ISO (mesmo instante)."""
    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("America/Sao_Paulo")
        now = datetime.now(tz)
        return now.strftime("%d/%m/%Y %H:%M:%S"), now.isoformat(timespec="seconds")
    except Exception:
        now = datetime.now(timezone.utc)
        return now.strftime("%d/%m/%Y %H:%M:%S"), now.isoformat(timespec="seconds")


def linha_planilha(dados: Dict[str, Any]) -> List[str]:
    data_hora_br, iso = _agora_envio_brasilia()
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
    row.append(data_hora_br)
    row.append(iso)
    row.append("")  # Envio? — preenchido após tentativa Salesforce
    row.append("")  # Log / erro
    row.append("")  # Link do contato
    return row


def cabecalho_planilha() -> List[str]:
    return [c["label"] for c in CAMPOS] + [
        "Data e hora do envio",
        "Carimbo ISO",
        "Envio?",
        "Log / erro",
        "Link do contato",
    ]


def _norm_cabecalho_planilha(s: str) -> str:
    """Normaliza texto de cabeçalho para casar com colunas da planilha."""
    return " ".join((s or "").strip().split()).casefold()


def _strip_valor_celula_planilha(val: Any) -> str:
    """Remove espaços invisíveis (NBSP etc.) e bordas — comum em cópias do Excel/Sheets."""
    if val is None:
        return ""
    s = str(val).replace("\u00a0", " ").replace("\u2007", " ").replace("\u202f", " ")
    return s.strip()


def _indice_coluna_planilha_para_campo(
    hmap: Dict[str, int], headers: List[str], label_campo: str
) -> Optional[int]:
    """
    Índice da coluna cujo cabeçalho casa com o rótulo do campo.
    Aceita cabeçalho com ou sem o sufixo « *» usado nos rótulos obrigatórios do app.
    """
    lab = (label_campo or "").strip()
    candidatos: List[str] = []
    candidatos.append(_norm_cabecalho_planilha(lab))
    if lab.endswith(" *"):
        candidatos.append(_norm_cabecalho_planilha(lab[:-2].strip()))
    for cand in candidatos:
        if cand in hmap:
            return hmap[cand]
    for i, h in enumerate(headers):
        hs = (h or "").strip()
        if not hs:
            continue
        if hs == lab:
            return i
        if lab.endswith(" *") and hs == lab[:-2].strip():
            return i
        if _norm_cabecalho_planilha(hs) in candidatos:
            return i
    return None


def dados_dict_de_linha_planilha(headers: List[str], cells: List[str]) -> Dict[str, Any]:
    """
    Converte uma linha da aba Corretores (valores alinhados aos cabeçalhos) em dict de chaves do formulário.
    Cabeçalhos devem corresponder aos rótulos em CAMPOS (como em `cabecalho_planilha`).
    """
    hmap: Dict[str, int] = {}
    for i, h in enumerate(headers):
        key = _norm_cabecalho_planilha(h)
        if key and key not in hmap:
            hmap[key] = i
    # Garante células alinhadas ao número de colunas do cabeçalho
    if len(cells) < len(headers):
        cells = list(cells) + [""] * (len(headers) - len(cells))
    dados: Dict[str, Any] = {}
    for c in CAMPOS:
        idx = _indice_coluna_planilha_para_campo(hmap, headers, c["label"])
        raw = ""
        if idx is not None and idx < len(cells):
            raw = _strip_valor_celula_planilha(cells[idx])
        tipo = c["tipo"]
        if tipo == "multiselect":
            if not raw:
                dados[c["key"]] = []
            else:
                partes = [
                    _strip_valor_celula_planilha(p)
                    for p in re.split(r"[;\n]", raw)
                    if _strip_valor_celula_planilha(p)
                ]
                dados[c["key"]] = partes
        elif tipo == "number":
            if not raw:
                dados[c["key"]] = None
            else:
                try:
                    dados[c["key"]] = float(raw.replace(",", "."))
                except ValueError:
                    dados[c["key"]] = None
        elif tipo == "checkbox":
            v = raw.lower()
            dados[c["key"]] = v in ("true", "1", "sim", "yes", "verdadeiro", "x")
        else:
            dados[c["key"]] = raw or ""
    return dados


def ler_planilha_corretores_bruta(
    creds_dict: Dict[str, Any],
    spreadsheet_id: str,
    worksheet_name: str,
) -> Tuple[List[str], List[List[str]]]:
    """Cabeçalho (linha 1) e linhas de dados seguintes (ignora linhas totalmente vazias)."""
    gc = _cliente_gspread(creds_dict)
    sh = gc.open_by_key(spreadsheet_id)
    ws = sh.worksheet(worksheet_name)
    all_v = ws.get_all_values()
    if not all_v:
        return [], []
    headers = list(all_v[0])
    rows: List[List[str]] = []
    for r in all_v[1:]:
        if any((c or "").strip() for c in r):
            rows.append(list(r))
    return headers, rows


def _preview_linha_planilha(headers: List[str], cells: List[str]) -> str:
    d = dados_dict_de_linha_planilha(headers, cells)
    nome = (d.get("nome_completo") or "").strip()[:36]
    em = (d.get("email") or "").strip()[:32]
    partes = [p for p in (nome, em) if p]
    return " · ".join(partes) if partes else "(sem nome/e-mail visível)"


def _teste_planilha_sf_habilitado() -> bool:
    """Controlado pela constante `FICHA_TEST_PLANILHA_ATIVO` (bloco «Modo teste» junto aos IDs da planilha)."""
    return bool(FICHA_TEST_PLANILHA_ATIVO)


def _aplicar_dados_teste_ao_session_state(dados: Dict[str, Any]) -> None:
    """Grava valores no session_state e no snapshot para todas as etapas enxergarem os dados."""
    ss = st.session_state
    snap = dict(ss.get("ficha_snap_campos") or {})
    for c in CAMPOS:
        k = c["key"]
        if k not in dados:
            continue
        ss[f"fld_{k}"] = dados[k]
        snap[k] = dados[k]
    ss["ficha_snap_campos"] = snap


def _executar_teste_criar_sf_de_linha_planilha(
    *,
    row_1based_sheet: int,
    headers: List[str],
    cells: List[str],
    atualizar_status_nesta_linha: bool,
    anexar_nova_linha_duplicada: bool,
    enviar_email_boas_vindas: bool,
) -> Tuple[bool, str]:
    """
    Monta payload a partir da linha da planilha, cria contato no Salesforce.
    Retorna (ok, mensagem_html_ou_texto).
    """
    creds = _credenciais_de_secrets(st.secrets if hasattr(st, "secrets") else None)
    if not creds:
        return False, "Configure **[google_sheets]** nos Secrets (SERVICE_ACCOUNT_JSON)."

    gs: Dict[str, Any] = {}
    if hasattr(st, "secrets"):
        try:
            gs = dict(st.secrets.get("google_sheets", {}))
        except Exception:
            gs = {}
    sid, wname = _ids_planilha_modo_teste(gs)

    dados = dados_dict_de_linha_planilha(headers, cells)
    dados = enriquecer_derivados_vendas_rj(dados)
    erros = validar_obrigatorios(dados)
    if erros:
        lista = "<br>".join(f"• {html.escape(e)}" for e in erros)
        return False, f"<strong>Validação:</strong><br>{lista}"

    _aplicar_secrets_sf()
    if not _credenciais_salesforce_ok():
        return False, "Salesforce não configurado (Secrets / variáveis USER, PASSWORD, TOKEN)."
    if not _SF_SDK_DISPONIVEL:
        return False, "Pacote **simple_salesforce** não instalado."

    payload, avisos = montar_payload_salesforce(dados)
    avisos = list(avisos)
    avisos.extend(_enriquecer_mobile_phone(payload, dados))

    row_num_atualizar = row_1based_sheet

    if anexar_nova_linha_duplicada:
        try:
            linha = linha_planilha(dados)
            cab = cabecalho_planilha()
            row_num_atualizar = anexar_linha(linha, cab, sid, wname, creds)
        except Exception as e:
            return False, f"Erro ao anexar linha na planilha: {html.escape(str(e))}"

    sf = conectar_salesforce()
    if not sf:
        if atualizar_status_nesta_linha and row_num_atualizar >= 2:
            try:
                atualizar_status_envio_salesforce(
                    sid, wname, creds, row_num_atualizar, "Erro",
                    "Falha ao conectar ao Salesforce.", "",
                )
            except Exception:
                pass
        return False, "Falha ao conectar ao Salesforce (credenciais ou rede)."

    cid, err = criar_contato_payload(sf, payload)
    link = _url_contact(cid) if cid else ""

    if atualizar_status_nesta_linha and row_num_atualizar >= 2:
        try:
            if cid:
                atualizar_status_envio_salesforce(sid, wname, creds, row_num_atualizar, "Sucesso", "", link)
            else:
                atualizar_status_envio_salesforce(
                    sid,
                    wname,
                    creds,
                    row_num_atualizar,
                    "Erro",
                    (_explicacao_erro_record_type_se_aplicavel(err))[:49000]
                    if err
                    else "Erro desconhecido",
                    "",
                )
        except Exception as ex:
            avisos.append(f"Planilha (status): {ex}")

    if enviar_email_boas_vindas:
        try:
            _tentar_enviar_email_boas_vindas(dados, cid if cid else None)
        except Exception as ex:
            avisos.append(f"E-mail: {ex}")

    av_txt = ""
    if avisos:
        av_txt = "<br><strong>Avisos:</strong><br>" + "<br>".join(f"• {html.escape(str(a))}" for a in avisos)

    if cid:
        url_esc = html.escape(link)
        return True, (
            f"<strong>Contato criado.</strong> Id: <code>{html.escape(str(cid))}</code><br>"
            f'<a href="{url_esc}" target="_blank" rel="noopener">Abrir no Salesforce</a>'
            f"{av_txt}"
        )
    err_txt = _explicacao_erro_record_type_se_aplicavel(err) if err else "desconhecido"
    return False, f"<strong>Erro Salesforce:</strong> {_html_erro_salesforce_multilinha(err_txt)}{av_txt}"


def _render_sidebar_teste_planilha_sf() -> None:
    """Painel na sidebar: escolher linha da planilha e testar criação no SF (sem preencher o formulário manualmente)."""
    with st.sidebar:
        st.markdown("##### Teste rápido — planilha → Salesforce")
        st.caption(
            "Lê a planilha definida em **FICHA_TEST_PLANILHA_SPREADSHEET_ID** / "
            "**FICHA_TEST_PLANILHA_WORKSHEET_NAME** (se vazios, usa Secrets). **Não** exige LGPD. "
            "Em produção: **FICHA_TEST_PLANILHA_ATIVO = False**."
        )
        if st.button("Carregar linhas da planilha", key="test_pl_carregar"):
            creds = _credenciais_de_secrets(st.secrets if hasattr(st, "secrets") else None)
            if not creds:
                st.error("Secrets **google_sheets** ausente ou JSON inválido.")
            else:
                gs: Dict[str, Any] = {}
                if hasattr(st, "secrets"):
                    try:
                        gs = dict(st.secrets.get("google_sheets", {}))
                    except Exception:
                        gs = {}
                sid, wname = _ids_planilha_modo_teste(gs)
                try:
                    h, rows = ler_planilha_corretores_bruta(creds, sid, wname)
                    st.session_state["test_pl_headers"] = h
                    st.session_state["test_pl_rows"] = rows
                    st.success(f"{len(rows)} linha(s) com dados (cabeçalho: {len(h)} colunas).")
                except Exception as e:
                    st.error(f"Falha ao ler a planilha: {e}")

        headers = list(st.session_state.get("test_pl_headers") or [])
        rows = list(st.session_state.get("test_pl_rows") or [])
        if not rows or not headers:
            st.info(
                "Clique em **Carregar linhas da planilha**. A aba vem das constantes de teste ou de **WORKSHEET_NAME** nos Secrets."
            )
            return

        labels = [
            f"Linha {i + 2} — {_preview_linha_planilha(headers, rows[i])}"
            for i in range(len(rows))
        ]
        opts_idx = list(range(len(labels)))
        escolha = st.selectbox(
            "Linha da planilha (linha 2 = primeira de dados)",
            opts_idx,
            format_func=lambda i: labels[i],
            key="test_pl_select_idx",
        )
        idx = int(escolha) if escolha is not None else 0
        row_1based = idx + 2

        atualizar = st.checkbox(
            "Atualizar **Envio?**, **Log / erro** e **Link do contato** na planilha "
            "(na linha escolhida; se duplicar abaixo, na **linha nova**)",
            value=True,
            key="test_pl_atualizar_status",
        )
        duplicar = st.checkbox(
            "Antes do SF, **anexar** cópia da linha no fim da aba (mantém a linha original intacta)",
            value=False,
            key="test_pl_duplicar_linha",
        )
        mail_test = st.checkbox("Disparar também **e-mail de boas-vindas** (mais lento)", value=False, key="test_pl_mail")

        if st.button("Carregar esta linha no formulário", key="test_pl_aplicar_form"):
            cells = rows[idx]
            dados = enriquecer_derivados_vendas_rj(dados_dict_de_linha_planilha(headers, cells))
            _aplicar_dados_teste_ao_session_state(dados)
            st.session_state["ficha_secao_idx"] = 0
            st.success("Formulário preenchido a partir da planilha. Revise as etapas e envie se quiser.")
            st.rerun()

        if st.button("Criar contato no Salesforce (teste)", type="primary", key="test_pl_criar_sf"):
            cells = rows[idx]
            ok, msg = _executar_teste_criar_sf_de_linha_planilha(
                row_1based_sheet=row_1based,
                headers=headers,
                cells=cells,
                atualizar_status_nesta_linha=atualizar,
                anexar_nova_linha_duplicada=duplicar,
                enviar_email_boas_vindas=mail_test,
            )
            if ok:
                st.markdown(
                    f'<div class="ficha-alert ficha-alert--azul">{msg}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="ficha-alert ficha-alert--vermelho">{msg}</div>',
                    unsafe_allow_html=True,
                )


def secoes_ordenadas() -> List[str]:
    presentes = {c["sec"] for c in CAMPOS}
    return [s for s in SEC_ORDER if s in presentes]


def campos_por_secao(sec: str) -> List[Campo]:
    return [c for c in CAMPOS if c["sec"] == sec]

# =============================================================================
# INTEGRADO: google_sheets_corretor
# =============================================================================
_PEM_END_MARKERS = (
    "-----END PRIVATE KEY-----",
    "-----END RSA PRIVATE KEY-----",
    "-----END ENCRYPTED PRIVATE KEY-----",
)


def _reparar_private_key_json_com_quebras_literais(s: str) -> str:
    """
    Muitos ambientes colam o JSON com a chave PEM em várias linhas reais dentro da string,
    o que quebra `json.loads`. Reescape o valor de private_key como uma única string JSON.
    """
    k = s.find('"private_key"')
    if k == -1:
        k = s.find("'private_key'")
    if k == -1:
        return s
    colon = s.find(":", k)
    if colon == -1:
        return s
    q_open = s.find('"', colon)
    if q_open == -1:
        return s
    val_start = q_open + 1
    rest = s[val_start:]
    end_pem = -1
    for mark in _PEM_END_MARKERS:
        p = rest.find(mark)
        if p != -1:
            end_pem = p + len(mark)
            break
    if end_pem == -1:
        return s
    pem = rest[:end_pem]
    after = rest[end_pem:]
    i = 0
    while i < len(after) and after[i] in " \t\r\n":
        i += 1
    if i >= len(after) or after[i] != '"':
        return s
    tail = after[i + 1 :]
    inner_esc = json.dumps(pem)[1:-1]
    return s[:val_start] + inner_esc + '"' + tail


def _parse_json_conta_servico_google(s: str) -> Optional[Dict[str, Any]]:
    """Tenta json.loads; se falhar, repara private_key e tenta de novo."""
    s = s.strip().lstrip("\ufeff")
    if not s:
        return None
    candidates = (s, _reparar_private_key_json_com_quebras_literais(s))
    seen: set[str] = set()
    for cand in candidates:
        if cand in seen:
            continue
        seen.add(cand)
        try:
            parsed = json.loads(cand)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        if isinstance(parsed, dict):
            return parsed
    return None

# ID padrão da planilha informada pelo usuário
DEFAULT_SPREADSHEET_ID = "1_9x4rfHoP2M47qXJENoD3vMLf_7rWUhNjrU8EtESxy8"
DEFAULT_WORKSHEET_NAME = "Corretores"
# Aba com a lista de nomes de conta para o formulário (coluna de cabeçalho na linha 1)
DEFAULT_GERENTES_WORKSHEET = "Gerentes"
DEFAULT_COL_NOME_CONTA = "Nome da Conta"

# --- Modo teste (sidebar): linha da planilha → criar contato no Salesforce ---
# Altere aqui no código; deixe ATIVO = False em produção.
FICHA_TEST_PLANILHA_ATIVO = False
# Se não vazio, o painel de teste lê esta planilha/aba (ignora SPREADSHEET_ID/WORKSHEET_NAME dos Secrets).
FICHA_TEST_PLANILHA_SPREADSHEET_ID = ""
FICHA_TEST_PLANILHA_WORKSHEET_NAME = ""


def _ids_planilha_modo_teste(gs: Dict[str, Any]) -> Tuple[str, str]:
    """ID e aba usados pelo teste rápido: constantes acima, senão Secrets / DEFAULT_*."""
    fix_id = (FICHA_TEST_PLANILHA_SPREADSHEET_ID or "").strip()
    if fix_id:
        wn = (FICHA_TEST_PLANILHA_WORKSHEET_NAME or "").strip() or DEFAULT_WORKSHEET_NAME
        return fix_id, wn
    return str(gs.get("SPREADSHEET_ID", DEFAULT_SPREADSHEET_ID)), str(
        gs.get("WORKSHEET_NAME", DEFAULT_WORKSHEET_NAME)
    )


def _credenciais_de_secrets(st_secrets: Any) -> Optional[Dict[str, Any]]:
    """Lê JSON da conta de serviço a partir de st.secrets['google_sheets']. Nunca propaga exceção."""
    try:
        if st_secrets is None:
            return None
        gs = (
            st_secrets.get("google_sheets")
            if hasattr(st_secrets, "get")
            else st_secrets["google_sheets"]
        )
    except (KeyError, TypeError, AttributeError):
        return None
    try:
        if not gs:
            return None
        raw = gs.get("SERVICE_ACCOUNT_JSON") or gs.get("service_account_json")
        if not raw:
            return None
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            return _parse_json_conta_servico_google(raw)
        return None
    except Exception:
        return None


def _cliente_gspread(creds_dict: Dict[str, Any]):
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)


def _col_letter(n: int) -> str:
    """Converte índice de coluna 1-based para letra(s) A, B, ..., Z, AA."""
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def anexar_linha(
    linha: List[str],
    cabecalho: List[str],
    spreadsheet_id: str,
    worksheet_name: str,
    creds_dict: Dict[str, Any],
) -> int:
    """
    Garante que a aba existe, cabeçalho na linha 1 (se vazia) e anexa a linha.
    """
    gc = _cliente_gspread(creds_dict)
    sh = gc.open_by_key(spreadsheet_id)
    try:
        ws = sh.worksheet(worksheet_name)
    except Exception:
        ws = sh.add_worksheet(title=worksheet_name, rows=1000, cols=max(len(cabecalho), 30))

    existing = ws.get_all_values()
    if not existing or not any(cell.strip() for cell in existing[0]):
        ws.update("A1", [cabecalho], value_input_option="USER_ENTERED")
    elif len(existing[0]) < len(cabecalho):
        # Cabeçalho existente mais curto — preenche células faltantes (linha 1)
        pad = existing[0] + [""] * (len(cabecalho) - len(existing[0]))
        for i, h in enumerate(cabecalho):
            if i >= len(pad) or not (pad[i] or "").strip():
                pad[i] = h
        ws.update("A1", [pad[: len(cabecalho)]], value_input_option="USER_ENTERED")

    ws.append_row(linha, value_input_option="USER_ENTERED")
    return len(ws.get_all_values())


def atualizar_status_envio_salesforce(
    spreadsheet_id: str,
    worksheet_name: str,
    creds_dict: Dict[str, Any],
    row_1based: int,
    envio: str,
    log_erro: str,
    link: str,
) -> None:
    """
    Preenche na linha indicada as colunas **Envio?**, **Log / erro** e **Link do contato**
    (cabeçalhos definidos em corretor_campos.cabecalho_planilha).
    """
    gc = _cliente_gspread(creds_dict)
    sh = gc.open_by_key(spreadsheet_id)
    ws = sh.worksheet(worksheet_name)
    headers = ws.row_values(1)
    mapping = {
        "Envio?": envio,
        "Log / erro": (log_erro or "")[:49000],
        "Link do contato": link or "",
    }
    for h, val in mapping.items():
        if h not in headers:
            continue
        col = headers.index(h) + 1
        cell = f"{_col_letter(col)}{row_1based}"
        ws.update(cell, [[val]], value_input_option="USER_ENTERED")


def listar_nomes_conta_aba_gerentes(
    spreadsheet_id: str,
    creds_dict: Dict[str, Any],
    worksheet_name: str = DEFAULT_GERENTES_WORKSHEET,
    column_header: str = DEFAULT_COL_NOME_CONTA,
) -> List[str]:
    """
    Lê a planilha indicada, aba `worksheet_name`, e devolve valores únicos e não vazios
    da coluna cujo cabeçalho (linha 1) coincide com `column_header` (ignora maiúsculas/minúsculas e espaços).
    """
    gc = _cliente_gspread(creds_dict)
    sh = gc.open_by_key(spreadsheet_id)
    ws = sh.worksheet(worksheet_name)
    rows = ws.get_all_values()
    if not rows:
        return []
    headers = [str(h or "").strip() for h in rows[0]]
    target = (column_header or "").strip().lower()
    col_idx = None
    for i, h in enumerate(headers):
        if h.strip().lower() == target:
            col_idx = i
            break
    if col_idx is None:
        return []
    seen: set[str] = set()
    out: List[str] = []
    for r in rows[1:]:
        if col_idx >= len(r):
            continue
        v = str(r[col_idx] or "").strip()
        if not v or v in seen:
            continue
        seen.add(v)
        out.append(v)
    out.sort(key=lambda s: s.casefold())
    return out


def carimbo_brasilia_iso() -> str:
    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("America/Sao_Paulo")
        return datetime.now(tz).isoformat(timespec="seconds")
    except Exception:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

# =============================================================================
# INTEGRADO: ficha_seguranca
# =============================================================================
_RL_JANELA_S = int(os.environ.get("FICHA_RL_JANELA_S", "600"))  # 10 min
_RL_MAX_JANELA = int(os.environ.get("FICHA_RL_MAX_JANELA", "4"))
_RL_MAX_DIA = int(os.environ.get("FICHA_RL_MAX_DIA", "12"))
# Tempo mínimo (s) entre abrir o formulário e enviar (anti-script imediato)
_TMIN_ENVIO_S = int(os.environ.get("FICHA_TMIN_ENVIO_S", "12"))

_UA_BLOQUEIO_SUBSTR = (
    "curl/",
    "wget/",
    "python-requests",
    "scrapy",
    "aiohttp",
    "httpx",
    "go-http-client",
    "java/",
    "libwww",
    "httpclient",
    "axios/",
)


def _headers() -> dict[str, str]:
    try:
        ctx = getattr(st, "context", None)
        if ctx is None:
            return {}
        hd = getattr(ctx, "headers", None)
        if hd is None:
            return {}
        if isinstance(hd, dict):
            return {str(k): str(v) for k, v in hd.items()}
        return {str(k): str(v) for k, v in dict(hd).items()}
    except Exception:
        return {}


def user_agent() -> str:
    h = _headers()
    return (h.get("User-Agent") or h.get("user-agent") or "").strip()


def user_agent_bloqueado() -> bool:
    if os.environ.get("FICHA_DISABLE_UA_CHECK", "").strip().lower() in ("1", "true", "yes", "on"):
        return False
    ua = user_agent().lower()
    if not ua:
        # Sem User-Agent (Streamlit sem context.headers ou proxy) — só bloqueia se forçado
        return os.environ.get("FICHA_BLOCK_EMPTY_UA", "").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
    return any(s in ua for s in _UA_BLOQUEIO_SUBSTR)


def _agora() -> float:
    return time.time()


def iniciar_sessao_formulario() -> None:
    """Marca o instante em que a sessão passou a usar o fluxo do formulário."""
    ss = st.session_state
    if ss.get("ficha_seg_t0") is None:
        ss["ficha_seg_t0"] = _agora()


def tempo_minimo_envio_ok() -> tuple[bool, str]:
    if os.environ.get("FICHA_DISABLE_TMIN", "").strip().lower() in ("1", "true", "yes", "on"):
        return True, ""
    ss = st.session_state
    t0 = ss.get("ficha_seg_t0")
    if t0 is None:
        iniciar_sessao_formulario()
        t0 = ss.get("ficha_seg_t0")
    try:
        t0f = float(t0)
    except (TypeError, ValueError):
        t0f = _agora()
    dt = _agora() - t0f
    if dt < _TMIN_ENVIO_S:
        return False, (
            f"Por segurança, aguarde alguns segundos antes de enviar "
            f"(mínimo {_TMIN_ENVIO_S}s na página)."
        )
    return True, ""


def limite_taxa_ok() -> tuple[bool, str]:
    """Limita tentativas de envio por sessão (mitiga abuso e scripts)."""
    if os.environ.get("FICHA_DISABLE_RL", "").strip().lower() in ("1", "true", "yes", "on"):
        return True, ""
    ss = st.session_state
    now = _agora()
    ts: list[float] = ss.get("ficha_rl_envios_ts") or []
    if not isinstance(ts, list):
        ts = []
    ts = [float(t) for t in ts if isinstance(t, (int, float))]
    ts = [t for t in ts if now - t < 86400]
    recentes = [t for t in ts if now - t < _RL_JANELA_S]
    if len(recentes) >= _RL_MAX_JANELA:
        return False, "Muitas tentativas de envio em pouco tempo. Aguarde e tente novamente."
    if len(ts) >= _RL_MAX_DIA:
        return False, "Limite diário de tentativas de envio atingido. Tente novamente mais tarde."
    return True, ""


def registrar_tentativa_envio() -> None:
    """Chamar ao processar um clique em Enviar (antes da validação de campos)."""
    ss = st.session_state
    now = _agora()
    ts: list[float] = ss.get("ficha_rl_envios_ts") or []
    if not isinstance(ts, list):
        ts = []
    ts = [float(t) for t in ts if isinstance(t, (int, float)) and now - t < 86400]
    ts.append(now)
    ss["ficha_rl_envios_ts"] = ts


def honeypot_ok() -> bool:
    """Campo oculto: se preenchido, trata como bot (não revelar ao cliente)."""
    v = st.session_state.get("ficha_hp_website")
    if v is None:
        return True
    if isinstance(v, str) and v.strip():
        return False
    return True


def verificar_antes_envio() -> tuple[bool, str]:
    """
    Ordem: UA → tempo mínimo → honeypot (se existir campo) → taxa.
    Ao passar, registra a tentativa na janela de rate limit.
    """
    if user_agent_bloqueado():
        return False, "Acesso não autorizado a partir deste cliente."
    ok, msg = tempo_minimo_envio_ok()
    if not ok:
        return False, msg
    if not honeypot_ok():
        return False, "Não foi possível concluir o envio. Atualize a página e tente novamente."
    ok, msg = limite_taxa_ok()
    if not ok:
        return False, msg
    registrar_tentativa_envio()
    return True, ""


def injetar_cliente_e_meta() -> None:
    """
    Injeta no documento pai (uma vez): meta robots, referrer, dissuasão leve a DevTools.
    Desative com FICHA_DISABLE_CLIENT_HARDENING=1 (útil para debug acessível).
    """
    if os.environ.get("FICHA_DISABLE_CLIENT_HARDENING", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return
    try:
        import streamlit.components.v1 as components
    except ImportError:
        return

    noindex = os.environ.get("FICHA_NOINDEX", "1").strip().lower() not in ("0", "false", "no", "off")

    meta_robots = (
        "var m=document.createElement('meta');m.name='robots';m.content='noindex,nofollow';hd.appendChild(m);"
        if noindex
        else ""
    )
    ref = (
        "var r=document.createElement('meta');r.name='referrer';r.content='strict-origin-when-cross-origin';hd.appendChild(r);"
    )

    html = f"""
<div style="display:none" aria-hidden="true">sec</div>
<script>
(function() {{
  try {{
    var p = window.parent;
    if (!p || p.__fichaSegInit) return;
    p.__fichaSegInit = true;
    var doc = p.document;
    var hd = doc.head;
    if (!hd) return;
    {meta_robots}
    {ref}
    doc.addEventListener('contextmenu', function(e) {{ e.preventDefault(); }}, true);
    doc.addEventListener('keydown', function(e) {{
      if (e.key === 'F12') {{ e.preventDefault(); return false; }}
      if (e.ctrlKey && e.shiftKey && (e.key === 'I' || e.key === 'J' || e.key === 'C')) {{
        e.preventDefault(); return false;
      }}
      if (e.ctrlKey && (e.key === 'u' || e.key === 'U')) {{ e.preventDefault(); return false; }}
    }}, true);
  }} catch (err) {{}}
}})();
</script>
"""
    components.html(html, height=0, scrolling=False)


# =============================================================================
# App Streamlit — Ficha Vendas RJ
# =============================================================================
COR_AZUL_ESC = "#04428f"
COR_VERMELHO = "#cb0935"
COR_FUNDO = "#04428f"
COR_BORDA = "#eef2f6"
COR_INPUT_BG = "#f0f2f6"
COR_TEXTO_MUTED = "#64748b"
# Rótulos de campos (texto neutro; vermelho só no * via .ficha-star-req)
COR_TEXTO_LABEL = "#1e293b"
# Tom mais escuro do vermelho (gradiente do botão primário)
COR_VERMELHO_ESCURO = "#9e0828"


def _hex_rgb_triplet(hex_color: str) -> str:
    """Converte #RRGGBB em 'r, g, b' para uso em rgba(...)."""
    x = (hex_color or "").strip().lstrip("#")
    if len(x) != 6:
        return "0, 0, 0"
    return f"{int(x[0:2], 16)}, {int(x[2:4], 16)}, {int(x[4:6], 16)}"


RGB_AZUL_CSS = _hex_rgb_triplet(COR_AZUL_ESC)
RGB_VERMELHO_CSS = _hex_rgb_triplet(COR_VERMELHO)

URL_LOGO_DIRECIONAL_EMAIL = (
    "https://logodownload.org/wp-content/uploads/2021/04/direcional-engenharia-logo.png"
)

# Logos na raiz (mesma pasta deste .py ou raiz do repositório) — upload manual
LOGO_TOPO_ARQUIVO = "502.57_LOGO DIRECIONAL_V2F-01.png"
FAVICON_ARQUIVO = "502.57_LOGO D_COR_V3F.png"


def _resolver_png_raiz(nome: str) -> Path | None:
    """Procura o PNG na pasta do app e na pasta pai (raiz do repo no Streamlit Cloud)."""
    for base in (_DIR_APP, _DIR_APP.parent):
        p = base / nome
        if p.is_file():
            return p
    return None


BASE_URL_CONTACT_VIEW = "https://direcional.lightning.force.com/lightning/r/Contact"

# Recursos exibidos no popup pós-cadastro (corretor)
URL_LINKTREE_MARKETING = "https://linktr.ee/comercialdirecionalrj"
URL_FORM_SIMULADOR = "https://forms.gle/NLibApxbaimEbdBEA"
URL_YOUTUBE_SIMULADOR = "https://youtu.be/dE42s0g7K-c"
URL_YOUTUBE_SIMULADOR_EMBED = "https://www.youtube.com/embed/dE42s0g7K-c"
URL_DIRI_ACADEMY = "https://diriacademy.skore.io/login"
URL_SALESFORCE_VENDAS = "https://direcional.my.site.com/vendas"
URL_WHATSAPP_EQUIPE = "https://chat.whatsapp.com/KnZg4Zax3Z20viB7XEWvmo"

# Mesmos links do popup — reutilizados no e-mail automático de boas-vindas.
LINKS_POS_CADASTRO: list[tuple[str, str]] = [
    ("Materiais de marketing (Linktree)", URL_LINKTREE_MARKETING),
    ("Pedir acesso ao simulador de negociação", URL_FORM_SIMULADOR),
    ("Vídeo — como usar o simulador (YouTube)", URL_YOUTUBE_SIMULADOR),
    ("Treinamentos — Diri Academy", URL_DIRI_ACADEMY),
    ("Salesforce (portal de vendas)", URL_SALESFORCE_VENDAS),
    ("Entrar no grupo — WhatsApp", URL_WHATSAPP_EQUIPE),
]

# Texto institucional do e-mail automático (apresentação + materiais de vendas).
_APRESENTACAO_DIRECIONAL_PLAIN = (
    "A Direcional Engenharia é uma das principais empresas de incorporação e construção do Brasil, "
    "com histórico de entregas, foco em qualidade e relacionamento transparente com clientes e parceiros. "
    "Na operação Direcional Vendas Rio de Janeiro, você integra nossa rede comercial com acesso a "
    "materiais, treinamentos e ferramentas para atuar com nossos empreendimentos."
)

# Popup pós-cadastro: mesma altura do minimapa e do iframe do YouTube (largura 100% do diálogo)
POPUP_MAPA_ALTURA_PX = 320

TAB_LABELS: dict[str, str] = {
    "Informações para contato": "Informações de contato",
    "Dados Pessoais": "Pessoais",
    "Dados de Usuário": "Usuário",
    "Dados para Contato": "Contato",
    "Dados Familiares": "Família",
    "Dados Bancários Pessoa Física": "Bancário PF",
    "CRECI/TTI": "CRECI",
    "Dados Integração": "Integração",
    "Preferência de contato": "Preferências",
}


def _tab_label(sec: str) -> str:
    return TAB_LABELS.get(sec, sec[:28])


def _url_contact(cid: str) -> str:
    return f"{BASE_URL_CONTACT_VIEW}/{cid}/view"


def _somente_digitos(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def _aplicar_secrets_sf():
    try:
        if hasattr(st, "secrets") and "salesforce" in st.secrets:
            sec = st.secrets["salesforce"]
            if sec.get("USER"):
                os.environ["SALESFORCE_USER"] = str(sec["USER"]).strip()
            if sec.get("PASSWORD"):
                os.environ["SALESFORCE_PASSWORD"] = str(sec["PASSWORD"]).strip()
            if sec.get("TOKEN"):
                os.environ["SALESFORCE_TOKEN"] = str(sec["TOKEN"]).strip()
            os.environ.pop("SF_RECORD_TYPE_ID", None)
            for rt_key in ("RECORD_TYPE_ID", "record_type_id", "RECORD_TYPE_CORRETOR"):
                rt = str(sec.get(rt_key) or "").strip()
                if rt and rt.lower() not in ("omit", "none", "false", "-", "0"):
                    os.environ["SF_RECORD_TYPE_ID"] = rt
                    break
    except Exception:
        pass


def _credenciais_salesforce_ok() -> bool:
    u = (os.environ.get("SALESFORCE_USER") or "").strip()
    p = (os.environ.get("SALESFORCE_PASSWORD") or "").strip()
    t = (os.environ.get("SALESFORCE_TOKEN") or "").strip()
    return bool(u and p and t)


def aplicar_estilo():
    bg_url = (
        "https://images.unsplash.com/photo-1497366216548-37526070297c"
        "?auto=format&fit=crop&w=1920&q=80"
    )
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800;900&family=Inter:wght@400;500;600;700&display=swap');
        @keyframes fichaFadeIn {{
            from {{ opacity: 0; transform: translateY(18px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        @keyframes fichaShimmer {{
            0% {{ background-position: 0% 50%; }}
            100% {{ background-position: 200% 50%; }}
        }}
        html, body {{ font-family: 'Inter', sans-serif; color: {COR_TEXTO_LABEL}; }}
        [data-testid="stAppViewContainer"] {{
            background:
                linear-gradient(160deg, rgba({RGB_AZUL_CSS}, 0.88) 0%, rgba({RGB_AZUL_CSS}, 0.72) 45%, rgba({RGB_VERMELHO_CSS}, 0.15) 100%),
                url("{bg_url}") center / cover no-repeat !important;
            background-attachment: scroll !important;
        }}
        [data-testid="stHeader"] {{ background: transparent !important; }}
        [data-testid="stToolbar"] {{
            background: rgba(255,255,255,0.15) !important;
            border-radius: 12px;
        }}
        /* Área principal: topo/base mais compactos para a box não “flutuar” com margem excessiva */
        [data-testid="stMain"] {{
            padding-left: clamp(14px, 5vw, 56px) !important;
            padding-right: clamp(14px, 5vw, 56px) !important;
            padding-top: clamp(12px, 3.5vh, 40px) !important;
            padding-bottom: clamp(14px, 4vh, 44px) !important;
            box-sizing: border-box !important;
        }}
        section.main > div {{
            padding-top: 0.25rem !important;
            padding-bottom: 0.35rem !important;
        }}
        .block-container {{
            max-width: 920px !important;
            margin-left: auto !important;
            margin-right: auto !important;
            margin-top: clamp(4px, 1vh, 14px) !important;
            margin-bottom: clamp(4px, 1vh, 14px) !important;
            padding: 1.45rem 2.25rem 1.55rem 2.25rem !important;
            background: rgba(255, 255, 255, 0.97) !important;
            backdrop-filter: blur(14px) saturate(1.2);
            -webkit-backdrop-filter: blur(14px) saturate(1.2);
            border-radius: 24px !important;
            border: 1px solid rgba(255, 255, 255, 0.85) !important;
            box-shadow:
                0 4px 6px -1px rgba({RGB_AZUL_CSS}, 0.08),
                0 24px 48px -12px rgba({RGB_AZUL_CSS}, 0.22),
                inset 0 1px 0 rgba(255, 255, 255, 0.9) !important;
            animation: fichaFadeIn 0.7s cubic-bezier(0.22, 1, 0.36, 1) both;
        }}
        h1, h2, h3 {{ font-family: 'Montserrat', sans-serif !important; color: {COR_AZUL_ESC} !important; }}
        .ficha-logo-wrap {{
            text-align: center;
            padding: 0.1rem 0 0.45rem 0;
        }}
        .ficha-logo-wrap img {{
            max-height: 72px;
            width: auto;
            max-width: min(280px, 85vw);
            height: auto;
            object-fit: contain;
            display: inline-block;
            vertical-align: middle;
        }}
        .ficha-hero-stack {{
            width: 100%;
            max-width: 100%;
            margin-bottom: 0.35rem;
            box-sizing: border-box;
        }}
        .ficha-hero {{
            text-align: center;
            padding: 0.5rem 0 0 0;
            margin: 0 auto 0 auto;
            max-width: 640px;
            animation: fichaFadeIn 0.85s cubic-bezier(0.22, 1, 0.36, 1) 0.1s both;
        }}
        .ficha-hero .ficha-title {{
            font-family: 'Montserrat', sans-serif;
            font-size: clamp(1.35rem, 3.5vw, 1.75rem);
            font-weight: 900;
            color: {COR_AZUL_ESC};
            margin: 0;
            line-height: 1.25;
            letter-spacing: -0.02em;
        }}
        .ficha-hero .ficha-sub {{
            color: #475569;
            font-size: 0.95rem;
            margin: 0.45rem 0 0 0;
            line-height: 1.45;
        }}
        /* Linha animada: largura total; margem igual acima/abaixo para ficar ao centro entre subtítulo e texto introdutório. */
        .ficha-hero-bar-wrap {{
            width: 100%;
            max-width: 100%;
            margin: clamp(0.85rem, 2.4vw, 1.2rem) 0;
            padding: 0;
            box-sizing: border-box;
        }}
        .ficha-intro {{
            width: 100%;
            max-width: 100%;
            margin: 0 0 0.35rem 0;
            padding: 0 0 0.35rem 0;
            box-sizing: border-box;
            text-align: justify;
            text-justify: inter-word;
            hyphens: auto;
            -webkit-hyphens: auto;
            color: #334155;
            font-size: 0.95rem;
            line-height: 1.55;
        }}
        .ficha-intro strong {{
            font-weight: 600;
            color: #1e293b;
        }}
        /* Rótulos de campo: texto neutro; só o * em vermelho (.ficha-star-req) */
        .ficha-input-label {{
            font-size: 0.875rem;
            font-weight: 600;
            color: {COR_TEXTO_LABEL};
            margin: 0 0 0.35rem 0;
            line-height: 1.45;
        }}
        .ficha-star-req {{
            color: {COR_VERMELHO} !important;
            font-weight: 800;
            margin-left: 0.12em;
        }}
        /* Widgets Streamlit: rótulos visíveis não herdam azul da marca */
        [data-testid="stWidgetLabel"] label,
        [data-testid="stWidgetLabel"] p,
        [data-testid="stWidgetLabel"] {{
            color: {COR_TEXTO_LABEL} !important;
        }}
        div[data-testid="stTextInput"] label,
        div[data-testid="stTextArea"] label,
        div[data-testid="stSelectbox"] label,
        div[data-testid="stMultiSelect"] label,
        div[data-testid="stCheckbox"] label {{
            color: {COR_TEXTO_LABEL} !important;
        }}
        /* Honeypot: campo após #ficha-hp-anchor (não preencher) */
        #ficha-hp-anchor ~ div [data-testid="stTextInput"] {{
            position: absolute !important;
            left: -9999px !important;
            width: 1px !important;
            height: 1px !important;
            overflow: hidden !important;
            opacity: 0 !important;
            pointer-events: none !important;
        }}
        .ficha-hero-bar {{
            height: 4px;
            width: 100%;
            margin: 0;
            border-radius: 999px;
            background: linear-gradient(90deg, {COR_AZUL_ESC}, {COR_VERMELHO}, {COR_AZUL_ESC});
            background-size: 200% 100%;
            animation: fichaShimmer 4s ease-in-out infinite alternate;
        }}
        /* Barra de etapas do formulário: vermelho → azul Direcional (substitui st.progress). */
        .ficha-etapas-progress {{
            width: 100%;
            margin: 0 0 0.65rem 0;
        }}
        .ficha-etapas-progress-track {{
            height: 8px;
            background: rgba(226, 232, 240, 0.95);
            border-radius: 999px;
            overflow: hidden;
            border: 1px solid rgba({RGB_AZUL_CSS}, 0.08);
        }}
        .ficha-etapas-progress-fill {{
            height: 100%;
            min-width: 0;
            border-radius: 999px;
            background: linear-gradient(90deg, {COR_VERMELHO} 0%, {COR_AZUL_ESC} 100%);
            transition: width 0.4s cubic-bezier(0.22, 1, 0.36, 1);
            box-shadow: 0 1px 3px rgba({RGB_AZUL_CSS}, 0.12);
        }}
        /* Container com borda (st.container(border=True)) — reforço visual opcional */
        [data-testid="stVerticalBlockBorderWrapper"] {{
            border-radius: 16px !important;
        }}
        .section-card {{
            border: 1px solid rgba(226, 232, 240, 0.95);
            background: linear-gradient(180deg, #ffffff 0%, #fafbfc 100%);
            border-radius: 16px;
            padding: 1.1rem 1.35rem 1rem 1.35rem;
            margin-bottom: 1.15rem;
            box-shadow: 0 1px 3px rgba({RGB_AZUL_CSS}, 0.06);
            transition: box-shadow 0.35s ease, transform 0.35s ease;
            animation: fichaFadeIn 0.55s cubic-bezier(0.22, 1, 0.36, 1) both;
        }}
        .section-card:hover {{
            box-shadow: 0 8px 24px -6px rgba({RGB_AZUL_CSS}, 0.12);
            transform: translateY(-1px);
        }}
        .section-head {{
            font-family: 'Montserrat', sans-serif;
            font-size: 0.78rem;
            color: {COR_AZUL_ESC};
            text-align: center;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            font-weight: 800;
            margin-bottom: 0.85rem;
            padding-bottom: 0.55rem;
            border-bottom: 2px solid #e8eef5;
        }}
        div[data-baseweb="input"] {{
            border-radius: 10px !important;
            border: 1px solid #e2e8f0 !important;
            background-color: {COR_INPUT_BG} !important;
            transition: border-color 0.2s ease, box-shadow 0.2s ease;
        }}
        div[data-baseweb="input"]:focus-within {{
            border-color: rgba({RGB_AZUL_CSS}, 0.35) !important;
            box-shadow: 0 0 0 3px rgba({RGB_AZUL_CSS}, 0.08) !important;
        }}
        .stButton > button {{
            border-radius: 12px !important;
            transition: transform 0.2s ease, box-shadow 0.2s ease !important;
        }}
        .stButton > button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 20px -6px rgba({RGB_AZUL_CSS}, 0.25) !important;
        }}
        .stButton button[kind="primary"] {{
            background: linear-gradient(180deg, {COR_VERMELHO} 0%, {COR_VERMELHO_ESCURO} 100%) !important;
            color: #ffffff !important;
            border: none !important;
            font-weight: 700 !important;
        }}
        /* Link botão — WhatsApp (verde marca #25D366) */
        a[href*="whatsapp.com"],
        a[href*="wa.me"] {{
            background-color: #25D366 !important;
            color: #ffffff !important;
            border: 1px solid #1ebe57 !important;
            border-radius: 12px !important;
            font-weight: 600 !important;
            text-decoration: none !important;
            box-shadow: 0 2px 8px rgba(37, 211, 102, 0.35) !important;
        }}
        a[href*="whatsapp.com"]:hover,
        a[href*="wa.me"]:hover {{
            background-color: #20bd5a !important;
            border-color: #1aa34a !important;
            color: #ffffff !important;
            box-shadow: 0 4px 14px rgba(37, 211, 102, 0.45) !important;
        }}
        /* Alertas nativos Streamlit: forçar paleta Direcional (sem verde/azul claro/vermelho pastel) */
        div[data-testid="stAlert"] {{
            border-radius: 14px !important;
            border: 2px solid {COR_AZUL_ESC} !important;
            background: #ffffff !important;
            box-shadow: 0 2px 12px rgba({RGB_AZUL_CSS}, 0.1) !important;
        }}
        div[data-testid="stAlert"] p,
        div[data-testid="stAlert"] span,
        div[data-testid="stAlert"] div[data-testid="stMarkdownContainer"],
        div[data-testid="stAlert"] div[data-testid="stMarkdownContainer"] * {{
            color: {COR_AZUL_ESC} !important;
        }}
        div[data-testid="stAlert"] svg {{
            fill: {COR_AZUL_ESC} !important;
            color: {COR_AZUL_ESC} !important;
        }}
        /* Alertas customizados (substituem st.success/warning/info na maior parte do app) */
        .ficha-alert {{
            border-radius: 14px;
            padding: 14px 16px;
            margin: 0 0 12px 0;
            font-size: 0.95rem;
            line-height: 1.55;
            box-sizing: border-box;
        }}
        .ficha-alert--azul {{
            border: 2px solid {COR_AZUL_ESC};
            background: #ffffff;
            color: {COR_AZUL_ESC};
            box-shadow: 0 2px 12px rgba({RGB_AZUL_CSS}, 0.1);
        }}
        .ficha-alert--azul strong {{
            color: {COR_AZUL_ESC};
        }}
        .ficha-alert--vermelho {{
            border: 2px solid {COR_VERMELHO};
            background: #ffffff;
            color: {COR_AZUL_ESC};
            box-shadow: 0 2px 12px rgba({RGB_VERMELHO_CSS}, 0.12);
        }}
        .ficha-alert--vermelho strong {{
            color: {COR_VERMELHO};
        }}
        .ficha-alert a {{
            color: {COR_AZUL_ESC} !important;
            font-weight: 600;
        }}
        .footer {{
            text-align: center;
            padding: 0.85rem 0 0.35rem 0;
            color: #64748b;
            font-size: 0.82rem;
        }}
        div[data-testid="stMarkdown"] p {{ color: #334155; line-height: 1.55; }}
        /* Player YouTube: mesma largura do mapa (100% do diálogo); altura definida inline = POPUP_MAPA_ALTURA_PX */
        .ficha-popup-video-wrap {{
            width: 100%;
            max-width: 100%;
            margin: 0.5rem 0 1rem 0;
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid #e2e8f0;
            background: #0f172a;
            box-shadow: 0 4px 14px rgba({RGB_AZUL_CSS}, 0.12);
            box-sizing: border-box;
        }}
        iframe.ficha-popup-video {{
            width: 100%;
            height: 100%;
            min-height: 0;
            border: none;
            display: block;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _md_bold_to_html(s: str) -> str:
    """Converte trechos **texto** em <strong>; o restante é escapado para HTML."""
    if "**" not in s:
        return html.escape(s)
    parts: list[str] = []
    i = 0
    while i < len(s):
        j = s.find("**", i)
        if j == -1:
            parts.append(html.escape(s[i:]))
            break
        parts.append(html.escape(s[i:j]))
        k = s.find("**", j + 2)
        if k == -1:
            parts.append(html.escape(s[j:]))
            break
        parts.append(f"<strong>{html.escape(s[j + 2 : k])}</strong>")
        i = k + 2
    return "".join(parts)


def _alert_azul(msg: str) -> None:
    """Aviso informativo — borda e ênfase azul Direcional (COR_AZUL_ESC)."""
    st.markdown(
        f'<div class="ficha-alert ficha-alert--azul">{_md_bold_to_html(msg)}</div>',
        unsafe_allow_html=True,
    )


def _alert_vermelho(msg: str) -> None:
    """Alerta de atenção — borda vermelha Direcional (COR_VERMELHO), texto azul escuro."""
    st.markdown(
        f'<div class="ficha-alert ficha-alert--vermelho">{_md_bold_to_html(msg)}</div>',
        unsafe_allow_html=True,
    )


def _alert_vermelho_html(inner_html: str) -> None:
    """Como _alert_vermelho, com HTML já montado (trechos dinâmicos escapados pelo chamador)."""
    st.markdown(
        f'<div class="ficha-alert ficha-alert--vermelho">{inner_html}</div>',
        unsafe_allow_html=True,
    )


def _logo_arquivo_local() -> str | None:
    p_topo = _resolver_png_raiz(LOGO_TOPO_ARQUIVO)
    if p_topo:
        return str(p_topo)
    for name in ("logo_direcional.png", "logo_direcional.jpg", "logo_direcional.jpeg", "logo.png"):
        p = _DIR_APP / "assets" / name
        if p.is_file():
            return str(p)
    return None


def _logo_url_secrets() -> str | None:
    try:
        if hasattr(st, "secrets"):
            b = st.secrets.get("branding")
            if isinstance(b, dict):
                u = (b.get("LOGO_URL") or "").strip()
                if u:
                    return u
    except Exception:
        pass
    return None


def _logo_url_drive_por_id_arquivo() -> str | None:
    """URL de visualização pública a partir do ID do arquivo no Drive (variável de ambiente)."""
    fid = (os.environ.get("DIRECIONAL_LOGO_FILE_ID") or "").strip()
    if len(fid) < 10:
        return None
    return f"https://drive.google.com/uc?export=view&id={fid}"


def _exibir_logo_topo() -> None:
    """Logo centralizada no topo: arquivo em assets/, ou LOGO_URL, ou ID do arquivo no Drive."""
    path = _logo_arquivo_local()
    url = _logo_url_secrets() or _logo_url_drive_por_id_arquivo()
    try:
        if path:
            ext = Path(path).suffix.lower().lstrip(".")
            mime = "image/png" if ext == "png" else "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            st.markdown(
                f'<div class="ficha-logo-wrap"><img src="data:{mime};base64,{b64}" alt="Direcional" /></div>',
                unsafe_allow_html=True,
            )
            return
        if url:
            st.markdown(
                f'<div class="ficha-logo-wrap"><img src="{html.escape(url)}" alt="Direcional" /></div>',
                unsafe_allow_html=True,
            )
    except Exception:
        pass


def _cabecalho_pagina(*, com_intro_formulario: bool = False) -> None:
    _exibir_logo_topo()
    intro = ""
    if com_intro_formulario:
        intro = (
            '<p class="ficha-intro" lang="pt-BR">Você está a poucos passos de dar sequência ao seu credenciamento com a gente. '
            "<strong>Reserve alguns minutos</strong>, tenha seus documentos à mão e vá preenchendo com tranquilidade — "
            "use <strong>Avançar</strong> e <strong>Voltar</strong> para navegar. Na última etapa, confirme os dados e envie.</p>"
        )
    st.markdown(
        f'<div class="ficha-hero-stack">'
        f'<div class="ficha-hero">'
        f'<p class="ficha-title">Seja bem-vindo à Direcional Vendas RJ</p>'
        f'<p class="ficha-sub">Seu próximo passo começa aqui — '
        f'<strong>vamos conhecer você melhor</strong> para seguir com o credenciamento.</p>'
        f"</div>"
        f'<div class="ficha-hero-bar-wrap" aria-hidden="true">'
        f'<div class="ficha-hero-bar"></div>'
        f"</div>"
        f"{intro}"
        f"</div>",
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=300, show_spinner=False)
def _nomes_conta_coluna_gerentes_cached(
    spreadsheet_id: str,
    worksheet_gerentes: str,
    coluna_nome_conta: str,
    creds_json: str,
) -> tuple[str, ...]:
    """Cache por planilha/aba/coluna/credencial (JSON estável) — evita ler a aba a cada rerun."""
    try:
        creds = json.loads(creds_json)
        nomes = listar_nomes_conta_aba_gerentes(
            spreadsheet_id,
            creds,
            worksheet_name=worksheet_gerentes,
            column_header=coluna_nome_conta,
        )
        return tuple(nomes)
    except Exception:
        return tuple()


def _opcoes_nome_conta() -> list[str]:
    """
    Opções do select «Nome da conta»: valores únicos da coluna **Nome da Conta** na aba **Gerentes**
    da mesma planilha Google (Secrets [google_sheets]). Se a leitura falhar ou vier vazia,
    usa [ficha_defaults] account_names / account_name ou NOMES_CONTA_FIXOS.
    """
    creds = _credenciais_de_secrets(st.secrets if hasattr(st, "secrets") else None)
    if creds:
        gs: dict[str, Any] = {}
        if hasattr(st, "secrets"):
            try:
                gs = dict(st.secrets.get("google_sheets", {}))
            except Exception:
                gs = {}
        sid = str(gs.get("SPREADSHEET_ID", DEFAULT_SPREADSHEET_ID)).strip()
        ws_g = str(
            gs.get("GERENTES_WORKSHEET")
            or gs.get("gerentes_worksheet")
            or DEFAULT_GERENTES_WORKSHEET
        ).strip() or DEFAULT_GERENTES_WORKSHEET
        col_nc = str(
            gs.get("NOME_CONTA_COLUMN")
            or gs.get("nome_conta_column")
            or DEFAULT_COL_NOME_CONTA
        ).strip() or DEFAULT_COL_NOME_CONTA
        try:
            creds_json = json.dumps(creds, sort_keys=True)
        except (TypeError, ValueError):
            creds_json = "{}"
        tupla = _nomes_conta_coluna_gerentes_cached(sid, ws_g, col_nc, creds_json)
        if tupla:
            return list(tupla)

    fd = _ficha_defaults_de_secrets()
    raw = fd.get("account_names")
    if isinstance(raw, list) and raw:
        return [str(x).strip() for x in raw if str(x).strip()]
    one = str(fd.get("account_name", "")).strip()
    if one:
        return [one]
    return list(NOMES_CONTA_FIXOS)


def _label_obrigatorio_partes(label: str) -> tuple[str, bool]:
    """Se o rótulo termina com ' *', devolve texto sem o asterisco e True."""
    s = (label or "").rstrip()
    if s.endswith(" *"):
        return s[:-2].rstrip(), True
    return label, False


def _widget_campo(c: dict):
    k = c["key"]
    sk = f"fld_{k}"
    label = c["label"]
    help_txt = c.get("help")
    tipo = c["tipo"]

    plain, obrig = _label_obrigatorio_partes(label)
    lv = "collapsed" if obrig else "visible"
    if obrig:
        st.markdown(
            f'<div class="ficha-input-label">{html.escape(plain)} '
            f'<span class="ficha-star-req" aria-hidden="true">*</span></div>',
            unsafe_allow_html=True,
        )
        widget_label = f"{plain} (campo obrigatório)"
    else:
        widget_label = label

    if tipo == "text":
        return st.text_input(widget_label, key=sk, help=help_txt, label_visibility=lv)
    if tipo == "textarea":
        return st.text_area(widget_label, key=sk, help=help_txt, height=88, label_visibility=lv)
    if tipo == "date":
        return st.text_input(
            widget_label, key=sk, placeholder="31/12/2024", help=help_txt, label_visibility=lv
        )
    if tipo == "number":
        return st.text_input(
            widget_label,
            key=sk,
            help=help_txt or "Use ponto ou vírgula decimal.",
            label_visibility=lv,
        )
    if tipo == "id":
        return st.text_input(widget_label, key=sk, help=help_txt, label_visibility=lv)
    if tipo == "select":
        opts = c.get("opcoes") or [""]
        if k == "account_name":
            opts = _opcoes_nome_conta()
            if not opts:
                opts = list(NOMES_CONTA_FIXOS)
        elif k == "atividade":
            opts = list(ATIVIDADE_VENDAS_RJ_OPTS)
        if k == "possui_creci":
            opts = ["Sim", "Não"]
            return st.selectbox(
                widget_label,
                options=opts,
                index=None,
                placeholder="Selecione se possui CRECI",
                key=sk,
                help=help_txt,
                label_visibility=lv,
            )
        cur = st.session_state.get(sk)
        if cur is not None and cur not in opts:
            st.session_state[sk] = opts[0]
        return st.selectbox(widget_label, options=opts, key=sk, help=help_txt, label_visibility=lv)
    if tipo == "multiselect":
        opts = c.get("opcoes") or []
        return st.multiselect(
            widget_label, options=opts, default=[], key=sk, help=help_txt, label_visibility=lv
        )
    return st.text_input(widget_label, key=sk, help=help_txt, label_visibility=lv)


def _coletar_dados_formulario() -> dict[str, Any]:
    """Somente chaves presentes no session_state (etapa atual + campos sem widget)."""
    out: dict[str, Any] = {}
    for c in CAMPOS:
        sk = f"fld_{c['key']}"
        out[c["key"]] = st.session_state.get(sk)
    return out


def _coletar_dados_formulario_completo() -> dict[str, Any]:
    """
    Mescla snapshot das etapas já confirmadas (ficha_snap_campos) com o session_state.
    Necessário porque só a etapa corrente monta widgets — ao avançar, o Streamlit pode
    remover valores das etapas anteriores do state.
    """
    ss = st.session_state
    snap = dict(ss.get("ficha_snap_campos") or {})
    out: dict[str, Any] = {}
    for c in CAMPOS:
        k = c["key"]
        sk = f"fld_{k}"
        if sk in ss:
            out[k] = ss[sk]
        else:
            out[k] = snap.get(k)
    return out


def _snapshot_mesclar_todos_fld_do_session_state() -> None:
    """
    Copia todo `fld_*` ainda presente no session_state para `ficha_snap_campos`.
    Necessário no «Enviar»: a última etapa acabou de dar submit no form; outras chaves
    podem já ter sido removidas pelo Streamlit quando o widget desmontou — essas ficam só no snapshot
    das etapas anteriores (já mesclado antes de apagar).
    """
    ss = st.session_state
    snap = dict(ss.get("ficha_snap_campos") or {})
    for c in CAMPOS:
        if c["key"] in CAMPOS_OCULTOS_FORMULARIO:
            continue
        sk = f"fld_{c['key']}"
        if sk in ss:
            snap[c["key"]] = ss[sk]
    ss["ficha_snap_campos"] = snap


def _snapshot_persistir_secao_atual(sec: str) -> None:
    """Grava no snapshot os campos visíveis da etapa atual (chamar após validar «Avançar»)."""
    ss = st.session_state
    snap = dict(ss.get("ficha_snap_campos") or {})
    dados = _coletar_dados_formulario_completo()
    for c in campos_por_secao_visiveis(sec, dados):
        k = c["key"]
        sk = f"fld_{k}"
        if sk in ss:
            snap[k] = ss[sk]
    # Renderizados fora do st.form: garantir cópia explícita no «Avançar» (mesmo critério do loop).
    if sec == "Informações para contato" and "fld_unidade_negocio" in ss:
        snap["unidade_negocio"] = ss["fld_unidade_negocio"]
    if sec == "CRECI/TTI" and "fld_possui_creci" in ss:
        snap["possui_creci"] = ss["fld_possui_creci"]
    ss["ficha_snap_campos"] = snap


def _garantir_campos_secao_de_snapshot(sec: str) -> None:
    """Ao voltar ou reabrir uma etapa, repõe fld_* a partir do snapshot se a chave sumiu."""
    ss = st.session_state
    snap = ss.get("ficha_snap_campos") or {}
    dados = _coletar_dados_formulario_completo()
    for c in campos_por_secao_visiveis(sec, dados):
        k = c["key"]
        sk = f"fld_{k}"
        if sk not in ss and k in snap:
            ss[sk] = snap[k]


def _ficha_defaults_de_secrets() -> dict[str, Any]:
    """Valores fixos não exibidos no formulário — seção [ficha_defaults] nos Secrets."""
    try:
        d = st.secrets.get("ficha_defaults", {})
        return dict(d) if isinstance(d, dict) else {}
    except Exception:
        return {}


def _init_defaults():
    """Padrões Vendas RJ; regional/origem/status/ids vêm de [ficha_defaults] nos Secrets."""
    fd = _ficha_defaults_de_secrets()
    if "fld_regional" not in st.session_state:
        st.session_state["fld_regional"] = str(fd.get("regional", "RJ")).strip() or "RJ"
    if "fld_status_corretor" not in st.session_state:
        st.session_state["fld_status_corretor"] = (
            str(fd.get("status_corretor", "Pré credenciado")).strip() or "Pré credenciado"
        )
    if "fld_origem" not in st.session_state:
        st.session_state["fld_origem"] = str(fd.get("origem", "RH")).strip() or "RH"
    if "fld_account_id" not in st.session_state:
        st.session_state["fld_account_id"] = str(fd.get("account_id", "")).strip()
    if "fld_owner_id" not in st.session_state:
        st.session_state["fld_owner_id"] = str(fd.get("owner_id", "")).strip()


def _enriquecer_mobile_phone(payload: dict[str, Any], dados: dict[str, Any]) -> list[str]:
    avisos: list[str] = []
    if payload.get("MobilePhone"):
        return avisos
    m = _somente_digitos(str(dados.get("mobile") or ""))
    if len(m) >= 10:
        payload["MobilePhone"] = m[:11]
        return avisos
    tipo = (dados.get("tipo_pix") or "").strip()
    dp = str(dados.get("dados_pix") or "")
    if tipo == "Telefone":
        mt = _somente_digitos(dp)
        if len(mt) >= 10:
            payload["MobilePhone"] = mt[:11]
            return avisos
    return avisos


def _nome_candidato_ficha(dados: dict[str, Any]) -> str:
    nome = (dados.get("nome_completo") or "").strip()
    return nome or "Candidato"


def montar_html_email_ficha_pdf(dados: dict[str, Any]) -> str:
    """Corpo HTML do e-mail (estilo Direcional: azul COR_AZUL_ESC, vermelho COR_VERMELHO)."""
    nome = html.escape(_nome_candidato_ficha(dados))
    cpf = html.escape(str(dados.get("cpf") or ""))
    emitido = html.escape(datetime.now().strftime("%d/%m/%Y %H:%M"))
    logo = html.escape(URL_LOGO_DIRECIONAL_EMAIL)
    azul = COR_AZUL_ESC
    verm = COR_VERMELHO
    borda = COR_BORDA

    linhas: list[str] = []
    for c in CAMPOS:
        k = c["key"]
        val = dados.get(k)
        if val is None or (isinstance(val, list) and len(val) == 0):
            continue
        if isinstance(val, str) and not val.strip():
            continue
        label = html.escape(c["label"])
        if isinstance(val, list):
            vtxt = html.escape("; ".join(str(x) for x in val))
        else:
            vtxt = html.escape(str(val))
        linhas.append(
            "<tr>"
            f"<td style=\"padding:10px 12px;border:1px solid {borda};background:{COR_INPUT_BG};"
            f"font-weight:600;color:{azul};font-size:13px;width:38%;\">{label}</td>"
            f"<td style=\"padding:10px 12px;border:1px solid {borda};color:#334155;font-size:13px;\">{vtxt}</td>"
            "</tr>"
        )
    if not linhas:
        linhas.append(
            f"<tr><td colspan=\"2\" style=\"padding:14px;color:{COR_TEXTO_MUTED};font-size:13px;\">"
            "Nenhum dado preenchido.</td></tr>"
        )
    tbody = "\n".join(linhas)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:24px;background:#f1f5f9;font-family:'Segoe UI',Inter,Arial,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;margin:0 auto;">
<tr><td align="center">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:14px;overflow:hidden;
box-shadow:0 8px 28px rgba({RGB_AZUL_CSS},0.08);border:1px solid {borda};">
<tr>
<td align="center" style="background:{azul};padding:22px 20px;border-bottom:4px solid {verm};">
<img src="{logo}" alt="Direcional Engenharia" width="168" style="display:block;max-width:100%;height:auto;">
</td>
</tr>
<tr>
<td style="padding:28px 24px 8px 24px;">
<p style="margin:0 0 8px 0;font-size:18px;font-weight:700;color:{azul};text-align:center;">Ficha cadastral recebida</p>
<p style="margin:0;font-size:14px;line-height:1.55;color:#475569;text-align:center;">
Olá, <strong>{nome}</strong> — segue o resumo dos dados enviados. O PDF completo está em <strong>anexo</strong>.
</p>
<p style="margin:12px 0 0 0;font-size:12px;color:{COR_TEXTO_MUTED};text-align:center;">Emitido em {emitido}</p>
</td>
</tr>
<tr><td style="padding:0 24px 12px 24px;">
<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;font-size:13px;">
<tr style="background:{azul};color:#ffffff;">
<th colspan="2" align="left" style="padding:10px 12px;font-weight:700;">Identificação</th>
</tr>
<tr><td style="padding:10px 12px;border:1px solid {borda};color:{azul};font-weight:600;">Nome</td>
<td style="padding:10px 12px;border:1px solid {borda};">{nome}</td></tr>
<tr><td style="padding:10px 12px;border:1px solid {borda};color:{azul};font-weight:600;">CPF</td>
<td style="padding:10px 12px;border:1px solid {borda};">{cpf}</td></tr>
</table>
</td></tr>
<tr><td style="padding:8px 24px 24px 24px;">
<p style="margin:0 0 10px 0;font-size:12px;font-weight:700;color:{azul};text-transform:uppercase;letter-spacing:0.06em;">
Dados do formulário</p>
<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
{tbody}
</table>
</td></tr>
<tr><td style="padding:16px 20px;background:{azul};text-align:center;">
<p style="margin:0;font-size:11px;color:rgba(255,255,255,0.88);">Direcional Engenharia · Vendas Rio de Janeiro</p>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""


def gerar_pdf_ficha(dados: dict[str, Any]) -> bytes:
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as e:
        raise ImportError(
            "Pacote 'reportlab' não encontrado. Execute: python -m pip install reportlab"
        ) from e

    def _registrar_fonte_pdf() -> str:
        """Registra TTF com suporte a UTF-8 (acentos PT-BR). Sem TTF, usa Helvetica + cp1252 em _cell_txt."""
        candidatos: list[str] = []
        sysname = platform.system()
        if sysname == "Windows":
            w = os.environ.get("WINDIR", r"C:\Windows")
            candidatos.extend(
                [
                    os.path.join(w, "Fonts", "arialuni.ttf"),
                    os.path.join(w, "Fonts", "arial.ttf"),
                    os.path.join(w, "Fonts", "Arial.ttf"),
                ]
            )
        elif sysname == "Darwin":
            candidatos.extend(
                [
                    "/Library/Fonts/Arial Unicode.ttf",
                    "/System/Library/Fonts/Supplemental/Arial.ttf",
                    "/Library/Fonts/Arial.ttf",
                ]
            )
        else:
            # Linux (Streamlit Cloud, Docker): caminhos usuais de pacotes de fontes
            for root in ("/usr/share/fonts", "/usr/local/share/fonts"):
                if not os.path.isdir(root):
                    continue
                for sub, nome in (
                    ("truetype/dejavu", "DejaVuSans.ttf"),
                    ("TTF", "DejaVuSans.ttf"),
                    ("truetype/liberation", "LiberationSans-Regular.ttf"),
                    ("truetype/noto", "NotoSans-Regular.ttf"),
                    ("truetype/freefont", "FreeSans.ttf"),
                ):
                    p = os.path.join(root, sub, nome)
                    if os.path.isfile(p):
                        candidatos.append(p)
        # Fonte junto ao app (deploy: copiar DejaVuSans.ttf para assets/fonts/)
        _font_app = _DIR_APP / "assets" / "fonts" / "DejaVuSans.ttf"
        if _font_app.is_file():
            candidatos.insert(0, str(_font_app))

        for path in candidatos:
            if os.path.isfile(path):
                try:
                    pdfmetrics.registerFont(TTFont("FichaPdfFont", path))
                    return "FichaPdfFont"
                except Exception:
                    continue
        return "Helvetica"

    font = _registrar_fonte_pdf()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    azul = colors.HexColor(COR_AZUL_ESC)
    verm = colors.HexColor(COR_VERMELHO)
    st_banner = ParagraphStyle(
        name="Banner",
        parent=styles["Normal"],
        fontName=font,
        fontSize=11,
        leading=14,
        textColor=colors.white,
        alignment=TA_CENTER,
        spaceAfter=0,
    )
    st_sub = ParagraphStyle(
        name="Sub",
        parent=styles["Normal"],
        fontName=font,
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor(COR_TEXTO_MUTED),
        alignment=TA_CENTER,
        spaceAfter=10,
    )
    st_body = ParagraphStyle(name="Corpo", parent=styles["Normal"], fontName=font, fontSize=9, leading=12)

    def _cell_txt(x: Any) -> str:
        """Texto seguro para Paragraph: TTF aceita Unicode; Helvetica usa WinAnsi (cp1252) para PT-BR."""
        s = str(x) if x is not None else ""
        if font != "Helvetica":
            return s
        # Helvetica no ReportLab = WinAnsiEncoding (~cp1252): português completo, sem «?» nos acentos.
        try:
            return s.encode("cp1252", "replace").decode("cp1252")
        except Exception:
            return s

    def _para_celula(s: str) -> Paragraph:
        """Células da tabela como Paragraph (Unicode + acentos) com escape XML mínimo."""
        t = _xml_escape_para_pdf(_cell_txt(s)).replace("\n", "<br/>")
        return Paragraph(t, st_body)

    largura = 17 * cm
    story: list = []
    # Cabeçalho marca (faixa azul + linha vermelha)
    head_tbl = Table(
        [[Paragraph(_cell_txt("FICHA CADASTRAL | DIRECIONAL VENDAS RJ"), st_banner)]],
        colWidths=[largura],
    )
    head_tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), azul),
                ("TOPPADDING", (0, 0), (-1, -1), 11),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(head_tbl)
    red_bar = Table([[""]], colWidths=[largura], rowHeights=[0.14 * cm])
    red_bar.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), verm)]))
    story.append(red_bar)
    story.append(Spacer(1, 0.35 * cm))
    story.append(
        Paragraph(
            _cell_txt(f"Emitido em: {datetime.now().strftime('%d/%m/%Y %H:%M')}"),
            st_sub,
        )
    )
    story.append(Spacer(1, 0.2 * cm))

    linhas_tab: list[list[str]] = []
    for c in CAMPOS:
        k = c["key"]
        val = dados.get(k)
        if val is None or (isinstance(val, list) and len(val) == 0):
            continue
        if isinstance(val, str) and not val.strip():
            continue
        label = c["label"]
        if isinstance(val, list):
            vtxt = "; ".join(str(x) for x in val)
        else:
            vtxt = str(val)
        linhas_tab.append([_para_celula(label), _para_celula(vtxt)])

    if linhas_tab:
        hdr_bg = colors.HexColor("#e8eef5")
        t = Table(
            [[_para_celula("Campo"), _para_celula("Resposta")]] + linhas_tab,
            colWidths=[6 * cm, 11 * cm],
        )
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), hdr_bg),
                    ("TEXTCOLOR", (0, 0), (-1, 0), azul),
                    ("FONTNAME", (0, 0), (-1, -1), font),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("FONTSIZE", (0, 0), (-1, 0), 9),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor(COR_BORDA)),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(COR_INPUT_BG)]),
                ]
            )
        )
        story.append(t)
    else:
        story.append(Paragraph(_cell_txt("(Nenhum dado preenchido)"), st_body))

    doc.build(story)
    return buf.getvalue()


def montar_corpo_email_boas_vindas(
    dados: dict[str, Any],
    link_contato_sf: str | None,
    *,
    tem_pdf_anexo: bool,
) -> tuple[str, str]:
    """Corpo do e-mail automático: apresentação Direcional, cadastro, materiais de vendas e PDF."""
    nome = _nome_candidato_ficha(dados)
    nome_esc = html.escape(nome)
    logo = html.escape(URL_LOGO_DIRECIONAL_EMAIL)
    azul = COR_AZUL_ESC
    verm = COR_VERMELHO
    borda = COR_BORDA

    linhas_txt: list[str] = []
    itens_html: list[str] = []
    for label, url in LINKS_POS_CADASTRO:
        linhas_txt.append(f"- {label}: {url}")
        itens_html.append(
            f'<li style="margin:10px 0;line-height:1.45;">'
            f'<a href="{html.escape(url)}" style="color:{azul};font-weight:600;text-decoration:none;">'
            f"{html.escape(label)}</a>"
            f'<br><span style="font-size:12px;color:{COR_TEXTO_MUTED};word-break:break-all;">{html.escape(url)}</span>'
            f"</li>"
        )
    if link_contato_sf:
        linhas_txt.append(f"- Seu cadastro no Salesforce: {link_contato_sf}")
        itens_html.append(
            f'<li style="margin:10px 0;line-height:1.45;">'
            f'<a href="{html.escape(link_contato_sf)}" '
            f'style="color:{azul};font-weight:600;text-decoration:none;">'
            f"Abrir seu cadastro no Salesforce</a></li>"
        )

    bloco_pdf_plain = (
        "Anexamos neste e-mail o PDF da sua ficha cadastral (cópia do que você enviou pelo formulário).\n\n"
        if tem_pdf_anexo
        else "Não foi possível gerar o PDF automaticamente neste envio; use o popup do formulário "
        "(após o cadastro) para baixar a cópia ou solicitar reenvio.\n\n"
    )
    bloco_pdf_html = (
        f'<p style="margin:0 0 16px 0;padding:14px 16px;background:{COR_INPUT_BG};border-radius:10px;'
        f'border-left:4px solid {verm};font-size:14px;line-height:1.55;color:#334155;">'
        f"<strong>PDF em anexo:</strong> segue a cópia em PDF da sua ficha cadastral.</p>"
        if tem_pdf_anexo
        else f'<p style="margin:0 0 16px 0;font-size:13px;line-height:1.55;color:{COR_TEXTO_MUTED};">'
        f"Se o PDF não estiver disponível neste e-mail, abra o <strong>popup de boas-vindas</strong> no "
        f"formulário para baixar ou reenviar a cópia.</p>"
    )

    plain = (
        f"Olá, {nome},\n\n"
        "Bem-vindo(a) à Direcional Vendas Rio de Janeiro.\n\n"
        "Recebemos o seu cadastro com sucesso. Você já está registrado(a) em nossa base — "
        "agradecemos a confiança e o tempo dedicado.\n\n"
        "--- A Direcional ---\n"
        f"{_APRESENTACAO_DIRECIONAL_PLAIN}\n\n"
        "--- Materiais e canais para sua atuação ---\n"
        + "\n".join(linhas_txt)
        + "\n\n"
        + bloco_pdf_plain
        + "No popup do formulário você também encontra o mapa de empreendimentos e o vídeo do simulador.\n\n"
        "Direcional Engenharia · Vendas Rio de Janeiro"
    )

    apresent_esc = html.escape(_APRESENTACAO_DIRECIONAL_PLAIN)

    html_body = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:24px;background:#f1f5f9;font-family:'Segoe UI',Inter,Arial,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;margin:0 auto;">
<tr><td align="center">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:14px;overflow:hidden;
box-shadow:0 8px 28px rgba({RGB_AZUL_CSS},0.08);border:1px solid {borda};">
<tr>
<td align="center" style="background:{azul};padding:22px 20px;border-bottom:4px solid {verm};">
<img src="{logo}" alt="Direcional Engenharia" width="168" style="display:block;max-width:100%;height:auto;">
</td>
</tr>
<tr>
<td style="padding:28px 24px 8px 24px;">
<p style="margin:0 0 8px 0;font-size:20px;font-weight:700;color:{azul};text-align:center;">
Bem-vindo(a) à Direcional Vendas RJ</p>
<p style="margin:0;font-size:15px;line-height:1.65;color:#475569;text-align:center;">
Olá, <strong>{nome_esc}</strong> — <strong>seu cadastro foi recebido</strong> e você já integra nossa operação comercial.
Obrigado(a) por escolher seguir conosco.
</p>
</td>
</tr>
<tr><td style="padding:16px 28px 8px 28px;">
<p style="margin:0 0 10px 0;font-size:15px;font-weight:700;color:{azul};">A Direcional</p>
<p style="margin:0;font-size:14px;line-height:1.65;color:#475569;">{apresent_esc}</p>
</td></tr>
<tr><td style="padding:16px 28px 8px 28px;">
<p style="margin:0 0 10px 0;font-size:15px;font-weight:700;color:{azul};">Materiais e canais para vendas</p>
<p style="margin:0 0 12px 0;font-size:13px;line-height:1.55;color:{COR_TEXTO_MUTED};">
Abaixo, links para marketing, simulador, treinamentos, portal e grupo da equipe — os mesmos recursos do formulário.
</p>
<ul style="margin:0;padding-left:18px;color:#334155;font-size:14px;">
{"".join(itens_html)}
</ul>
</td></tr>
<tr><td style="padding:8px 28px 8px 28px;">
{bloco_pdf_html}
<p style="margin:0;font-size:13px;line-height:1.55;color:{COR_TEXTO_MUTED};">
No <strong>popup de boas-vindas</strong> do formulário há também o <strong>mapa de empreendimentos</strong> e o
<strong>vídeo</strong> do simulador (mesma experiência visual do cadastro).
</p>
</td></tr>
<tr><td style="padding:20px 24px 28px 24px;border-top:1px solid {borda};">
<p style="margin:0;font-size:12px;color:{COR_TEXTO_MUTED};text-align:center;">
Direcional Engenharia · Vendas Rio de Janeiro
</p>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""

    return plain, html_body


def _smtp_erro_amigavel(exc: BaseException) -> str:
    """Evita exibir dict/tuple cru do Gmail (ex.: destinatário «K» inválido)."""
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        partes: list[str] = []
        rec = getattr(exc, "recipients", None) or {}
        for addr, tup in rec.items():
            if isinstance(tup, tuple) and len(tup) >= 2:
                cod, raw = tup[0], tup[1]
                msg = (
                    raw.decode("utf-8", "replace")
                    if isinstance(raw, (bytes, bytearray))
                    else str(raw)
                )
                partes.append(f"{addr}: código {cod} — {msg[:280]}")
            else:
                partes.append(f"{addr}: {tup}")
        if partes:
            return (
                "O servidor recusou o destinatário. Confira se o **E-mail** no formulário está completo "
                "(ex.: nome@empresa.com.br). Detalhe: " + " | ".join(partes[:2])
            )
    return str(exc)


def enviar_email_boas_vindas_candidato(
    dados: dict[str, Any],
    pdf_bytes: bytes | None,
    link_contato_sf: str | None,
) -> tuple[bool, str]:
    """Envia ao e-mail do formulário o agradecimento + links (e PDF se houver)."""
    cfg = _get_smtp_from_secrets()
    if not cfg or not cfg["host"] or not cfg["user"]:
        return False, "SMTP não configurado ([ficha_email] nos Secrets)."

    dest = (dados.get("email") or "").strip()
    if not dest:
        return False, "E-mail do candidato não informado no formulário."
    if not email_contato_formato_valido(dest):
        return False, "E-mail do cadastro inválido — use formato nome@dominio.com (evite abreviações como uma única letra)."

    nome = _nome_candidato_ficha(dados)
    tem_pdf = bool(pdf_bytes)
    plain, html_body = montar_corpo_email_boas_vindas(
        dados, link_contato_sf, tem_pdf_anexo=tem_pdf
    )

    msg = MIMEMultipart()
    msg["Subject"] = (
        f"Bem-vindo(a) — Direcional Vendas RJ | Ficha e materiais — {nome}"
        if tem_pdf
        else f"Bem-vindo(a) — Direcional Vendas RJ | Cadastro recebido — {nome}"
    )
    msg["From"] = cfg["from_addr"]
    msg["To"] = dest

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(plain, "plain", "utf-8"))
    alt.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(alt)

    if pdf_bytes:
        part = MIMEApplication(pdf_bytes, _subtype="pdf")
        part.add_header(
            "Content-Disposition",
            "attachment",
            filename="ficha_cadastral_direcional_vendas_rj.pdf",
        )
        msg.attach(part)

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"]) as server:
            server.starttls()
            server.login(cfg["user"], cfg["password"])
            server.sendmail(cfg["from_addr"], [dest], msg.as_string())
        return True, "E-mail enviado (apresentação, materiais e PDF, se gerado) para o e-mail do cadastro."
    except Exception as e:
        return False, _smtp_erro_amigavel(e)


def _tentar_enviar_email_boas_vindas(dados: dict[str, Any], contact_id: str | None) -> None:
    """Dispara o e-mail automático; não interrompe o fluxo se falhar."""
    ss = st.session_state
    pdf_bytes: bytes | None = None
    try:
        pdf_bytes = gerar_pdf_ficha(dados)
    except Exception:
        pass
    link = _url_contact(contact_id) if contact_id else None
    ok, msg = enviar_email_boas_vindas_candidato(dados, pdf_bytes, link)
    ss["ficha_email_boas_vindas_ok"] = ok
    ss["ficha_email_boas_vindas_msg"] = msg


def _get_smtp_from_secrets():
    """
    Lê [ficha_email] nos Secrets. Chaves esperadas:
      smtp_server, smtp_port (padrão 587), sender_email, sender_password
    Compatibilidade: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, TO_EMAIL, FROM_EMAIL.
    Destinatário fixo opcional: to_email ou TO_EMAIL (senão use o campo na tela).
    """
    try:
        s = st.secrets.get("ficha_email", {})
        host = (s.get("smtp_server") or s.get("SMTP_HOST") or "").strip()
        port_raw = s.get("smtp_port", s.get("SMTP_PORT", 587))
        port = int(port_raw) if port_raw not in (None, "") else 587
        user = (s.get("sender_email") or s.get("SMTP_USER") or "").strip()
        password = (s.get("sender_password") or s.get("SMTP_PASSWORD") or "").strip()
        to_fixed = (s.get("to_email") or s.get("TO_EMAIL") or "").strip()
        if to_fixed and not email_contato_formato_valido(to_fixed):
            to_fixed = ""
        return {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "to": to_fixed,
            "from_addr": user or (s.get("FROM_EMAIL") or "").strip(),
        }
    except Exception:
        return None


def enviar_email_pdf(pdf_bytes: bytes, dados: dict[str, Any], destinatario_extra: str | None) -> tuple[bool, str]:
    cfg = _get_smtp_from_secrets()
    if not cfg or not cfg["host"] or not cfg["user"]:
        return False, (
            "E-mail não configurado (adicione [ficha_email] com smtp_server e sender_email nos Secrets)."
        )

    to_list = [cfg["to"]] if cfg["to"] else []
    if destinatario_extra and destinatario_extra.strip():
        to_list.append(destinatario_extra.strip())
    if not to_list:
        return False, "Informe um e-mail de destino no campo abaixo (ou to_email em [ficha_email], opcional)."
    for addr in to_list:
        if not email_contato_formato_valido(addr):
            return False, (
                f"E-mail de destino inválido ({addr!r}) — use formato completo nome@dominio.com."
            )

    nome = _nome_candidato_ficha(dados)
    msg = MIMEMultipart()
    msg["Subject"] = f"Ficha Cadastral — Direcional Vendas RJ — {nome}"
    msg["From"] = cfg["from_addr"]
    msg["To"] = ", ".join(to_list)

    corpo_txt = (
        "Segue em anexo a cópia da ficha cadastral enviada pelo formulário "
        "Ficha Cadastral | Direcional Vendas RJ.\n\n"
        f"Nome: {nome}\n"
        f"CPF: {dados.get('cpf', '')}\n"
    )
    corpo_html = montar_html_email_ficha_pdf(dados)
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(corpo_txt, "plain", "utf-8"))
    alt.attach(MIMEText(corpo_html, "html", "utf-8"))
    msg.attach(alt)

    part = MIMEApplication(pdf_bytes, _subtype="pdf")
    part.add_header("Content-Disposition", "attachment", filename="ficha_cadastral_direcional_vendas_rj.pdf")
    msg.attach(part)

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"]) as server:
            server.starttls()
            server.login(cfg["user"], cfg["password"])
            server.sendmail(cfg["from_addr"], to_list, msg.as_string())
        return True, "E-mail enviado com sucesso."
    except Exception as e:
        return False, _smtp_erro_amigavel(e)


def _section_container():
    """Container com borda quando suportado (Streamlit recente)."""
    try:
        return st.container(border=True)
    except TypeError:
        return st.container()


def _render_secao_formulario(secoes: list[str]) -> None:
    """Uma seção por vez; navegação por botões na parte inferior."""
    ss = st.session_state
    ss.setdefault("ficha_secao_idx", 0)
    n = len(secoes)
    if n == 0:
        _alert_vermelho("Nenhuma seção de formulário configurada.")
        return

    idx = max(0, min(int(ss["ficha_secao_idx"]), n - 1))
    ss["ficha_secao_idx"] = idx
    sec = secoes[idx]
    _garantir_campos_secao_de_snapshot(sec)

    if ss.get("ficha_erros_secao_idx") is not None and int(ss["ficha_erros_secao_idx"]) != idx:
        ss.pop("ficha_erros_secao", None)
        ss.pop("ficha_erros_secao_idx", None)

    rotulo_curto = _tab_label(sec)
    st.caption(f"Só mais um pouco: **{idx + 1}** de **{n}** · {rotulo_curto}")
    pct = 100.0 * float(idx + 1) / float(n)
    st.markdown(
        f'<div class="ficha-etapas-progress" role="progressbar" '
        f'aria-valuenow="{idx + 1}" aria-valuemin="1" aria-valuemax="{n}" '
        f'aria-label="Progresso das etapas do cadastro">'
        f'<div class="ficha-etapas-progress-track">'
        f'<div class="ficha-etapas-progress-fill" style="width:{pct:.4f}%"></div>'
        f"</div></div>",
        unsafe_allow_html=True,
    )

    with _section_container():
        st.markdown(
            f'<p class="section-head">{sec}</p>',
            unsafe_allow_html=True,
        )
        # Campos que controlam visibilidade de outros devem ficar FORA do st.form: dentro do form
        # o Streamlit só sincroniza o state no envio, então «Sim» em CRECI não mostraria os demais campos.
        dados_sec = _coletar_dados_formulario_completo()
        if sec == "CRECI/TTI":
            c_pc = next((c for c in CAMPOS if c["key"] == "possui_creci"), None)
            if c_pc:
                _widget_campo(c_pc)
            dados_sec = _coletar_dados_formulario_completo()
            cols = [
                c
                for c in campos_por_secao_visiveis(sec, dados_sec)
                if c["key"] != "possui_creci"
            ]
        elif sec == "Informações para contato":
            c_un = next((c for c in CAMPOS if c["key"] == "unidade_negocio"), None)
            if c_un:
                _widget_campo(c_un)
            dados_sec = _coletar_dados_formulario_completo()
            cols = [
                c
                for c in campos_por_secao_visiveis(sec, dados_sec)
                if c["key"] != "unidade_negocio"
            ]
        else:
            cols = campos_por_secao_visiveis(sec, dados_sec)

        mid = (len(cols) + 1) // 2
        # st.form: ao usar «Avançar» / «Enviar», todos os valores da etapa são gravados de uma vez
        # (evita depender de Enter ou blur em text_input/select).
        form_key = f"ficha_etapa_{idx}"
        with st.form(form_key, clear_on_submit=False, border=False):
            if len(cols) <= 3:
                for c in cols:
                    _widget_campo(c)
            else:
                left, right = st.columns(2)
                for i, c in enumerate(cols):
                    with left if i < mid else right:
                        _widget_campo(c)

            st.markdown("<br/>", unsafe_allow_html=True)
            if idx < n - 1:
                col_voltar, col_avancar = st.columns(2)
                with col_voltar:
                    clicou_voltar = st.form_submit_button(
                        "Voltar",
                        use_container_width=True,
                        disabled=(idx <= 0),
                    )
                with col_avancar:
                    clicou_avancar = st.form_submit_button(
                        "Avançar",
                        type="primary",
                        use_container_width=True,
                    )
            else:
                st.markdown(
                    '<p id="ficha-hp-anchor" style="display:none" aria-hidden="true"></p>',
                    unsafe_allow_html=True,
                )
                st.text_input(
                    "Company website",
                    key="ficha_hp_website",
                    label_visibility="collapsed",
                    max_chars=96,
                )
                st.markdown(
                    '<div class="ficha-input-label">Estou de acordo com o uso dos meus dados para o '
                    "credenciamento na Direcional, conforme a LGPD. "
                    '<span class="ficha-star-req" aria-hidden="true">*</span></div>',
                    unsafe_allow_html=True,
                )
                st.checkbox(
                    "Estou de acordo com o uso dos meus dados para o credenciamento na Direcional, conforme a LGPD. "
                    "(campo obrigatório)",
                    key="fld_lgpd_ficha",
                    label_visibility="collapsed",
                )
                col_voltar, col_enviar = st.columns(2)
                with col_voltar:
                    clicou_voltar = st.form_submit_button(
                        "Voltar",
                        use_container_width=True,
                        disabled=(len(secoes) <= 1),
                    )
                with col_enviar:
                    clicou_enviar = st.form_submit_button(
                        "Enviar meu cadastro",
                        type="primary",
                        use_container_width=True,
                    )

        if idx < n - 1:
            if clicou_voltar:
                ss["ficha_secao_idx"] = idx - 1
                ss.pop("ficha_erros_secao", None)
                ss.pop("ficha_erros_secao_idx", None)
                st.rerun()
            if clicou_avancar:
                dados = _coletar_dados_formulario_completo()
                erros_sec = validar_obrigatorios_secao(sec, dados)
                if erros_sec:
                    ss["ficha_erros_secao"] = erros_sec
                    ss["ficha_erros_secao_idx"] = idx
                    st.rerun()
                _snapshot_persistir_secao_atual(sec)
                _snapshot_mesclar_todos_fld_do_session_state()
                ss.pop("ficha_erros_secao", None)
                ss.pop("ficha_erros_secao_idx", None)
                ss["ficha_secao_idx"] = idx + 1
                st.rerun()
        else:
            if clicou_voltar:
                ss.pop("ficha_erros_envio", None)
                ss["ficha_secao_idx"] = max(0, len(secoes) - 2)
                st.rerun()
            if clicou_enviar:
                _processar_envio_cadastro()

        if ss.get("ficha_erros_secao_idx") == idx and ss.get("ficha_erros_secao"):
            lista = "<br>".join(f"• {html.escape(e)}" for e in ss["ficha_erros_secao"])
            _alert_vermelho_html(
                f"<strong>Preencha os campos obrigatórios desta etapa:</strong><br>{lista}"
            )


def _limpar_session_formulario():
    for c in CAMPOS:
        sk = f"fld_{c['key']}"
        if sk in st.session_state:
            del st.session_state[sk]
    for k in (
        "fld_lgpd_ficha",
        "fc_mail_extra",
        "fc_mail_extra_popup",
        "ficha_sucesso",
        "ficha_secao_idx",
        "ficha_erros_secao",
        "ficha_erros_secao_idx",
        "ficha_snap_campos",
        "ficha_email_boas_vindas_ok",
        "ficha_email_boas_vindas_msg",
        "ficha_erros_envio",
        "ficha_seg_t0",
        "ficha_rl_envios_ts",
        "ficha_hp_website",
        "ficha_popup_recursos_ok",
        "ficha_modo_teste_design",
    ):
        if k in st.session_state:
            del st.session_state[k]


def _design_teste_habilitado() -> bool:
    """Modo teste de layout: env `FICHA_DESIGN_TEST=1` ou URL `?design_test=1`."""
    if (os.environ.get("FICHA_DESIGN_TEST") or "").strip().lower() in ("1", "true", "yes", "on"):
        return True
    try:
        v = st.query_params.get("design_test", "")
        return str(v).strip().lower() in ("1", "true", "yes", "on")
    except Exception:
        return False


def _design_teste_expander_aberto() -> bool:
    try:
        v = st.query_params.get("design_test", "")
        return str(v).strip().lower() in ("1", "true", "yes", "on")
    except Exception:
        return False


def _dados_ficha_demo_design() -> dict[str, Any]:
    """Dados fictícios para pré-visualizar PDF e e-mail no modo teste de design."""
    demo: dict[str, Any] = {}
    for c in CAMPOS:
        k = c["key"]
        tipo = c["tipo"]
        op = c.get("opcoes") or []
        if tipo == "multiselect":
            cand = [x for x in op if x and str(x).strip() and x != "--Nenhum--"]
            demo[k] = [cand[0]] if cand else ["RJ"]
        elif tipo == "select":
            cand = [x for x in op if x and str(x).strip() and x != "--Nenhum--"]
            demo[k] = cand[0] if cand else "—"
        elif tipo == "date":
            demo[k] = date(1990, 5, 15)
        elif tipo == "number":
            demo[k] = 1.0
        elif tipo == "checkbox":
            demo[k] = True
        elif tipo == "id":
            demo[k] = ""
        else:
            demo[k] = f"[Preview] {c['label'][:48]}"
    demo["nome_completo"] = "Maria Silva Santos (pré-visualização design)"
    opts = _opcoes_nome_conta()
    demo["account_name"] = opts[0] if opts else (NOMES_CONTA_FIXOS[0] if NOMES_CONTA_FIXOS else "Conta demo")
    demo["cpf"] = "123.456.789-09"
    demo["email"] = "maria.silva.demo@exemplo.com.br"
    demo["mobile"] = "(21) 99999-0000"
    return enriquecer_derivados_vendas_rj(demo)


def _ativar_cenario_teste_design() -> None:
    """Simula sucesso + popup sem planilha/Salesforce; preenche dados demo para ver PDF/e-mail."""
    ss = st.session_state
    ss["ficha_sucesso"] = True
    ss["ficha_popup_recursos_ok"] = False
    ss["ficha_modo_teste_design"] = True
    ss["ficha_dados_enviados"] = _dados_ficha_demo_design()
    ss["sf_contact_id"] = None
    ss["sf_erro"] = None
    ss["sf_avisos"] = []


def _processar_envio_cadastro() -> None:
    """Grava planilha, tenta Salesforce e define tela de sucesso."""
    ss = st.session_state
    ss.pop("ficha_erros_envio", None)
    ok_sec, msg_sec = verificar_antes_envio()
    if not ok_sec:
        ss["ficha_erros_envio"] = {"kind": "text", "text": msg_sec}
        return
    secoes_env = secoes_com_campos_visiveis()
    idx_env = max(0, min(int(ss.get("ficha_secao_idx", 0)), len(secoes_env) - 1))
    if secoes_env:
        _snapshot_persistir_secao_atual(secoes_env[idx_env])
    # Última etapa: valores do form acabam de entrar no session_state; etapas antigas já no snap.
    _snapshot_mesclar_todos_fld_do_session_state()
    dados = enriquecer_derivados_vendas_rj(_coletar_dados_formulario_completo())
    erros = validar_obrigatorios(dados)
    if not ss.get("fld_lgpd_ficha"):
        erros.append("Concordância LGPD *")
    if erros:
        ss["ficha_erros_envio"] = {"kind": "validation", "items": erros}
        return

    ss.pop("ficha_modo_teste_design", None)

    creds = _credenciais_de_secrets(st.secrets if hasattr(st, "secrets") else None)
    if not creds:
        ss["ficha_erros_envio"] = {
            "kind": "text",
            "text": (
                "Configure **[google_sheets]** nos Secrets com `SERVICE_ACCOUNT_JSON` "
                "(JSON da conta de serviço com acesso à planilha)."
            ),
        }
        return

    gs = {}
    if hasattr(st, "secrets"):
        try:
            gs = dict(st.secrets.get("google_sheets", {}))
        except Exception:
            gs = {}
    sid = str(gs.get("SPREADSHEET_ID", DEFAULT_SPREADSHEET_ID))
    wname = str(gs.get("WORKSHEET_NAME", DEFAULT_WORKSHEET_NAME))

    linha = linha_planilha(dados)
    cab = cabecalho_planilha()

    try:
        row_num = anexar_linha(linha, cab, sid, wname, creds)
    except Exception as e:
        ss["ficha_erros_envio"] = {
            "kind": "html",
            "html": f"<strong>Erro ao gravar na planilha:</strong> {html.escape(str(e))}",
        }
        return

    ss["ficha_dados_enviados"] = dados
    ss["sf_contact_id"] = None
    ss["sf_erro"] = None
    ss["sf_avisos"] = []

    _aplicar_secrets_sf()
    if not _credenciais_salesforce_ok():
        atualizar_status_envio_salesforce(
            sid, wname, creds, row_num, "Erro", "Salesforce não configurado (Secrets USER/PASSWORD/TOKEN).", ""
        )
        ss["sf_erro"] = "Salesforce não configurado nos Secrets."
        _tentar_enviar_email_boas_vindas(dados, None)
        ss["ficha_sucesso"] = True
        st.rerun()
        return

    if not _SF_SDK_DISPONIVEL:
        atualizar_status_envio_salesforce(
            sid, wname, creds, row_num, "Erro", "simple_salesforce não instalado.", ""
        )
        ss["sf_erro"] = "Pacote simple_salesforce não instalado (veja requirements.txt)."
        _tentar_enviar_email_boas_vindas(dados, None)
        ss["ficha_sucesso"] = True
        st.rerun()
        return

    payload, avisos = montar_payload_salesforce(dados)
    avisos = list(avisos)
    avisos.extend(_enriquecer_mobile_phone(payload, dados))

    with st.spinner("Conectando ao Salesforce e criando contato..."):
        sf = conectar_salesforce()
    if not sf:
        atualizar_status_envio_salesforce(
            sid, wname, creds, row_num, "Erro", "Falha ao conectar ao Salesforce (credenciais ou rede).", ""
        )
        ss["sf_erro"] = "Falha ao conectar ao Salesforce."
        ss["sf_avisos"] = avisos
        _tentar_enviar_email_boas_vindas(dados, None)
        ss["ficha_sucesso"] = True
        st.rerun()
        return

    cid, err = criar_contato_payload(sf, payload)
    link = _url_contact(cid) if cid else ""

    if cid:
        atualizar_status_envio_salesforce(sid, wname, creds, row_num, "Sucesso", "", link)
        ss["sf_contact_id"] = cid
        ss["sf_erro"] = None
    else:
        err_full = _explicacao_erro_record_type_se_aplicavel(err)
        atualizar_status_envio_salesforce(sid, wname, creds, row_num, "Erro", err_full[:49000], "")
        ss["sf_erro"] = err_full if err else "Erro desconhecido ao criar contato."

    ss["sf_avisos"] = avisos
    _tentar_enviar_email_boas_vindas(dados, cid if cid else None)
    ss["ficha_sucesso"] = True
    st.rerun()


@st.dialog("Obrigado — você faz parte da nossa operação", width="medium")
def _dialog_recursos_pos_cadastro() -> None:
    """Popup ao concluir o cadastro: mapa, vídeo e links úteis."""
    ss = st.session_state

    st.markdown(
        """
**Recebemos o seu cadastro com sucesso.** Você deve ter recebido **automaticamente** no seu e-mail do cadastro
uma mensagem com **apresentação da Direcional**, **links de materiais de vendas** e, quando possível, o **PDF da ficha** em anexo.

Aqui no popup: **mapa** de empreendimentos, **vídeo** do simulador e **links** úteis.
        """.strip()
    )
    st.markdown("##### Empreendimentos no mapa")
    st.caption(
        "Minimapa: **+** / **−** para zoom, arraste para mover e **tela cheia** no canto superior direito."
    )
    try:
        from empreendimentos_mapa import render_mapa_empreendimentos_streamlit

        render_mapa_empreendimentos_streamlit(
            altura_px=POPUP_MAPA_ALTURA_PX,
            streamlit_key="mapa_empreendimentos_folium_popup_v3",
        )
    except Exception as e:
        st.caption(f"Mapa indisponível: {e}")
    st.markdown("##### Como usar o simulador")
    st.markdown(
        f'<div class="ficha-popup-video-wrap" style="height:{POPUP_MAPA_ALTURA_PX}px;">'
        f'<iframe class="ficha-popup-video" src="{html.escape(URL_YOUTUBE_SIMULADOR_EMBED)}" '
        f'title="Como usar o simulador de negociação" loading="lazy" '
        f'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" '
        f"allowfullscreen referrerpolicy=\"strict-origin-when-cross-origin\"></iframe>"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.caption(f"Abrir no YouTube: [{URL_YOUTUBE_SIMULADOR}]({URL_YOUTUBE_SIMULADOR})")

    st.markdown("##### Links úteis")
    st.link_button(
        "Materiais de marketing (Linktree)",
        URL_LINKTREE_MARKETING,
        use_container_width=True,
    )
    st.link_button(
        "Pedir acesso ao simulador de negociação",
        URL_FORM_SIMULADOR,
        use_container_width=True,
    )
    st.link_button(
        "Treinamentos — Diri Academy",
        URL_DIRI_ACADEMY,
        use_container_width=True,
    )
    st.link_button(
        "Salesforce (portal de vendas)",
        URL_SALESFORCE_VENDAS,
        use_container_width=True,
    )
    st.link_button(
        "Entrar no grupo — WhatsApp",
        URL_WHATSAPP_EQUIPE,
        use_container_width=True,
    )

    st.markdown("")
    if st.button("Finalizar", type="primary", use_container_width=True, key="ficha_dialog_recursos_fechar"):
        ss["ficha_popup_recursos_ok"] = True
        st.rerun()


def main():
    fav = _resolver_png_raiz(FAVICON_ARQUIVO)
    st.set_page_config(
        page_title="Credenciamento | Direcional Vendas RJ",
        page_icon=str(fav) if fav else None,
        layout="centered",
        initial_sidebar_state="expanded" if FICHA_TEST_PLANILHA_ATIVO else "collapsed",
    )
    _aplicar_secrets_sf()
    aplicar_estilo()
    injetar_cliente_e_meta()

    ss = st.session_state
    ss.setdefault("ficha_sucesso", False)

    if _teste_planilha_sf_habilitado():
        _render_sidebar_teste_planilha_sf()

    if ss.get("ficha_sucesso"):
        if not ss.get("ficha_popup_recursos_ok"):
            _dialog_recursos_pos_cadastro()

        if ss.get("ficha_modo_teste_design"):
            _alert_azul(
                "**Modo teste de design:** nenhum dado foi enviado para planilha ou Salesforce. "
                "Os campos do PDF/e-mail estão preenchidos com **dados fictícios** para pré-visualização. "
                "Use **Finalizar** no popup para fechá-lo e conferir o restante da tela."
            )

        _cabecalho_pagina()
        cid = ss.get("sf_contact_id")
        err_sf = ss.get("sf_erro")
        if cid:
            _alert_azul(
                "**Recebemos o seu cadastro.** Tudo certo por aqui — guarde o link abaixo se quiser consultar depois."
            )
        elif err_sf:
            _alert_azul(
                "**Recebemos o seu cadastro.** Se aparecer um aviso técnico abaixo, nossa equipe pode te ajudar."
            )
        else:
            _alert_azul("**Recebemos o seu cadastro.** Confira os detalhes abaixo.")
        if cid:
            url_reg = html.escape(_url_contact(cid))
            st.markdown(
                f'<div class="ficha-alert ficha-alert--azul"><strong>Seu registro:</strong> '
                f'<a href="{url_reg}" target="_blank" rel="noopener">Abrir cadastro</a></div>',
                unsafe_allow_html=True,
            )
        elif err_sf:
            _alert_vermelho_html(
                f"<strong>Detalhe:</strong> {_html_erro_salesforce_multilinha(err_sf)}"
            )

        avisos = ss.get("sf_avisos") or []
        if avisos:
            lista = "<br>".join(f"• {html.escape(a)}" for a in avisos)
            _alert_vermelho_html(f"<strong>Avisos:</strong><br>{lista}")

        ok_mail = ss.get("ficha_email_boas_vindas_ok")
        msg_mail = ss.get("ficha_email_boas_vindas_msg") or ""
        if ok_mail is True:
            _alert_azul(
                "**Enviamos um e-mail automático** para o endereço do cadastro com **apresentação da Direcional**, "
                "**materiais e links de vendas**, **PDF da ficha em anexo** (quando a geração funcionar) e link do "
                "Salesforce, se o contato tiver sido criado."
            )
        elif ok_mail is False and msg_mail:
            _alert_vermelho_html(
                f"<strong>E-mail automático:</strong> {html.escape(msg_mail)} "
                "(confira [ficha_email] nos Secrets e o campo <strong>E-mail</strong> no formulário.)"
            )

        st.caption(
            "No popup: mapa, vídeo e links úteis. O **e-mail principal** (com apresentação, links e PDF) "
            "já foi disparado para o e-mail do formulário ao concluir o envio."
        )

        if st.button("Começar um novo cadastro", use_container_width=True):
            _limpar_session_formulario()
            ss["ficha_sucesso"] = False
            ss.pop("ficha_dados_enviados", None)
            ss.pop("sf_contact_id", None)
            ss.pop("sf_erro", None)
            ss.pop("sf_avisos", None)
            ss.pop("ficha_secao_idx", None)
            ss.pop("ficha_popup_recursos_ok", None)
            ss.pop("ficha_email_boas_vindas_ok", None)
            ss.pop("ficha_email_boas_vindas_msg", None)
            st.rerun()

        st.markdown(
            '<div class="footer">Direcional Engenharia · Vendas Rio de Janeiro<br/>developed by lucas maia</div>',
            unsafe_allow_html=True,
        )
        return

    _cabecalho_pagina(com_intro_formulario=True)

    if _design_teste_habilitado():
        with st.expander(
            "Modo teste de design — popup e tela de sucesso (sem enviar dados)",
            expanded=_design_teste_expander_aberto(),
        ):
            st.markdown(
                "Simula o **cadastro concluído**: abre o **popup** (mapa, vídeo, links, PDF e e-mail) e a **tela de sucesso**, "
                "sem gravar na planilha Google nem no Salesforce. O PDF e o e-mail usam **dados fictícios** para você ver o layout."
            )
            st.caption(
                "Ative este bloco com a variável de ambiente **FICHA_DESIGN_TEST=1** "
                "ou com **?design_test=1** na URL (o expander abre já expandido)."
            )
            if st.button(
                "Simular cadastro enviado e abrir o popup",
                type="secondary",
                key="ficha_simular_sucesso_design",
            ):
                _ativar_cenario_teste_design()
                st.rerun()

    _init_defaults()
    iniciar_sessao_formulario()
    secoes = secoes_com_campos_visiveis()
    _render_secao_formulario(secoes)

    fe = ss.get("ficha_erros_envio")
    if fe:
        kind = fe.get("kind")
        if kind == "validation":
            linhas = "<br>".join(f"• {html.escape(e)}" for e in fe.get("items") or [])
            _alert_vermelho_html(
                f"<strong>Quase lá</strong> — falta completar:<br>{linhas}"
            )
        elif kind == "html":
            _alert_vermelho_html(fe.get("html") or "")
        elif kind == "text":
            _alert_vermelho(fe.get("text") or "")


if __name__ == "__main__":
    main()
