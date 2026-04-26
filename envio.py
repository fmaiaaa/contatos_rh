# -*- coding: utf-8 -*-
"""
Ficha de credenciamento — Direcional Vendas RJ (corretores).
APP 2: GESTÃO E INTEGRAÇÃO SALESFORCE
Este app lê a planilha, permite filtrar e enviar selecionados para o Salesforce.
"""
from __future__ import annotations

import base64
import html
import json
import os
import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Any, Dict, List, Tuple
from pathlib import Path

_DIR_APP = Path(__file__).resolve().parent

# --- Salesforce Integration (Original Logic) ---
try:
    from simple_salesforce import Salesforce, SalesforceAuthenticationFailed
except ImportError:
    Salesforce = None

# --- Constantes de Design e Identidade (Alinhadas ao App 1) ---
COR_AZUL_ESC = "#04428f"
COR_VERMELHO = "#cb0935"
COR_FUNDO = "#04428f"
COR_BORDA = "#eef2f6"
COR_INPUT_BG = "#f0f2f6"
COR_TEXTO_MUTED = "#64748b"
COR_TEXTO_LABEL = "#1e293b"
COR_VERMELHO_ESCURO = "#9e0828"

URL_LOGO_DIRECIONAL_EMAIL = "https://logodownload.org/wp-content/uploads/2021/04/direcional-engenharia-logo.png"
LOGO_TOPO_ARQUIVO = "502.57_LOGO DIRECIONAL_V2F-01.png"
FAVICON_ARQUIVO = "502.57_LOGO D_COR_V3F.png"

def _hex_rgb_triplet(hex_color: str) -> str:
    x = hex_color.lstrip("#")
    return f"{int(x[0:2], 16)}, {int(x[2:4], 16)}, {int(x[4:6], 16)}"

RGB_AZUL_CSS = _hex_rgb_triplet(COR_AZUL_ESC)
RGB_VERMELHO_CSS = _hex_rgb_triplet(COR_VERMELHO)

def aplicar_estilo_gestao():
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
            background: linear-gradient(135deg, rgba({RGB_AZUL_CSS}, 0.85) 0%, rgba({RGB_VERMELHO_CSS}, 0.15) 100%),
                        url("{bg_url}") center / cover no-repeat !important;
            background-attachment: fixed !important;
        }}
        
        .block-container {{
            max-width: 1200px !important;
            padding-top: 2rem !important;
            padding-bottom: 2rem !important;
            background: rgba(255, 255, 255, 0.85) !important;
            backdrop-filter: blur(20px);
            border-radius: 24px !important;
            border: 1px solid rgba(255, 255, 255, 0.45);
            box-shadow: 0 24px 48px -12px rgba({RGB_AZUL_CSS}, 0.25);
            animation: fichaFadeIn 0.7s ease-out both;
            margin-top: 20px !important;
        }}
        
        h1, h2, h3 {{ font-family: 'Montserrat', sans-serif !important; color: {COR_AZUL_ESC} !important; }}
        
        .ficha-logo-wrap {{
            text-align: center;
            padding: 0.1rem 0 0.45rem 0;
        }}
        .ficha-logo-wrap img {{
            max-height: 60px; width: auto;
            object-fit: contain; display: inline-block;
        }}

        .ficha-hero-bar {{
            height: 4px; width: 100%; border-radius: 999px;
            background: linear-gradient(90deg, {COR_AZUL_ESC}, {COR_VERMELHO}, {COR_AZUL_ESC});
            background-size: 200% 100%; animation: fichaShimmer 4s infinite alternate;
            margin: 1rem 0;
        }}

        .stButton button[kind="primary"] {{
            background: linear-gradient(180deg, {COR_VERMELHO} 0%, {COR_VERMELHO_ESCURO} 100%) !important;
            border: none !important; border-radius: 12px !important; font-weight: 700 !important;
            color: white !important;
        }}
        
        /* Estilização da Barra Lateral */
        [data-testid="stSidebar"] {{
            background-color: rgba(255, 255, 255, 0.9) !important;
            backdrop-filter: blur(10px);
            border-right: 1px solid {COR_BORDA};
        }}
        
        .stDataFrame {{ 
            border: 1px solid {COR_BORDA}; 
            border-radius: 12px; 
            overflow: hidden; 
            background: white !important;
        }}
        </style>
    """, unsafe_allow_html=True)

def _resolver_png_raiz(nome: str) -> Path | None:
    for base in (_DIR_APP, _DIR_APP.parent):
        p = base / nome
        if p.is_file(): return p
    return None

def _exibir_logo_topo():
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

def conectar_salesforce():
    sf_sec = st.secrets.get("salesforce", {})
    user = (os.environ.get("SALESFORCE_USER") or sf_sec.get("USER") or "").strip()
    pwd = (os.environ.get("SALESFORCE_PASSWORD") or sf_sec.get("PASSWORD") or "").strip()
    token = (os.environ.get("SALESFORCE_TOKEN") or sf_sec.get("TOKEN") or "").strip()
    if not (user and pwd and token): return None
    try:
        return Salesforce(username=user, password=pwd, security_token=token, domain="login")
    except: return None

def ler_base_planilha():
    import gspread
    from google.oauth2.service_account import Credentials
    gs_sec = st.secrets["google_sheets"]
    creds_raw = gs_sec.get("SERVICE_ACCOUNT_JSON")
    creds_dict = creds_raw if isinstance(creds_raw, dict) else json.loads(creds_raw)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    gc = gspread.authorize(Credentials.from_service_account_info(creds_dict, scopes=scopes))
    sh = gc.open_by_key(gs_sec["SPREADSHEET_ID"])
    ws = sh.worksheet(gs_sec.get("WORKSHEET_NAME", "Corretores"))
    
    # --- Correção do Erro de Duplicados ---
    # Em vez de get_all_records(), lemos os valores brutos
    raw_data = ws.get_all_values()
    if not raw_data:
        return pd.DataFrame(), ws
        
    headers = raw_data[0]
    # Tornar cabeçalhos únicos adicionando um sufixo numérico se houver duplicatas
    seen = {}
    new_headers = []
    for h in headers:
        if not h: h = "unnamed"
        if h in seen:
            seen[h] += 1
            new_headers.append(f"{h}_{seen[h]}")
        else:
            seen[h] = 0
            new_headers.append(h)
            
    df = pd.DataFrame(raw_data[1:], columns=new_headers)
    return df, ws

def atualizar_status_planilha(ws: Any, df_idx: int, status: str, log: str, link: str = ""):
    row_num = df_idx + 2
    raw_headers = ws.row_values(1)
    
    # Mapeamento dinâmico baseado no nome da coluna (mesmo com duplicatas na leitura do DF, no Sheets usamos o índice real)
    def find_col(name):
        try:
            return raw_headers.index(name) + 1
        except ValueError:
            return None

    idx_envio = find_col("Envio?")
    idx_log = find_col("Log / erro")
    idx_link = find_col("Link do contato (Salesforce)") or 2 # Fallback coluna B
    
    if idx_envio: ws.update_cell(row_num, idx_envio, status)
    if idx_log: ws.update_cell(row_num, idx_log, log)
    if link: ws.update_cell(row_num, idx_link, link)

def main():
    fav = _resolver_png_raiz(FAVICON_ARQUIVO)
    st.set_page_config(page_title="Gestão Vendas RJ | Direcional", page_icon=str(fav) if fav else None, layout="wide")
    aplicar_estilo_gestao()
    
    _exibir_logo_topo()
    st.markdown('<p style="font-family:\'Montserrat\'; font-size:1.8rem; font-weight:900; color:#04428f; text-align:center; margin:0;">Painel de Gestão de Credenciamento</p>', unsafe_allow_html=True)
    st.markdown('<div class="ficha-hero-bar"></div>', unsafe_allow_html=True)

    # --- Carregamento de Dados ---
    try:
        df, ws = ler_base_planilha()
    except Exception as e:
        st.error(f"Erro ao conectar com a planilha: {e}")
        st.info("Dica: Verifique se os cabeçalhos na planilha Google estão corretos.")
        return

    if df.empty:
        st.warning("A planilha está vazia ou não pôde ser lida.")
        return

    # --- Sidebar de Filtros ---
    with st.sidebar:
        st.markdown("### 🔍 Filtros de Busca")
        
        # Identificar colunas corretamente (tratando os sufixos de duplicatas se existirem)
        col_status = "Envio?" if "Envio?" in df.columns else "Envio?_1" if "Envio?_1" in df.columns else None
        col_regional = "Regional *" if "Regional *" in df.columns else "Regional *_1" if "Regional *_1" in df.columns else None
        col_nome = "Nome completo *" if "Nome completo *" in df.columns else "Nome completo *_1" if "Nome completo *_1" in df.columns else None

        f_status = st.multiselect("Status de Envio", options=list(df[col_status].unique()) if col_status else ["Pendente", "Sucesso", "Erro"])
        f_regional = st.multiselect("Regional", options=list(df[col_regional].unique()) if col_regional else [])
        f_nome = st.text_input("Busca por Nome")
        
        st.divider()
        st.caption("Desenvolvido por Lucas Maia")

    # --- Aplicação de Filtros ---
    df_f = df.copy()
    if f_status and col_status: df_f = df_f[df_f[col_status].isin(f_status)]
    if f_regional and col_regional: df_f = df_f[df_f[col_regional].isin(f_regional)]
    if f_nome and col_nome: df_f = df_f[df_f[col_nome].str.contains(f_nome, case=False, na=False)]

    st.write(f"📋 Encontrados: **{len(df_f)}** registros")
    
    # Adiciona coluna de seleção
    df_f.insert(0, "Selecionar", False)
    
    # Configuração de colunas para o editor
    edited_df = st.data_editor(
        df_f,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Selecionar": st.column_config.CheckboxColumn("Enviar?", help="Marque para integrar ao Salesforce", default=False),
            "Link do contato (Salesforce)": st.column_config.LinkColumn("Salesforce Link"),
        },
        disabled=[c for c in df_f.columns if c != "Selecionar"]
    )

    selecionados = edited_df[edited_df["Selecionar"] == True]

    # --- Botão de Ação ---
    if not selecionados.empty:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button(f"🚀 Enviar {len(selecionados)} corretores para o Salesforce", type="primary", use_container_width=True):
            sf = conectar_salesforce()
            if not sf:
                st.error("Falha na autenticação com Salesforce. Verifique as credenciais.")
                return

            prog_bar = st.progress(0.0)
            status_text = st.empty()
            
            for i, (idx, row) in enumerate(selecionados.iterrows()):
                nome_cand = row.get(col_nome, "Candidato")
                status_text.markdown(f"⏳ Processando: **{nome_cand}**")
                
                try:
                    # Divisão de nome para Salesforce
                    partes = str(nome_cand).strip().split(None, 1)
                    fname = partes[0][:40]
                    lname = (partes[1] if len(partes) > 1 else partes[0])[:80]
                    
                    payload = {
                        "FirstName": fname,
                        "LastName": lname,
                        "Email": row.get("E-mail *"),
                        "MobilePhone": str(row.get("Celular *")),
                        "CPF__c": str(row.get("CPF *")),
                        "Regional__c": row.get("Regional *"),
                        "Status_Corretor__c": row.get("Status Corretor *"),
                        "Unidade_Negocio__c": row.get("Fará parte de qual rede? *"),
                        "Atividade__c": row.get("Função na operação *"),
                        "Origem__c": "RH"
                    }
                    
                    res = sf.Contact.create(payload)
                    cid = res.get("id")
                    
                    if cid:
                        link = f"https://direcional.lightning.force.com/lightning/r/Contact/{cid}/view"
                        atualizar_status_planilha(ws, idx, "Sucesso", CarimboStatus(), link)
                        st.toast(f"✅ {fname} integrado!")
                    else:
                        atualizar_status_planilha(ws, idx, "Erro", "Salesforce não retornou ID")
                
                except Exception as e:
                    atualizar_status_planilha(ws, idx, "Erro", str(e)[:250])
                    st.error(f"Erro ao processar {nome_cand}: {e}")
                
                prog_bar.progress((i + 1) / len(selecionados))
            
            status_text.success(f"✨ Concluído! {len(selecionados)} registros processados.")
            st.rerun()

def CarimboStatus():
    return f"Enviado via Dashboard em {datetime.now().strftime('%d/%m/%Y %H:%M')}"

if __name__ == "__main__":
    main()
