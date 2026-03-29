# -*- coding: utf-8 -*-
"""
Ficha de credenciamento — Direcional Vendas RJ (corretores).
Backend: planilha Google + Salesforce (detalhes operacionais fora desta tela).
"""

from __future__ import annotations

import base64
import html
import io
import os
import platform
import re
import smtplib
from datetime import date, datetime
from pathlib import Path
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import streamlit as st

from corretor_campos import (
    CAMPOS,
    cabecalho_planilha,
    campos_por_secao,
    linha_planilha,
    montar_payload_salesforce,
    secoes_ordenadas,
    validar_obrigatorios,
    validar_obrigatorios_secao,
)
from google_sheets_corretor import (
    DEFAULT_SPREADSHEET_ID,
    DEFAULT_WORKSHEET_NAME,
    _credenciais_de_secrets,
    anexar_linha,
    atualizar_status_envio_salesforce,
)

try:
    from salesforce_api import conectar_salesforce, criar_contato_payload
except ImportError:
    conectar_salesforce = None
    criar_contato_payload = None

COR_AZUL_ESC = "#002c5d"
COR_VERMELHO = "#e30613"
COR_FUNDO = "#fcfdfe"
COR_BORDA = "#eef2f6"
COR_INPUT_BG = "#f0f2f6"
COR_TEXTO_MUTED = "#64748b"

URL_LOGO_DIRECIONAL_EMAIL = (
    "https://logodownload.org/wp-content/uploads/2021/04/direcional-engenharia-logo.png"
)

_DIR_APP = Path(__file__).resolve().parent

BASE_URL_CONTACT_VIEW = "https://direcional.lightning.force.com/lightning/r/Contact"

# Recursos exibidos no popup pós-cadastro (corretor)
URL_LINKTREE_MARKETING = "https://linktr.ee/comercialdirecionalrj"
URL_FORM_SIMULADOR = "https://forms.gle/NLibApxbaimEbdBEA"
URL_YOUTUBE_SIMULADOR = "https://youtu.be/dE42s0g7K-c"
URL_YOUTUBE_SIMULADOR_EMBED = "https://www.youtube.com/embed/dE42s0g7K-c"
URL_DIRI_ACADEMY = "https://diriacademy.skore.io/login"
URL_SALESFORCE_VENDAS = "https://direcional.my.site.com/vendas"
URL_WHATSAPP_EQUIPE = "https://chat.whatsapp.com/KnZg4Zax3Z20viB7XEWvmo"

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
    "Contrato e dados PJ": "Contrato / PJ",
    "Histórico Equipe": "Histórico",
    "Datas": "Datas",
    "Dados Integração": "Integração",
    "Anexos": "Anexos",
    "Preferred Contact Method": "Preferências",
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
        html, body {{ font-family: 'Inter', sans-serif; color: {COR_AZUL_ESC}; }}
        [data-testid="stAppViewContainer"] {{
            background:
                linear-gradient(160deg, rgba(0, 44, 93, 0.88) 0%, rgba(0, 44, 93, 0.72) 45%, rgba(227, 6, 19, 0.15) 100%),
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
                0 4px 6px -1px rgba(0, 44, 93, 0.08),
                0 24px 48px -12px rgba(0, 44, 93, 0.22),
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
            border: 1px solid rgba(0, 44, 93, 0.08);
        }}
        .ficha-etapas-progress-fill {{
            height: 100%;
            min-width: 0;
            border-radius: 999px;
            background: linear-gradient(90deg, {COR_VERMELHO} 0%, {COR_AZUL_ESC} 100%);
            transition: width 0.4s cubic-bezier(0.22, 1, 0.36, 1);
            box-shadow: 0 1px 3px rgba(0, 44, 93, 0.12);
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
            box-shadow: 0 1px 3px rgba(0, 44, 93, 0.06);
            transition: box-shadow 0.35s ease, transform 0.35s ease;
            animation: fichaFadeIn 0.55s cubic-bezier(0.22, 1, 0.36, 1) both;
        }}
        .section-card:hover {{
            box-shadow: 0 8px 24px -6px rgba(0, 44, 93, 0.12);
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
            border-color: rgba(0, 44, 93, 0.35) !important;
            box-shadow: 0 0 0 3px rgba(0, 44, 93, 0.08) !important;
        }}
        .stButton > button {{
            border-radius: 12px !important;
            transition: transform 0.2s ease, box-shadow 0.2s ease !important;
        }}
        .stButton > button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 20px -6px rgba(0, 44, 93, 0.25) !important;
        }}
        .stButton button[kind="primary"] {{
            background: linear-gradient(180deg, {COR_VERMELHO} 0%, #c50512 100%) !important;
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
            box-shadow: 0 2px 12px rgba(0, 44, 93, 0.1) !important;
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
            box-shadow: 0 2px 12px rgba(0, 44, 93, 0.1);
        }}
        .ficha-alert--azul strong {{
            color: {COR_AZUL_ESC};
        }}
        .ficha-alert--vermelho {{
            border: 2px solid {COR_VERMELHO};
            background: #ffffff;
            color: {COR_AZUL_ESC};
            box-shadow: 0 2px 12px rgba(227, 6, 19, 0.12);
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
            box-shadow: 0 4px 14px rgba(0, 44, 93, 0.12);
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
    """Aviso informativo — borda e ênfase azul Direcional (#002c5d)."""
    st.markdown(
        f'<div class="ficha-alert ficha-alert--azul">{_md_bold_to_html(msg)}</div>',
        unsafe_allow_html=True,
    )


def _alert_vermelho(msg: str) -> None:
    """Alerta de atenção — borda vermelha Direcional (#e30613), texto azul escuro."""
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


def _widget_campo(c: dict):
    k = c["key"]
    sk = f"fld_{k}"
    label = c["label"]
    help_txt = c.get("help")
    tipo = c["tipo"]

    if tipo == "text":
        return st.text_input(label, key=sk, help=help_txt)
    if tipo == "textarea":
        return st.text_area(label, key=sk, help=help_txt, height=88)
    if tipo == "date":
        return st.text_input(label, key=sk, placeholder="31/12/2024", help=help_txt)
    if tipo == "number":
        return st.text_input(label, key=sk, help=help_txt or "Use ponto ou vírgula decimal.")
    if tipo == "id":
        return st.text_input(label, key=sk, help=help_txt)
    if tipo == "select":
        opts = c.get("opcoes") or [""]
        cur = st.session_state.get(sk)
        if cur is not None and cur not in opts:
            st.session_state[sk] = opts[0]
        return st.selectbox(label, options=opts, key=sk, help=help_txt)
    if tipo == "multiselect":
        opts = c.get("opcoes") or []
        return st.multiselect(label, options=opts, default=[], key=sk, help=help_txt)
    return st.text_input(label, key=sk, help=help_txt)


def _coletar_dados_formulario() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for c in CAMPOS:
        sk = f"fld_{c['key']}"
        out[c["key"]] = st.session_state.get(sk)
    return out


def _init_defaults():
    """Sugestões padrão para Vendas RJ (podem ser alteradas)."""
    if "fld_regional" not in st.session_state:
        st.session_state["fld_regional"] = "RJ"
    if "fld_status_corretor" not in st.session_state:
        st.session_state["fld_status_corretor"] = "Pré credenciado"
    if "fld_origem" not in st.session_state:
        st.session_state["fld_origem"] = "Indicação"


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
    payload["MobilePhone"] = "21999999999"
    avisos.append(
        "Sugerimos informar seu **celular com DDD** ou uma chave PIX em **Telefone** "
        "para facilitarmos o seu contato."
    )
    return avisos


def _nome_candidato_ficha(dados: dict[str, Any]) -> str:
    nome = (dados.get("nome_completo") or "").strip()
    if not nome:
        nome = f"{dados.get('first_name') or ''} {dados.get('last_name') or ''}".strip()
    return nome or "Candidato"


def montar_html_email_ficha_pdf(dados: dict[str, Any]) -> str:
    """Corpo HTML do e-mail (estilo Direcional: azul #002c5d, vermelho #e30613)."""
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
            f"<td style=\"padding:10px 12px;border:1px solid {borda};background:#f8fafc;"
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
box-shadow:0 8px 28px rgba(0,44,93,0.08);border:1px solid {borda};">
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
        candidatos: list[str] = []
        if platform.system() == "Windows":
            w = os.environ.get("WINDIR", r"C:\Windows")
            candidatos.extend(
                [
                    os.path.join(w, "Fonts", "arial.ttf"),
                    os.path.join(w, "Fonts", "Arial.ttf"),
                    os.path.join(w, "Fonts", "arialuni.ttf"),
                ]
            )
        else:
            candidatos.extend(
                [
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    "/usr/share/fonts/TTF/DejaVuSans.ttf",
                ]
            )
        for p in candidatos:
            if os.path.isfile(p):
                try:
                    pdfmetrics.registerFont(TTFont("FichaPdfFont", p))
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
        s = str(x) if x is not None else ""
        if font == "Helvetica":
            return s.encode("ascii", "replace").decode("ascii")
        return s

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
        linhas_tab.append([_cell_txt(label), _cell_txt(vtxt)])

    if linhas_tab:
        hdr_bg = colors.HexColor("#e8eef5")
        t = Table([["Campo", "Resposta"]] + linhas_tab, colWidths=[6 * cm, 11 * cm])
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
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fcfdfe")]),
                ]
            )
        )
        story.append(t)
    else:
        story.append(Paragraph(_cell_txt("(Nenhum dado preenchido)"), st_body))

    doc.build(story)
    return buf.getvalue()


def _get_smtp_from_secrets():
    try:
        s = st.secrets.get("ficha_email", {})
        return {
            "host": s.get("SMTP_HOST", "").strip(),
            "port": int(s.get("SMTP_PORT", 587)),
            "user": s.get("SMTP_USER", "").strip(),
            "password": s.get("SMTP_PASSWORD", "").strip(),
            "to": s.get("TO_EMAIL", "").strip(),
            "from_addr": s.get("FROM_EMAIL", "").strip() or s.get("SMTP_USER", "").strip(),
        }
    except Exception:
        return None


def enviar_email_pdf(pdf_bytes: bytes, dados: dict[str, Any], destinatario_extra: str | None) -> tuple[bool, str]:
    cfg = _get_smtp_from_secrets()
    if not cfg or not cfg["host"] or not cfg["user"]:
        return False, "E-mail não configurado (adicione [ficha_email] nos Secrets do Streamlit)."

    to_list = [cfg["to"]] if cfg["to"] else []
    if destinatario_extra and destinatario_extra.strip():
        to_list.append(destinatario_extra.strip())
    if not to_list:
        return False, "Defina TO_EMAIL em [ficha_email] ou informe um e-mail abaixo."

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
        return False, str(e)


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
        if ss.get("ficha_erros_secao_idx") == idx and ss.get("ficha_erros_secao"):
            lista = "<br>".join(f"• {html.escape(e)}" for e in ss["ficha_erros_secao"])
            _alert_vermelho_html(
                f"<strong>Preencha os campos obrigatórios desta etapa:</strong><br>{lista}"
            )
        cols = campos_por_secao(sec)
        mid = (len(cols) + 1) // 2
        if len(cols) <= 3:
            for c in cols:
                _widget_campo(c)
        else:
            left, right = st.columns(2)
            for i, c in enumerate(cols):
                with left if i < mid else right:
                    _widget_campo(c)

        # Mesma largura dos campos: botões dentro do mesmo container da seção.
        if idx < n - 1:
            st.markdown("<br/>", unsafe_allow_html=True)
            col_voltar, col_avancar = st.columns(2)
            with col_voltar:
                if st.button(
                    "Voltar",
                    use_container_width=True,
                    key="ficha_nav_voltar",
                    disabled=(idx <= 0),
                ):
                    ss["ficha_secao_idx"] = idx - 1
                    ss.pop("ficha_erros_secao", None)
                    ss.pop("ficha_erros_secao_idx", None)
                    st.rerun()
            with col_avancar:
                if st.button("Avançar", type="primary", use_container_width=True, key="ficha_nav_avancar"):
                    dados = _coletar_dados_formulario()
                    erros_sec = validar_obrigatorios_secao(sec, dados)
                    if erros_sec:
                        ss["ficha_erros_secao"] = erros_sec
                        ss["ficha_erros_secao_idx"] = idx
                        st.rerun()
                    ss.pop("ficha_erros_secao", None)
                    ss.pop("ficha_erros_secao_idx", None)
                    ss["ficha_secao_idx"] = idx + 1
                    st.rerun()


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
    demo["first_name"] = "Maria"
    demo["last_name"] = "Silva Santos"
    demo["account_name"] = "Imobiliária Parceira — Demo"
    demo["cpf"] = "123.456.789-09"
    demo["email"] = "maria.silva.demo@exemplo.com.br"
    demo["mobile"] = "(21) 99999-0000"
    demo["apelido"] = "Maria"
    return demo


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
    dados = _coletar_dados_formulario()
    erros = validar_obrigatorios(dados)
    if not ss.get("fld_lgpd_ficha"):
        erros.append("Concordância LGPD *")
    if erros:
        linhas = "<br>".join(f"• {html.escape(e)}" for e in erros)
        _alert_vermelho_html(
            f"<strong>Quase lá</strong> — falta completar:<br>{linhas}"
        )
        return

    ss.pop("ficha_modo_teste_design", None)

    creds = _credenciais_de_secrets(st.secrets if hasattr(st, "secrets") else None)
    if not creds:
        _alert_vermelho(
            "Configure **`[google_sheets]`** nos Secrets com `SERVICE_ACCOUNT_JSON` "
            "(JSON da conta de serviço com acesso à planilha)."
        )
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
        _alert_vermelho_html(
            f"<strong>Erro ao gravar na planilha:</strong> {html.escape(str(e))}"
        )
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
        ss["ficha_sucesso"] = True
        st.rerun()
        return

    if conectar_salesforce is None or criar_contato_payload is None:
        atualizar_status_envio_salesforce(
            sid, wname, creds, row_num, "Erro", "Módulo salesforce_api não encontrado.", ""
        )
        ss["sf_erro"] = "Módulo salesforce_api não encontrado."
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
        atualizar_status_envio_salesforce(sid, wname, creds, row_num, "Erro", str(err)[:49000], "")
        ss["sf_erro"] = str(err) if err else "Erro desconhecido ao criar contato."

    ss["sf_avisos"] = avisos
    ss["ficha_sucesso"] = True
    st.rerun()


@st.dialog("Obrigado — você faz parte da nossa operação", width="medium")
def _dialog_recursos_pos_cadastro() -> None:
    """Popup ao concluir o cadastro: PDF, e-mail, mapa, vídeo e links úteis."""
    ss = st.session_state
    dados_sf = dict(ss.get("ficha_dados_enviados") or {})
    pdf_bytes: bytes | None = None
    try:
        pdf_bytes = gerar_pdf_ficha(dados_sf)
    except ImportError as e:
        st.caption(str(e))
    except Exception as e:
        st.caption(f"Não foi possível gerar o PDF: {e}")

    st.markdown(
        """
**Recebemos o seu cadastro com sucesso.** Agradecemos a confiança e o tempo dedicado —
é uma alegria ter você na **Direcional Vendas RJ**.

Confira no **mapa** os empreendimentos, o **vídeo** do simulador (mesma largura do mapa), os **links** úteis,
depois sua **cópia em PDF** e o **envio por e-mail**.
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
            streamlit_key="mapa_empreendimentos_folium_popup",
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

    st.markdown("##### Sua cópia em PDF")
    if pdf_bytes is not None:
        st.download_button(
            label="Baixar PDF",
            data=pdf_bytes,
            file_name=f"ficha_cadastral_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True,
            key="ficha_popup_dl_pdf",
        )
    else:
        st.caption("Instale **reportlab** para gerar o PDF.")

    st.markdown("##### Receber por e-mail")
    mail_extra = st.text_input(
        "Outro e-mail (opcional)",
        placeholder="seu@email.com",
        key="fc_mail_extra_popup",
        label_visibility="visible",
    )
    if st.button("Enviar PDF por e-mail", use_container_width=True, key="ficha_popup_enviar_email"):
        if pdf_bytes is None:
            _alert_vermelho("PDF indisponível.")
        else:
            ok, msg = enviar_email_pdf(pdf_bytes, dados_sf, mail_extra)
            if ok:
                _alert_azul(msg)
            else:
                _alert_vermelho(msg)

    st.markdown("")
    if st.button("Finalizar", type="primary", use_container_width=True, key="ficha_dialog_recursos_fechar"):
        ss["ficha_popup_recursos_ok"] = True
        st.rerun()


def main():
    st.set_page_config(
        page_title="Credenciamento | Direcional Vendas RJ",
        page_icon=None,
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    _aplicar_secrets_sf()
    aplicar_estilo()

    ss = st.session_state
    ss.setdefault("ficha_sucesso", False)

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
                f"<strong>Detalhe:</strong> {html.escape(str(err_sf))}"
            )

        avisos = ss.get("sf_avisos") or []
        if avisos:
            lista = "<br>".join(f"• {html.escape(a)}" for a in avisos)
            _alert_vermelho_html(f"<strong>Avisos:</strong><br>{lista}")

        st.caption(
            "A **cópia em PDF** e o **envio por e-mail** ficam no **popup** de boas-vindas "
            "(junto do mapa, vídeo e links). Se você já fechou o popup, inicie um novo cadastro para abri-lo de novo."
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
            st.rerun()

        st.markdown(
            '<div class="footer">Direcional Engenharia · Vendas Rio de Janeiro</div>',
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
    secoes = secoes_ordenadas()
    _render_secao_formulario(secoes)

    ultima = len(secoes) > 0 and int(st.session_state.get("ficha_secao_idx", 0)) == len(secoes) - 1
    if ultima:
        st.markdown("---")
        st.checkbox(
            "Estou de acordo com o uso dos meus dados para o credenciamento na Direcional, conforme a LGPD. *",
            key="fld_lgpd_ficha",
        )
        if st.button("Enviar meu cadastro", type="primary", use_container_width=True, key="ficha_enviar"):
            _processar_envio_cadastro()
        if st.button(
            "Voltar",
            use_container_width=True,
            key="ficha_voltar_ultima",
            disabled=(len(secoes) <= 1),
        ):
            ss["ficha_secao_idx"] = max(0, len(secoes) - 2)
            st.rerun()


if __name__ == "__main__":
    main()
