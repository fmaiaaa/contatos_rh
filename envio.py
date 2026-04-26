# -*- coding: utf-8 -*-
"""
Ficha de credenciamento — Direcional Vendas RJ (corretores).
APP 2: GESTÃO E INTEGRAÇÃO SALESFORCE
Exibição de pendentes, seleção múltipla e persistência de logs.
"""
from __future__ import annotations

import base64
import html
import json
import os
import streamlit as st
import pandas as pd
import time
from datetime import datetime
from typing import Any, Dict, List, Tuple
from pathlib import Path

_DIR_APP = Path(__file__).resolve().parent

# --- Salesforce Integration ---
try:
    from simple_salesforce import Salesforce, SalesforceAuthenticationFailed
except ImportError:
    Salesforce = None

# --- Constantes de Design (Sincronizadas com App 1) ---
COR_AZUL_ESC = "#04428f"
COR_VERMELHO = "#cb0935"
COR_VERMELHO_ESCURO = "#9e0828"
COR_BORDA = "#eef2f6"
URL_LOGO_DIRECIONAL = "https://logodownload.org/wp-content/uploads/2021/04/direcional-engenharia-logo.png"
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
        
        header[data-testid="stHeader"], [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"] {{
            display: none !important; visibility: hidden !important; height: 0px !important;
        }}
        
        .stApp {{
            background: linear-gradient(135deg, rgba({RGB_AZUL_CSS}, 0.85) 0%, rgba({RGB_VERMELHO_CSS}, 0.15) 100%),
                        url("{bg_url}") center / cover no-repeat !important;
            background-attachment: fixed !important;
        }}
        
        .block-container {{
            max-width: 1200px !important;
            padding-top: 2rem !important;
            background: rgba(255, 255, 255, 0.85) !important;
            backdrop-filter: blur(20px);
            border-radius: 24px !important;
            border: 1px solid rgba(255, 255, 255, 0.45);
            box-shadow: 0 24px 48px -12px rgba({RGB_AZUL_CSS}, 0.25);
            margin-top: 20px !important;
        }}
        
        h1, h2, h3 {{ font-family: 'Montserrat', sans-serif !important; color: {COR_AZUL_ESC} !important; }}
        
        .ficha-logo-wrap {{
            text-align: center;
            padding: 0.1rem 0 0.45rem 0;
        }}
        .ficha-logo-wrap img {{
            max-height: 65px; width: auto;
            object-fit: contain; display: inline-block;
        }}

        .ficha-hero-bar {{
            height: 4px; width: 100%; border-radius: 999px;
            background: linear-gradient(90deg, {COR_AZUL_ESC}, {COR_VERMELHO}, {COR_AZUL_ESC});
            background-size: 200% 100%; animation: fichaShimmer 4s infinite alternate;
            margin: 1rem 0;
        }}
        
        @keyframes fichaShimmer {{ 0% {{ background-position: 0% 50%; }} 100% {{ background-position: 200% 50%; }} }}

        .stButton button[kind="primary"] {{
            background: linear-gradient(180deg, {COR_VERMELHO} 0%, {COR_VERMELHO_ESCURO} 100%) !important;
            border: none !important; border-radius: 12px !important; font-weight: 700 !important;
            color: white !important;
        }}

        .log-container {{
            background: rgba(248, 250, 252, 0.9);
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 15px;
            margin-top: 20px;
            font-family: 'Inter', sans-serif;
            max-height: 400px;
            overflow-y: auto;
        }}
        
        .log-entry {{ padding: 5px 0; border-bottom: 1px solid #f1f5f9; font-size: 13px; }}
        .log-success {{ color: #16a34a; font-weight: 600; }}
        .log-error {{ color: #dc2626; font-weight: 600; }}
        </style>
    """, unsafe_allow_html=True)

def _resolver_png_raiz(nome: str) -> Path | None:
    for base in (_DIR_APP, _DIR_APP.parent):
        p = base / nome
        if p.is_file(): return p
    return None

def _exibir_logo_topo() -> None:
    path = _resolver_png_raiz(LOGO_TOPO_ARQUIVO)
    try:
        if path:
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            st.markdown(f'<div class="ficha-logo-wrap"><img src="data:image/png;base64,{b64}" alt="Direcional" /></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="ficha-logo-wrap"><img src="{URL_LOGO_DIRECIONAL}" alt="Direcional" /></div>', unsafe_allow_html=True)
    except:
        st.markdown(f'<div class="ficha-logo-wrap"><img src="{URL_LOGO_DIRECIONAL}" alt="Direcional" /></div>', unsafe_allow_html=True)

def conectar_salesforce():
    sf_sec = st.secrets.get("salesforce", {})
    user = (os.environ.get("SALESFORCE_USER") or sf_sec.get("USER", "")).strip()
    pwd = (os.environ.get("SALESFORCE_PASSWORD") or sf_sec.get("PASSWORD", "")).strip()
    token = (os.environ.get("SALESFORCE_TOKEN") or sf_sec.get("TOKEN", "")).strip()
    if not (user and pwd and token): return None
    try:
        return Salesforce(username=user, password=pwd, security_token=token, domain="login")
    except: return None

def ler_base_pendente():
    import gspread
    from google.oauth2.service_account import Credentials
    gs_sec = st.secrets["google_sheets"]
    creds_dict = json.loads(gs_sec["SERVICE_ACCOUNT_JSON"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    gc = gspread.authorize(Credentials.from_service_account_info(creds_dict, scopes=scopes))
    sh = gc.open_by_key(gs_sec["SPREADSHEET_ID"])
    ws = sh.worksheet(gs_sec.get("WORKSHEET_NAME", "Corretores"))
    
    # Tratamento manual de cabeçalhos duplicados para evitar erro do pandas
    raw_data = ws.get_all_values()
    if not raw_data: return pd.DataFrame(), ws
        
    headers = raw_data[0]
    seen = {}
    new_headers = []
    for h in headers:
        if not h: h = "Vazio"
        if h in seen:
            seen[h] += 1
            new_headers.append(f"{h}_{seen[h]}")
        else:
            seen[h] = 0
            new_headers.append(h)
            
    df = pd.DataFrame(raw_data[1:], columns=new_headers)
    
    # Filtro: Somente quem não possui link do Salesforce
    col_link = "Link Salesforce" if "Link Salesforce" in df.columns else "Link do contato (Salesforce)"
    if col_link in df.columns:
        df_pendentes = df[df[col_link].astype(str).str.strip() == ""]
    else:
        df_pendentes = df
        
    return df_pendentes, ws

def atualizar_status_planilha(ws: Any, df_idx: int, status: str, log: str, link: str = ""):
    row_num = df_idx + 2
    raw_headers = ws.row_values(1)
    
    def find_col(name):
        try: return raw_headers.index(name) + 1
        except ValueError: return None

    idx_envio = find_col("Envio?")
    idx_log = find_col("Log / erro")
    idx_link = find_col("Link Salesforce") or find_col("Link do contato (Salesforce)")
    
    if idx_envio: ws.update_cell(row_num, idx_envio, status)
    if idx_log: ws.update_cell(row_num, idx_log, log)
    if idx_link and link: ws.update_cell(row_num, idx_link, link)

def formatar_planilha_base(ws: Any):
    """Aplica organização visual na planilha Google (Cores e Bordas)."""
    try:
        headers = ws.row_values(1)
        n = len(headers)
        
        def rgb(r: float, g: float, b: float): return {"red": r, "green": g, "blue": b, "alpha": 1.0}
        
        # Batch update simplificado para o cabeçalho
        requests = [{
            "repeatCell": {
                "range": {"sheetId": ws.id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": n},
                "cell": {"userEnteredFormat": {"backgroundColor": rgb(0.01, 0.25, 0.56), "textFormat": {"foregroundColor": rgb(1,1,1), "bold": True}}},
                "fields": "userEnteredFormat(backgroundColor,textFormat)"
            }
        }]
        ws.spreadsheet.batch_update({"requests": requests})
    except: pass

def main():
    fav = _resolver_png_raiz(FAVICON_ARQUIVO)
    st.set_page_config(page_title="Dashboard | Direcional", page_icon=str(fav) if fav else None, layout="wide")
    aplicar_estilo_gestao()
    
    _exibir_logo_topo()
    st.markdown('<p style="font-family:\'Montserrat\'; font-size:1.8rem; font-weight:900; color:#04428f; text-align:center; margin:0;">Gestão de Integração Salesforce</p>', unsafe_allow_html=True)
    st.markdown('<div class="ficha-hero-bar"></div>', unsafe_allow_html=True)

    # Inicializar logs no session_state
    if 'gestao_logs' not in st.session_state:
        st.session_state['gestao_logs'] = []

    try:
        df, ws = ler_base_pendente()
    except Exception as e:
        st.error(f"Erro ao conectar com a planilha: {e}")
        return

    if df.empty:
        st.info("Nenhum cadastro pendente encontrado.")
        if st.button("Recarregar Dados"):
            st.session_state['gestao_logs'] = []
            st.rerun()
        return

    # Interface de Seleção
    st.markdown("### Cadastros Pendentes")
    col_sel_all, col_status = st.columns([1, 4])
    
    with col_sel_all:
        selecionar_todos = st.toggle("Selecionar todos", value=False)

    # Preparar DataFrame para o editor
    df_display = df.copy()
    df_display.insert(0, "Selecionar", selecionar_todos)

    edited_df = st.data_editor(
        df_display,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Selecionar": st.column_config.CheckboxColumn("Enviar?", default=False),
        },
        disabled=[c for c in df_display.columns if c != "Selecionar"]
    )

    selecionados = edited_df[edited_df["Selecionar"] == True]

    # Botão de Ação
    if not selecionados.empty:
        if st.button(f"Realizar envio de {len(selecionados)} corretores selecionados", type="primary", use_container_width=True):
            sf = conectar_salesforce()
            if not sf:
                st.error("Falha na autenticação com Salesforce. Verifique os Secrets.")
                return

            prog_bar = st.progress(0.0)
            status_text = st.empty()
            
            sucessos = 0
            erros = 0

            for i, (idx, row) in enumerate(selecionados.iterrows()):
                nome = row.get("Nome completo *") or row.get("Nome completo") or "Candidato"
                status_text.markdown(f"**Integrando:** {nome}")
                
                try:
                    # Payload simplificado baseado na estrutura original
                    partes = str(nome).strip().split(None, 1)
                    fname = partes[0][:40]
                    lname = (partes[1] if len(partes) > 1 else partes[0])[:80]
                    
                    payload = {
                        "FirstName": fname,
                        "LastName": lname,
                        "Email": row.get("E-mail *") or row.get("E-mail"),
                        "MobilePhone": str(row.get("Celular *") or row.get("Celular")),
                        "CPF__c": str(row.get("CPF *") or row.get("CPF")),
                        "Regional__c": row.get("Regional *") or row.get("Regional"),
                        "Origem__c": "RH"
                    }
                    
                    res = sf.Contact.create(payload)
                    cid = res.get("id")
                    
                    if cid:
                        link = f"https://direcional.lightning.force.com/lightning/r/Contact/{cid}/view"
                        atualizar_status_planilha(ws, idx, "Sucesso", "Integrado via Dashboard", link)
                        st.session_state['gestao_logs'].append({"status": "sucesso", "msg": f"Sucesso: {nome} integrado com sucesso."})
                        sucessos += 1
                    else:
                        atualizar_status_planilha(ws, idx, "Erro", "Salesforce não retornou ID")
                        st.session_state['gestao_logs'].append({"status": "erro", "msg": f"Erro: {nome} - Salesforce não retornou ID."})
                        erros += 1
                
                except Exception as e:
                    err_msg = str(e)[:200]
                    atualizar_status_planilha(ws, idx, "Erro", err_msg)
                    st.session_state['gestao_logs'].append({"status": "erro", "msg": f"Falha: {nome} - {err_msg}"})
                    erros += 1
                
                # Pausa para visualização e atualização do tqdm (progress bar)
                time.sleep(1.0)
                prog_bar.progress((i + 1) / len(selecionados))

            status_text.success(f"Processamento concluído. Sucessos: {sucessos} | Erros: {erros}")
            formatar_planilha_base(ws)
            st.rerun()

    # Exibição dos Logs Persistentes
    if st.session_state['gestao_logs']:
        st.markdown("### Logs de Processamento")
        with st.container():
            st.markdown('<div class="log-container">', unsafe_allow_html=True)
            for log in reversed(st.session_state['gestao_logs']):
                clase = "log-success" if log['status'] == "sucesso" else "log-error"
                st.markdown(f'<div class="log-entry {clase}">{log["msg"]}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        if st.button("Limpar logs e realizar novo envio", use_container_width=True):
            st.session_state['gestao_logs'] = []
            st.rerun()

if __name__ == "__main__":
    main()
