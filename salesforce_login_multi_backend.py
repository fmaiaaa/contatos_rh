# -*- coding: utf-8 -*-
"""
Login no Salesforce (My Domain Direcional) e salva o HTML da página resultante.
Múltiplos backends com fallback automático.

Uso:
  python salesforce_login_multi_backend.py --user email --password senha [--totp 123456]
  python salesforce_login_multi_backend.py --backend playwright   # forçar um backend

Altere PREFERRED_BACKEND abaixo para escolher a biblioteca. Se falhar, as outras são tentadas.
Playwright: após pip install playwright, rode uma vez: playwright install chromium
"""

import os
import re
import sys
import argparse
from urllib.parse import urljoin, urlparse

# =============================================================================
# CONSTANTE: selecione a biblioteca a ser usada (primeira tentativa).
# Opções possíveis:
#   "selenium"       - Selenium + Chrome/Edge (navegador real, suporta 2FA e Lightning)
#   "playwright"     - Playwright (navegador headless ou com UI)
#   "requests"       - requests (HTTP puro, sem JS; login clássico)
#   "requests_bs4"   - requests + BeautifulSoup (parsing do form com BS4)
#   "mechanicalsoup" - MechanicalSoup (requests + BS4 para formulários)
#   "httpx"          - httpx (similar ao requests)
#   "httpx_bs4"      - httpx + BeautifulSoup
# Se a opção escolhida falhar ou não estiver instalada, as outras são tentadas em ordem.
# =============================================================================
PREFERRED_BACKEND = "requests"

BACKEND_OPTIONS = [
    "selenium",
    "playwright",
    "requests",
    "requests_bs4",
    "mechanicalsoup",
    "httpx",
    "httpx_bs4",
]

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


# ---------- Parsing de formulário (regex, usado por requests/httpx) ----------
def extrair_formulario_regex(html, base_url):
    form_match = re.search(r'<form[^>]*\s+action=["\']([^"\']*)["\']', html, re.IGNORECASE | re.DOTALL)
    action = form_match.group(1).strip() if form_match else base_url
    if action.startswith("/"):
        action = urljoin(base_url, action)
    inputs = {}
    for m in re.finditer(r'<input[^>]+>', html, re.IGNORECASE):
        tag = m.group(0)
        if re.search(r'\btype=["\'](?:submit|button|image)["\']', tag, re.I):
            continue
        name = re.search(r'\bname=["\']([^"\']+)["\']', tag, re.I)
        if not name:
            continue
        name = name.group(1)
        val = re.search(r'\bvalue=["\']([^"\']*)["\']', tag, re.I)
        inputs[name] = val.group(1) if val else ""
    username_name = password_name = None
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


def extrair_form_totp_regex(html, base_url):
    form_match = re.search(r'<form[^>]*\s+action=["\']([^"\']*)["\']', html, re.IGNORECASE | re.DOTALL)
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
        val = re.search(r'\bvalue=["\']([^"\']*)["\']', tag, re.I)
        inputs[name.group(1)] = val.group(1) if val else ""
    return action, inputs


# ---------- Parsing com BeautifulSoup (para requests_bs4, httpx_bs4, mechanicalsoup) ----------
def _extrair_formulario_bs4(html, base_url):
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return extrair_formulario_regex(html, base_url)
    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form")
    if not form:
        return extrair_formulario_regex(html, base_url)
    action = form.get("action") or base_url
    if action.startswith("/"):
        action = urljoin(base_url, action)
    inputs = {}
    for inp in form.find_all("input"):
        name = inp.get("name")
        if not name or inp.get("type") in ("submit", "button", "image"):
            continue
        inputs[name] = inp.get("value") or ""
    username_name = password_name = None
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


def _extrair_form_totp_bs4(html, base_url):
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return extrair_form_totp_regex(html, base_url)
    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form")
    if not form:
        return extrair_form_totp_regex(html, base_url)
    action = form.get("action") or base_url
    if action.startswith("/"):
        action = urljoin(base_url, action)
    inputs = {}
    for inp in form.find_all("input"):
        name = inp.get("name")
        if name and inp.get("type") not in ("submit", "button"):
            inputs[name] = inp.get("value") or ""
    return action, inputs


# ---------- Backend: requests ----------
def _login_requests(user, password, totp, arquivo_saida):
    import requests
    session = requests.Session()
    session.headers.update(HEADERS)
    r = session.get(URL_COM_START, timeout=30, allow_redirects=True)
    r.raise_for_status()
    html, base_url = r.text, f"{urlparse(r.url).scheme}://{urlparse(r.url).netloc}"
    if "<form" not in html.lower() and "redirectOnLoad" in html:
        r = session.get(URL_LOGIN, timeout=30, allow_redirects=True)
        r.raise_for_status()
        html, base_url = r.text, f"{urlparse(r.url).scheme}://{urlparse(r.url).netloc}"
    action, form_data, uname, pname = extrair_formulario_regex(html, base_url)
    form_data[uname], form_data[pname] = user, password
    form_data["un"], form_data["width"], form_data["height"] = user, "1920", "1080"
    form_data["Login"] = "Fazer login"
    r2 = session.post(action, data=form_data, timeout=30, allow_redirects=True)
    r2.raise_for_status()
    has_totp = "TotpVerificationUi" in r2.url and ("name=\"tc\"" in r2.text or "name='tc'" in r2.text or 'id="tc"' in r2.text)
    if has_totp and totp:
        _, form_2fa = extrair_form_totp_regex(r2.text, urlparse(r2.url).scheme + "://" + urlparse(r2.url).netloc)
        form_2fa["tc"], form_2fa["save"] = totp, "Verificar"
        r3 = session.post(r2.url, data=form_2fa, timeout=30, allow_redirects=True)
        r3.raise_for_status()
        return r3.text, r3.url
    return r2.text, r2.url


# ---------- Backend: requests + BeautifulSoup ----------
def _login_requests_bs4(user, password, totp, arquivo_saida):
    import requests
    session = requests.Session()
    session.headers.update(HEADERS)
    r = session.get(URL_COM_START, timeout=30, allow_redirects=True)
    r.raise_for_status()
    html, base_url = r.text, f"{urlparse(r.url).scheme}://{urlparse(r.url).netloc}"
    if "<form" not in html.lower() and "redirectOnLoad" in html:
        r = session.get(URL_LOGIN, timeout=30, allow_redirects=True)
        r.raise_for_status()
        html, base_url = r.text, f"{urlparse(r.url).scheme}://{urlparse(r.url).netloc}"
    action, form_data, uname, pname = _extrair_formulario_bs4(html, base_url)
    form_data[uname], form_data[pname] = user, password
    form_data["un"], form_data["width"], form_data["height"] = user, "1920", "1080"
    form_data["Login"] = "Fazer login"
    r2 = session.post(action, data=form_data, timeout=30, allow_redirects=True)
    r2.raise_for_status()
    has_totp = "TotpVerificationUi" in r2.url and ("name=\"tc\"" in r2.text or "name='tc'" in r2.text or 'id="tc"' in r2.text)
    if has_totp and totp:
        base_2fa = f"{urlparse(r2.url).scheme}://{urlparse(r2.url).netloc}"
        _, form_2fa = _extrair_form_totp_bs4(r2.text, base_2fa)
        form_2fa["tc"], form_2fa["save"] = totp, "Verificar"
        r3 = session.post(r2.url, data=form_2fa, timeout=30, allow_redirects=True)
        r3.raise_for_status()
        return r3.text, r3.url
    return r2.text, r2.url


# ---------- Backend: httpx ----------
def _login_httpx(user, password, totp, arquivo_saida):
    import httpx
    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=30) as client:
        r = client.get(URL_COM_START)
        r.raise_for_status()
        html, base_url = r.text, f"{urlparse(str(r.url)).scheme}://{urlparse(str(r.url)).netloc}"
        if "<form" not in html.lower() and "redirectOnLoad" in html:
            r = client.get(URL_LOGIN)
            r.raise_for_status()
            html, base_url = r.text, f"{urlparse(str(r.url)).scheme}://{urlparse(str(r.url)).netloc}"
        action, form_data, uname, pname = extrair_formulario_regex(html, base_url)
        form_data[uname], form_data[pname] = user, password
        form_data["un"], form_data["width"], form_data["height"] = user, "1920", "1080"
        form_data["Login"] = "Fazer login"
        r2 = client.post(action, data=form_data)
        r2.raise_for_status()
        has_totp = "TotpVerificationUi" in str(r2.url) and ("name=\"tc\"" in r2.text or "name='tc'" in r2.text or 'id="tc"' in r2.text)
        if has_totp and totp:
            base_2fa = f"{urlparse(str(r2.url)).scheme}://{urlparse(str(r2.url)).netloc}"
            _, form_2fa = extrair_form_totp_regex(r2.text, base_2fa)
            form_2fa["tc"], form_2fa["save"] = totp, "Verificar"
            r3 = client.post(str(r2.url), data=form_2fa)
            r3.raise_for_status()
            return r3.text, str(r3.url)
        return r2.text, str(r2.url)


# ---------- Backend: httpx + BeautifulSoup ----------
def _login_httpx_bs4(user, password, totp, arquivo_saida):
    import httpx
    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=30) as client:
        r = client.get(URL_COM_START)
        r.raise_for_status()
        html, base_url = r.text, f"{urlparse(str(r.url)).scheme}://{urlparse(str(r.url)).netloc}"
        if "<form" not in html.lower() and "redirectOnLoad" in html:
            r = client.get(URL_LOGIN)
            r.raise_for_status()
            html, base_url = r.text, f"{urlparse(str(r.url)).scheme}://{urlparse(str(r.url)).netloc}"
        action, form_data, uname, pname = _extrair_formulario_bs4(html, base_url)
        form_data[uname], form_data[pname] = user, password
        form_data["un"], form_data["width"], form_data["height"] = user, "1920", "1080"
        form_data["Login"] = "Fazer login"
        r2 = client.post(action, data=form_data)
        r2.raise_for_status()
        has_totp = "TotpVerificationUi" in str(r2.url) and ("name=\"tc\"" in r2.text or "name='tc'" in r2.text or 'id="tc"' in r2.text)
        if has_totp and totp:
            base_2fa = f"{urlparse(str(r2.url)).scheme}://{urlparse(str(r2.url)).netloc}"
            _, form_2fa = _extrair_form_totp_bs4(r2.text, base_2fa)
            form_2fa["tc"], form_2fa["save"] = totp, "Verificar"
            r3 = client.post(str(r2.url), data=form_2fa)
            r3.raise_for_status()
            return r3.text, str(r3.url)
        return r2.text, str(r2.url)


# ---------- Backend: MechanicalSoup ----------
def _login_mechanicalsoup(user, password, totp, arquivo_saida):
    import mechanicalsoup
    browser = mechanicalsoup.StatefulBrowser()
    browser.set_user_agent(HEADERS.get("User-Agent", ""))
    r = browser.open(URL_COM_START)
    if not r.ok:
        raise RuntimeError(f"GET login: {r.status_code}")
    page = browser.get_current_page()
    if not page.find("form"):
        r = browser.open(URL_LOGIN)
        if not r.ok:
            raise RuntimeError(f"GET login fallback: {r.status_code}")
    browser.select_form("form")
    form = browser.get_current_form()
    uname = pname = None
    for inp in form.form.find_all("input"):
        n = (inp.get("name") or "").lower()
        if n in ("username", "email", "j_id0:j_id1:username"):
            uname = inp.get("name")
        if n in ("pw", "password", "j_id0:j_id1:password"):
            pname = inp.get("name")
    if uname:
        form[uname] = user
    if pname:
        form[pname] = password
    try:
        form["un"] = user
        form["width"] = "1920"
        form["height"] = "1080"
    except Exception:
        pass
    r2 = browser.submit_selected()
    if "TotpVerificationUi" in str(r2.url) and totp:
        browser.select_form("form")
        f2 = browser.get_current_form()
        try:
            f2["tc"] = totp
        except Exception:
            pass
        r3 = browser.submit_selected()
        return r3.text, str(r3.url)
    return r2.text, str(r2.url)


# ---------- Backend: Selenium ----------
def _login_selenium(user, password, totp, arquivo_saida):
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.service import Service
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service)
    except Exception:
        driver = webdriver.Chrome()
    driver.implicitly_wait(15)
    try:
        driver.get(URL_COM_START)
        wait = WebDriverWait(driver, 20)
        un = wait.until(EC.presence_of_element_located((By.ID, "username")))
        un.clear()
        un.send_keys(user)
        pw = driver.find_element(By.ID, "password")
        pw.clear()
        pw.send_keys(password)
        driver.find_element(By.ID, "Login").click()
        if totp:
            try:
                tc = WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "tc")))
                tc.clear()
                tc.send_keys(totp)
                driver.find_element(By.ID, "save").click()
            except Exception:
                pass
        WebDriverWait(driver, 25).until(lambda d: "salesforce.com" in d.current_url and ("TotpVerificationUi" not in d.current_url or not totp))
        html = driver.page_source
        url = driver.current_url
        return html, url
    finally:
        driver.quit()


# ---------- Backend: Playwright ----------
def _login_playwright(user, password, totp, arquivo_saida):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        try:
            page.goto(URL_COM_START, wait_until="domcontentloaded", timeout=30000)
            page.fill("input#username", user)
            page.fill("input#password", password)
            page.click("input#Login")
            if totp:
                page.wait_for_selector("input#tc", timeout=15000)
                page.fill("input#tc", totp)
                page.click("input#save")
            page.wait_for_load_state("networkidle", timeout=25000)
            html = page.content()
            url = page.url
            return html, url
        finally:
            browser.close()


# ---------- Dispatcher e fallback ----------
_BACKEND_FUNCS = {
    "selenium": _login_selenium,
    "playwright": _login_playwright,
    "requests": _login_requests,
    "requests_bs4": _login_requests_bs4,
    "mechanicalsoup": _login_mechanicalsoup,
    "httpx": _login_httpx,
    "httpx_bs4": _login_httpx_bs4,
}


def obter_credenciais():
    parser = argparse.ArgumentParser(description="Login Salesforce (multi-backend)")
    parser.add_argument("--user", "-u", help="E-mail de login")
    parser.add_argument("--password", "-p", help="Senha")
    parser.add_argument("--totp", "-t", help="Código Google Authenticator (2FA)")
    parser.add_argument("--out", "-o", default=ARQUIVO_SAIDA, help="Arquivo HTML de saída")
    parser.add_argument("--backend", "-b", choices=BACKEND_OPTIONS, default=None, help="Forçar backend (default: usar PREFERRED_BACKEND e fallbacks)")
    args = parser.parse_args()
    user = (args.user or os.environ.get("SALESFORCE_USER", "")).strip()
    password = (args.password or os.environ.get("SALESFORCE_PASSWORD", "")).strip()
    totp = (args.totp or os.environ.get("SALESFORCE_TOTP", "")).strip()
    return user, password, totp, args.out, args.backend


def run_login(user, password, totp, arquivo_saida, backend_forcar=None):
    order = [backend_forcar or PREFERRED_BACKEND]
    order += [b for b in BACKEND_OPTIONS if b not in order]
    last_error = None
    for backend in order:
        if backend not in _BACKEND_FUNCS:
            continue
        print(f"Tentando backend: {backend}...")
        try:
            html, url = _BACKEND_FUNCS[backend](user, password, totp, arquivo_saida)
            print(f"Backend '{backend}' concluído com sucesso.")
            return html, url, backend
        except ImportError as e:
            last_error = e
            print(f"Backend '{backend}' não disponível (falta instalar): {e}")
        except Exception as e:
            last_error = e
            print(f"Backend '{backend}' falhou: {e}")
    raise RuntimeError(f"Todos os backends falharam. Último erro: {last_error}")


def main():
    user, password, totp, arquivo_saida, backend_forcar = obter_credenciais()
    if not user or not password:
        print("Use SALESFORCE_USER e SALESFORCE_PASSWORD ou --user e --password.")
        sys.exit(1)
    try:
        html, url, used = run_login(user, password, totp, arquivo_saida, backend_forcar)
        with open(arquivo_saida, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"HTML salvo em: {arquivo_saida} ({len(html)} caracteres)")
        print(f"URL final: {url}")
        print(f"Backend usado: {used}")
    except RuntimeError as e:
        print(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
