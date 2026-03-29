# Como rodar o projeto Salesforce (Corretores)

> **Secrets (Salesforce + Google Sheets):** veja **`COMO_SECRETS_CORRETOR.md`**.

## 1. Preparar o ambiente

Abra o **CMD** ou **PowerShell** na pasta **`salesforce`**:

```cmd
cd "...\Automações - Lucas\salesforce"
```

Instale as dependências (uma vez):

```cmd
pip install -r requirements.txt
```

Isso instala: `requests`, `pandas`, `openpyxl`, `streamlit`, `simple_salesforce`, `gspread`, `google-auth`, etc.

---

## 2. Rodar a interface (Streamlit) – recomendado

Aqui você preenche o formulário **Novo Contato: Corretor**, salva na **planilha Google** e/ou **cria o contato via API**.

```cmd
streamlit run salesforce_streamlit.py
```

O navegador abre em **http://localhost:8501**.

- **Salesforce (USER, PASSWORD, TOKEN)**: só nos **Secrets** do app — não há campos de login na tela.
- **Código Authenticator**: campo na tela só para o botão “Login e salvar HTML” quando houver 2FA.
- **Salvar na planilha Google**: exige `SERVICE_ACCOUNT_JSON` no `secrets.toml` (ver `COMO_SECRETS_CORRETOR.md`).

---

## 2b. Ficha Cadastral | Direcional Vendas RJ

Formulário **multipágina** (indicação, dados pessoais, endereço, acadêmico, bancário, PJ opcional, complementares). Após **Enviar ficha**: baixar **PDF** com a cópia e, se configurado, **enviar o PDF por e-mail**.

```cmd
streamlit run ficha_cadastral_vendas_rj_streamlit.py
```

**E-mail (opcional):** em `.streamlit/secrets.toml`:

```toml
[ficha_email]
SMTP_HOST = "smtp.seuprovedor.com"
SMTP_PORT = 587
SMTP_USER = "usuario"
SMTP_PASSWORD = "senha"
FROM_EMAIL = "remetente@empresa.com.br"
TO_EMAIL = "destino@empresa.com.br"
```

Se faltar algum campo obrigatório no envio, o app abre uma **página extra** só com os itens pendentes.

Após enviar a ficha, é possível **baixar PDF**, **enviar por e-mail** (`[ficha_email]` nos Secrets) e **criar o contato no Salesforce** com o mesmo `[salesforce]` do app Corretor — o payload é montado em `ficha_cadastral_payload.py` (campos alinhados a `criar_contato_exemplo_completo.py`).

---

## 3. Rodar só o script de login e salvar HTML (terminal)

Útil para obter o HTML da página após o login (sem abrir o Streamlit).

### No CMD (use aspas em volta de tudo):

```cmd
set "SALESFORCE_USER=lucas.maia@direcional.com.br"
set "SALESFORCE_PASSWORD=Cabuloso.102"
set "SALESFORCE_TOTP=AW7amoDwbkPnbMUASVUgPQlyy"
python salesforce_login_salvar_html.py
```

Ou com parâmetros (sem variáveis de ambiente):

```cmd
python salesforce_login_salvar_html.py --user lucas.maia@direcional.com.br --password sua_senha --totp 123456
```

O arquivo **salesforce_pagina_pos_login.html** é gerado na mesma pasta. O `--totp` é opcional (obrigatório se a conta tiver 2FA).

### No PowerShell:

```powershell
$env:SALESFORCE_USER="lucas.maia@direcional.com.br"
$env:SALESFORCE_PASSWORD="sua_senha"
$env:SALESFORCE_TOTP="123456"
python salesforce_login_salvar_html.py
```

---

## 4. Rodar só a API (testar conexão e listar campos)

Para testar a conexão com a API e listar os campos do objeto Contato.

### No CMD (senha e token separados – recomendado):

```cmd
set "SALESFORCE_USER=lucas.maia@direcional.com.br"
set "SALESFORCE_PASSWORD=sua_senha"
set "SALESFORCE_TOKEN=token_do_email"
python salesforce_api.py
```

### No CMD (senha + token colados):

```cmd
set "SALESFORCE_USER=lucas.maia@direcional.com.br"
set "SALESFORCE_PASSWORD=suasenhatokendoemail"
python salesforce_api.py
```

### No PowerShell:

```powershell
$env:SALESFORCE_USER="lucas.maia@direcional.com.br"
$env:SALESFORCE_PASSWORD="sua_senha"
$env:SALESFORCE_TOKEN="token_do_email"
python salesforce_api.py
```

Se der certo, o script imprime a lista de campos do Contact no terminal.

---

## Picklists no Streamlit

Os valores dos campos que são **picklist** no Salesforce (objeto **Contact**) estão em `corretor_campos.py`, alinhados ao export `salesforce_objetos_describe.json`. Se o org ganhar novos valores de lista, atualize o JSON (describe) e copie as opções para as constantes `_ATIVIDADE`, `_BANCO`, etc.

**Naturalidade** permanece texto livre no describe não traz valores de lista.

**Campos dependentes** (ex.: motivos x outros campos no org): o Streamlit não filtra opções dinamicamente; combinações inválidas podem ser rejeitadas pela API do Salesforce.

---

## Resumo rápido

| O que fazer                         | Comando                              |
|------------------------------------|--------------------------------------|
| Abrir a tela (login + planilha)    | `streamlit run salesforce_streamlit.py` |
| Só salvar HTML pós-login           | Definir USER, PASSWORD (e TOTP), depois `python salesforce_login_salvar_html.py` |
| Testar API e listar campos Contact | Definir USER, PASSWORD e TOKEN, depois `python salesforce_api.py` |

Lembrete: no CMD, use `set "VAR=valor"` (aspas em volta de **VAR=valor**), para o valor não ficar com aspas.
