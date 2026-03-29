# -*- coding: utf-8 -*-
"""
Agente de preenchimento de dados de Corretores a partir da ficha cadastral.

Funcionalidades:
- Abre um diálogo do Windows para selecionar o arquivo Excel da ficha cadastral.
- Lê a planilha e monta os dados do corretor conforme regras.
- Usa fuzzy matching ("IA") para associar "Quem indicou você para esta vaga?"
  a uma Account existente (ex.: DIRECIONAL VENDAS RJ - EQUIPE ...).
- Cria contatos no Salesforce.
- Gera um relatório em PDF com:
  - linhas sem match de conta (indicação não encontrada),
  - erros de criação no Salesforce.

Dependências:
  pip install pandas openpyxl simple-salesforce rapidfuzz fpdf2 gspread google-auth
"""

import os
import unicodedata
from datetime import datetime, date
from typing import List, Tuple, Dict, Any

import pandas as pd
from rapidfuzz import process, fuzz
from fpdf import FPDF
from tkinter import Tk, filedialog

from salesforce_api import conectar_salesforce

# Padrão para filtrar contas de equipe
PADRAO_ACCOUNT = "DIRECIONAL VENDAS RJ - EQUIPE %"
# Limiar de similaridade para aceitar match (0-100)
LIMIAR_SIMILARIDADE = 70

# E-mail padrão de fallback quando o e-mail da planilha é inválido
EMAIL_FALLBACK = "apreencherdirecional@gmail.com"

# Caminho base: pasta deste script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def selecionar_arquivo_excel() -> str:
    """Abre um diálogo do Windows para selecionar um arquivo Excel e retorna o caminho."""
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    caminho = filedialog.askopenfilename(
        title="Selecione a planilha de Ficha Cadastral",
        filetypes=[("Excel files", "*.xlsx;*.xls")],
    )
    root.destroy()
    return caminho


def carregar_planilha(path: str) -> pd.DataFrame:
    df = pd.read_excel(path)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def normalizar_nome(texto: Any) -> str:
    """
    Limpa e normaliza nomes para comparação:
    - converte para string
    - remove acentos
    - converte para minúsculas
    - remove caracteres que não sejam letras ou espaço
    - compacta espaços em branco.
    """
    if texto is None or (isinstance(texto, float) and pd.isna(texto)):
        return ""
    s = str(texto).strip()
    if not s:
        return ""
    # remover acentos
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    # tudo minúsculo
    s = s.lower()
    # manter apenas letras e espaços
    s = "".join(c if c.isalpha() or c.isspace() else " " for c in s)
    # compactar espaços
    s = " ".join(s.split())
    return s


def limpar_email(valor: Any) -> str:
    """
    Limpa/valida o e-mail vindo da planilha.
    - Remove espaços
    - Ignora valores vazios, '#N/A' ou claramente inválidos (sem '@').
    """
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return EMAIL_FALLBACK
    s = str(valor).strip()
    if not s or s.upper() == "#N/A":
        return EMAIL_FALLBACK
    if "@" not in s:
        return EMAIL_FALLBACK
    return s


def limpar_escolaridade(valor: Any) -> str:
    """
    Normaliza a escolaridade livre da planilha para um valor aceito na picklist restrita.
    Exemplo:
      - "Ensino Fundamental Completo" -> "Ensino Fundamental"
    Para outros valores, devolve o texto original (trim), para não perder informação.
    """
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    s = str(valor).strip()
    if not s or s.upper() == "#N/A":
        return ""
    s_norm = normalizar_nome(s)
    if "fundamental" in s_norm:
        return "Ensino Fundamental"
    # aqui você pode adicionar outras regras caso veja mais erros de picklist
    return s

def carregar_contas_direcional_vendas(sf) -> pd.DataFrame:
    """Carrega contas DIRECIONAL VENDAS RJ - EQUIPE ... para uso no matching."""
    soql = f"""
        SELECT Id, Name
        FROM Account
        WHERE Name LIKE '{PADRAO_ACCOUNT}'
    """
    print("Buscando contas DIRECIONAL VENDAS RJ - EQUIPE ...")
    res = sf.query(soql)
    registros = []
    while True:
        registros.extend(res.get("records", []))
        if res.get("done"):
            break
        next_url = res.get("nextRecordsUrl")
        if not next_url:
            break
        res = sf.query_more(next_url, True)
    df_accounts = pd.DataFrame(
        [{"Id": r["Id"], "Name": r["Name"]} for r in registros if r.get("Name")]
    )

    # IA simples: extrair apenas a parte do nome da pessoa na equipe
    # Ex.: "DIRECIONAL VENDAS RJ - EQUIPE VICTOR HUGO" -> "VICTOR HUGO"
    def extrair_nome_pessoa_da_conta(nome_conta: str) -> str:
        s = str(nome_conta)
        up = s.upper()
        if "EQUIPE" in up:
            pessoa = up.split("EQUIPE", 1)[1].strip()
        else:
            pessoa = s.strip()
        return pessoa

    df_accounts["NomePessoa"] = df_accounts["Name"].apply(extrair_nome_pessoa_da_conta)
    # Versão normalizada para comparação com IA
    df_accounts["NomePessoaNorm"] = df_accounts["NomePessoa"].apply(normalizar_nome)

    print(f"Encontradas {len(df_accounts)} contas de equipe.")
    return df_accounts


def extrair_nome_indicador(valor: Any) -> str:
    """
    Extrai um nome base de 'Quem indicou você para esta vaga?'.
    Ex.: 'Instagram (Vitor)' -> 'Vitor'
    """
    if valor is None or pd.isna(valor):
        return ""
    s = str(valor).strip()
    if "(" in s and ")" in s:
        dentro = s.split("(", 1)[1].split(")", 1)[0]
        return dentro.strip()
    # fallback simples
    return s.split("-")[0].strip()


def encontrar_conta_mais_provavel(nome_base: str, contas_df: pd.DataFrame) -> Tuple[str, str, int]:
    """Encontra a Account name/id mais provável via fuzzy matching."""
    if not nome_base:
        return None, None, 0

    # IA: normalizar nome_base e comparar com NomePessoaNorm
    nome_norm = normalizar_nome(nome_base)
    if not nome_norm:
        return None, None, 0

    nomes_norm = contas_df["NomePessoaNorm"].tolist()

    # Usamos partial_ratio para lidar melhor com abreviacoes e partes de nome
    match_norm, score, idx = process.extractOne(
        nome_norm,
        nomes_norm,
        scorer=fuzz.partial_ratio,
    )
    if score >= LIMIAR_SIMILARIDADE:
        account_id = contas_df.iloc[idx]["Id"]
        account_name = contas_df.iloc[idx]["Name"]
        return account_id, account_name, score
    return None, None, score


def dividir_nome_completo(nome: Any) -> Tuple[str, str]:
    """Divide 'Nome completo' em (primeiro_nome, sobrenome)."""
    if not nome or pd.isna(nome):
        return "", ""
    partes = str(nome).strip().split()
    if not partes:
        return "", ""
    if len(partes) == 1:
        return partes[0], ""
    return partes[0], " ".join(partes[1:])


def parse_data(valor: Any):
    """Converte datas da planilha para datetime.date, se possível."""
    if isinstance(valor, (datetime, date)):
        return valor.date()
    if isinstance(valor, str) and valor.strip():
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(valor.strip(), fmt).date()
            except ValueError:
                continue
    return None


def montar_payload_corretor(row, account_id, account_name_sugerido, score_match) -> Dict[str, Any]:
    """
    Monta o payload do Contact com base na linha da planilha.

    IMPORTANTE: os nomes de campos com __c são EXEMPLOS.
    Troque pelos nomes de API reais do seu org.
    """
    nome_completo = row.get("Nome completo:", "")
    primeiro_nome, sobrenome = dividir_nome_completo(nome_completo)

    genero = str(row.get("Gênero:", "")).strip()
    if genero.lower().startswith("masc"):
        tratamento = "Sr."
    elif genero.lower().startswith("fem"):
        tratamento = "Sra."
    else:
        tratamento = ""

    data_nasc = parse_data(row.get("Data de nascimento:", ""))
    data_entrevista = parse_data(row.get("Hora de início", ""))

    email_limpo = limpar_email(row.get("E-mail"))
    escolaridade_limpa = limpar_escolaridade(row.get("Informe sua escolaridade:", ""))

    payload: Dict[str, Any] = {
        "FirstName": primeiro_nome,
        "LastName": sobrenome or primeiro_nome or "Sem Nome",
        "Salutation": tratamento,
        "Email": email_limpo,
        "MobilePhone": str(row.get("Telefone com DDD:", "")).strip(),
        "AccountId": account_id,
        "Apelido__c": primeiro_nome,  # Apelido
        "Status_Corretor__c": "Ativo",
        "Regional__c": row.get("Estado:", ""),
        "Origem__c": "RH",
        "Sexo__c": genero,
        "Camiseta__c": row.get("Tamanho da camisa:", ""),
        "Atividade__c": "Corretor N1",
        "Escolaridade__c": escolaridade_limpa,
        "Data_da_Entrevista__c": data_entrevista.isoformat() if data_entrevista else None,
        # Usamos a mesma data de entrevista também para o campo de parceiro, já existente na org
        "Data_Transferencia_Corretor_Parceiro__c": data_entrevista.isoformat() if data_entrevista else None,
        "Unidade_Negocio__c": "Direcional",
        # Campo padrão de Contact para data de nascimento
        "Birthdate": data_nasc.isoformat() if data_nasc else None,
        "EstadoCivil__c": row.get("Estado civil:", ""),
        "CPF__c": row.get("CPF:", ""),
        "Nacionalidade__c": row.get("País de nascimento:", ""),
        "Naturalidade__c": row.get("Cidade de Nascimento:", ""),
        "RG__c": row.get("RG:", ""),
        "UF_Naturalidade__c": row.get("Cidade de Nascimento:", ""),
        "UF_RG__c": row.get("UF de emissão do RG/RNE:", ""),
        "Tipo_do_PIX__c": row.get("Tipo de PIX:", ""),
        "Dados_para_PIX__c": row.get("Informa a sua chave Pix:", ""),
        "Nome_do_Pai__c": row.get("Nome completo do Pai", ""),
        "Nome_da_Mae__c": row.get("Nome completo da mãe:", ""),
        "Banco__c": row.get("Banco:", ""),
        "Conta_Banc_ria__c": row.get("Conta com dígito:", ""),
        "Ag_ncia_Banc_ria__c": row.get("Agência:", ""),
        "Tipo_Corretor__c": "Direcional Vendas - Autônomos",
        "Data_Contrato__c": date.today().isoformat(),
        "Data_Credenciamento__c": date.today().isoformat(),
    }
    payload = {k: v for k, v in payload.items() if v not in (None, "")}
    return payload


class RelatorioPDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 12)
        self.cell(0, 8, "Relatorio de processamento de Corretores", ln=1)
        self.set_font("Arial", "", 9)
        self.cell(0, 6, datetime.now().strftime("%d/%m/%Y %H:%M"), ln=1)
        self.ln(2)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)


def gerar_relatorio_pdf(
    contatos_criados: List[Dict[str, Any]],
    casos_sem_conta: List[Dict[str, Any]],
    erros_criacao: List[Dict[str, Any]],
    caminho_pdf: str,
) -> None:
    pdf = RelatorioPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", "", 10)

    # Seção 1: Contatos criados com sucesso
    pdf.cell(0, 8, "1. Contatos criados com sucesso", ln=1)
    pdf.ln(2)

    if not contatos_criados:
        pdf.cell(0, 6, "Nenhum contato criado nesta execucao.", ln=1)
    else:
        for c in contatos_criados:
            linha_txt = (
                f"Linha: {c['linha']} | Nome: {c.get('nome')} | "
                f"Conta: {c.get('conta')} | Score: {c.get('score')} | "
                f"Id: {c.get('id')} | URL: {c.get('url')}"
            )
            pdf.multi_cell(0, 5, linha_txt)
            pdf.ln(1)

    # Seção 2: Linhas sem match de conta
    pdf.add_page()
    pdf.cell(
        0,
        8,
        "2. Linhas sem match de conta (indicacao nao encontrada ou abaixo do limiar)",
        ln=1,
    )
    pdf.ln(2)

    if not casos_sem_conta:
        pdf.cell(0, 6, "Nenhum caso sem match de conta.", ln=1)
    else:
        for caso in casos_sem_conta:
            pdf.multi_cell(
                0,
                5,
                f"Linha: {caso['linha']} | Indicacao: {caso['indicacao_raw']} | "
                f"nome_base: {caso['nome_base']} | score={caso['score']}",
            )
            pdf.ln(1)

    # Seção 3: Erros de criacao de contato no Salesforce
    pdf.add_page()
    pdf.cell(0, 8, "3. Contatos nao criados (erros de criacao no Salesforce)", ln=1)
    pdf.ln(2)

    if not erros_criacao:
        pdf.cell(0, 6, "Nenhum erro de criacao de contato.", ln=1)
    else:
        for err in erros_criacao:
            pdf.multi_cell(
                0,
                5,
                f"Linha: {err['linha']} | Nome: {err.get('nome')} | Erro: {err['erro']}",
            )
            pdf.ln(1)

    os.makedirs(os.path.dirname(caminho_pdf), exist_ok=True)
    pdf.output(caminho_pdf)


def main() -> None:
    print("Conectando ao Salesforce...")
    sf = conectar_salesforce()
    if not sf:
        print("Nao foi possivel conectar ao Salesforce.")
        return

    contas_df = carregar_contas_direcional_vendas(sf)

    print("Selecione o arquivo Excel da ficha cadastral...")
    caminho_planilha = selecionar_arquivo_excel()
    if not caminho_planilha:
        print("Nenhum arquivo selecionado. Encerrando.")
        return

    print(f"Lendo planilha: {caminho_planilha}")
    df = carregar_planilha(caminho_planilha)
    print(f"Total de linhas na planilha: {len(df)}")

    # Determinar URL base da instância para montar links dos contatos
    base_instance = getattr(sf, "sf_instance", "")
    if base_instance and not base_instance.startswith("http"):
        base_url = f"https://{base_instance}"
    else:
        base_url = (base_instance or "").split("/services")[0]

    contatos_criados: List[Dict[str, Any]] = []
    casos_sem_conta: List[Dict[str, Any]] = []
    erros_criacao: List[Dict[str, Any]] = []

    for idx, row in df.iterrows():
        nome_completo = row.get("Nome completo:", "")
        if not nome_completo or pd.isna(nome_completo):
            continue

        indicacao_raw = row.get("Quem indicou você para esta vaga?", "")

        nome_base_indicador = extrair_nome_indicador(indicacao_raw)
        account_id, account_name_sugerido, score = encontrar_conta_mais_provavel(
            nome_base_indicador, contas_df
        )

        if not account_id:
            casos_sem_conta.append(
                {
                    "linha": idx + 2,  # +2 considerando cabeçalho
                    "indicacao_raw": indicacao_raw,
                    "nome_base": nome_base_indicador,
                    "score": score,
                }
            )
            continue

        payload = montar_payload_corretor(row, account_id, account_name_sugerido, score)

        try:
            res = sf.Contact.create(payload)
            contact_id = res.get("id")
            if base_url and contact_id:
                contact_url = f"{base_url}/lightning/r/Contact/{contact_id}/view"
            else:
                contact_url = contact_id or ""
            print(
                f"[{idx+2}] Contato criado: {res.get('id')} | "
                f"{payload.get('FirstName')} {payload.get('LastName')} | "
                f"Conta: {account_name_sugerido} (score={score})"
            )
            contatos_criados.append(
                {
                    "linha": idx + 2,
                    "nome": f"{payload.get('FirstName')} {payload.get('LastName')}",
                    "id": contact_id,
                    "url": contact_url,
                    "conta": account_name_sugerido,
                    "score": score,
                }
            )
        except Exception as e:
            erros_criacao.append(
                {
                    "linha": idx + 2,
                    "nome": nome_completo,
                    "erro": str(e),
                }
            )
            print(f"[{idx+2}] Erro ao criar contato: {e}")

    # Gerar relatório PDF
    relatorios_dir = os.path.join(BASE_DIR, "relatorios_corretor")
    caminho_pdf = os.path.join(
        relatorios_dir,
        f"relatorio_corretor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
    )
    gerar_relatorio_pdf(contatos_criados, casos_sem_conta, erros_criacao, caminho_pdf)
    print(f"Relatorio PDF gerado em: {caminho_pdf}")


if __name__ == "__main__":
    main()

