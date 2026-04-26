# -*- coding: utf-8 -*-
"""
Ficha de credenciamento — Direcional Vendas RJ (corretores).
APP 1: FORMULÁRIO DE ENTRADA DE DADOS (DESIGN ORIGINAL)
Cabeçalho de duas linhas: Rótulo (Linha 1) e API Name (Linha 2).
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

# --- Constantes de Design e Identidade ---
COR_AZUL_ESC = "#04428f"
COR_VERMELHO = "#cb0935"
COR_FUNDO = "#04428f"
COR_BORDA = "#eef2f6"
COR_INPUT_BG = "#f0f2f6"
COR_TEXTO_MUTED = "#64748b"
COR_TEXTO_LABEL = "#1e293b"
COR_VERMELHO_ESCURO = "#9e0828"

LOGO_TOPO_ARQUIVO = "502.57_LOGO DIRECIONAL_V2F-01.png"
FAVICON_ARQUIVO = "502.57_LOGO D_COR_V3F.png"
URL_LOGO_DIRECIONAL_EMAIL = "https://logodownload.org/wp-content/uploads/2021/04/direcional-engenharia-logo.png"

URL_YOUTUBE_BOAS_VINDAS_RH_EMBED = "https://www.youtube.com/embed/7cm3wFnoCSY"
POPUP_MAPA_ALTURA_PX = 320

# =============================================================================
# DEFINIÇÃO DE CAMPOS (ORDEM ORGANIZADA PARA A BASE)
# =============================================================================
SEC_ORDER: Tuple[str, ...] = (
    "Dados Pessoais",
    "Endereço",
    "Dados para Contato",
    "Dados Familiares",
    "Dados Bancários Pessoa Física",
    "Informações para contato",
    "CRECI/TTI",
    "Preferência de contato",
)

REGIONAIS = ["--Nenhum--", "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"]
SEXOS = ["--Nenhum--", "Masculino", "Feminino"]
CAMISETAS = ["--Nenhum--", "PP", "P", "M", "G", "GG", "XGG"]
UNIDADES_NEGOCIO = ["--Nenhum--", "Direcional", "Riva", "Outra imobiliária (parceira)"]
ATIVIDADE_VENDAS_RJ_OPTS = ["--Nenhum--", "Corretor Parceiro", "Corretor", "Captador"]
ESTADOS_UF = ["--Nenhum--"] + [u for u in REGIONAIS if u != "--Nenhum--"]

def _z(**kw) -> Dict[str, Any]: return kw

def _campos_def() -> List[Dict[str, Any]]:
    return [
        _z(key="nome_completo", label="Nome completo *", sec="Dados Pessoais", tipo="text", sf="Name", req=True),
        _z(key="birthdate", label="Data de nascimento *", sec="Dados Pessoais", tipo="date", sf="Birthdate", req=True),
        _z(key="estado_civil", label="Estado Civil *", sec="Dados Pessoais", tipo="select", sf="EstadoCivil__c", opcoes=["--Nenhum--", "Solteiro", "Casado", "Divorciado", "Viúvo"], req=True),
        _z(key="nome_conjuge", label="Nome do Cônjuge", sec="Dados Pessoais", tipo="text", sf="Nome_do_Conjuge__c", req=False),
        _z(key="cpf", label="CPF *", sec="Dados Pessoais", tipo="text", sf="CPF__c", req=True),
        _z(key="uf_naturalidade", label="UF Naturalidade *", sec="Dados Pessoais", tipo="select", sf="UF_Naturalidade__c", opcoes=ESTADOS_UF, req=True),
        _z(key="rg", label="RG *", sec="Dados Pessoais", tipo="text", sf="RG__c", req=True),
        _z(key="uf_rg", label="UF RG *", sec="Dados Pessoais", tipo="select", sf="UF_RG__c", opcoes=ESTADOS_UF, req=True),
        _z(key="endereco_cep", label="CEP *", sec="Endereço", tipo="text", sf="EnderecoResidencialCEP__c", req=True),
        _z(key="endereco_logradouro", label="Logradouro *", sec="Endereço", tipo="text", sf="EnderecoResidencialLogradouro__c", req=True),
        _z(key="endereco_numero", label="Número *", sec="Endereço", tipo="text", sf="EnderecoResidencialNumero__c", req=True),
        _z(key="endereco_bairro", label="Bairro *", sec="Endereço", tipo="text", sf="EnderecoResidencialBairro__c", req=True),
        _z(key="endereco_cidade", label="Cidade *", sec="Endereço", tipo="text", sf="EnderecoResidencialCidade__c", req=True),
        _z(key="endereco_estado", label="Estado (UF) *", sec="Endereço", tipo="select", sf="EnderecoResidencialEstado__c", opcoes=ESTADOS_UF, req=True),
        _z(key="mobile", label="Celular *", sec="Dados para Contato", tipo="text", sf="MobilePhone", req=True),
        _z(key="email", label="E-mail *", sec="Dados para Contato", tipo="text", sf="Email", req=True),
        _z(key="nome_mae", label="Nome da Mãe *", sec="Dados Familiares", tipo="text", sf="Nome_da_Mae__c", req=True),
        _z(key="nome_pai", label="Nome do Pai *", sec="Dados Familiares", tipo="text", sf="Nome_do_Pai__c", req=True),
        _z(key="banco", label="Banco *", sec="Dados Bancários Pessoa Física", tipo="select", sf="Banco__c", opcoes=["--Nenhum--", "001 – Banco do Brasil S.A.", "033 – Banco Santander (Brasil) S.A.", "104 – Caixa Econômica Federal", "237 – Banco Bradesco S.A."], req=True),
        _z(key="conta_bancaria", label="Conta Bancária *", sec="Dados Bancários Pessoa Física", tipo="text", sf="Conta_Banc_ria__c", req=True),
        _z(key="agencia_bancaria", label="Agência Bancária *", sec="Dados Bancários Pessoa Física", tipo="text", sf="Ag_ncia_Banc_ria__c", req=True),
        _z(key="gerente_vendas", label="Gerente de vendas *", sec="Informações para contato", tipo="select", sf="AccountId", req=True),
        _z(key="regional", label="Regional *", sec="Informações para contato", tipo="select", sf="Regional__c", opcoes=REGIONAIS, req=True),
        _z(key="sexo", label="Sexo *", sec="Informações para contato", tipo="select", sf="Sexo__c", opcoes=SEXOS, req=True),
        _z(key="camiseta", label="Camiseta *", sec="Informações para contato", tipo="select", sf="Camiseta__c", opcoes=CAMISETAS, req=True),
        _z(key="unidade_negocio", label="Fará parte de qual rede? *", sec="Informações para contato", tipo="select", sf="Unidade_Negocio__c", opcoes=UNIDADES_NEGOCIO, req=True),
        _z(key="atividade", label="Função na operação *", sec="Informações para contato", tipo="select", sf="Atividade__c", opcoes=ATIVIDADE_VENDAS_RJ_OPTS, req=True),
        _z(key="possui_creci", label="Possui CRECI? *", sec="CRECI/TTI", tipo="select", sf="Possui_CRECI__c", opcoes=["Sim", "Não"], req=True),
        _z(key="creci", label="CRECI", sec="CRECI/TTI", tipo="text", sf="CRECI__c", req=False),
        _z(key="status_creci", label="Status CRECI", sec="CRECI/TTI", tipo="select", sf="Status_CRECI__c", opcoes=["--Nenhum--", "Definitivo", "Estágio", "Pendente"], req=False),
    ]

CAMPOS = _campos_def()
CAMPOS_OCULTOS_FORMULARIO = frozenset({"salutation", "apelido", "data_entrevista", "data_contrato", "data_credenciamento"})

# =============================================================================
# LÓGICA DE FORMATAÇÃO E ORGANIZAÇÃO (CRITICAL)
# =============================================================================
def _aplicar_organizacao_planilha(ws: Any):
    """Garante cabeçalho de duas linhas e cores por seção na base."""
    headers_row1 = ["Data Envio", "Link Salesforce"] + [c["label"] for c in CAMPOS] + ["Envio?", "Log / erro"]
    headers_row2 = ["Timestamp", "Salesforce_Link"] + [c["sf"] if c["sf"] else "N/A" for c in CAMPOS] + ["Status_Envio", "Log_Erro"]
    
    # Limpa e reseta se estiver vazio
    if not ws.get_all_values():
        ws.update("A1", [headers_row1, headers_row2])
    
    try:
        from gspread_formatting import format_cell_range, CellFormat, Color, TextFormat
        # Cores Direcional (Azul para Pessoais, Cinza para Endereço, etc)
        format_cell_range(ws, "A1:Z2", CellFormat(textFormat=TextFormat(bold=True), backgroundColor=Color(0.9, 0.9, 0.9)))
    except: pass

def aplicar_estilo():
    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700;900&family=Inter:wght@400;600&display=swap');
        header[data-testid="stHeader"], [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"] {{
            display: none !important; visibility: hidden !important; height: 0px !important;
        }}
        .stApp {{
            background: linear-gradient(135deg, rgba({_hex_rgb_triplet(COR_AZUL_ESC)}, 0.82) 0%, rgba({_hex_rgb_triplet(COR_VERMELHO)}, 0.22) 100%),
                        url("https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=1920&q=80") center / cover no-repeat !important;
        }}
        .block-container {{
            max-width: 920px !important; padding: 2rem !important; background: rgba(255, 255, 255, 0.85) !important;
            backdrop-filter: blur(18px); border-radius: 24px !important; box-shadow: 0 24px 48px -12px rgba(4,66,143,0.18);
            margin-top: 20px !important;
        }}
        h1, h2, h3 {{ font-family: 'Montserrat' !important; color: {COR_AZUL_ESC} !important; }}
        .ficha-hero-bar {{
            height: 4px; width: 100%; border-radius: 999px;
            background: linear-gradient(90deg, {COR_AZUL_ESC}, {COR_VERMELHO}, {COR_AZUL_ESC});
            background-size: 200% 100%; margin: 1.2rem 0;
        }}
        .section-head {{ font-weight: 800; border-bottom: 2px solid #eef2f6; padding-bottom: 0.5rem; margin-bottom: 1rem; color: {COR_AZUL_ESC}; text-transform: uppercase; font-size: 0.8rem; }}
        .stButton button[kind="primary"] {{ background: linear-gradient(180deg, {COR_VERMELHO} 0%, {COR_VERMELHO_ESCURO} 100%) !important; color: white !important; font-weight: 700 !important; border-radius: 12px !important; }}
        </style>
    """, unsafe_allow_html=True)

def _hex_rgb_triplet(hex_color: str) -> str:
    x = hex_color.lstrip("#")
    return f"{int(x[0:2], 16)}, {int(x[2:4], 16)}, {int(x[4:6], 16)}"

def _exibir_logo_topo():
    st.markdown(f'<div style="text-align:center; padding-bottom:1rem;"><img src="{URL_LOGO_DIRECIONAL_EMAIL}" width="180"></div>', unsafe_allow_html=True)

# =============================================================================
# BACKEND (SALVAMENTO NA BASE)
# =============================================================================
def _processar_envio_cadastro():
    ss = st.session_state
    dados = dict(ss.get("ficha_snap_campos", {}))
    for c in CAMPOS:
        sk = f"fld_{c['key']}"
        if sk in ss: dados[c["key"]] = ss[sk]
    
    if not ss.get("fld_lgpd_ficha"):
        st.error("A concordância com a LGPD é obrigatória.")
        return

    try:
        import gspread
        from google.oauth2.service_account import Credentials
        gs_cfg = st.secrets["google_sheets"]
        creds_dict = json.loads(gs_cfg["SERVICE_ACCOUNT_JSON"])
        gc = gspread.authorize(Credentials.from_service_account_info(creds_dict, ["https://www.googleapis.com/auth/spreadsheets"]))
        
        sh = gc.open_by_key(gs_cfg["SPREADSHEET_ID"])
        ws = sh.worksheet(gs_cfg.get("WORKSHEET_NAME", "Corretores"))
        
        _aplicar_organizacao_planilha(ws)
        
        # Gerar linha (Timestamp, Link Vazio, Dados..., Pendente, Log)
        linha = [datetime.now().strftime("%d/%m/%Y %H:%M:%S"), ""]
        for c in CAMPOS:
            v = dados.get(c["key"], "")
            linha.append(str(v) if v is not None else "")
        linha.extend(["Pendente", "Aguardando envio via Dashboard"])
        
        ws.append_row(linha, value_input_option="USER_ENTERED")
        ss["ficha_sucesso"] = True
        st.rerun()
    except Exception as e:
        st.error(f"Erro na base: {e}")

def main():
    st.set_page_config(page_title="Credenciamento | Direcional", layout="centered")
    aplicar_estilo()
    
    ss = st.session_state
    if "ficha_sucesso" not in ss: ss["ficha_sucesso"] = False
    if "step" not in ss: ss["step"] = 0
    if "ficha_snap_campos" not in ss: ss["ficha_snap_campos"] = {}

    if ss["ficha_sucesso"]:
        _exibir_logo_topo()
        st.success("✓ Cadastro realizado com sucesso na base de dados!")
        st.video(URL_YOUTUBE_BOAS_VINDAS_RH_EMBED)
        if st.button("Fazer novo cadastro"):
            for k in list(ss.keys()): del ss[k]
            st.rerun()
        return

    _exibir_logo_topo()
    st.markdown('<p style="text-align:center; font-family:Montserrat; font-weight:900; font-size:1.6rem; color:#04428f; margin:0;">Credenciamento Vendas RJ</p>', unsafe_allow_html=True)
    st.markdown('<div class="ficha-hero-bar"></div>', unsafe_allow_html=True)

    secoes = SEC_ORDER
    idx = ss["step"]
    sec = secoes[idx]
    
    st.progress((idx + 1) / len(secoes), text=f"Etapa {idx+1} de {len(secoes)}: {sec}")

    with st.container():
        st.markdown(f'<p class="section-head">{sec}</p>', unsafe_allow_html=True)
        cols_vis = [c for c in CAMPOS if c["sec"] == sec and c["key"] not in CAMPOS_OCULTOS_FORMULARIO]
        
        with st.form(f"f_{idx}", border=False):
            for i in range(0, len(cols_vis), 2):
                c1 = cols_vis[i]
                c2 = cols_vis[i+1] if i+1 < len(cols_vis) else None
                L, R = st.columns(2) if c2 else (st.container(), None)
                with L: 
                    k, sk, label, tipo = c1["key"], f"fld_{c1['key']}", c1["label"], c1["tipo"]
                    if tipo == "text": st.text_input(label, key=sk)
                    elif tipo == "select": st.selectbox(label, options=c1.get("opcoes", ["--Nenhum--"]), key=sk)
                    elif tipo == "date": st.date_input(label, key=sk, format="DD/MM/YYYY", min_value=date(1900,1,1))
                if c2:
                    with R:
                        k, sk, label, tipo = c2["key"], f"fld_{c2['key']}", c2["label"], c2["tipo"]
                        if tipo == "text": st.text_input(label, key=sk)
                        elif tipo == "select": st.selectbox(label, options=c2.get("opcoes", ["--Nenhum--"]), key=sk)
                        elif tipo == "date": st.date_input(label, key=sk, format="DD/MM/YYYY", min_value=date(1900,1,1))
            
            if idx == len(secoes) - 1:
                st.checkbox("Aceito os termos da LGPD. *", key="fld_lgpd_ficha")
            
            st.markdown("<br>", unsafe_allow_html=True)
            col_b, col_n = st.columns(2)
            with col_b:
                if st.form_submit_button("Voltar", use_container_width=True, disabled=(idx == 0)):
                    ss["step"] -= 1
                    st.rerun()
            with col_n:
                label = "Finalizar" if idx == len(secoes) - 1 else "Avançar"
                if st.form_submit_button(label, type="primary", use_container_width=True):
                    for c in cols_vis: ss["ficha_snap_campos"][c["key"]] = ss.get(f"fld_{c['key']}")
                    if idx < len(secoes) - 1:
                        ss["step"] += 1
                        st.rerun()
                    else:
                        _processar_envio_cadastro()

    st.markdown('<div style="text-align:center; color:#64748b; font-size:0.75rem; margin-top:3rem;">Direcional Engenharia · Vendas Rio de Janeiro</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
