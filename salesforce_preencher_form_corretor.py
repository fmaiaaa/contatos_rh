# -*- coding: utf-8 -*-
"""
Login no Salesforce com Playwright, abre o formulário Novo Contato: Corretor
e preenche os campos. NÃO clica em Salvar.

Uso:
  python salesforce_preencher_form_corretor.py --user email --password senha [--totp 123456]
  python salesforce_preencher_form_corretor.py --user email --password senha --arquivo planilha.xlsx [--linha 0] [--id 123]

Dados podem vir do dicionário DADOS_CORRETOR ou de uma planilha (--arquivo) no formato
da tabela de formulário (Id, E-mail, Nome completo:, CPF:, RG:, etc.).
"""

import os
import sys
import argparse
import time

try:
    import pandas as pd
except ImportError:
    pd = None

# URL que já leva ao novo Contato Corretor após login
URL_COM_START = (
    "https://direcional.my.salesforce.com?ec=302&startURL="
    "%2Fvisualforce%2Fsession%3Furl%3Dhttps%253A%252F%252Fdirecional.lightning.force.com"
    "%252Flightning%252Fo%252FContact%252Fnew%253FrecordTypeId%253D012f1000000n6nN%2526count%253D1%253B"
)

# Mapeamento: nome da coluna na planilha (após normalização) -> rótulo do campo no formulário Salesforce
MAPEAMENTO_PLANILHA_PARA_FORM = {
    "Nome completo": "Nome completo",
    "Nome completo:": "Nome completo",
    "Nome": "Apelido",
    "E-mail": "Email",
    "E-mail Corporativo:": "E-mail Direcional",
    "E-mail Corporativo": "E-mail Direcional",
    "CPF:": "CPF",
    "CPF": "CPF",
    "RG:": "RG",
    "RG": "RG",
    "Data de nascimento:": "Data de nascimento",
    "Data de nascimento": "Data de nascimento",
    "UF de emissão do RG/RNE:": "UF RG",
    "Nome completo do Pai": "Nome do Pai",
    "Nome completo da mãe:": "Nome da Mãe",
    "Nome completo da mãe": "Nome da Mãe",
    "País de nascimento:": "Nacionalidade",
    "País de nascimento": "Nacionalidade",
    "Banco:": "Banco",
    "Banco": "Banco",
    "Agência:": "Agência Bancária",
    "Agência": "Agência Bancária",
    "Conta com dígito:": "Conta Bancária",
    "Conta com dígito": "Conta Bancária",
    "Conta com Digito:": "Conta Bancária",
    "Estado:": "UF Naturalidade",
    "Estado": "UF Naturalidade",
    "Tipo de PIX:": "Tipo do PIX",
    "Tipo de PIX": "Tipo do PIX",
    "Informa a sua chave Pix:": "Dados para PIX",
    "Informa a sua chave Pix": "Dados para PIX",
    "Cidade de Nascimento:": "Naturalidade",
    "Cidade de Nascimento": "Naturalidade",
    "Estado civil:": "Estado Civil",
    "Estado civil": "Estado Civil",
    "Nome do cônjuge:": "Nome do Cônjuge",
    "Nome do cônjuge": "Nome do Cônjuge",
    "Quantidade de filhos:": "Quantidade de Filhos",
    "Quantidade de filhos": "Quantidade de Filhos",
    "Telefone com DDD:": "Celular",
    "Telefone com DDD": "Celular",
    "Informe sua escolaridade:": "Escolaridade",
    "Informe sua escolaridade": "Escolaridade",
    "Tipo de CRECI:": "Status CRECI",
    "Tipo de CRECI": "Status CRECI",
    "Número do CRECI:": "CRECI",
    "Número do CRECI": "CRECI",
    "Nome do supervisor do CRECI:": "Nome do Responsável",
    "Nome do supervisor do CRECI": "Nome do Responsável",
    "Validade do CRECI:": "Validade CRECI",
    "Validade do CRECI": "Validade CRECI",
    "Tipo de conta:": "Tipo de Conta",
    "Tipo de conta": "Tipo de Conta",
    "Informe o Nº do CNPJ:": "CNPJ",
    "Informe o Nº do CNPJ": "CNPJ",
    "Banco:1": "Banco",
    "Agência:1": "Agência Bancária",
    "Conta com Digito": "Conta Bancária",
    "Tamanho da camisa:": "Camiseta",
    "Tamanho da camisa": "Camiseta",
    "Gênero:": "Sexo",
    "Gênero": "Sexo",
}

# Dados de exemplo (fallback quando não há --arquivo). Chave = rótulo do campo no formulário.
DADOS_CORRETOR = {
    "Nome completo": "Primeiro Nome Sobrenome",
    "Primeiro Nome": "Primeiro Nome",
    "Sobrenome": "Sobrenome",
    "Apelido": "Apelido",
    "Email": "email@exemplo.com",
    "Celular": "31999999999",
    "Telefone": "3133334444",
    "CPF": "12345678900",
    "RG": "MG1234567",
    "Data de nascimento": "01/01/1990",
    "Data da Entrevista": "25/02/2025",
    "Data Contrato": "01/02/2025",
    "Data Credenciamento": "01/02/2025",
    "Naturalidade": "Belo Horizonte",
    "Nome do Pai": "Nome Pai",
    "Nome da Mãe": "Nome Mãe",
    "Dados para PIX": "12345678900",
    "Conta Bancária": "12345-6",
    "Agência Bancária": "0001",
    "Observações": "Preenchido via automação (não salvar).",
}


def _banner():
    print("=" * 78)
    print("SALESFORCE | PREENCHIMENTO DE FORMULÁRIO CORRETOR (PLAYWRIGHT)")
    print("=" * 78)


def _log_etapa(msg):
    print(f"\n[ETAPA] {msg}")


def _log_ok(msg):
    print(f"[OK] {msg}")


def _log_warn(msg):
    print(f"[AVISO] {msg}")


def _log_err(msg):
    print(f"[ERRO] {msg}")


def _normalizar_nome_coluna(s):
    """Remove espaços extras e dois pontos no final para matching."""
    if pd.isna(s) or not isinstance(s, str):
        return ""
    return str(s).strip().rstrip(":").strip()


def carregar_dados_planilha(arquivo, linha=0, id_val=None):
    """
    Carrega uma linha da planilha (Excel ou CSV) no formato da tabela de formulário.
    arquivo: caminho para .xlsx, .xls ou .csv
    linha: índice da linha (0-based). Ignorado se id_val for informado.
    id_val: se informado, busca a linha cuja coluna 'Id' seja igual a id_val.
    Retorna dict rótulo_formulário -> valor para preencher no Salesforce.
    """
    if pd is None:
        raise ImportError("Instale pandas: pip install pandas openpyxl")
    path = os.path.abspath(arquivo)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xls"):
        df = pd.read_excel(path, engine="openpyxl" if ext == ".xlsx" else None)
    else:
        df = pd.read_csv(path, encoding="utf-8", sep=";", on_bad_lines="skip")
        if len(df.columns) == 1 and "," in str(df.iloc[0, 0]):
            df = pd.read_csv(path, encoding="utf-8", sep=",", on_bad_lines="skip")
    df.columns = [_normalizar_nome_coluna(c) for c in df.columns]
    if id_val is not None:
        col_id = None
        for c in df.columns:
            if _normalizar_nome_coluna(c).lower() == "id":
                col_id = c
                break
        if col_id is None:
            raise ValueError("Coluna 'Id' não encontrada na planilha.")
        idx = df[col_id].astype(str).str.strip() == str(id_val).strip()
        if not idx.any():
            raise ValueError(f"Nenhuma linha com Id = {id_val}.")
        row = df.loc[idx].iloc[0]
    else:
        if linha < 0 or linha >= len(df):
            raise IndexError(f"Linha {linha} fora do intervalo (0 a {len(df)-1}). Total de linhas: {len(df)}.")
        row = df.iloc[linha]
    out = {}
    partes_endereco = []
    colunas_endereco_norm = {"informe a cidade de residência", "bairro residencial", "rua de residência", "complemento", "número de residência", "informe seu cep"}
    for col_plan in df.columns:
        norm = _normalizar_nome_coluna(col_plan).lower()
        label_form = MAPEAMENTO_PLANILHA_PARA_FORM.get(col_plan)
        if label_form is None:
            for k in MAPEAMENTO_PLANILHA_PARA_FORM:
                if _normalizar_nome_coluna(k).lower() == norm:
                    label_form = MAPEAMENTO_PLANILHA_PARA_FORM[k]
                    break
        if label_form is None:
            if norm in colunas_endereco_norm:
                val = row.get(col_plan)
                if not (pd.isna(val) or (isinstance(val, str) and not str(val).strip())):
                    partes_endereco.append(str(val).strip())
            continue
        val = row.get(col_plan)
        if pd.isna(val) or (isinstance(val, str) and not val.strip()):
            continue
        if hasattr(val, "strftime"):
            val = val.strftime("%d/%m/%Y")
        else:
            val = str(val).strip()
        out[label_form] = val
    if partes_endereco:
        out["Observações"] = " | ".join(partes_endereco)
    if "Nome completo" in out and "Primeiro Nome" not in out:
        nome = out["Nome completo"]
        partes = nome.split(None, 1)
        out["Primeiro Nome"] = partes[0] if partes else nome
        out["Sobrenome"] = partes[1] if len(partes) > 1 else ""
    return out


def _preencher_campo_texto(page, label_ou_placeholder, valor, timeout=5000):
    """Preenche um campo de texto localizando por label ou placeholder."""
    if not valor:
        return
    try:
        # Tenta por label acessível (Salesforce Lightning às vezes expõe o label)
        loc = page.getByLabel(label_ou_placeholder, exact=False)
        loc.wait_for(state="visible", timeout=timeout)
        loc.fill(str(valor), timeout=timeout)
        return
    except Exception:
        pass
    try:
        # Tenta por placeholder
        loc = page.getByPlaceholder(label_ou_placeholder)
        loc.wait_for(state="visible", timeout=timeout)
        loc.fill(str(valor), timeout=timeout)
        return
    except Exception:
        pass
    try:
        # Tenta por role textbox com nome
        loc = page.getByRole("textbox", name=label_ou_placeholder)
        loc.fill(str(valor), timeout=timeout)
        return
    except Exception:
        pass
    try:
        # Fallback: campo cujo nome/placeholder contém o label (Lightning usa data-* ou aria-label)
        loc = page.locator(f"input[placeholder*='{label_ou_placeholder[:20]}'], input[aria-label*='{label_ou_placeholder[:20]}']").first
        loc.fill(str(valor), timeout=timeout)
    except Exception:
        pass


def _preencher_combobox(page, label, valor, timeout=5000):
    """Abre combobox pelo label e seleciona a opção com o texto indicado."""
    if not valor or valor in ("--Nenhum--", ""):
        return
    try:
        # Combobox no Lightning: muitas vezes é um botão ou div com role=combobox
        cb = page.getByLabel(label, exact=False).first
        cb.wait_for(state="visible", timeout=timeout)
        cb.click()
        time.sleep(0.3)
        page.getByRole("option", name=valor).first.click(timeout=timeout)
    except Exception:
        try:
            cb = page.getByRole("combobox", name=label)
            cb.click()
            time.sleep(0.3)
            page.getByRole("option", name=valor).click(timeout=timeout)
        except Exception:
            pass


def preencher_formulario_corretor(page, dados, timeout_campo=6000):
    """
    Preenche o formulário Novo Contato: Corretor.
    dados: dict label -> valor (ex.: {"Sobrenome": "Silva", "Email": "a@b.com"}).
    Campos de data: use formato 31/12/2024.
    """
    # Campos de texto / data (obrigatórios e comuns)
    campos_texto = [
        "Nome completo", "Primeiro Nome", "Sobrenome", "Apelido",
        "Email", "Celular", "Telefone", "E-mail Direcional", "Celular 2", "Outro telefone",
        "CPF", "RG", "PIS", "Naturalidade", "Dados para PIX",
        "Data de nascimento", "Data da Entrevista", "Data Contrato", "Data Credenciamento",
        "Data Transferência Corretor Parceiro", "Data Matrícula - TTI", "Data de conclusão",
        "Validade CRECI", "Data Descredenciamento", "Data de Saída", "Data de Transferência",
        "Data Reativação", "Data Entrada Recruta+", "Data Saída Recruta+",
        "Nome do Pai", "Nome da Mãe", "Quantidade de Filhos", "Nome do Cônjuge",
        "Conta Bancária", "Agência Bancária", "CRECI", "Observações",
        "Nome do Responsável", "CRECI do Responsável", "CNPJ", "Razão Social",
    ]
    preenchidos_texto = 0
    for label in campos_texto:
        valor = dados.get(label)
        if valor is None:
            continue
        try:
            _preencher_campo_texto(page, label, str(valor).strip(), timeout=timeout_campo)
            preenchidos_texto += 1
        except Exception as e:
            _log_warn(f"Campo '{label}' não preenchido: {e}")

    # Comboboxes (picklist) – só preenche se tiver valor no dict
    combos = [
        "Tratamento", "Status Corretor", "Regional", "Origem", "Sexo", "Camiseta", "Atividade",
        "Escolaridade", "Unidade Negocio", "Estado Civil", "Nacionalidade", "UF Naturalidade",
        "UF RG", "Tipo do PIX", "Tipo de Conta", "Status CRECI", "Tipo Corretor",
        "Faturamento Comissão", "Tipo de desligamento", "Motivo Descredenciamento",
        "Possui Filho(s)?", "Banco",
    ]
    preenchidos_combo = 0
    for label in combos:
        valor = dados.get(label)
        if valor is None:
            continue
        try:
            _preencher_combobox(page, label, str(valor).strip(), timeout=timeout_campo)
            preenchidos_combo += 1
        except Exception as e:
            _log_warn(f"Combobox '{label}' não preenchido: {e}")

    _log_ok(f"Campos de texto/data preenchidos: {preenchidos_texto}")
    _log_ok(f"Comboboxes preenchidos: {preenchidos_combo}")


def run_playwright_login_e_preencher(user, password, totp, dados, manter_aberto_sec=60):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        try:
            _log_etapa("Abrindo página de login")
            page.goto(URL_COM_START, wait_until="domcontentloaded", timeout=30000)
            page.fill("input#username", user)
            page.fill("input#password", password)
            page.click("input#Login")
            if totp:
                _log_etapa("Aguardando código 2FA")
                page.wait_for_selector("input#tc", timeout=20000)
                page.fill("input#tc", totp)
                page.click("input#save")
            _log_etapa("Aguardando carregamento do formulário Novo Contato: Corretor")
            page.wait_for_load_state("networkidle", timeout=45000)
            # Garantir que estamos na tela de novo contato (Lightning)
            time.sleep(2)
            _log_etapa("Preenchendo campos do formulário (não será clicado em Salvar)")
            preencher_formulario_corretor(page, dados)
            _log_ok("Preenchimento concluído. Navegador permanecerá aberto (não clique em Salvar ainda).")
            if manter_aberto_sec > 0:
                time.sleep(manter_aberto_sec)
        finally:
            browser.close()


def main():
    _banner()
    parser = argparse.ArgumentParser(description="Login Salesforce + preencher Novo Contato Corretor (sem salvar)")
    parser.add_argument("--user", "-u", help="E-mail de login")
    parser.add_argument("--password", "-p", help="Senha")
    parser.add_argument("--totp", "-t", help="Código Google Authenticator (2FA)")
    parser.add_argument("--manter-aberto", type=int, default=60, help="Segundos com o navegador aberto após preencher (0 = fechar logo)")
    parser.add_argument("--arquivo", "-a", help="Planilha (Excel ou CSV) no formato da tabela de formulário (Id, E-mail, Nome completo:, CPF:, etc.)")
    parser.add_argument("--linha", "-l", type=int, default=0, help="Índice da linha a usar (0-based). Ignorado se --id for informado.")
    parser.add_argument("--id", "-i", help="Valor da coluna Id para selecionar a linha na planilha")
    args = parser.parse_args()
    user = (args.user or os.environ.get("SALESFORCE_USER", "")).strip()
    password = (args.password or os.environ.get("SALESFORCE_PASSWORD", "")).strip()
    totp = (args.totp or os.environ.get("SALESFORCE_TOTP", "")).strip()
    if not user or not password:
        _log_err("Use SALESFORCE_USER e SALESFORCE_PASSWORD ou --user e --password.")
        sys.exit(1)
    dados = dict(DADOS_CORRETOR)
    if args.arquivo:
        try:
            carregados = carregar_dados_planilha(args.arquivo, linha=args.linha, id_val=args.id)
            dados.update(carregados)
            _log_ok(f"Dados carregados da planilha: {len(carregados)} campos.")
        except Exception as e:
            _log_err(f"Erro ao carregar planilha: {e}")
            sys.exit(1)
    run_playwright_login_e_preencher(user, password, totp, dados, args.manter_aberto)


if __name__ == "__main__":
    main()
