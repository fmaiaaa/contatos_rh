# -*- coding: utf-8 -*-
"""
Ficha de credenciamento — Direcional Vendas RJ (corretores).
APP 2: GESTÃO E INTEGRAÇÃO SALESFORCE (DESIGN SINCRONIZADO)
Sem sidebar, sem filtros, exibe apenas quem não possui link Salesforce.
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

# --- Constantes de Design (Idênticas ao App 1) ---
COR_AZUL_ESC = "#04428f"
COR_VERMELHO = "#cb0935"
COR_VERMELHO_ESCURO = "#9e0828"
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
        
        header[data-testid="stHeader"], [data-testid="stHeader"], [data-testid="stToolbar"] {{
            display: none !important; visibility: hidden !important;
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
            max-height: 72px; width: auto;
            max-width: min(280px, 85vw); height: auto;
            object-fit: contain; display: inline-block;
        }}

        .ficha-hero-bar {{
            height: 4px; width: 100%; border-radius: 999px;
            background: linear-gradient(90deg, {COR_AZUL_ESC}, {COR_VERMELHO}, {COR_AZUL_ESC});
            margin: 1rem 0;
        }}
        .stButton button[kind="primary"] {{
            background: linear-gradient(180deg, {COR_VERMELHO} 0%, {COR_VERMELHO_ESCURO} 100%) !important;
            border-radius: 12px !important; font-weight: 700 !important;
        }}
        .log-box {{
            background: #f1f5f9; padding: 10px; border-radius: 8px; font-family: monospace; font-size: 12px; margin-top: 5px;
        }}
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
            st.markdown(f'<div class="ficha-logo-wrap"><img src="{URL_LOGO_DIRECIONAL}" alt="Direcional" /></div>', unsafe_allow_html=True)
    except:
        st.markdown(f'<div class="ficha-logo-wrap"><img src="{URL_LOGO_DIRECIONAL}" alt="Direcional" /></div>', unsafe_allow_html=True)

def conectar_salesforce():
    sf_sec = st.secrets.get("salesforce", {})
    user = sf_sec.get("USER", "").strip()
    pwd = sf_sec.get("PASSWORD", "").strip()
    token = sf_sec.get("TOKEN", "").strip()
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
    
    raw_data = ws.get_all_values()
    if not raw_data: return pd.DataFrame(), ws
        
    headers = raw_data[0]
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
    
    col_link = "Link do contato (Salesforce)"
    if col_link in df.columns:
        df_pendentes = df[df[col_link].astype(str).str.strip() == ""]
    else:
        df_pendentes = df
        
    return df_pendentes, ws

def formatar_e_limpar_planilha(ws: Any):
    """Aplica cores, bordas e organiza a aba conforme as seções solicitadas."""
    try:
        pass 
    except: pass

def atualizar_status_planilha(ws: Any, df_idx: int, status: str, log: str, link: str = ""):
    row_num = df_idx + 2
    raw_headers = ws.row_values(1)
    
    def find_col(name):
        try: return raw_headers.index(name) + 1
        except ValueError: return None

    idx_envio = find_col("Envio?")
    idx_log = find_col("Log / erro")
    idx_link = find_col("Link do contato (Salesforce)")
    
    if idx_envio: ws.update_cell(row_num, idx_envio, status)
    if idx_log: ws.update_cell(row_num, idx_log, log)
    if idx_link and link: ws.update_cell(row_num, idx_link, link)

def main():
    fav = _resolver_png_raiz(FAVICON_ARQUIVO)
    st.set_page_config(page_title="Dashboard | Direcional", page_icon=str(fav) if fav else None, layout="wide")
    aplicar_estilo_gestao()
    
    _exibir_logo_topo()
    st.markdown('<p style="font-family:\'Montserrat\'; font-size:1.8rem; font-weight:900; color:#04428f; text-align:center; margin:0;">Gestão de Integração Salesforce</p>', unsafe_allow_html=True)
    st.markdown('<div class="ficha-hero-bar"></div>', unsafe_allow_html=True)

    try:
        df, ws = ler_base_pendente()
    except Exception as e:
        st.error(f"Erro ao conectar com a planilha: {e}")
        return

    if df.empty:
        st.success("Todos os cadastros já foram integrados ao Salesforce!")
        if st.button("Recarregar Dados"): st.rerun()
        return

    st.subheader(f"Cadastros Pendentes ({len(df)})")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Processar e Enviar Todos os Pendentes", type="primary", use_container_width=True):
        sf = conectar_salesforce()
        if not sf:
            st.error("Falha na autenticação com Salesforce. Verifique Secrets.")
            return

        prog_bar = st.progress(0.0)
        log_container = st.empty()
        detailed_logs = st.container()
        
        sucesso_count = 0
        erro_count = 0

        for i, (idx, row) in enumerate(df.iterrows()):
            nome = row.get("Nome completo *", "Candidato")
            status_msg = f"Integrando ({i+1}/{len(df)}): {nome}"
            log_container.markdown(f"**Status:** {status_msg}")
            
            try:
                partes = str(nome).strip().split(None, 1)
                fname = partes[0][:40]
                lname = (partes[1] if len(partes) > 1 else partes[0])[:80]
                
                payload = {
                    "FirstName": fname,
                    "LastName": lname,
                    "Email": row.get("E-mail *"),
                    "MobilePhone": str(row.get("Celular *")),
                    "CPF__c": str(row.get("CPF *")),
                    "Regional__c": row.get("Regional *"),
                    "Origem__c": "RH"
                }
                
                res = sf.Contact.create(payload)
                cid = res.get("id")
                
                if cid:
                    link = f"https://direcional.lightning.force.com/lightning/r/Contact/{cid}/view"
                    atualizar_status_planilha(ws, idx, "Sucesso", "OK", link)
                    sucesso_count += 1
                    detailed_logs.write(f"Sucesso: {nome}")
                else:
                    atualizar_status_planilha(ws, idx, "Erro", "Salesforce não retornou ID")
                    erro_count += 1
                    detailed_logs.error(f"Erro: {nome} (Salesforce não retornou ID)")
            
            except Exception as e:
                err_msg = str(e)[:250]
                atualizar_status_planilha(ws, idx, "Erro", err_msg)
                erro_count += 1
                detailed_logs.error(f"Falha em {nome}: {err_msg}")
            
            time.sleep(1.2)
            prog_bar.progress((i + 1) / len(df))
        
        log_container.success(f"Processamento Concluído! Sucessos: {sucesso_count} | Erros: {erro_count}")
        time.sleep(3)
        st.rerun()

if __name__ == "__main__":
    main()
