# -*- coding: utf-8 -*-
"""
Ficha de credenciamento — Direcional Vendas RJ (corretores).
APP 1: FORMULÁRIO DE ENTRADA DE DADOS
"""
from __future__ import annotations

import base64
import html
import io
import json
import logging
import os
import platform
import re
import smtplib
import sys
import time
import traceback
from datetime import date, datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape as _xml_escape_para_pdf
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests
import streamlit as st

_DIR_APP = Path(__file__).resolve().parent
_LOG_FICHA = logging.getLogger(__name__)

# --- Salesforce (simple_salesforce) ---
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
        err_msg = str(e)
        err_trace = traceback.format_exc()
        err_kind = type(e).__name__
        return None, f"[{err_kind}] {err_msg}\n\n{err_trace}"

def _explicacao_erro_record_type_se_aplicavel(err: Any) -> str:
    base = (str(err).strip() if err is not None else "") or "Erro desconhecido"
    u = base.upper()
    compact = u.replace(" ", "")
    if "INVALID_CROSS_REFERENCE_KEY" not in compact:
        return base
    return (
        base
        + "\n\n▸ O Id na URL (prefixo **012**) em geral está correto. Este erro indica que o **usuário da integração** "
        "(login em [salesforce] **USER** nos Secrets) **não pode usar esse Record Type** no objeto Contact.\n"
    )

def _html_erro_salesforce_multilinha(msg: Any) -> str:
    return html.escape(str(msg)).replace("\n", "<br/>")

def _registrar_debug_envio(etapa: str, detalhe: Any = "") -> None:
    ss = st.session_state
    trilha = list(ss.get("ficha_debug_envio") or [])
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    txt = str(detalhe or "").strip()
    trilha.append({"ts": stamp, "etapa": str(etapa or "").strip() or "evento", "detalhe": txt[:8000]})
    ss["ficha_debug_envio"] = trilha[-120:]

# =============================================================================
# CAMPOS E CONFIGURAÇÕES
# =============================================================================
RECORD_TYPE_CORRETOR = ""
_SF_ID_15_18 = re.compile(r"^[a-zA-Z0-9]{15}(?:[a-zA-Z0-9]{3})?$")

def _id_e_record_type_plausivel(rid: str) -> bool:
    if not rid or len(rid) < 3 or not _SF_ID_15_18.match(rid):
        return False
    return rid[:3] == "012"

_EMAIL_CONTATO_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

def email_contato_formato_valido(val: Any) -> bool:
    s = (str(val).strip() if val is not None else "") or ""
    if not s or len(s) > 254:
        return False
    return bool(_EMAIL_CONTATO_RE.match(s))

_EMAIL_CORP_MARKERS = (".direcionalvendas", ".rivavendas")
_MSG_EMAIL_CORPORATIVO_OBRIGATORIO = "E-mail * — use o **e-mail corporativo** com **.direcionalvendas** ou **.rivavendas** no login."

def email_corporativo_direcionalvendas_obrigatorio(val: Any) -> bool:
    if not email_contato_formato_valido(val): return False
    s = (str(val).strip() if val is not None else "").lower()
    return any(marker in s for marker in _EMAIL_CORP_MARKERS)

def record_type_id_contato_payload_e_aviso() -> Tuple[str, str]:
    for candidate in ((os.environ.get("SF_RECORD_TYPE_ID") or "").strip(), (RECORD_TYPE_CORRETOR or "").strip()):
        if not candidate: continue
        if not _SF_ID_15_18.match(candidate): continue
        if _id_e_record_type_plausivel(candidate): return candidate, ""
        return ("", "Secrets [salesforce] RECORD_TYPE_ID está incorreto.")
    return "", ""

SEC_ORDER: Tuple[str, ...] = ("Dados Pessoais", "Endereço", "Dados para Contato", "Dados Familiares", "Dados Bancários Pessoa Física", "Informações para contato", "CRECI/TTI", "Preferência de contato", "Dados de Usuário", "Dados Integração")

SF_OMIT_INSERT = frozenset({"Blacklist__c", "RetornoIntegracaoContaBancaria__c", "C_digo_Pessoa_UAU__c", "Corretor_Associado__c", "MultiplicadorFinal__c", "Contact_ID__c", "ErroIntegracaoUAU__c", "RetornoIntegracaoPessoa__c", "Data_Descredenciamento__c", "Origem__c"})

REGIONAIS = ["--Nenhum--", "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"]
ORIGENS = ["--Nenhum--", "RH", "Indicação", "Gerente", "Diretor", "DiRi Talent", "Coordenador", "Gupy", "MARINHA", "Creci", "Parceria Estácio"]
STATUS_CORRETOR = ["--Nenhum--", "Ativo", "Inativo", "Pré credenciado", "Reativado"]
SALUTATIONS = ["--Nenhum--", "Sr.", "Sra.", "Dr.", "Dra."]
SEXOS = ["--Nenhum--", "Masculino", "Feminino"]
CAMISETAS = ["--Nenhum--", "PP", "P", "M", "G", "GG", "XGG"]
UNIDADE_REDE_OUTRA_IMOBILIARIA = "Outra imobiliária (parceira)"
UNIDADES_NEGOCIO = ["--Nenhum--", "Direcional", "Riva", UNIDADE_REDE_OUTRA_IMOBILIARIA]
_UNIDADE_NEGOCIO_UI_PARA_SF: Dict[str, str] = {"Direcional": "Direcional", "Riva": "Riva", UNIDADE_REDE_OUTRA_IMOBILIARIA: UNIDADE_REDE_OUTRA_IMOBILIARIA}
ATIVIDADE_VENDAS_RJ_OPTS = ["--Nenhum--", "Corretor Parceiro", "Corretor", "Captador"]
TIPO_PIX = ["--Nenhum--", "CPF", "CNPJ", "E-mail", "Celular", "Chave aleatória"]
ESTADOS_UF = ["--Nenhum--", "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"]
CAPITAL_POR_UF_BR: Dict[str, str] = {"AC": "Rio Branco", "AL": "Maceió", "AM": "Manaus", "AP": "Macapá", "BA": "Salvador", "CE": "Fortaleza", "DF": "Brasília", "ES": "Vitória", "GO": "Goiânia", "MA": "São Luís", "MG": "Belo Horizonte", "MS": "Campo Grande", "MT": "Cuiabá", "PA": "Belém", "PB": "João Pessoa", "PE": "Recife", "PI": "Teresina", "PR": "Curitiba", "RJ": "Rio de Janeiro", "RN": "Natal", "RO": "Porto Velho", "RR": "Boa Vista", "RS": "Porto Alegre", "SC": "Florianópolis", "SE": "Aracaju", "SP": "São Paulo", "TO": "Palmas"}

def _naturalidade_capital_por_uf(uf: Any) -> str:
    s = (str(uf).strip() if uf is not None else "")
    return CAPITAL_POR_UF_BR.get(s, "")

POSSUI_FILHOS = ["--Nenhum--", "Sim", "Não"]
TIPO_CONTA_BANCARIA = ["--Nenhum--", "Corrente", "Poupança"]
_ESTADO_CIVIL = ["Solteiro", "Casado", "Divorciado", "Viúvo"]
_ESCOLARIDADE = ["Ensino Fundamental", "Ensino Médio", "Superior em Andamento", "Superior Completo", "Mestrado em Andamento", "Mestrado Concluído", "Doutorado em Andamento", "Doutorado Concluído"]
_NACIONALIDADE = ["Brasileiro", "Estrangeira", "Espanhola"]
_ATIVIDADE = ["Captador", "Estagiário", "Corretor", "Coordenador", "Gerente de Vendas", "Gerente Regional", "Diretor", "Gerente", "Captador Recruta+", "Gerente Recruta+", "Corretor N1", "Gerente de Vendas N1", "Diretor de Vendas", "Analista", "Assistente", "Cliente", "Coordenador de Produto", "Coordenador de Vendas", "Diretor de Incorporação", "Gerente Comercial", "Gerente de Parcerias", "Imobiliária Parceira", "Pasteiro (a)", "Superintendente", "Supervisor", "Autônomo Parceiro", "Corretor Parceiro", "Recepção", "Coordenador de Parcerias"]
_TIPO_CORRETOR = ["Direcional Vendas – GRI (CLT)", "Direcional Vendas – Autônomos", "Parceiros (Externo)"]
_STATUS_CRECI = ["Concluído Provas", "Definitivo", "Estágio", "Matriculado", "Pendente", "Protocolo Definitivo", "Protocolo Estágio", "Pendente Prova"]
_BANCO = ["001 – Banco do Brasil S.A.", "004 - BANCO DO NORDESTE DO BRASIL S.A.", "033 – Banco Santander (Brasil) S.A.", "070 - BCO BRB SA - BRASILIA", "104 – Caixa Econômica Federal", "237 – Banco Bradesco S.A.", "260 – Banco Nubank", "341 – Banco Itaú S.A."]

ESTADO_CIVIL_OPTS = ["--Nenhum--"] + _ESTADO_CIVIL
ESCOLARIDADE_OPTS = ["--Nenhum--"] + _ESCOLARIDADE
NACIONALIDADE_OPTS = ["--Nenhum--"] + _NACIONALIDADE
ATIVIDADE_OPTS = ["--Nenhum--"] + _ATIVIDADE
TIPO_CORRETOR_OPTS = ["--Nenhum--"] + _TIPO_CORRETOR
STATUS_CRECI_OPTS = ["--Nenhum--"] + _STATUS_CRECI
BANCO_OPTS = ["--Nenhum--"] + _BANCO
PREFERRED_METHOD_OPTS = ["Telefone de Trabalho", "Telefone residencial", "Celular", "Email de trabalho", "Email pessoal", "Sem preferência"]
NOMES_CONTA_FIXOS: Tuple[str, ...] = ("RH",)

def _z(**kw) -> Dict[str, Any]: return kw

def _campos_def() -> List[Dict[str, Any]]:
    return [
        _z(key="account_id", label="Nome da conta — Id (Account)", sec="Informações para contato", tipo="id", sf="AccountId", req=False),
        _z(key="owner_id", label="Proprietário do contato", sec="Informações para contato", tipo="id", sf="OwnerId", req=False),
        _z(key="gerente_vendas", label="Gerente de vendas *", sec="Informações para contato", tipo="select", sf="AccountId", opcoes=["--Nenhum--"], req=True),
        _z(key="nome_completo", label="Nome completo *", sec="Dados Pessoais", tipo="text", sf=None, req=True),
        _z(key="salutation", label="Tratamento", sec="Informações para contato", tipo="select", sf="Salutation", opcoes=SALUTATIONS, req=False),
        _z(key="apelido", label="Apelido", sec="Informações para contato", tipo="text", sf="Apelido__c", req=False),
        _z(key="status_corretor", label="Status Corretor *", sec="Informações para contato", tipo="select", sf="Status_Corretor__c", opcoes=STATUS_CORRETOR, req=True),
        _z(key="regional", label="Regional *", sec="Informações para contato", tipo="select", sf="Regional__c", opcoes=REGIONAIS, req=True),
        _z(key="origem", label="Origem *", sec="Informações para contato", tipo="select", sf="Origem__c", opcoes=ORIGENS, req=True),
        _z(key="sexo", label="Sexo *", sec="Informações para contato", tipo="select", sf="Sexo__c", opcoes=SEXOS, req=True),
        _z(key="camiseta", label="Camiseta *", sec="Informações para contato", tipo="select", sf="Camiseta__c", opcoes=CAMISETAS, req=True),
        _z(key="unidade_negocio", label="Fará parte de qual rede? *", sec="Informações para contato", tipo="select", sf="Unidade_Negocio__c", opcoes=UNIDADES_NEGOCIO, req=True),
        _z(key="atividade", label="Função na operação *", sec="Informações para contato", tipo="select", sf="Atividade__c", opcoes=ATIVIDADE_OPTS, req=True),
        _z(key="escolaridade", label="Escolaridade", sec="Informações para contato", tipo="select", sf="Escolaridade__c", opcoes=ESCOLARIDADE_OPTS, req=False),
        _z(key="birthdate", label="Data de nascimento *", sec="Dados Pessoais", tipo="date", sf="Birthdate", req=True),
        _z(key="estado_civil", label="Estado Civil *", sec="Dados Pessoais", tipo="select", sf="EstadoCivil__c", opcoes=ESTADO_CIVIL_OPTS, req=True),
        _z(key="nome_conjuge", label="Nome do Cônjuge", sec="Dados Pessoais", tipo="text", sf="Nome_do_Conjuge__c", req=False),
        _z(key="cpf", label="CPF *", sec="Dados Pessoais", tipo="text", sf="CPF__c", req=True),
        _z(key="nacionalidade", label="Nacionalidade *", sec="Dados Pessoais", tipo="select", sf="Nacionalidade__c", opcoes=NACIONALIDADE_OPTS, req=True),
        _z(key="uf_naturalidade", label="UF Naturalidade *", sec="Dados Pessoais", tipo="select", sf="UF_Naturalidade__c", opcoes=ESTADOS_UF, req=True),
        _z(key="naturalidade", label="Naturalidade *", sec="Dados Pessoais", tipo="text", sf="Naturalidade__c", req=True),
        _z(key="rg", label="RG *", sec="Dados Pessoais", tipo="text", sf="RG__c", req=True),
        _z(key="uf_rg", label="UF RG *", sec="Dados Pessoais", tipo="select", sf="UF_RG__c", opcoes=ESTADOS_UF, req=True),
        _z(key="tipo_pix", label="Tipo do PIX *", sec="Dados Pessoais", tipo="select", sf="Tipo_do_PIX__c", opcoes=TIPO_PIX, req=True),
        _z(key="dados_pix", label="Dados para PIX *", sec="Dados Pessoais", tipo="text", sf="Dados_para_PIX__c", req=True),
        _z(key="endereco_cep", label="CEP *", sec="Endereço", tipo="text", sf="EnderecoResidencialCEP__c", req=True),
        _z(key="endereco_logradouro", label="Logradouro *", sec="Endereço", tipo="text", sf="EnderecoResidencialLogradouro__c", req=True),
        _z(key="endereco_numero", label="Número *", sec="Endereço", tipo="text", sf="EnderecoResidencialNumero__c", req=True),
        _z(key="endereco_complemento", label="Complemento", sec="Endereço", tipo="text", sf="EnderecoResidencialComplemento__c", req=False),
        _z(key="endereco_bairro", label="Bairro *", sec="Endereço", tipo="text", sf="EnderecoResidencialBairro__c", req=True),
        _z(key="endereco_cidade", label="Cidade *", sec="Endereço", tipo="text", sf="EnderecoResidencialCidade__c", req=True),
        _z(key="endereco_estado", label="Estado (UF) *", sec="Endereço", tipo="select", sf="EnderecoResidencialEstado__c", opcoes=ESTADOS_UF, req=True),
        _z(key="mobile", label="Celular *", sec="Dados para Contato", tipo="text", sf="MobilePhone", req=True),
        _z(key="email", label="E-mail *", sec="Dados para Contato", tipo="text", sf="Email", req=True),
        _z(key="nome_mae", label="Nome da Mãe *", sec="Dados Familiares", tipo="text", sf="Nome_da_Mae__c", req=True),
        _z(key="nome_pai", label="Nome do Pai *", sec="Dados Familiares", tipo="text", sf="Nome_do_Pai__c", req=True),
        _z(key="possui_filhos", label="Possui Filho(s)?", sec="Dados Familiares", tipo="select", sf="Possui_Filho__c", opcoes=POSSUI_FILHOS, req=False),
        _z(key="banco", label="Banco *", sec="Dados Bancários Pessoa Física", tipo="select", sf="Banco__c", opcoes=BANCO_OPTS, req=True),
        _z(key="conta_bancaria", label="Conta Bancária *", sec="Dados Bancários Pessoa Física", tipo="text", sf="Conta_Banc_ria__c", req=True),
        _z(key="agencia_bancaria", label="Agência Bancária *", sec="Dados Bancários Pessoa Física", tipo="text", sf="Ag_ncia_Banc_ria__c", req=True),
        _z(key="possui_creci", label="Possui CRECI? *", sec="CRECI/TTI", tipo="select", sf=None, opcoes=["Sim", "Não"], req=True),
        _z(key="status_creci", label="Status CRECI", sec="CRECI/TTI", tipo="select", sf="Status_CRECI__c", opcoes=STATUS_CRECI_OPTS, req=False),
        _z(key="creci", label="CRECI", sec="CRECI/TTI", tipo="text", sf="CRECI__c", req=False),
        _z(key="validade_creci", label="Validade CRECI", sec="CRECI/TTI", tipo="date", sf="Validade_CRECI__c", req=False),
    ]

CAMPOS = _campos_def()
CAMPOS_OCULTOS_FORMULARIO = frozenset({"salutation", "apelido", "status_corretor", "regional", "origem", "account_id", "owner_id"})

# --- Funções de Suporte (Design e Planilha) ---
def aplicar_estilo():
    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@700;900&family=Inter:wght@400;600&display=swap');
        .stApp {{ background: linear-gradient(135deg, #04428f 0%, #cb0935 100%); }}
        .block-container {{ background: rgba(255, 255, 255, 0.9); border-radius: 20px; padding: 2rem !important; }}
        h1, h2, h3 {{ color: #04428f !important; }}
        .section-head {{ font-weight: 800; border-bottom: 2px solid #eee; margin-bottom: 1rem; }}
        </style>
    """, unsafe_allow_html=True)

def _cabecalho_pagina(com_intro_formulario=False):
    st.markdown(f'<h1 style="text-align:center">Credenciamento Direcional RJ</h1>', unsafe_allow_html=True)
    if com_intro_formulario:
        st.info("Preencha as etapas abaixo com atenção. Seus dados serão gravados com segurança.")

def _widget_campo(c):
    k, sk, label, tipo = c["key"], f"fld_{c['key']}", c["label"], c["tipo"]
    if tipo == "text": st.text_input(label, key=sk)
    elif tipo == "select": st.selectbox(label, options=c.get("opcoes", []), key=sk)
    elif tipo == "date": st.date_input(label, key=sk)
    elif tipo == "id": st.text_input(label, key=sk)

def _processar_envio_cadastro():
    ss = st.session_state
    dados = {c["key"]: ss.get(f"fld_{c['key']}") for c in CAMPOS}
    # Lógica de gravação na Planilha
    creds = _credenciais_de_secrets(st.secrets)
    if not creds:
        st.error("Credenciais do Google não configuradas.")
        return
    
    gs = dict(st.secrets.get("google_sheets", {}))
    sid = gs.get("SPREADSHEET_ID", "1_9x4rfHoP2M47qXJENoD3vMLf_7rWUhNjrU8EtESxy8")
    wname = gs.get("WORKSHEET_NAME", "Corretores")
    
    try:
        # Simulação de anexar linha conforme código original
        from google.oauth2.service_account import Credentials
        import gspread
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        gc = gspread.authorize(Credentials.from_service_account_info(creds, scopes=scopes))
        sh = gc.open_by_key(sid)
        ws = sh.worksheet(wname)
        
        linha = [datetime.now().strftime("%d/%m/%Y %H:%M:%S"), ""] + [str(v) for v in dados.values()] + ["Pendente", ""]
        ws.append_row(linha)
        
        ss["ficha_sucesso"] = True
        st.success("Cadastro gravado com sucesso na base!")
    except Exception as e:
        st.error(f"Erro ao salvar na planilha: {e}")

def _credenciais_de_secrets(s):
    try: return json.loads(s["google_sheets"]["SERVICE_ACCOUNT_JSON"])
    except: return None

def main():
    st.set_page_config(page_title="Formulário | Direcional Vendas RJ", layout="centered")
    aplicar_estilo()
    _cabecalho_pagina(com_intro_formulario=True)
    
    if st.session_state.get("ficha_sucesso"):
        st.balloons()
        st.success("Obrigado! Seu cadastro foi recebido.")
        if st.button("Novo Cadastro"):
            st.session_state["ficha_sucesso"] = False
            st.rerun()
        return

    secoes = SEC_ORDER
    ss = st.session_state
    idx = ss.get("step", 0)
    sec = secoes[idx]
    
    st.markdown(f"### Etapa {idx+1}: {sec}")
    cols_sec = [c for c in CAMPOS if c["sec"] == sec and c["key"] not in CAMPOS_OCULTOS_FORMULARIO]
    
    with st.form(f"form_{idx}"):
        for c in cols_sec: _widget_campo(c)
        
        c1, c2 = st.columns(2)
        with c1:
            if idx > 0 and st.form_submit_button("Voltar"):
                ss["step"] = idx - 1
                st.rerun()
        with c2:
            if idx < len(secoes) - 1:
                if st.form_submit_button("Próximo"):
                    ss["step"] = idx + 1
                    st.rerun()
            else:
                if st.form_submit_button("Finalizar e Enviar"):
                    _processar_envio_cadastro()
                    st.rerun()

if __name__ == "__main__":
    main()
