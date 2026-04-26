# -*- coding: utf-8 -*-
"""
Ficha de credenciamento — Direcional Vendas RJ (corretores).
APP 1: FORMULÁRIO DE ENTRADA DE DADOS (DESIGN ORIGINAL)
Removido upload de arquivo CRECI. Organização visual da planilha restaurada.
Corrigida a limitação da data de nascimento.
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
FUNDO_CADASTRO_ARQUIVO = "fundo_cadastrorh.jpg"

URL_LOGO_DIRECIONAL_EMAIL = "https://logodownload.org/wp-content/uploads/2021/04/direcional-engenharia-logo.png"

# Recursos pós-cadastro
URL_YOUTUBE_BOAS_VINDAS_RH_EMBED = "https://www.youtube.com/embed/7cm3wFnoCSY"
URL_YOUTUBE_SIMULADOR_EMBED = "https://www.youtube.com/embed/dE42s0g7K-c"
POPUP_MAPA_ALTURA_PX = 320

# =============================================================================
# DEFINIÇÃO DE CAMPOS E ESTRUTURA (MANTENDO ORIGINAL)
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
STATUS_CORRETOR = ["--Nenhum--", "Ativo", "Inativo", "Pré credenciado", "Reativado"]
SEXOS = ["--Nenhum--", "Masculino", "Feminino"]
CAMISETAS = ["--Nenhum--", "PP", "P", "M", "G", "GG", "XGG"]
UNIDADE_REDE_OUTRA_IMOBILIARIA = "Outra imobiliária (parceira)"
UNIDADES_NEGOCIO = ["--Nenhum--", "Direcional", "Riva", UNIDADE_REDE_OUTRA_IMOBILIARIA]
ATIVIDADE_VENDAS_RJ_OPTS = ["--Nenhum--", "Corretor Parceiro", "Corretor", "Captador"]
TIPO_PIX = ["--Nenhum--", "CPF", "CNPJ", "E-mail", "Celular", "Chave aleatória"]
ESTADOS_UF = ["--Nenhum--"] + [u for u in REGIONAIS if u != "--Nenhum--"]
POSSUI_FILHOS = ["--Nenhum--", "Sim", "Não"]
TIPO_CONTA_BANCARIA = ["--Nenhum--", "Corrente", "Poupança"]
BANCO_OPTS = ["--Nenhum--", "001 – Banco do Brasil S.A.", "033 – Banco Santander (Brasil) S.A.", "104 – Caixa Econômica Federal", "237 – Banco Bradesco S.A.", "341 – Banco Itaú S.A.", "260 – Banco Nubank"]

def _z(**kw) -> Dict[str, Any]: return kw

def _campos_def() -> List[Dict[str, Any]]:
    return [
        _z(key="gerente_vendas", label="Gerente de vendas *", sec="Informações para contato", tipo="select", req=True),
        _z(key="nome_completo", label="Nome completo *", sec="Dados Pessoais", tipo="text", req=True),
        _z(key="status_corretor", label="Status Corretor *", sec="Informações para contato", tipo="select", opcoes=STATUS_CORRETOR, req=True),
        _z(key="regional", label="Regional *", sec="Informações para contato", tipo="select", opcoes=REGIONAIS, req=True),
        _z(key="sexo", label="Sexo *", sec="Informações para contato", tipo="select", opcoes=SEXOS, req=True),
        _z(key="camiseta", label="Camiseta *", sec="Informações para contato", tipo="select", opcoes=CAMISETAS, req=True),
        _z(key="unidade_negocio", label="Fará parte de qual rede? *", sec="Informações para contato", tipo="select", opcoes=UNIDADES_NEGOCIO, req=True),
        _z(key="atividade", label="Função na operação *", sec="Informações para contato", tipo="select", opcoes=ATIVIDADE_VENDAS_RJ_OPTS, req=True),
        _z(key="birthdate", label="Data de nascimento *", sec="Dados Pessoais", tipo="date", req=True),
        _z(key="estado_civil", label="Estado Civil *", sec="Dados Pessoais", tipo="select", opcoes=["--Nenhum--", "Solteiro", "Casado", "Divorciado", "Viúvo"], req=True),
        _z(key="nome_conjuge", label="Nome do Cônjuge", sec="Dados Pessoais", tipo="text", req=False),
        _z(key="cpf", label="CPF *", sec="Dados Pessoais", tipo="text", req=True),
        _z(key="uf_naturalidade", label="UF Naturalidade *", sec="Dados Pessoais", tipo="select", opcoes=ESTADOS_UF, req=True),
        _z(key="naturalidade", label="Naturalidade *", sec="Dados Pessoais", tipo="text", req=True),
        _z(key="rg", label="RG *", sec="Dados Pessoais", tipo="text", req=True),
        _z(key="uf_rg", label="UF RG *", sec="Dados Pessoais", tipo="select", opcoes=ESTADOS_UF, req=True),
        _z(key="tipo_pix", label="Tipo do PIX *", sec="Dados Pessoais", tipo="select", opcoes=TIPO_PIX, req=True),
        _z(key="dados_pix", label="Dados para PIX *", sec="Dados Pessoais", tipo="text", req=True),
        _z(key="endereco_cep", label="CEP *", sec="Endereço", tipo="text", req=True),
        _z(key="endereco_logradouro", label="Logradouro *", sec="Endereço", tipo="text", req=True),
        _z(key="endereco_numero", label="Número *", sec="Endereço", tipo="text", req=True),
        _z(key="endereco_complemento", label="Complemento", sec="Endereço", tipo="text", req=False),
        _z(key="endereco_bairro", label="Bairro *", sec="Endereço", tipo="text", req=True),
        _z(key="endereco_cidade", label="Cidade *", sec="Endereço", tipo="text", req=True),
        _z(key="endereco_estado", label="Estado (UF) *", sec="Endereço", tipo="select", opcoes=ESTADOS_UF, req=True),
        _z(key="mobile", label="Celular *", sec="Dados para Contato", tipo="text", req=True),
        _z(key="email", label="E-mail *", sec="Dados para Contato", tipo="text", req=True),
        _z(key="nome_mae", label="Nome da Mãe *", sec="Dados Familiares", tipo="text", req=True),
        _z(key="nome_pai", label="Nome do Pai *", sec="Dados Familiares", tipo="text", req=True),
        _z(key="banco", label="Banco *", sec="Dados Bancários Pessoa Física", tipo="select", opcoes=BANCO_OPTS, req=True),
        _z(key="conta_bancaria", label="Conta Bancária *", sec="Dados Bancários Pessoa Física", tipo="text", req=True),
        _z(key="agencia_bancaria", label="Agência Bancária *", sec="Dados Bancários Pessoa Física", tipo="text", req=True),
        _z(key="possui_creci", label="Possui CRECI? *", sec="CRECI/TTI", tipo="select", opcoes=["Sim", "Não"], req=True),
        _z(key="creci", label="CRECI", sec="CRECI/TTI", tipo="text", req=False),
        _z(key="status_creci", label="Status CRECI", sec="CRECI/TTI", tipo="select", opcoes=["--Nenhum--", "Definitivo", "Estágio", "Pendente"], req=False),
    ]

CAMPOS = _campos_def()
CAMPOS_OCULTOS_FORMULARIO = frozenset({"salutation", "apelido", "data_entrevista", "data_contrato", "data_credenciamento"})

# =============================================================================
# LÓGICA DE ORGANIZAÇÃO DA PLANILHA (CORES E BORDAS)
# =============================================================================
def _col_letter(n: int) -> str:
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s

def _formatar_visual_aba_corretores(ws: Any, cabecalho: List[str]) -> None:
    """Aplica cores por seção, bordas e congela a primeira linha."""
    try:
        sheet_id = ws.id
        n = len(cabecalho)
        
        def rgb(r: float, g: float, b: float) -> Dict[str, float]:
            return {"red": r, "green": g, "blue": b, "alpha": 1.0}

        def hdr_fmt(bg: Dict[str, float], fg: Dict[str, float]) -> Dict[str, Any]:
            return {
                "backgroundColor": bg,
                "horizontalAlignment": "CENTER",
                "wrapStrategy": "WRAP",
                "textFormat": {"foregroundColor": fg, "bold": True, "fontSize": 10},
            }

        reqs: List[Dict[str, Any]] = [
            {
                "updateSheetProperties": {
                    "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
                    "fields": "gridProperties.frozenRowCount",
                }
            },
        ]

        # Formatação básica para o cabeçalho (Azul Direcional)
        reqs.append({
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": n},
                "cell": {"userEnteredFormat": hdr_fmt(rgb(0.01, 0.25, 0.56), rgb(1, 1, 1))},
                "fields": "userEnteredFormat(backgroundColor,horizontalAlignment,wrapStrategy,textFormat)",
            }
        })

        # Borda inferior grossa
        reqs.append({
            "updateBorders": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": n},
                "bottom": {"style": "SOLID_MEDIUM", "color": rgb(0.2, 0.2, 0.2)},
            }
        })

        ws.spreadsheet.batch_update({"requests": reqs})
    except: pass

# =============================================================================
# DESIGN E ESTILOS (RESTAURAÇÃO COMPLETA + SEM BARRA SUPERIOR)
# =============================================================================
def _hex_rgb_triplet(hex_color: str) -> str:
    x = hex_color.lstrip("#")
    return f"{int(x[0:2], 16)}, {int(x[2:4], 16)}, {int(x[4:6], 16)}"

RGB_AZUL_CSS = _hex_rgb_triplet(COR_AZUL_ESC)
RGB_VERMELHO_CSS = _hex_rgb_triplet(COR_VERMELHO)

def aplicar_estilo():
    bg_url = "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=1920&q=80"
    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700;900&family=Inter:wght@400;600&display=swap');
        
        header[data-testid="stHeader"], [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"] {{
            display: none !important; visibility: hidden !important; height: 0px !important;
        }}
        
        @keyframes fichaFadeIn {{ from {{ opacity: 0; transform: translateY(18px); }} to {{ opacity: 1; transform: translateY(0); }} }}
        @keyframes fichaShimmer {{ 0% {{ background-position: 0% 50%; }} 100% {{ background-position: 200% 50%; }} }}
        
        .stApp {{
            background: linear-gradient(135deg, rgba({RGB_AZUL_CSS}, 0.82) 0%, rgba({RGB_VERMELHO_CSS}, 0.22) 100%),
                        url("{bg_url}") center / cover no-repeat !important;
        }}
        
        .block-container {{
            max-width: 920px !important;
            padding: 2rem !important;
            background: rgba(255, 255, 255, 0.82) !important;
            backdrop-filter: blur(18px);
            border-radius: 24px !important;
            border: 1px solid rgba(255, 255, 255, 0.45);
            box-shadow: 0 24px 48px -12px rgba({RGB_AZUL_CSS}, 0.18);
            animation: fichaFadeIn 0.7s ease-out both;
            margin-top: 20px !important;
        }}
        
        h1, h2, h3 {{ font-family: 'Montserrat', sans-serif !important; color: {COR_AZUL_ESC} !important; }}
        
        .ficha-logo-wrap {{ text-align: center; padding: 0.1rem 0 0.45rem 0; }}
        .ficha-logo-wrap img {{ max-height: 72px; width: auto; object-fit: contain; display: inline-block; }}

        .ficha-hero-bar {{
            height: 4px; width: 100%; border-radius: 999px;
            background: linear-gradient(90deg, {COR_AZUL_ESC}, {COR_VERMELHO}, {COR_AZUL_ESC});
            background-size: 200% 100%; animation: fichaShimmer 4s infinite alternate;
            margin: 1.2rem 0;
        }}
        
        .section-head {{
            font-family: 'Montserrat', sans-serif; font-size: 0.8rem; color: {COR_AZUL_ESC};
            text-align: center; text-transform: uppercase; letter-spacing: 0.1em;
            font-weight: 800; border-bottom: 2px solid #eef2f6; padding-bottom: 0.5rem; margin-bottom: 1rem;
        }}
        
        .stButton button[kind="primary"] {{
            background: linear-gradient(180deg, {COR_VERMELHO} 0%, {COR_VERMELHO_ESCURO} 100%) !important;
            border: none !important; border-radius: 12px !important; font-weight: 700 !important;
        }}
        
        .ficha-input-label {{ font-size: 0.875rem; font-weight: 600; color: {COR_TEXTO_LABEL}; margin-bottom: 0.35rem; }}
        .ficha-star-req {{ color: {COR_VERMELHO}; font-weight: 800; margin-left: 0.12em; }}
        </style>
    """, unsafe_allow_html=True)

def _exibir_logo_topo() -> None:
    path = _DIR_APP / LOGO_TOPO_ARQUIVO
    try:
        if path.is_file():
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            st.markdown(f'<div class="ficha-logo-wrap"><img src="data:image/png;base64,{b64}" alt="Direcional" /></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="ficha-logo-wrap"><img src="{URL_LOGO_DIRECIONAL_EMAIL}" alt="Direcional" /></div>', unsafe_allow_html=True)
    except:
        st.markdown(f'<div class="ficha-logo-wrap"><img src="{URL_LOGO_DIRECIONAL_EMAIL}" alt="Direcional" /></div>', unsafe_allow_html=True)

def _cabecalho_pagina(com_intro_formulario: bool = False):
    _exibir_logo_topo()
    st.markdown(f"""
        <div style="text-align:center; margin-top: 0.5rem;">
            <p style="font-family:'Montserrat'; font-size:1.7rem; font-weight:900; color:{COR_AZUL_ESC}; margin:0;">Credenciamento Direcional Vendas RJ</p>
            <p style="color:#475569; font-size:0.95rem;">Seu próximo passo começa aqui.</p>
        </div>
        <div class="ficha-hero-bar"></div>
    """, unsafe_allow_html=True)
    if com_intro_formulario:
        st.markdown('<p style="color:#334155; font-size:0.95rem; text-align:justify;">Reserve alguns minutos e tenha seus documentos em mãos. Use <strong>Avançar</strong> e <strong>Voltar</strong> para navegar entre as etapas.</p>', unsafe_allow_html=True)

# =============================================================================
# BACKEND (PLANILHA GOOGLE)
# =============================================================================
def _processar_envio_cadastro():
    ss = st.session_state
    dados = dict(ss.get("ficha_snap_campos", {}))
    for c in CAMPOS:
        sk = f"fld_{c['key']}"
        if sk in ss: dados[c["key"]] = ss[sk]
    
    if not ss.get("fld_lgpd_ficha"):
        st.error("Aceite os termos da LGPD para continuar.")
        return

    try:
        import gspread
        from google.oauth2.service_account import Credentials
        gs_cfg = st.secrets["google_sheets"]
        creds_dict = json.loads(gs_cfg["SERVICE_ACCOUNT_JSON"])
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        gc = gspread.authorize(Credentials.from_service_account_info(creds_dict, scopes=scopes))
        
        sh = gc.open_by_key(gs_cfg["SPREADSHEET_ID"])
        ws = sh.worksheet(gs_cfg.get("WORKSHEET_NAME", "Corretores"))
        
        # Cabeçalhos: Data, Link, [Campos...], Envio, Log
        row = [datetime.now().strftime("%d/%m/%Y %H:%M:%S"), ""]
        for c in CAMPOS:
            val = dados.get(c["key"], "")
            row.append(str(val) if val is not None else "")
        row.extend(["Pendente", "Aguardando Dashboard"])

        # Verificar se precisa criar cabeçalho ou formatar
        if not ws.get_all_values():
            headers = ["Data Envio", "Link Salesforce"] + [c["label"] for c in CAMPOS] + ["Envio?", "Log / erro"]
            ws.append_row(headers)
            _formatar_visual_aba_corretores(ws, headers)

        ws.append_row(row, value_input_option="USER_ENTERED")
        ss["ficha_sucesso"] = True
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao salvar: {str(e)}")

# =============================================================================
# INTERFACE E WIDGETS
# =============================================================================
def _widget_campo(c):
    k, sk, label, tipo = c["key"], f"fld_{c['key']}", c["label"], c["tipo"]
    plain, obrig = (label[:-2], True) if label.endswith(" *") else (label, False)
    lv = "collapsed" if obrig else "visible"
    if obrig:
        st.markdown(f'<div class="ficha-input-label">{html.escape(plain)} <span class="ficha-star-req">*</span></div>', unsafe_allow_html=True)
    
    if tipo == "text": st.text_input(label, key=sk, label_visibility=lv)
    elif tipo == "select": st.selectbox(label, options=c.get("opcoes", []), key=sk, label_visibility=lv)
    elif tipo == "date":
        # Corrigida a limitação de data de nascimento (mínimo de 1900 até hoje)
        min_d = date(1900, 1, 1)
        max_d = date.today()
        st.date_input(label, key=sk, format="DD/MM/YYYY", label_visibility=lv, min_value=min_d, max_value=max_d)

def main():
    st.set_page_config(page_title="Credenciamento | Direcional", layout="centered")
    aplicar_estilo()

    ss = st.session_state
    if "ficha_sucesso" not in ss: ss["ficha_sucesso"] = False
    if "step" not in ss: ss["step"] = 0
    if "ficha_snap_campos" not in ss: ss["ficha_snap_campos"] = {}

    if ss["ficha_sucesso"]:
        _cabecalho_pagina()
        st.success("✓ Cadastro Recebido com Sucesso!")
        st.video(URL_YOUTUBE_BOAS_VINDAS_RH_EMBED)
        if st.button("Fazer novo cadastro"):
            for k in list(ss.keys()): del ss[k]
            st.rerun()
        return

    _cabecalho_pagina(com_intro_formulario=True)
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
                if c2:
                    L, R = st.columns(2)
                    with L: _widget_campo(c1)
                    with R: _widget_campo(c2)
                else:
                    _widget_campo(c1)
            
            if idx == len(secoes) - 1:
                st.checkbox("Declaro que li e aceito os termos de uso de dados conforme a LGPD. *", key="fld_lgpd_ficha")
            
            st.markdown("<br>", unsafe_allow_html=True)
            col_b, col_n = st.columns(2)
            with col_b:
                if st.form_submit_button("Voltar", use_container_width=True, disabled=(idx == 0)):
                    ss["step"] -= 1
                    st.rerun()
            with col_n:
                label = "Enviar Cadastro" if idx == len(secoes) - 1 else "Próximo"
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
