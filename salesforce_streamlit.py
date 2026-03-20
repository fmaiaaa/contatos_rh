# -*- coding: utf-8 -*-
"""
Novo Contato: Corretor — formulário alinhado ao Salesforce + gravação na planilha Google
e envio opcional via API (simple_salesforce).
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import streamlit as st

try:
    from salesforce_api import conectar_salesforce, criar_contato_payload
except ImportError:
    conectar_salesforce = None
    criar_contato_payload = None

from corretor_campos import (
    CAMPOS,
    cabecalho_planilha,
    campos_por_secao,
    linha_planilha,
    montar_payload_salesforce,
    secoes_ordenadas,
    validar_obrigatorios,
)
from google_sheets_corretor import (
    DEFAULT_SPREADSHEET_ID,
    DEFAULT_WORKSHEET_NAME,
    _credenciais_de_secrets,
    anexar_linha,
    carimbo_brasilia_iso,
)

# Cores Direcional
COR_AZUL_ESC = "#002c5d"
COR_VERMELHO = "#e30613"
COR_FUNDO = "#fcfdfe"
COR_BORDA = "#eef2f6"
COR_INPUT_BG = "#f0f2f6"


def _aplicar_secrets_sf():
    """Injeta SALESFORCE_* a partir de st.secrets (opcional)."""
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


def aplicar_estilo():
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800;900&family=Inter:wght@400;500;600;700&display=swap');
        html, body, [data-testid="stAppViewContainer"] {{
            font-family: 'Inter', sans-serif;
            color: {COR_AZUL_ESC};
            background-color: {COR_FUNDO};
        }}
        h1, h2, h3 {{ font-family: 'Montserrat', sans-serif !important; color: {COR_AZUL_ESC} !important; }}
        .block-container {{ max-width: 1200px !important; padding: 1.5rem !important; }}
        .section-card {{
            border: 1px solid {COR_BORDA};
            background: #ffffff;
            border-radius: 14px;
            padding: 12px 14px 8px 14px;
            margin-bottom: 10px;
        }}
        .section-head {{
            font-family: 'Montserrat', sans-serif;
            font-size: 0.82rem;
            color: {COR_AZUL_ESC};
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-weight: 800;
            margin-bottom: 8px;
            padding-bottom: 6px;
            border-bottom: 2px solid #edf2f7;
        }}
        div[data-baseweb="input"] {{
            border-radius: 8px !important;
            border: 1px solid #e2e8f0 !important;
            background-color: {COR_INPUT_BG} !important;
        }}
        .stButton button[kind="primary"] {{
            background: {COR_VERMELHO} !important;
            color: #ffffff !important;
            border: none !important;
            font-weight: 700 !important;
        }}
        .footer {{ text-align: center; padding: 24px 0; color: {COR_AZUL_ESC}; font-size: 0.8rem; opacity: 0.75; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _widget_campo(c: dict):
    """Renderiza um campo dentro de form; usa st.session_state com chave fixa."""
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
        return st.selectbox(label, options=opts, key=sk, help=help_txt)
    if tipo == "multiselect":
        opts = c.get("opcoes") or []
        return st.multiselect(label, options=opts, default=[], key=sk, help=help_txt)
    return st.text_input(label, key=sk, help=help_txt)


def _coletar_dados_formulario() -> dict:
    out = {}
    for c in CAMPOS:
        sk = f"fld_{c['key']}"
        out[c["key"]] = st.session_state.get(sk)
    return out


def main():
    st.set_page_config(
        page_title="Corretor — Salesforce + Planilha",
        page_icon="📋",
        layout="wide",
    )
    _aplicar_secrets_sf()
    aplicar_estilo()

    st.markdown(
        f'<div style="text-align:center;padding:20px 0 8px 0;">'
        f'<p style="font-family:Montserrat,sans-serif;font-size:1.6rem;font-weight:900;color:{COR_AZUL_ESC};margin:0;">'
        f'NOVO CONTATO: CORRETOR</p>'
        f'<p style="color:#334155;font-size:0.95rem;">Preencha os campos conforme o Salesforce. '
        f'Salve na planilha Google e/ou envie para o Salesforce via API.</p></div>',
        unsafe_allow_html=True,
    )

    with st.expander("Credenciais (Salesforce API + login HTML opcional)", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            login = st.text_input("E-mail Salesforce", key="sf_login", placeholder="email@empresa.com.br")
        with c2:
            senha = st.text_input("Senha", type="password", key="sf_senha")
        with c3:
            token_api = st.text_input(
                "Security Token (API)",
                type="password",
                key="sf_token",
                help="Para criar contato via API.",
            )
        with c4:
            totp = st.text_input("Authenticator (6 dígitos)", max_chars=6, key="sf_totp", help="Só para exportar HTML.")

    st.markdown("---")

    with st.form("form_corretor", clear_on_submit=False):
        for sec in secoes_ordenadas():
            st.markdown(f'<div class="section-card"><div class="section-head">{sec}</div>', unsafe_allow_html=True)
            cols = campos_por_secao(sec)
            # duas colunas quando muitos campos
            mid = (len(cols) + 1) // 2
            if len(cols) <= 3:
                for c in cols:
                    _widget_campo(c)
            else:
                left, right = st.columns(2)
                for i, c in enumerate(cols):
                    with left if i < mid else right:
                        _widget_campo(c)
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("### Ações")
        b1, b2, b3 = st.columns(3)
        with b1:
            sub_plan = st.form_submit_button("Salvar na planilha Google", use_container_width=True)
        with b2:
            sub_sf = st.form_submit_button("Criar contato no Salesforce (API)", type="primary", use_container_width=True)
        with b3:
            sub_html = st.form_submit_button("Login e salvar HTML (local)", use_container_width=True)

    dados = _coletar_dados_formulario()

    # --- Salvar Google
    if sub_plan:
        erros = validar_obrigatorios(dados)
        if erros:
            st.error("Preencha os obrigatórios:\n- " + "\n- ".join(erros))
        else:
            creds = _credenciais_de_secrets(st.secrets if hasattr(st, "secrets") else None)
            if not creds:
                st.error(
                    "Configure **st.secrets** → seção `[google_sheets]` com `SERVICE_ACCOUNT_JSON` "
                    "(JSON da conta de serviço). Veja `COMO_SECRETS_CORRETOR.md`."
                )
            else:
                try:
                    gs = {}
                    if hasattr(st, "secrets"):
                        try:
                            gs = dict(st.secrets.get("google_sheets", {}))
                        except Exception:
                            gs = {}
                    sid = gs.get("SPREADSHEET_ID", DEFAULT_SPREADSHEET_ID)
                    wname = gs.get("WORKSHEET_NAME", DEFAULT_WORKSHEET_NAME)
                    ts = carimbo_brasilia_iso()
                    row = linha_planilha(dados, ts)
                    anexar_linha(row, cabecalho_planilha(), str(sid), str(wname), creds)
                    st.success(f"Linha gravada na planilha (aba **{wname}**).")
                except Exception as e:
                    st.error(f"Erro ao gravar na planilha: {e}")

    # --- Salesforce API
    if sub_sf:
        erros = validar_obrigatorios(dados)
        if erros:
            st.error("Preencha os obrigatórios:\n- " + "\n- ".join(erros))
        elif not login or not senha or not (token_api and str(token_api).strip()):
            st.error("Informe **e-mail**, **senha** e **Security Token** para a API.")
        elif conectar_salesforce is None or criar_contato_payload is None:
            st.error("Módulo **salesforce_api** não encontrado.")
        else:
            payload, avisos = montar_payload_salesforce(dados)
            os.environ["SALESFORCE_USER"] = login.strip()
            os.environ["SALESFORCE_PASSWORD"] = senha.strip()
            os.environ["SALESFORCE_TOKEN"] = (token_api or "").strip()
            with st.spinner("Conectando e criando contato..."):
                sf = conectar_salesforce()
            if not sf:
                st.error("Falha ao conectar ao Salesforce.")
            else:
                cid, err = criar_contato_payload(sf, payload)
                if cid:
                    st.success(f"Contato criado: **{cid}**")
                    st.markdown(
                        f'<div style="padding:10px;background:#f0fdf4;border-radius:8px;">'
                        f'<a href="https://direcional.lightning.force.com/lightning/r/Contact/{cid}/view" '
                        f'target="_blank">Abrir no Salesforce</a></div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.error(f"Erro ao criar contato: {err}")
                if avisos:
                    st.warning("Avisos:\n- " + "\n- ".join(avisos))

    # --- Login HTML (subprocess)
    if sub_html:
        if not login or not senha:
            st.error("Preencha **e-mail** e **senha**.")
        else:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            script_login = os.path.join(script_dir, "salesforce_login_salvar_html.py")
            arquivo_html = os.path.join(script_dir, "salesforce_pagina_pos_login.html")
            if not os.path.isfile(script_login):
                st.error("Arquivo **salesforce_login_salvar_html.py** não encontrado.")
            else:
                env = os.environ.copy()
                env["SALESFORCE_USER"] = login.strip()
                env["SALESFORCE_PASSWORD"] = senha.strip()
                if totp and str(totp).strip():
                    env["SALESFORCE_TOTP"] = str(totp).strip()
                with st.spinner("Login e gravação do HTML..."):
                    try:
                        cmd = [sys.executable, script_login, "--out", arquivo_html]
                        if totp and str(totp).strip():
                            cmd.extend(["--totp", str(totp).strip()])
                        r = subprocess.run(
                            cmd,
                            env=env,
                            capture_output=True,
                            text=True,
                            timeout=120,
                            cwd=script_dir,
                        )
                        if r.returncode == 0 and os.path.isfile(arquivo_html):
                            st.success("HTML salvo.")
                            with open(arquivo_html, "r", encoding="utf-8") as f:
                                html_content = f.read()
                            st.download_button(
                                "Baixar HTML pós-login",
                                html_content,
                                file_name="salesforce_pagina_pos_login.html",
                                mime="text/html",
                            )
                        else:
                            st.error((r.stderr or r.stdout or "Erro desconhecido")[:4000])
                    except Exception as e:
                        st.error(str(e))

    st.markdown('<div class="footer">Direcional Engenharia · Cadastro Corretor</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
