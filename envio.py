# -*- coding: utf-8 -*-
"""
Ficha de credenciamento — Direcional Vendas RJ (corretores).
APP 2: GESTÃO E INTEGRAÇÃO SALESFORCE
Este app lê a planilha, permite filtrar e enviar selecionados para o Salesforce.
"""
from __future__ import annotations

import json
import os
import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Any, Dict, List, Tuple
from pathlib import Path

# --- Salesforce Integration (Original Logic) ---
try:
    from simple_salesforce import Salesforce, SalesforceAuthenticationFailed
except ImportError:
    Salesforce = None

# --- Re-utilização do Estilo e Identidade ---
COR_AZUL_ESC = "#04428f"
COR_VERMELHO = "#cb0935"
RGB_AZUL_CSS = "4, 66, 143" # #04428f

def aplicar_estilo_gestao():
    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@700;900&family=Inter:wght@400;600&display=swap');
        .stApp {{ background: #f8fafc; }}
        h1, h2, h3 {{ font-family: 'Montserrat'; color: {COR_AZUL_ESC}; }}
        .stButton button[kind="primary"] {{
            background: {COR_VERMELHO} !important; border: none !important; border-radius: 10px !important;
        }}
        [data-testid="stSidebar"] {{ background-color: #f1f5f9; }}
        .stDataFrame {{ border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; }}
        </style>
    """, unsafe_allow_html=True)

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
    data = ws.get_all_records()
    return pd.DataFrame(data), ws

def atualizar_status_planilha(ws: Any, df_idx: int, status: str, log: str, link: str = ""):
    # A linha na planilha é df_idx + 2 (considerando cabeçalho)
    # Assumindo a estrutura: [0]Data, [1]Link, ... [N-1]Envio, [N]Log
    row_num = df_idx + 2
    cols = ws.row_values(1)
    
    idx_link = 2 # Coluna B
    idx_envio = len(cols) - 1
    idx_log = len(cols)
    
    ws.update_cell(row_num, idx_envio, status)
    ws.update_cell(row_num, idx_log, log)
    if link:
        ws.update_cell(row_num, idx_link, link)

def main():
    st.set_page_config(page_title="Gestão Vendas RJ | Direcional", layout="wide")
    aplicar_estilo_gestao()
    
    st.title("📊 Painel de Gestão de Credenciamento")
    st.caption("Consulte as respostas e envie candidatos selecionados para o Salesforce.")

    # --- Carregamento de Dados ---
    try:
        df, ws = ler_base_planilha()
    except Exception as e:
        st.error(f"Erro ao conectar com a planilha: {e}")
        return

    # --- Sidebar de Filtros ---
    with st.sidebar:
        st.image("https://logodownload.org/wp-content/uploads/2021/04/direcional-engenharia-logo.png", width=150)
        st.markdown("### Filtros")
        
        f_status = st.multiselect("Status de Envio", options=list(df["Envio?"].unique()) if "Envio?" in df else ["Pendente", "Sucesso", "Erro"])
        f_regional = st.multiselect("Regional", options=list(df["Regional *"].unique()) if "Regional *" in df else [])
        f_nome = st.text_input("Busca por Nome")
        
        st.divider()
        st.info("Selecione os registros na tabela ao lado e clique em 'Processar Envio' no topo.")

    # --- Aplicação de Filtros ---
    df_f = df.copy()
    if f_status: df_f = df_f[df_f["Envio?"].isin(f_status)]
    if f_regional: df_f = df_f[df_f["Regional *"].isin(f_regional)]
    if f_nome: df_f = df_f[df_f["Nome completo *"].str.contains(f_nome, case=False, na=False)]

    # --- Área Principal com Editor de Dados ---
    if df_f.empty:
        st.warning("Nenhum registro encontrado com os filtros selecionados.")
        return

    st.write(f"Exibindo **{len(df_f)}** registros encontrados:")
    
    # Adiciona coluna de seleção
    df_f.insert(0, "Selecionar", False)
    
    edited_df = st.data_editor(
        df_f,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Selecionar": st.column_config.CheckboxColumn("Envio?", help="Selecione para enviar ao Salesforce", default=False),
            "Link do contato (Salesforce)": st.column_config.LinkColumn("Salesforce Link"),
        },
        disabled=[c for c in df_f.columns if c != "Selecionar"]
    )

    selecionados = edited_df[edited_df["Selecionar"] == True]

    # --- Botão de Ação ---
    if not selecionados.empty:
        if st.button(f"🚀 Processar Envio ({len(selecionados)} selecionados)", type="primary"):
            sf = conectar_salesforce()
            if not sf:
                st.error("Erro na conexão com Salesforce. Verifique as credenciais nos Secrets.")
                return

            prog = st.progress(0.0)
            status_area = st.empty()
            
            for i, (idx, row) in enumerate(selecionados.iterrows()):
                status_area.write(f"Processando: {row['Nome completo *']}...")
                
                # Montar Payload Salesforce (Lógica original)
                try:
                    # Divisão básica de nome
                    partes = str(row["Nome completo *"]).strip().split(None, 1)
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
                    
                    # Chamada Salesforce
                    res = sf.Contact.create(payload)
                    cid = res.get("id")
                    
                    if cid:
                        link = f"https://direcional.lightning.force.com/lightning/r/Contact/{cid}/view"
                        atualizar_status_planilha(ws, idx, "Sucesso", "Enviado via Dashboard", link)
                        st.toast(f"✅ {fname} enviado!")
                    else:
                        atualizar_status_planilha(ws, idx, "Erro", "Salesforce não retornou ID", "")
                
                except Exception as e:
                    atualizar_status_planilha(ws, idx, "Erro", str(e)[:200])
                    st.error(f"Erro em {row['Nome completo *']}: {e}")
                
                prog.progress((i + 1) / len(selecionados))
            
            status_area.success("Processamento em lote concluído!")
            st.rerun()

if __name__ == "__main__":
    main()
