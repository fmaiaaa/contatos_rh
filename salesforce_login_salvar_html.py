# -*- coding: utf-8 -*-
"""
Login no Salesforce (My Domain Direcional) e salva o HTML da página resultante em um arquivo.
Usa apenas requests (sem Selenium). Credenciais por variáveis de ambiente ou argumentos.

Uso no PowerShell:
  $env:SALESFORCE_USER="seu_email@direcional.com.br"
  $env:SALESFORCE_PASSWORD="sua_senha"
  python salesforce_login_salvar_html.py

Uso no CMD:
  set SALESFORCE_USER=seu_email@direcional.com.br
  set SALESFORCE_PASSWORD=sua_senha
  python salesforce_login_salvar_html.py

Ou com argumentos:
  python salesforce_login_salvar_html.py --user seu_email --password sua_senha

Arquivo gerado: salesforce_pagina_pos_login.html (na mesma pasta do script)
Requisitos: pip install requests
"""

import os
import re
import sys
import argparse
from urllib.parse import urljoin, urlparse

import requests

# URL para onde o redirect do Visualforce manda (página de login / início)
URL_LOGIN = "https://direcional.my.salesforce.com"
URL_COM_START = (
    "https://direcional.my.salesforce.com?ec=302&startURL="
    "%2Fvisualforce%2Fsession%3Furl%3Dhttps%253A%252F%252Fdirecional.lightning.force.com"
    "%252Flightning%252Fo%252FContact%252Fnew%253FrecordTypeId%253D012f1000000n6nN%2526count%253D1%253B"
)
ARQUIVO_SAIDA = "salesforce_pagina_pos_login.html"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


def obter_credenciais():
    parser = argparse.ArgumentParser(description="Login Salesforce e salvar HTML (requests)")
    parser.add_argument("--user", "-u", help="E-mail de login")
    parser.add_argument("--password", "-p", help="Senha")
    parser.add_argument("--totp", "-t", help="Código de 6 dígitos do Google Authenticator (2FA)")
    parser.add_argument("--out", "-o", default=ARQUIVO_SAIDA, help="Arquivo HTML de saída")
    args = parser.parse_args()
    user = args.user or os.environ.get("SALESFORCE_USER", "").strip()
    password = args.password or os.environ.get("SALESFORCE_PASSWORD", "").strip()
    totp = args.totp or os.environ.get("SALESFORCE_TOTP", "").strip()
    return user, password, totp, args.out


def extrair_formulario(html, base_url):
    """Extrai action e campos do primeiro form que tenha campo de senha."""
    # Action do form
    form_match = re.search(
        r'<form[^>]*\s+action=["\']([^"\']*)["\']',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    action = form_match.group(1).strip() if form_match else base_url
    if action.startswith("/"):
        action = urljoin(base_url, action)

    # Todos os inputs: name e value
    inputs = {}
    for m in re.finditer(
        r'<input[^>]+>',
        html,
        re.IGNORECASE,
    ):
        tag = m.group(0)
        if re.search(r'\btype=["\'](?:submit|button|image)["\']', tag, re.I):
            continue
        name = re.search(r'\bname=["\']([^"\']+)["\']', tag, re.I)
        if not name:
            continue
        name = name.group(1)
        val = re.search(r'\bvalue=["\']([^"\']*)["\']', tag, re.I)
        inputs[name] = val.group(1) if val else ""

    # Nomes típicos Salesforce: username, pw (ou password)
    username_name = None
    password_name = None
    for name in inputs:
        n = name.lower()
        if n in ("username", "email", "j_id0:j_id1:username"):
            username_name = name
        if n in ("pw", "password", "j_id0:j_id1:password"):
            password_name = name
    if not username_name:
        username_name = "username"
    if not password_name:
        password_name = "pw"

    return action, inputs, username_name, password_name


def extrair_form_totp(html, base_url):
    """Extrai action e todos os inputs do form de verificação TOTP (2FA)."""
    form_match = re.search(
        r'<form[^>]*\s+action=["\']([^"\']*)["\']',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    action = form_match.group(1).strip() if form_match else base_url
    if action.startswith("/"):
        action = urljoin(base_url, action)
    inputs = {}
    for m in re.finditer(r'<input[^>]+>', html, re.IGNORECASE):
        tag = m.group(0)
        if re.search(r'\btype=["\'](?:submit|button)["\']', tag, re.I):
            continue
        name = re.search(r'\bname=["\']([^"\']+)["\']', tag, re.I)
        if not name:
            continue
        name = name.group(1)
        val = re.search(r'\bvalue=["\']([^"\']*)["\']', tag, re.I)
        inputs[name] = val.group(1) if val else ""
    return action, inputs


def main():
    user, password, totp, arquivo_saida = obter_credenciais()
    if not user or not password:
        print("Use variáveis de ambiente SALESFORCE_USER e SALESFORCE_PASSWORD ou --user e --password.")
        sys.exit(1)

    session = requests.Session()
    session.headers.update(HEADERS)

    # 1) GET da página de login (com startURL para pós-login)
    print("Obtendo página de login...")
    try:
        r = session.get(URL_COM_START, timeout=30, allow_redirects=True)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"Erro ao acessar Salesforce: {e}")
        sys.exit(1)

    html = r.text
    base_url = f"{urlparse(r.url).scheme}://{urlparse(r.url).netloc}"

    # Se a resposta for o redirect em JS (sem form), tentar direto a URL base
    if "<form" not in html.lower() and "redirectOnLoad" in html:
        print("Página de redirect detectada, tentando URL base...")
        try:
            r = session.get(URL_LOGIN, timeout=30, allow_redirects=True)
            r.raise_for_status()
            html = r.text
            base_url = f"{urlparse(r.url).scheme}://{urlparse(r.url).netloc}"
        except requests.RequestException as e:
            print(f"Erro: {e}")
            with open(arquivo_saida, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"HTML atual salvo em: {arquivo_saida}")
            sys.exit(1)

    action, form_data, username_name, password_name = extrair_formulario(html, base_url)
    form_data[username_name] = user
    form_data[password_name] = password
    # Campos preenchidos pelo JavaScript handleLogin() antes do submit
    form_data["un"] = user
    form_data["width"] = "1920"
    form_data["height"] = "1080"
    # Botão de submit (nome e valor como no HTML)
    form_data["Login"] = "Fazer login"

    # 2) POST do login
    print("Enviando login...")
    try:
        r2 = session.post(action, data=form_data, timeout=30, allow_redirects=True)
        r2.raise_for_status()
    except requests.RequestException as e:
        print(f"Erro no POST de login: {e}")
        with open(arquivo_saida, "w", encoding="utf-8") as f:
            f.write(r2.text if 'r2' in dir() else html)
        print(f"HTML salvo em: {arquivo_saida}")
        sys.exit(1)

    # 3) Se caiu na página de 2FA (TOTP) com campo do código e temos código, enviar verificação
    # Só considerar 2FA quando existir o input do código (evita enviar POST na página "tempo limite")
    has_totp_form = (
        "TotpVerificationUi" in r2.url
        and ("name=\"tc\"" in r2.text or "name='tc'" in r2.text or 'id="tc"' in r2.text)
    )
    if has_totp_form and totp:
        print("Página 2FA detectada. Enviando código do Authenticator...")
        base_2fa = f"{urlparse(r2.url).scheme}://{urlparse(r2.url).netloc}"
        _, form_2fa = extrair_form_totp(r2.text, base_2fa)
        form_2fa["tc"] = totp
        form_2fa["save"] = "Verificar"
        # POST para a mesma URL da página (r2.url) para preservar vcsrf e parâmetros na query string
        post_url_2fa = r2.url
        try:
            r3 = session.post(post_url_2fa, data=form_2fa, timeout=30, allow_redirects=True)
            r3.raise_for_status()
            final_html = r3.text
            final_url = r3.url
        except requests.RequestException as e:
            print(f"Erro no POST do código 2FA: {e}")
            final_html = r2.text
            final_url = r2.url
    else:
        final_html = r2.text
        final_url = r2.url
        if has_totp_form and not totp:
            print("Página 2FA detectada. Informe o código com --totp ou SALESFORCE_TOTP para passar.")
        elif "TotpVerificationUi" in r2.url and not has_totp_form and "tempo limite" in r2.text.lower():
            print("Sessão de verificação expirada. Faça um novo login e informe o código assim que aparecer no Authenticator.")

    with open(arquivo_saida, "w", encoding="utf-8") as f:
        f.write(final_html)
    print(f"HTML salvo em: {arquivo_saida} ({len(final_html)} caracteres)")
    print(f"URL final: {final_url}")


if __name__ == "__main__":
    main()
