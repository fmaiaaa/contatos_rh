# -*- coding: utf-8 -*-
"""
Ficha de credenciamento — Direcional Vendas RJ (corretores).
APP 1: FORMULÁRIO DE ENTRADA DE DADOS (DESIGN ORIGINAL)
Este app grava os dados na planilha Google; o envio ao Salesforce é feito pelo APP 2.
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

# --- Constantes de Design e Identidade (Mantidas Integrais) ---
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
URL_LINKTREE_MARKETING = "https://linktr.ee/comercialdirecionalrj"
URL_FORM_SIMULADOR = "https://forms.gle/NLibApxbaimEbdBEA"
URL_YOUTUBE_SIMULADOR = "https://youtu.be/dE42s0g7K-c"
URL_YOUTUBE_SIMULADOR_EMBED = "https://www.youtube.com/embed/dE42s0g7K-c"
URL_YOUTUBE_BOAS_VINDAS_RH = "https://youtu.be/7cm3wFnoCSY"
URL_YOUTUBE_BOAS_VINDAS_RH_EMBED = "https://www.youtube.com/embed/7cm3wFnoCSY"
URL_DIRI_ACADEMY = "https://diriacademy.skore.io/login"
URL_SALESFORCE_VENDAS = "https://direcional.my.site.com/vendas"
URL_WHATSAPP_EQUIPE = "https://chat.whatsapp.com/KnZg4Zax3Z20viB7XEWvmo"

LINKS_POS_CADASTRO: list[tuple[str, str]] = [
    ("Materiais de marketing (Linktree)", URL_LINKTREE_MARKETING),
    ("Pedir acesso ao simulador de negociação", URL_FORM_SIMULADOR),
    ("Vídeo — como usar o simulador (YouTube)", URL_YOUTUBE_SIMULADOR),
    ("Treinamentos — Diri Academy", URL_DIRI_ACADEMY),
    ("Salesforce (portal de vendas)", URL_SALESFORCE_VENDAS),
    ("Entrar no grupo — WhatsApp", URL_WHATSAPP_EQUIPE),
]

POPUP_MAPA_ALTURA_PX = 320

# =============================================================================
# DEFINIÇÃO DE CAMPOS E OPÇÕES (MANTENDO ESTRUTURA ORIGINAL)
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
ORIGENS = ["--Nenhum--", "RH", "Indicação", "Gerente", "Diretor", "DiRi Talent", "Coordenador", "Gupy", "MARINHA", "Creci", "Parceria Estácio"]
STATUS_CORRETOR = ["--Nenhum--", "Ativo", "Inativo", "Pré credenciado", "Reativado"]
SALUTATIONS = ["--Nenhum--", "Sr.", "Sra.", "Dr.", "Dra."]
SEXOS = ["--Nenhum--", "Masculino", "Feminino"]
CAMISETAS = ["--Nenhum--", "PP", "P", "M", "G", "GG", "XGG"]
UNIDADE_REDE_OUTRA_IMOBILIARIA = "Outra imobiliária (parceira)"
UNIDADES_NEGOCIO = ["--Nenhum--", "Direcional", "Riva", UNIDADE_REDE_OUTRA_IMOBILIARIA]
ATIVIDADE_VENDAS_RJ_OPTS = ["--Nenhum--", "Corretor Parceiro", "Corretor", "Captador"]
TIPO_PIX = ["--Nenhum--", "CPF", "CNPJ", "E-mail", "Celular", "Chave aleatória"]
ESTADOS_UF = ["--Nenhum--", "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"]
POSSUI_FILHOS = ["--Nenhum--", "Sim", "Não"]
TIPO_CONTA_BANCARIA = ["--Nenhum--", "Corrente", "Poupança"]
BANCO_OPTS = ["--Nenhum--", "001 – Banco do Brasil S.A.", "033 – Banco Santander (Brasil) S.A.", "104 – Caixa Econômica Federal", "237 – Banco Bradesco S.A.", "260 – Banco Nubank", "341 – Banco Itaú S.A."]
PREFERRED_METHOD_OPTS = ["Telefone de Trabalho", "Telefone residencial", "Celular", "Email de trabalho", "Email pessoal", "Sem preferência"]

CAPITAL_POR_UF_BR: Dict[str, str] = {
    "AC": "Rio Branco", "AL": "Maceió", "AM": "Manaus", "AP": "Macapá", "BA": "Salvador", "CE": "Fortaleza", 
    "DF": "Brasília", "ES": "Vitória", "GO": "Goiânia", "MA": "São Luís", "MG": "Belo Horizonte", "MS": "Campo Grande", 
    "MT": "Cuiabá", "PA": "Belém", "PB": "João Pessoa", "PE": "Recife", "PI": "Teresina", "PR": "Curitiba", 
    "RJ": "Rio de Janeiro", "RN": "Natal", "RO": "Porto Velho", "RR": "Boa Vista", "RS": "Porto Alegre", 
    "SC": "Florianópolis", "SE": "Aracaju", "SP": "São Paulo", "TO": "Palmas",
}

def _z(**kw) -> Dict[str, Any]: return kw

def _campos_def() -> List[Dict[str, Any]]:
    return [
        _z(key="gerente_vendas", label="Gerente de vendas *", sec="Informações para contato", tipo="select", sf="AccountId", opcoes=["--Nenhum--"], req=True),
        _z(key="nome_completo", label="Nome completo *", sec="Dados Pessoais", tipo="text", sf=None, req=True),
        _z(key="status_corretor", label="Status Corretor *", sec="Informações para contato", tipo="select", sf="Status_Corretor__c", opcoes=STATUS_CORRETOR, req=True),
        _z(key="regional", label="Regional *", sec="Informações para contato", tipo="select", sf="Regional__c", opcoes=REGIONAIS, req=True),
        _z(key="sexo", label="Sexo *", sec="Informações para contato", tipo="select", sf="Sexo__c", opcoes=SEXOS, req=True),
        _z(key="camiseta", label="Camiseta *", sec="Informações para contato", tipo="select", sf="Camiseta__c", opcoes=CAMISETAS, req=True),
        _z(key="unidade_negocio", label="Fará parte de qual rede? *", sec="Informações para contato", tipo="select", sf="Unidade_Negocio__c", opcoes=UNIDADES_NEGOCIO, req=True),
        _z(key="atividade", label="Função na operação *", sec="Informações para contato", tipo="select", sf="Atividade__c", opcoes=ATIVIDADE_VENDAS_RJ_OPTS, req=True),
        _z(key="birthdate", label="Data de nascimento *", sec="Dados Pessoais", tipo="date", sf="Birthdate", req=True),
        _z(key="estado_civil", label="Estado Civil *", sec="Dados Pessoais", tipo="select", sf="EstadoCivil__c", opcoes=["--Nenhum--", "Solteiro", "Casado", "Divorciado", "Viúvo"], req=True),
        _z(key="nome_conjuge", label="Nome do Cônjuge", sec="Dados Pessoais", tipo="text", sf="Nome_do_Conjuge__c", req=False),
        _z(key="cpf", label="CPF *", sec="Dados Pessoais", tipo="text", sf="CPF__c", req=True),
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
        _z(key="banco", label="Banco *", sec="Dados Bancários Pessoa Física", tipo="select", sf="Banco__c", opcoes=BANCO_OPTS, req=True),
        _z(key="conta_bancaria", label="Conta Bancária *", sec="Dados Bancários Pessoa Física", tipo="text", sf="Conta_Banc_ria__c", req=True),
        _z(key="agencia_bancaria", label="Agência Bancária *", sec="Dados Bancários Pessoa Física", tipo="text", sf="Ag_ncia_Banc_ria__c", req=True),
        _z(key="possui_creci", label="Possui CRECI? *", sec="CRECI/TTI", tipo="select", sf=None, opcoes=["Sim", "Não"], req=True),
        _z(key="creci", label="CRECI", sec="CRECI/TTI", tipo="text", sf="CRECI__c", req=False),
        _z(key="status_creci", label="Status CRECI", sec="CRECI/TTI", tipo="select", sf="Status_CRECI__c", opcoes=["--Nenhum--", "Definitivo", "Estágio", "Pendente"], req=False),
    ]

CAMPOS: List[Dict[str, Any]] = _campos_def()
CAMPOS_OCULTOS_FORMULARIO: frozenset[str] = frozenset({"salutation", "apelido", "data_entrevista", "data_contrato", "data_credenciamento"})

# =============================================================================
# SUPORTE PLANILHA E SEGURANÇA (MANTIDO)
# =============================================================================
def _norm_picklist(val: Any) -> str:
    s = (str(val).strip() if val is not None else "")
    if s in ("--Nenhum--", "Nenhum"): return ""
    return s

def _naturalidade_capital_por_uf(uf: Any) -> str:
    s = (str(uf).strip() if uf is not None else "")
    return CAPITAL_POR_UF_BR.get(s, "")

def email_contato_formato_valido(val: Any) -> bool:
    s = (str(val).strip() if val is not None else "")
    return bool(re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", s))

def _credenciais_de_secrets(st_secrets: Any) -> Optional[Dict[str, Any]]:
    try:
        gs = st_secrets.get("google_sheets")
        raw = gs.get("SERVICE_ACCOUNT_JSON")
        if isinstance(raw, dict): return raw
        return json.loads(raw)
    except: return None

# =============================================================================
# DESIGN E ESTILOS (RESTAURAÇÃO COMPLETA + REMOÇÃO DA BARRA BRANCA)
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
        
        /* Remover a barra branca e o menu superior do Streamlit */
        header[data-testid="stHeader"], 
        [data-testid="stHeader"], 
        [data-testid="stToolbar"],
        [data-testid="stDecoration"] {{
            display: none !important;
            visibility: hidden !important;
            height: 0px !important;
        }}
        
        #MainMenu {{ visibility: hidden; }}
        footer {{ visibility: hidden; }}

        @keyframes fichaFadeIn {{ from {{ opacity: 0; transform: translateY(18px); }} to {{ opacity: 1; transform: translateY(0); }} }}
        @keyframes fichaShimmer {{ 0% {{ background-position: 0% 50%; }} 100% {{ background-position: 200% 50%; }} }}
        
        .stApp {{
            background: linear-gradient(135deg, rgba({RGB_AZUL_CSS}, 0.82) 0%, rgba({RGB_VERMELHO_CSS}, 0.22) 100%),
                        url("{bg_url}") center / cover no-repeat !important;
        }}
        
        /* Ajuste de margem superior devido à remoção do header */
        .block-container {{
            max-width: 920px !important;
            padding-top: 2rem !important;
            padding-bottom: 2rem !important;
            background: rgba(255, 255, 255, 0.82) !important;
            backdrop-filter: blur(18px);
            border-radius: 24px !important;
            border: 1px solid rgba(255, 255, 255, 0.45);
            box-shadow: 0 24px 48px -12px rgba({RGB_AZUL_CSS}, 0.18);
            animation: fichaFadeIn 0.7s ease-out both;
            margin-top: 20px !important;
        }}
        
        h1, h2, h3 {{ font-family: 'Montserrat', sans-serif !important; color: {COR_AZUL_ESC} !important; }}
        
        .ficha-logo-wrap {{
            text-align: center;
            padding: 0.1rem 0 0.45rem 0;
        }}
        .ficha-logo-wrap img {{
            max-height: 72px; width: auto;
            max-width: min(280px, 85vw); height: auto;
            object-fit: contain; display: inline-block;
        }}

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

def _resolver_png_raiz(nome: str) -> Path | None:
    for base in (_DIR_APP, _DIR_APP.parent):
        p = base / nome
        if p.is_file(): return p
    return None

def _exibir_logo_topo() -> None:
    """Logo centralizada no topo: arquivo local ou URL de backup."""
    path = _resolver_png_raiz(LOGO_TOPO_ARQUIVO)
    try:
        if path:
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
# LÓGICA DE BACKEND (SALVAMENTO APENAS NA PLANILHA GOOGLE)
# =============================================================================
def _processar_envio_cadastro():
    ss = st.session_state
    dados = dict(ss.get("ficha_snap_campos", {}))
    for c in CAMPOS:
        sk = f"fld_{c['key']}"
        if sk in ss: dados[c["key"]] = ss[sk]
    
    if not ss.get("fld_lgpd_ficha"):
        st.error("Concordância com LGPD é obrigatória.")
        return

    creds = _credenciais_de_secrets(st.secrets)
    if not creds:
        st.error("Configuração da planilha não encontrada.")
        return

    st.caption("**Gravando cadastro...** Por favor, aguarde.")
    bar = st.progress(0.0)

    try:
        import gspread
        from google.oauth2.service_account import Credentials
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        gc = gspread.authorize(Credentials.from_service_account_info(creds, scopes=scopes))
        
        gs_cfg = st.secrets.get("google_sheets", {})
        sid = gs_cfg.get("SPREADSHEET_ID")
        wname = gs_cfg.get("WORKSHEET_NAME", "Corretores")
        
        sh = gc.open_by_key(sid)
        ws = sh.worksheet(wname)
        bar.progress(0.4)

        row = [datetime.now().strftime("%d/%m/%Y %H:%M:%S"), ""]
        for c in CAMPOS:
            val = dados.get(c["key"], "")
            row.append(str(val) if val is not None else "")
        
        row.extend(["Pendente", "Aguardando processamento pelo App de Gestão"])
        
        ws.append_row(row, value_input_option="USER_ENTERED")
        bar.progress(1.0)
        
        ss["ficha_sucesso"] = True
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao salvar na planilha: {str(e)}")

# =============================================================================
# INTERFACE DO FORMULÁRIO
# =============================================================================
def _widget_campo(c):
    k, sk, label, tipo = c["key"], f"fld_{c['key']}", c["label"], c["tipo"]
    plain, obrig = (label[:-2], True) if label.endswith(" *") else (label, False)
    
    if obrig:
        st.markdown(f'<div class="ficha-input-label">{html.escape(plain)} <span class="ficha-star-req">*</span></div>', unsafe_allow_html=True)
        lv = "collapsed"
    else:
        lv = "visible"

    if tipo == "text": st.text_input(label, key=sk, label_visibility=lv)
    elif tipo == "select": st.selectbox(label, options=c.get("opcoes", []), key=sk, label_visibility=lv)
    elif tipo == "date": st.date_input(label, key=sk, format="DD/MM/YYYY", label_visibility=lv)
    elif tipo == "textarea": st.text_area(label, key=sk, label_visibility=lv)

def main():
    fav = _resolver_png_raiz(FAVICON_ARQUIVO)
    st.set_page_config(page_title="Credenciamento | Direcional RJ", page_icon=str(fav) if fav else None, layout="centered")
    aplicar_estilo()

    ss = st.session_state
    if "ficha_sucesso" not in ss: ss["ficha_sucesso"] = False
    if "step" not in ss: ss["step"] = 0
    if "ficha_snap_campos" not in ss: ss["ficha_snap_campos"] = {}

    if ss["ficha_sucesso"]:
        _cabecalho_pagina()
        st.balloons()
        st.markdown(f"""
            <div style="border: 2px solid {COR_AZUL_ESC}; background: #fff; padding: 20px; border-radius: 15px;">
                <h3 style="margin-top:0; color:{COR_AZUL_ESC}">✓ Cadastro Realizado!</h3>
                <p>Seus dados foram salvos com sucesso em nossa base de análise.</p>
                <p>Nossa equipe de gestão irá revisar seu perfil. Assista ao vídeo de boas-vindas do nosso RH abaixo:</p>
            </div>
        """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.video(URL_YOUTUBE_BOAS_VINDAS_RH_EMBED)
        if st.button("Fazer outro cadastro"):
            for k in list(ss.keys()): del ss[k]
            st.rerun()
        return

    _cabecalho_pagina(com_intro_formulario=True)
    
    secoes = SEC_ORDER
    idx = ss["step"]
    sec = secoes[idx]
    
    pct = (idx + 1) / len(secoes)
    st.progress(pct, text=f"Progresso: Etapa {idx+1} de {len(secoes)} ({sec})")

    with st.container():
        st.markdown(f'<p class="section-head">{sec}</p>', unsafe_allow_html=True)
        cols_visiveis = [c for c in CAMPOS if c["sec"] == sec and c["key"] not in CAMPOS_OCULTOS_FORMULARIO]
        
        with st.form(f"step_form_{idx}", border=False):
            for i in range(0, len(cols_visiveis), 2):
                c1 = cols_visiveis[i]
                c2 = cols_visiveis[i+1] if i+1 < len(cols_visiveis) else None
                if c2:
                    L, R = st.columns(2)
                    with L: _widget_campo(c1)
                    with R: _widget_campo(c2)
                else:
                    _widget_campo(c1)
            
            if idx == len(secoes) - 1:
                st.markdown("---")
                st.checkbox("Li e aceito os termos de uso de dados conforme a LGPD. *", key="fld_lgpd_ficha")
            
            st.markdown("<br>", unsafe_allow_html=True)
            col_b, col_n = st.columns(2)
            with col_b:
                if st.form_submit_button("Voltar", use_container_width=True, disabled=(idx == 0)):
                    ss["step"] -= 1
                    st.rerun()
            with col_n:
                label = "Finalizar e Enviar" if idx == len(secoes) - 1 else "Avançar"
                if st.form_submit_button(label, type="primary", use_container_width=True):
                    for c in cols_visiveis:
                        ss["ficha_snap_campos"][c["key"]] = ss.get(f"fld_{c['key']}")
                    if idx < len(secoes) - 1:
                        ss["step"] += 1
                        st.rerun()
                    else:
                        _processar_envio_cadastro()

    st.markdown('<div style="text-align:center; color:#64748b; font-size:0.75rem; margin-top:3rem;">Direcional Engenharia · Vendas Rio de Janeiro</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
