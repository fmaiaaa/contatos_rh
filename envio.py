# -*- coding: utf-8 -*-
"""
Ficha de credenciamento — Direcional Vendas RJ (corretores).
APP 2: GESTÃO E INTEGRAÇÃO SALESFORCE
Design Premium Unificado, Logs Persistentes, Seleção Total e Processamento em Lote.
"""
from __future__ import annotations

import base64
import html
import json
import os
import streamlit as st
import pandas as pd
import time
import re
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
        }}
        .block-container {{
            max-width: 1200px !important; padding: 2rem !important; background: rgba(255, 255, 255, 0.88) !important;
            backdrop-filter: blur(20px); border-radius: 24px !important; box-shadow: 0 24px 48px -12px rgba(4,66,143,0.25);
            margin-top: 20px !important;
        }}
        h1, h2, h3 {{ font-family: 'Montserrat' !important; color: {COR_AZUL_ESC} !important; }}
        .ficha-hero-bar {{ height: 4px; width: 100%; border-radius: 999px; background: linear-gradient(90deg, {COR_AZUL_ESC}, {COR_VERMELHO}, {COR_AZUL_ESC}); margin: 1rem 0; }}
        .stButton button[kind="primary"] {{ background: linear-gradient(180deg, {COR_VERMELHO} 0%, {COR_VERMELHO_ESCURO} 100%) !important; color: white !important; font-weight: 700 !important; border-radius: 12px !important; }}
        .log-container {{ background: #ffffff; border: 1px solid #eef2f6; border-radius: 12px; padding: 20px; margin-top: 25px; max-height: 500px; overflow-y: auto; box-shadow: inset 0 2px 4px rgba(0,0,0,0.05); }}
        .log-entry {{ padding: 10px 0; font-size: 13px; line-height: 1.5; font-family: 'Inter', sans-serif; }}
        .log-divider {{ border: 0; border-top: 1px solid #f1f5f9; margin: 10px 0; }}
        .log-success {{ color: #16a34a; font-weight: 600; }}
        .log-error {{ color: #dc2626; font-weight: 600; }}
        </style>
    """, unsafe_allow_html=True)

def _exibir_logo_topo():
    st.markdown(f'<div style="text-align:center; padding-bottom:1rem;"><img src="{URL_LOGO_DIRECIONAL}" width="180"></div>', unsafe_allow_html=True)

def formatar_cpf_mascara(val: Any) -> str:
    digits = re.sub(r"\D", "", str(val or ""))
    if len(digits) != 11: return str(val or "")
    return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"

def conectar_salesforce():
    sf_sec = st.secrets.get("salesforce", {})
    user, pwd, token = sf_sec.get("USER", ""), sf_sec.get("PASSWORD", ""), sf_sec.get("TOKEN", "")
    if not (user and pwd and token): return None
    try: return Salesforce(username=user, password=pwd, security_token=token, domain="login")
    except: return None

def ler_base_pendente():
    import gspread
    from google.oauth2.service_account import Credentials
    gs_sec = st.secrets["google_sheets"]
    creds_dict = json.loads(gs_sec["SERVICE_ACCOUNT_JSON"])
    gc = gspread.authorize(Credentials.from_service_account_info(creds_dict, ["https://www.googleapis.com/auth/spreadsheets"]))
    sh = gc.open_by_key(gs_sec["SPREADSHEET_ID"])
    ws = sh.worksheet(gs_sec.get("WORKSHEET_NAME", "Corretores"))
    
    all_vals = ws.get_all_values()
    if len(all_vals) < 3: return pd.DataFrame(), ws, [] # Precisa de Row 1, Row 2 e Dados
    
    labels = all_vals[0]
    api_names = all_vals[1]
    data = all_vals[2:]
    
    df = pd.DataFrame(data, columns=labels)
    # Filtro: Mostrar somente quem não tem o Link do contato (Salesforce)
    col_link = "Link do contato (Salesforce)"
    df_pendentes = df[df[col_link].astype(str).str.strip() == ""]
    
    return df_pendentes, ws, api_names

def atualizar_linha_base(ws: Any, df_idx_orig: int, status: str, log: str, link: str = ""):
    row_num = df_idx_orig + 3 # +1 header1, +1 header2, +1 index0
    headers = ws.row_values(1)
    
    try:
        col_envio = headers.index("Envio?") + 1
        col_log = headers.index("Log / erro") + 1
        col_link = headers.index("Link do contato (Salesforce)") + 1
        
        ws.update_cell(row_num, col_envio, status)
        ws.update_cell(row_num, col_log, log)
        if link: ws.update_cell(row_num, col_link, link)
    except: pass

def main():
    st.set_page_config(page_title="Gestão | Direcional", layout="wide")
    aplicar_estilo_gestao()
    _exibir_logo_topo()
    st.markdown('<p style="text-align:center; font-family:Montserrat; font-weight:900; font-size:1.8rem; color:#04428f; margin:0;">Dashboard de Integração Salesforce</p>', unsafe_allow_html=True)
    st.markdown('<div class="ficha-hero-bar"></div>', unsafe_allow_html=True)

    if 'gestao_logs' not in st.session_state: st.session_state['gestao_logs'] = []

    try:
        df, ws, api_names = ler_base_pendente()
    except Exception as e:
        st.error(f"Erro na planilha: {e}")
        return

    if df.empty:
        st.info("Nenhum cadastro pendente encontrado.")
        if st.button("Limpar Histórico e Recarregar"):
            st.session_state['gestao_logs'] = []
            st.rerun()
        return

    st.markdown(f"### Cadastros sem Link Salesforce ({len(df)})")
    sel_total = st.toggle("Selecionar todos os pendentes", value=False)

    df_sel = df.copy()
    df_sel.insert(0, "Selecionar", sel_total)

    edited_df = st.data_editor(
        df_sel, hide_index=True, use_container_width=True,
        column_config={"Selecionar": st.column_config.CheckboxColumn("Enviar?", default=False)},
        disabled=[c for c in df_sel.columns if c != "Selecionar"]
    )

    selecionados = edited_df[edited_df["Selecionar"] == True]

    if not selecionados.empty:
        if st.button(f"Processar envio de {len(selecionados)} corretores", type="primary", use_container_width=True):
            sf = conectar_salesforce()
            if not sf:
                st.error("Erro no Salesforce. Verifique os Secrets.")
                return

            prog = st.progress(0.0)
            status_t = st.empty()
            
            sucessos, falhas = 0, 0
            
            # Mapeamento do cabeçalho para APIs (Row 1 -> Row 2)
            map_api = {label: api for label, api in zip(df.columns, api_names)}

            for i, (idx_df, row) in enumerate(selecionados.iterrows()):
                nome = row.get("Nome completo *", "Candidato")
                status_t.markdown(f"**Integrando:** {nome}")
                
                try:
                    # Montagem dinâmica do Payload usando Row 2 da planilha
                    payload = {}
                    for col_label, val in row.items():
                        if col_label == "Selecionar": continue
                        api_key = map_api.get(col_label)
                        if api_key and api_key not in ["Timestamp", "Salesforce_Link", "Status_Envio", "Log_Erro", "N/A"]:
                            # Tratamento Especial: CPF
                            if "CPF" in col_label: val = formatar_cpf_mascara(val)
                            # Tratamento Especial: Regional
                            if "Regional" in col_label and val == "RH": val = "RJ"
                            
                            payload[api_key] = str(val)

                    # Ajuste de Nome para Contato Salesforce
                    partes = str(nome).split(None, 1)
                    payload["FirstName"] = partes[0][:40]
                    payload["LastName"] = (partes[1] if len(partes) > 1 else partes[0])[:80]
                    payload["Origem__c"] = "RH"

                    res = sf.Contact.create(payload)
                    cid = res.get("id")
                    
                    if cid:
                        link = f"https://direcional.lightning.force.com/lightning/r/Contact/{cid}/view"
                        atualizar_linha_base(ws, idx_df, "Sucesso", "OK", link)
                        st.session_state['gestao_logs'].append({"status": "sucesso", "msg": f"Sucesso: {nome} enviado."})
                        sucessos += 1
                    else:
                        atualizar_linha_base(ws, idx_df, "Erro", "Sem ID")
                        falhas += 1
                except Exception as e:
                    msg_erro = str(e)[:300]
                    atualizar_linha_base(ws, idx_df, "Erro", msg_erro)
                    st.session_state['gestao_logs'].append({"status": "erro", "msg": f"Falha: {nome} - {msg_erro}"})
                    falhas += 1
                
                time.sleep(1.0) # Pausa para log
                prog.progress((i + 1) / len(selecionados))

            status_t.success(f"Fim do lote. Sucessos: {sucessos} | Falhas: {falhas}")
            st.rerun()

    if st.session_state['gestao_logs']:
        st.markdown("### Histórico de Processamento")
        l_html = '<div class="log-container">'
        for i, log in enumerate(reversed(st.session_state['gestao_logs'])):
            cls = "log-success" if log['status'] == "sucesso" else "log-error"
            l_html += f'<div class="log-entry {cls}">{log["msg"]}</div>'
            if i < len(st.session_state['gestao_logs']) - 1: l_html += '<hr class="log-divider">'
        l_html += '</div>'
        st.markdown(l_html, unsafe_allow_html=True)
        if st.button("Limpar histórico e realizar nova consulta", use_container_width=True):
            st.session_state['gestao_logs'] = []
            st.rerun()

if __name__ == "__main__": main()
