# -*- coding: utf-8 -*-
"""
Ficha de credenciamento — Direcional Vendas RJ (corretores).
APP 1: FORMULÁRIO DE ENTRADA DE DADOS
Design Premium, Dados Derivados, Cabeçalho de 2 Linhas e Aba Split App.
"""
from __future__ import annotations

import base64
import html
import io
import json
import logging
import os
import re
import streamlit as st
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_DIR_APP = Path(__file__).resolve().parent

# --- Constantes de Design ---
COR_AZUL_ESC = "#04428f"
COR_VERMELHO = "#cb0935"
COR_VERMELHO_ESCURO = "#9e0828"
COR_BORDA = "#eef2f6"
COR_TEXTO_LABEL = "#1e293b"
URL_LOGO_DIRECIONAL = "https://logodownload.org/wp-content/uploads/2021/04/direcional-engenharia-logo.png"

CAPITAIS_MAP = {
    "AC": "Rio Branco", "AL": "Maceió", "AM": "Manaus", "AP": "Macapá", "BA": "Salvador", "CE": "Fortaleza", 
    "DF": "Brasília", "ES": "Vitória", "GO": "Goiânia", "MA": "São Luís", "MG": "Belo Horizonte", "MS": "Campo Grande", 
    "MT": "Cuiabá", "PA": "Belém", "PB": "João Pessoa", "PE": "Recife", "PI": "Teresina", "PR": "Curitiba", 
    "RJ": "Rio de Janeiro", "RN": "Natal", "RO": "Porto Velho", "RR": "Boa Vista", "RS": "Porto Alegre", 
    "SC": "Florianópolis", "SE": "Aracaju", "SP": "São Paulo", "TO": "Palmas",
}

def normalize_text(text: Any) -> str:
    if text is None: return ""
    s = str(text).strip().upper()
    s = "".join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    return s

def formatar_cpf_mascara(val: Any) -> str:
    digits = re.sub(r"\D", "", str(val or ""))
    if len(digits) != 11: return str(val or "")
    return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"

# =============================================================================
# ESTRUTURA DE CAMPOS (PEDIDOS NO FORMULÁRIO)
# =============================================================================
SEC_ORDER = ("Dados Pessoais", "Endereço", "Dados para Contato", "Dados Familiares", "Dados Bancários Pessoa Física", "Informações para contato", "CRECI/TTI")

def _campos_def():
    return [
        {"key": "nome_completo", "label": "Nome completo *", "sec": "Dados Pessoais", "tipo": "text", "sf": "FirstName", "req": True},
        {"key": "birthdate", "label": "Data de nascimento *", "sec": "Dados Pessoais", "tipo": "date", "sf": "Birthdate", "req": True},
        {"key": "estado_civil", "label": "Estado Civil *", "sec": "Dados Pessoais", "tipo": "select", "sf": "EstadoCivil__c", "opcoes": ["--Nenhum--", "Solteiro", "Casado", "Divorciado", "Viúvo"], "req": True},
        {"key": "nome_conjuge", "label": "Nome do Cônjuge", "sec": "Dados Pessoais", "tipo": "text", "sf": "Nome_do_Conjuge__c", "req": False},
        {"key": "cpf", "label": "CPF *", "sec": "Dados Pessoais", "tipo": "text", "sf": "CPF__c", "req": True},
        {"key": "nacionalidade", "label": "Nacionalidade *", "sec": "Dados Pessoais", "tipo": "text", "sf": "Nacionalidade__c", "req": True},
        {"key": "uf_naturalidade", "label": "UF Naturalidade *", "sec": "Dados Pessoais", "tipo": "select", "sf": "UF_Naturalidade__c", "opcoes": list(CAPITAIS_MAP.keys()), "req": True},
        {"key": "rg", "label": "RG *", "sec": "Dados Pessoais", "tipo": "text", "sf": "RG__c", "req": True},
        {"key": "uf_rg", "label": "UF RG *", "sec": "Dados Pessoais", "tipo": "select", "sf": "UF_RG__c", "opcoes": list(CAPITAIS_MAP.keys()), "req": True},
        {"key": "tipo_pix", "label": "Tipo do PIX *", "sec": "Dados Pessoais", "tipo": "select", "sf": "Tipo_do_PIX__c", "opcoes": ["--Nenhum--", "CPF", "CNPJ", "E-mail", "Celular", "Chave aleatória"], "req": True},
        {"key": "dados_pix", "label": "Dados para PIX *", "sec": "Dados Pessoais", "tipo": "text", "sf": "Dados_para_PIX__c", "req": True},
        {"key": "endereco_cep", "label": "CEP *", "sec": "Endereço", "tipo": "text", "sf": "EnderecoResidencialCEP__c", "req": True},
        {"key": "endereco_logradouro", "label": "Logradouro *", "sec": "Endereço", "tipo": "text", "sf": "EnderecoResidencialLogradouro__c", "req": True},
        {"key": "endereco_numero", "label": "Número *", "sec": "Endereço", "tipo": "text", "sf": "EnderecoResidencialNumero__c", "req": True},
        {"key": "endereco_complemento", "label": "Complemento", "sec": "Endereço", "tipo": "text", "sf": "EnderecoResidencialComplemento__c", "req": False},
        {"key": "endereco_bairro", "label": "Bairro *", "sec": "Endereço", "tipo": "text", "sf": "EnderecoResidencialBairro__c", "req": True},
        {"key": "endereco_cidade", "label": "Cidade *", "sec": "Endereço", "tipo": "text", "sf": "EnderecoResidencialCidade__c", "req": True},
        {"key": "endereco_estado", "label": "Estado (UF) *", "sec": "Endereço", "tipo": "select", "sf": "EnderecoResidencialEstado__c", "opcoes": list(CAPITAIS_MAP.keys()), "req": True},
        {"key": "mobile", "label": "Celular *", "sec": "Dados para Contato", "tipo": "text", "sf": "MobilePhone", "req": True},
        {"key": "email", "label": "E-mail *", "sec": "Dados para Contato", "tipo": "text", "sf": "Email", "req": True},
        {"key": "nome_mae", "label": "Nome da Mãe *", "sec": "Dados Familiares", "tipo": "text", "sf": "Nome_da_Mae__c", "req": True},
        {"key": "nome_pai", "label": "Nome do Pai *", "sec": "Dados Familiares", "tipo": "text", "sf": "Nome_do_Pai__c", "req": True},
        {"key": "possui_filhos", "label": "Possui Filho(s)?", "sec": "Dados Familiares", "tipo": "select", "sf": "Possui_Filho__c", "opcoes": ["Não", "Sim"], "req": False},
        {"key": "qtd_filhos", "label": "Quantidade de Filhos", "sec": "Dados Familiares", "tipo": "text", "sf": "Quantidade_de_Filhos__c", "req": False},
        {"key": "banco", "label": "Banco *", "sec": "Dados Bancários Pessoa Física", "tipo": "select", "sf": "Banco__c", "opcoes": ["--Nenhum--", "001 – Banco do Brasil S.A.", "033 – Banco Santander", "104 – Caixa", "237 – Bradesco", "260 – Nubank"], "req": True},
        {"key": "conta_bancaria", "label": "Conta Bancária *", "sec": "Dados Bancários Pessoa Física", "tipo": "text", "sf": "Conta_Banc_ria__c", "req": True},
        {"key": "agencia_bancaria", "label": "Agência Bancária *", "sec": "Dados Bancários Pessoa Física", "tipo": "text", "sf": "Ag_ncia_Banc_ria__c", "req": True},
        {"key": "gerente_vendas", "label": "Gerente de vendas *", "sec": "Informações para contato", "tipo": "select", "sf": "Gerente_de_Vendas__c", "req": True},
        {"key": "sexo", "label": "Sexo *", "sec": "Informações para contato", "tipo": "select", "sf": "Sexo__c", "opcoes": ["--Nenhum--", "Masculino", "Feminino"], "req": True},
        {"key": "camiseta", "label": "Camiseta *", "sec": "Informações para contato", "tipo": "select", "sf": "Camiseta__c", "opcoes": ["--Nenhum--", "P", "M", "G", "GG"], "req": True},
        {"key": "unidade_negocio", "label": "Fará parte de qual rede? *", "sec": "Informações para contato", "tipo": "select", "sf": "Unidade_Negocio__c", "opcoes": ["Direcional", "Riva", "Outra imobiliária (parceira)"], "req": True},
        {"key": "atividade", "label": "Função na operação *", "sec": "Informações para contato", "tipo": "select", "sf": "Atividade__c", "opcoes": ["Corretor", "Captador", "Corretor Parceiro"], "req": True},
        {"key": "possui_creci", "label": "Possui CRECI? *", "sec": "CRECI/TTI", "tipo": "select", "sf": "Possui_CRECI__c", "opcoes": ["Não", "Sim"], "req": True},
        {"key": "creci", "label": "CRECI", "sec": "CRECI/TTI", "tipo": "text", "sf": "CRECI__c", "req": False},
        {"key": "status_creci", "label": "Status CRECI", "sec": "CRECI/TTI", "tipo": "select", "sf": "Status_CRECI__c", "opcoes": ["--Nenhum--", "Definitivo", "Estágio", "Pendente"], "req": False},
    ]

# Campos totais na base (incluindo derivados)
CAMPOS_TOTAL = _campos_def() + [
    {"key": "naturalidade", "label": "Naturalidade *", "sf": "Naturalidade__c"},
    {"key": "salutation", "label": "Tratamento", "sf": "Salutation"},
    {"key": "apelido", "label": "Apelido", "sf": "Apelido__c"},
    {"key": "regional", "label": "Regional *", "sf": "Regional__c"},
    {"key": "status_corretor", "label": "Status Corretor *", "sf": "Status_Corretor__c"},
    {"key": "origem", "label": "Origem *", "sf": "Origem__c"},
    {"key": "data_entrevista", "label": "Data da Entrevista", "sf": "Data_da_Entrevista__c"},
    {"key": "data_contrato", "label": "Data Contrato", "sf": "Data_Contrato__c"},
    {"key": "data_credenciamento", "label": "Data Credenciamento", "sf": "Data_Credenciamento__c"},
    {"key": "multiplicador_nivel", "label": "Multiplicador de Nível", "sf": "Multiplicador__c"},
    {"key": "multiplicador_regime", "label": "Multiplicador de Regime", "sf": "Multiplicador_de_Regime__c"},
    {"key": "tipo_corretor", "label": "Tipo Corretor *", "sf": "Tipo_Corretor__c"},
]

def aplicar_estilo():
    bg_url = "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=1920&q=80"
    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700;900&family=Inter:wght@400;600&display=swap');
        header[data-testid="stHeader"], [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"] {{
            display: none !important; visibility: hidden !important; height: 0px !important;
        }}
        .stApp {{
            background: linear-gradient(135deg, rgba({_hex_rgb_triplet(COR_AZUL_ESC)}, 0.82) 0%, rgba({_hex_rgb_triplet(COR_VERMELHO)}, 0.22) 100%),
                        url("{bg_url}") center / cover no-repeat !important;
        }}
        .block-container {{
            max-width: 920px !important; padding: 2rem !important; background: rgba(255, 255, 255, 0.85) !important;
            backdrop-filter: blur(18px); border-radius: 24px !important; box-shadow: 0 24px 48px -12px rgba(4,66,143,0.18);
            margin-top: 20px !important;
        }}
        h1, h2, h3 {{ font-family: 'Montserrat' !important; color: {COR_AZUL_ESC} !important; }}
        .ficha-hero-bar {{
            height: 4px; width: 100%; border-radius: 999px;
            background: linear-gradient(90deg, {COR_AZUL_ESC}, {COR_VERMELHO}, {COR_AZUL_ESC});
            background-size: 200% 100%; margin: 1.2rem 0;
        }}
        .section-head {{ font-weight: 800; border-bottom: 2px solid #eef2f6; padding-bottom: 0.5rem; margin-bottom: 1rem; color: {COR_AZUL_ESC}; text-transform: uppercase; font-size: 0.8rem; }}
        .stButton button[kind="primary"] {{ background: linear-gradient(180deg, {COR_VERMELHO} 0%, {COR_VERMELHO_ESCURO} 100%) !important; color: white !important; font-weight: 700 !important; border-radius: 12px !important; }}
        </style>
    """, unsafe_allow_html=True)

def _hex_rgb_triplet(hex_color: str) -> str:
    x = hex_color.lstrip("#")
    return f"{int(x[0:2], 16)}, {int(x[2:4], 16)}, {int(x[4:6], 16)}"

def _processar_envio_cadastro():
    ss = st.session_state
    dados = dict(ss.get("ficha_snap_campos", {}))
    # Captura campos da ultima etapa
    for c in _campos_def():
        if f"fld_{c['key']}" in ss: dados[c["key"]] = ss[f"fld_{c['key']}"]
    
    if not ss.get("fld_lgpd_ficha"):
        st.error("Aceite os termos da LGPD.")
        return

    try:
        import gspread
        from google.oauth2.service_account import Credentials
        gs_cfg = st.secrets["google_sheets"]
        creds_dict = json.loads(gs_cfg["SERVICE_ACCOUNT_JSON"])
        gc = gspread.authorize(Credentials.from_service_account_info(creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"]))
        sh = gc.open_by_key(gs_cfg["SPREADSHEET_ID"])
        ws = sh.worksheet("Split App")
        
        # --- DERIVAÇÃO DE DADOS ---
        dados["nome_completo"] = normalize_text(dados.get("nome_completo"))
        dados["nome_conjuge"] = normalize_text(dados.get("nome_conjuge")) if dados.get("estado_civil") == "Casado" else ""
        
        uf_nasc = str(dados.get("uf_naturalidade", "")).strip().upper()
        dados["naturalidade"] = CAPITAIS_MAP.get(uf_nasc, "")
        
        sexo = dados.get("sexo", "")
        dados["salutation"] = "Sr." if sexo == "Masculino" else "Sra." if sexo == "Feminino" else ""
        
        primeiro_nome = str(dados["nome_completo"]).split()[0]
        dados["apelido"] = f"{primeiro_nome}_RJ01"
        dados["regional"] = "RJ"
        dados["status_corretor"] = "Pré credenciado"
        dados["origem"] = "RH"
        
        hoje = datetime.now().strftime("%d/%m/%Y")
        dados["data_entrevista"] = dados["data_contrato"] = dados["data_credenciamento"] = hoje
        
        funcao = dados.get("atividade", "")
        dados["multiplicador_nivel"] = 0.9 if funcao == "Captador" else 1.0
        dados["multiplicador_regime"] = 1.0
        
        rede = dados.get("unidade_negocio", "")
        dados["tipo_corretor"] = "Parceiros (Externo)" if "Outra" in rede else "Direcional Vendas – Autônomos"

        # --- GRAVAÇÃO ---
        headers_row1 = ["Data e hora do envio", "Link do contato (Salesforce)"] + [c["label"] for c in CAMPOS_TOTAL] + ["Envio?", "Log / erro"]
        headers_row2 = ["Timestamp", "Link_SF"] + [c["sf"] for c in CAMPOS_TOTAL] + ["Status_Envio", "Log_Erro"]
        
        if not ws.get_all_values():
            ws.update("A1:ZZ2", [headers_row1, headers_row2])

        linha = [datetime.now().strftime("%d/%m/%Y %H:%M:%S"), ""]
        for c in CAMPOS_TOTAL:
            val = dados.get(c["key"], "")
            if c["key"] == "cpf": val = formatar_cpf_mascara(val)
            linha.append(str(val))
        linha.extend(["Pendente", "Aguardando Dashboard"])
        
        ws.append_row(linha, value_input_option="USER_ENTERED")
        ss["ficha_sucesso"] = True
        st.rerun()
    except Exception as e:
        st.error(f"Erro na base: {e}")

def main():
    st.set_page_config(page_title="Credenciamento | Direcional", layout="centered")
    aplicar_estilo()
    ss = st.session_state
    if "ficha_sucesso" not in ss: ss["ficha_sucesso"] = False
    if "step" not in ss: ss["step"] = 0
    if "ficha_snap_campos" not in ss: ss["ficha_snap_campos"] = {}

    if ss["ficha_sucesso"]:
        st.markdown(f'<div style="text-align:center;"><img src="{URL_LOGO_DIRECIONAL}" width="180"></div>', unsafe_allow_html=True)
        st.success("✓ Cadastro realizado com sucesso!")
        st.video("https://youtu.be/7cm3wFnoCSY")
        if st.button("Novo Cadastro"):
            for k in list(ss.keys()): del ss[k]
            st.rerun()
        return

    st.markdown(f'<div style="text-align:center;"><img src="{URL_LOGO_DIRECIONAL}" width="180"></div>', unsafe_allow_html=True)
    st.markdown('<p style="text-align:center; font-family:Montserrat; font-weight:900; font-size:1.6rem; color:#04428f; margin:0;">Credenciamento Vendas RJ</p>', unsafe_allow_html=True)
    st.markdown('<div class="ficha-hero-bar"></div>', unsafe_allow_html=True)

    secoes = SEC_ORDER
    idx = ss["step"]
    sec = secoes[idx]
    
    st.progress((idx + 1) / len(secoes), text=f"Etapa {idx+1} de {len(secoes)}: {sec}")

    with st.container():
        st.markdown(f'<p class="section-head">{sec}</p>', unsafe_allow_html=True)
        cols_vis = [c for c in _campos_def() if c["sec"] == sec]
        
        # Filtro de visibilidade do Cônjuge
        if sec == "Dados Pessoais" and normalize_text(ss.get("fld_estado_civil")) != "CASADO":
            cols_vis = [c for c in cols_vis if c["key"] != "nome_conjuge"]

        with st.form(f"f_{idx}", border=False):
            for i in range(0, len(cols_vis), 2):
                c1 = cols_vis[i]
                c2 = cols_vis[i+1] if i+1 < len(cols_vis) else None
                L, R = st.columns(2) if c2 else (st.container(), None)
                with L: 
                    k, sk, label, tipo = c1["key"], f"fld_{c1['key']}", c1["label"], c1["tipo"]
                    if tipo == "text": st.text_input(label, key=sk)
                    elif tipo == "select": st.selectbox(label, options=c1.get("opcoes", []), key=sk)
                    elif tipo == "date": st.date_input(label, key=sk, format="DD/MM/YYYY", min_value=date(1900,1,1))
                if c2:
                    with R:
                        k, sk, label, tipo = c2["key"], f"fld_{c2['key']}", c2["label"], c2["tipo"]
                        if tipo == "text": st.text_input(label, key=sk)
                        elif tipo == "select": st.selectbox(label, options=c2.get("opcoes", []), key=sk)
                        elif tipo == "date": st.date_input(label, key=sk, format="DD/MM/YYYY", min_value=date(1900,1,1))
            
            if idx == len(secoes) - 1:
                st.checkbox("Aceito os termos da LGPD. *", key="fld_lgpd_ficha")
            
            st.markdown("<br>", unsafe_allow_html=True)
            col_b, col_n = st.columns(2)
            with col_b:
                if st.form_submit_button("Voltar", use_container_width=True, disabled=(idx == 0)):
                    ss["step"] -= 1
                    st.rerun()
            with col_n:
                label = "Finalizar" if idx == len(secoes) - 1 else "Avançar"
                if st.form_submit_button(label, type="primary", use_container_width=True):
                    for c in cols_vis: ss["ficha_snap_campos"][c["key"]] = ss.get(f"fld_{c['key']}")
                    if idx < len(secoes) - 1:
                        ss["step"] += 1
                        st.rerun()
                    else:
                        _processar_envio_cadastro()

if __name__ == "__main__": main()
