# -*- coding: utf-8 -*-
"""
Salesforce - Login e envio de cadastro de corretores (Contact)
Semelhante ao sisarv_streamlit: login/senha configuráveis, upload de planilha.
Envio via API (simple_salesforce): use Security Token para "Enviar corretores".
Colunas esperadas: DATA DE PREECHIMENTO, IMPULSO, COORDENADOR, RESPONSÁVEL PELO PROCESSO,
GERENTE DESIGNADO, REGIONAL, EMAIL, TELEFONE, CPF, CHAVE PIX (APENAS CPF), DIA 1..6,
TECNORISK, CONTRATO, BV/SALES, CURSO TTI (IPA), CRECI ESTÁGIO, N° DO CRECI, DIRIACADEMY,
STATUS, COMENTÁRIOS E OBSERVAÇÕES.
"""

import streamlit as st
import pandas as pd
import io
import os
import subprocess
import sys

# Módulo da API Salesforce (SALESFORCE_PASSWORD = senha + Security Token)
try:
    from salesforce_api import conectar_salesforce, preenchimento_em_massa
except ImportError:
    conectar_salesforce = None
    preenchimento_em_massa = None

# Cores e estilo (referência Direcional)
COR_AZUL_ESC = "#002c5d"
COR_VERMELHO = "#e30613"
COR_FUNDO = "#fcfdfe"
COR_BORDA = "#eef2f6"
COR_INPUT_BG = "#f0f2f6"

COLUNAS_CORRETORES = [
    "DATA DE PREECHIMENTO", "IMPULSO", "COORDENADOR", "RESPONSÁVEL PELO PROCESSO",
    "GERENTE DESIGNADO", "REGIONAL", "EMAIL", "TELEFONE", "CPF",
    "CHAVE PIX ( APENAS CPF) ", "DIA 1", "DIA 2", "DIA 3", " DIA 4", "DIA 5", "DIA 6",
    "TECNORISK", "CONTRATO", "BV/SALES", "CURSO TTI (IPA)", "CRECI ESTÁGIO", "N° DO CRECI",
    "DIRIACADEMY", "STATUS", "COMENTÁRIOS E OBSERVAÇÕES",
]

# Record Type "Corretor" no Salesforce (ajuste se o Id for diferente no seu org)
RECORD_TYPE_CORRETOR = "012f1000000n6nN"


def _valor_coluna(row, df_cols, *nomes):
    """Obtém o valor da linha para a primeira coluna que existir (nome exato ou normalizado)."""
    cols_lower = {str(c).strip().lower(): c for c in df_cols}
    for n in nomes:
        k = str(n).strip().lower()
        if k in cols_lower:
            val = row.get(cols_lower[k])
            return val if pd.notna(val) and str(val).strip() else None
    return None


def planilha_para_contactos(df):
    """Converte DataFrame da planilha em lista de dicts para Contact (API)."""
    df_cols = list(df.columns)
    lista = []
    for _, row in df.iterrows():
        email = _valor_coluna(row, df_cols, "EMAIL")
        coordenador = _valor_coluna(row, df_cols, "COORDENADOR")
        telefone = _valor_coluna(row, df_cols, "TELEFONE")
        last_name = (coordenador if coordenador else str(email) if email else "Corretor").strip()[:80]
        contacto = {"LastName": last_name, "RecordTypeId": RECORD_TYPE_CORRETOR, "Description": "Importado via Streamlit (API)"}
        if email:
            contacto["Email"] = str(email).strip()[:80]
        if telefone:
            contacto["Phone"] = str(telefone).strip()[:40]
        lista.append(contacto)
    return lista


def aplicar_estilo():
    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800;900&family=Inter:wght@300;400;500;600;700&display=swap');

        html, body, [data-testid="stAppViewContainer"] {{
            font-family: 'Inter', sans-serif;
            color: {COR_AZUL_ESC};
            background-color: {COR_FUNDO};
        }}

        h1, h2, h3, h4 {{
            font-family: 'Montserrat', sans-serif !important;
            color: {COR_AZUL_ESC} !important;
            font-weight: 800;
            text-align: center;
        }}

        .block-container {{ max-width: 980px !important; padding: 2.2rem !important; }}

        .hero {{
            border: 1px solid {COR_BORDA};
            border-radius: 18px;
            background: linear-gradient(160deg, #ffffff 0%, #f8fbff 100%);
            padding: 22px 22px 18px 22px;
            margin-bottom: 18px;
            box-shadow: 0 12px 30px -24px rgba(0, 44, 93, 0.35);
        }}
        .hero-title {{
            font-family: 'Montserrat', sans-serif;
            color: {COR_AZUL_ESC};
            font-size: 1.25rem;
            font-weight: 900;
            margin: 0;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }}
        .hero-sub {{
            margin-top: 6px;
            color: #334155;
            font-size: 0.95rem;
            line-height: 1.45;
        }}
        .mini-grid {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 10px;
            margin-top: 14px;
        }}
        .mini-card {{
            border: 1px solid {COR_BORDA};
            border-radius: 12px;
            padding: 10px 12px;
            background: #ffffff;
        }}
        .mini-card b {{
            color: {COR_AZUL_ESC};
            font-size: 0.75rem;
            display: block;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            margin-bottom: 4px;
        }}
        .mini-card span {{
            color: #334155;
            font-size: 0.88rem;
        }}

        .section-card {{
            border: 1px solid {COR_BORDA};
            background: #ffffff;
            border-radius: 14px;
            padding: 16px 16px 10px 16px;
            margin-bottom: 14px;
        }}
        .section-head {{
            font-family: 'Montserrat', sans-serif;
            font-size: 0.86rem;
            color: {COR_AZUL_ESC};
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-weight: 800;
            margin-bottom: 8px;
            padding-bottom: 8px;
            border-bottom: 2px solid #edf2f7;
        }}

        div[data-baseweb="input"] {{
            border-radius: 8px !important;
            border: 1px solid #e2e8f0 !important;
            background-color: {COR_INPUT_BG} !important;
        }}

        .row-widget.stButton, .stButton {{
            width: 100% !important;
            max-width: 100% !important;
        }}
        .stButton {{ display: block !important; }}
        .stButton button {{
            font-family: 'Inter', sans-serif;
            border-radius: 8px !important;
            box-sizing: border-box !important;
            width: 100% !important;
            max-width: 100% !important;
            height: 38px !important;
            min-height: 38px !important;
            font-weight: 700 !important;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        .stButton button[kind="primary"] {{
            background: {COR_VERMELHO} !important;
            color: #ffffff !important;
            border: none !important;
        }}
        .stButton button[kind="primary"]:hover {{ background: #c40510 !important; }}

        .header-container {{
            text-align: center;
            padding: 46px 0;
            background: #ffffff;
            margin-bottom: 24px;
            border-radius: 0 0 24px 24px;
            border-bottom: 1px solid {COR_BORDA};
            box-shadow: 0 10px 25px -15px rgba(0,44,93,0.15);
        }}
        .header-title {{
            font-family: 'Montserrat', sans-serif;
            color: {COR_AZUL_ESC};
            font-size: 2.05rem;
            font-weight: 900;
            margin: 0;
            text-transform: uppercase;
            letter-spacing: 0.15em;
        }}
        .header-subtitle {{
            color: {COR_AZUL_ESC};
            font-size: 0.95rem;
            font-weight: 600;
            margin-top: 10px;
            opacity: 0.85;
        }}
        .status-ok {{
            border: 1px solid #bbf7d0;
            color: #166534;
            background: #f0fdf4;
            padding: 10px 12px;
            border-radius: 10px;
            font-size: 0.88rem;
            margin: 8px 0 12px 0;
        }}
        .status-info {{
            border: 1px solid #dbeafe;
            color: #1d4ed8;
            background: #eff6ff;
            padding: 10px 12px;
            border-radius: 10px;
            font-size: 0.88rem;
            margin: 8px 0 12px 0;
        }}
        .footer {{ text-align: center; padding: 32px 0; color: {COR_AZUL_ESC}; font-size: 0.8rem; opacity: 0.7; }}
        </style>
    """, unsafe_allow_html=True)


def carregar_planilha(uploaded_file):
    """Lê xlsx, csv ou similar e retorna DataFrame."""
    nome = (uploaded_file.name or "").lower()
    raw = uploaded_file.read()
    if nome.endswith(".xlsx") or nome.endswith(".xls"):
        return pd.read_excel(io.BytesIO(raw))
    if nome.endswith(".csv"):
        try:
            return pd.read_csv(io.BytesIO(raw), encoding="utf-8", sep=";")
        except Exception:
            return pd.read_csv(io.BytesIO(raw), encoding="utf-8", sep=",")
    if nome.endswith(".ods"):
        try:
            return pd.read_excel(io.BytesIO(raw), engine="odf")
        except Exception:
            st.error("Para arquivos .ods instale: pip install odfpy")
            return None
    st.warning("Formato não suportado. Use .xlsx, .csv ou .ods.")
    return None


def main():
    st.set_page_config(page_title="Salesforce - Corretores", page_icon="📋", layout="centered")
    aplicar_estilo()

    st.markdown(
        '<div class="header-container">'
        '<div class="header-title">Salesforce</div>'
        '<div class="header-subtitle">Login e cadastro de corretores (Contact)</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="hero">'
        '<p class="hero-title">Painel de Importação de Corretores</p>'
        '<div class="hero-sub">Use este painel para fazer login no Salesforce, baixar HTML pós-login e enviar corretores via API em lote.</div>'
        '<div class="mini-grid">'
        '<div class="mini-card"><b>Módulo 1</b><span>Login + exportação HTML</span></div>'
        '<div class="mini-card"><b>Módulo 2</b><span>Envio em massa via API</span></div>'
        '<div class="mini-card"><b>Entrada</b><span>Planilha XLSX/CSV/ODS</span></div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    with st.form("form_salesforce"):
        st.markdown('<div class="section-card"><div class="section-head">Credenciais Salesforce</div>', unsafe_allow_html=True)
        login = st.text_input("E-mail (login)", placeholder="seu_email@direcional.com.br", key="sf_login")
        senha = st.text_input("Senha", type="password", placeholder="••••••••", key="sf_senha")
        token_api = st.text_input(
            "Security Token (para envio via API)",
            type="password",
            placeholder="Cole o token recebido por e-mail (Reset My Security Token)",
            help="Para **Enviar corretores** via API: informe aqui o Security Token (recebido por e-mail ao redefinir em Configurações do Salesforce). Senha e token são enviados separados.",
            key="sf_token",
        )
        totp = st.text_input(
            "Código do Authenticator",
            placeholder="123456",
            max_chars=6,
            help="Código de 6 dígitos do Google Authenticator (obrigatório se a conta tiver 2FA). Usado apenas em 'Fazer login e salvar HTML'.",
            key="sf_totp",
        )
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-card"><div class="section-head">Planilha de Corretores</div>', unsafe_allow_html=True)
        st.caption("Colunas esperadas: DATA DE PREECHIMENTO, IMPULSO, COORDENADOR, EMAIL, TELEFONE, CPF, etc.")
        uploaded = st.file_uploader(
            "Envie a planilha (XLSX, CSV ou ODS) com os dados dos corretores",
            type=["xlsx", "xls", "csv", "ods"],
            key="sf_upload",
        )
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-card"><div class="section-head">Ações</div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            btn_login_html = st.form_submit_button("FAZER LOGIN E SALVAR HTML", type="primary", use_container_width=True)
        with col2:
            btn_enviar = st.form_submit_button("ENVIAR CORRETORES", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    if btn_login_html:
        if not login or not senha:
            st.error("Preencha **e-mail** e **senha** do Salesforce.")
            st.markdown('<div class="footer">Direcional Engenharia</div>', unsafe_allow_html=True)
            return
        script_dir = os.path.dirname(os.path.abspath(__file__))
        script_login = os.path.join(script_dir, "salesforce_login_salvar_html.py")
        arquivo_html = os.path.join(script_dir, "salesforce_pagina_pos_login.html")
        if not os.path.isfile(script_login):
            st.error("Arquivo **salesforce_login_salvar_html.py** não encontrado na mesma pasta.")
            return
        env = os.environ.copy()
        env["SALESFORCE_USER"] = login.strip()
        env["SALESFORCE_PASSWORD"] = senha.strip()
        if totp and totp.strip():
            env["SALESFORCE_TOTP"] = totp.strip()
        with st.spinner("Fazendo login e salvando HTML..."):
            try:
                cmd = [sys.executable, script_login, "--out", arquivo_html]
                if totp and totp.strip():
                    cmd.extend(["--totp", totp.strip()])
                r = subprocess.run(
                    cmd,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    cwd=script_dir,
                )
                if r.returncode == 0:
                    st.success("Login concluído. HTML salvo.")
                    st.markdown('<div class="status-ok">Autenticação concluída com sucesso. Você pode baixar o HTML pós-login abaixo.</div>', unsafe_allow_html=True)
                    if os.path.isfile(arquivo_html):
                        with open(arquivo_html, "r", encoding="utf-8") as f:
                            html_content = f.read()
                        st.download_button(
                            "Baixar HTML da página pós-login",
                            html_content,
                            file_name="salesforce_pagina_pos_login.html",
                            mime="text/html",
                            use_container_width=True,
                        )
                else:
                    st.error(f"Erro ao executar login. Verifique as credenciais e o código do Authenticator (6 dígitos).\n\n{r.stderr or r.stdout}")
            except subprocess.TimeoutExpired:
                st.error("Tempo esgotado. Tente rodar o script manualmente: python salesforce_login_salvar_html.py")
            except Exception as e:
                st.error(f"Erro: {e}")
        st.markdown('<div class="footer">Direcional Engenharia</div>', unsafe_allow_html=True)
        return

    if btn_enviar:
        if not login or not senha:
            st.error("Preencha **e-mail** e **senha** do Salesforce.")
            st.markdown('<div class="footer">Direcional Engenharia</div>', unsafe_allow_html=True)
            return
        if not (token_api and token_api.strip()):
            st.error("Para enviar corretores via API, preencha o **Security Token** (recebido por e-mail ao redefinir o token no Salesforce).")
            st.markdown('<div class="footer">Direcional Engenharia</div>', unsafe_allow_html=True)
            return
        if uploaded is None:
            st.error("Envie a planilha de corretores.")
            st.markdown('<div class="footer">Direcional Engenharia</div>', unsafe_allow_html=True)
            return
        if conectar_salesforce is None or preenchimento_em_massa is None:
            st.error("Módulo **salesforce_api** não encontrado. Instale: pip install simple_salesforce")
            st.markdown('<div class="footer">Direcional Engenharia</div>', unsafe_allow_html=True)
            return
        df_raw = carregar_planilha(uploaded)
        if df_raw is None or df_raw.empty:
            st.error("Não foi possível ler a planilha ou ela está vazia.")
            st.markdown('<div class="footer">Direcional Engenharia</div>', unsafe_allow_html=True)
            return
        df_raw.columns = df_raw.columns.str.strip()
        lista_contactos = planilha_para_contactos(df_raw)
        # Definir credenciais para a API (senha e token separados é o modo recomendado)
        os.environ["SALESFORCE_USER"] = login.strip()
        os.environ["SALESFORCE_PASSWORD"] = senha.strip()
        os.environ["SALESFORCE_TOKEN"] = (token_api.strip() or "")
        with st.spinner("Conectando ao Salesforce e enviando corretores via API..."):
            sf = conectar_salesforce()
        if sf is None:
            st.error("Não foi possível conectar ao Salesforce. Verifique e-mail, senha e Security Token.")
            st.markdown('<div class="footer">Direcional Engenharia</div>', unsafe_allow_html=True)
            return
        resultado = preenchimento_em_massa(sf, lista_contactos)
        if resultado is not None:
            st.success(f"Envio em massa concluído: **{len(lista_contactos)}** contacto(s) enviado(s) via API.")
        else:
            st.warning("O envio em massa foi executado; verifique no Salesforce se houve falhas em alguns registos.")
        st.markdown('<div class="status-info">Processamento finalizado. Confira os registros no Salesforce para validar duplicidades, erros de validação e campos obrigatórios.</div>', unsafe_allow_html=True)
        with st.expander("Visualizar primeiras linhas da planilha"):
            st.dataframe(df_raw.head(20), use_container_width=True, hide_index=True)
        st.markdown('<div class="footer">Direcional Engenharia</div>', unsafe_allow_html=True)
        return

    st.markdown(
        '<div class="footer">Informe as credenciais e use "Fazer login e salvar HTML" para obter a página pós-login, '
        'ou envie a planilha de corretores.</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
