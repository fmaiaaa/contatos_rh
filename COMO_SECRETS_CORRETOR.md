# Secrets e configuração — Cadastro Corretor

A interface **não** pede e-mail/senha/token do Salesforce na tela: use apenas os **Secrets** do Streamlit (Cloud ou `secrets.toml` local).

## 1. Arquivo local `.streamlit/secrets.toml`

Crie a pasta `.streamlit` na raiz do projeto (ou ao lado de `salesforce_streamlit.py`, conforme como você roda o app) e o arquivo `secrets.toml`:

```toml
# Salesforce (API — criar contato e/ou consultas)
[salesforce]
USER = "seu_email@direcional.com.br"
PASSWORD = "sua_senha"
TOKEN = "security_token_do_salesforce"

# Google Sheets — gravação na planilha
[google_sheets]
SPREADSHEET_ID = "1_9x4rfHoP2M47qXJENoD3vMLf_7rWUhNjrU8EtESxy8"
WORKSHEET_NAME = "Corretores"

# Cole o JSON completo da conta de serviço (uma linha ou bloco multilinha com aspas triplas)
SERVICE_ACCOUNT_JSON = '''
{
  "type": "service_account",
  "project_id": "...",
  "private_key_id": "...",
  "private_key": "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n",
  "client_email": "sua-conta@projeto.iam.gserviceaccount.com",
  "client_id": "...",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  ...
}
'''
```

### Google Cloud / Planilha

1. No Google Cloud Console, crie um projeto (ou use um existente), ative a **Google Sheets API** e a **Google Drive API**.
2. Crie uma **conta de serviço**, baixe o JSON da chave.
3. Abra a planilha no Google Sheets → **Compartilhar** → adicione o e-mail **`client_email`** do JSON com permissão de **Editor**.

Sem isso, o `gspread` retorna erro de permissão.

## 2. Streamlit Cloud

No painel do app → **Secrets**, cole o mesmo conteúdo TOML (sem comentários inválidos).  
**Importante:** o `SERVICE_ACCOUNT_JSON` deve ser JSON válido; em Cloud costuma-se colar o JSON inteiro em uma linha ou usar aspas triplas como no exemplo.

Variáveis de ambiente alternativas (se não usar `secrets.toml`):

- `SALESFORCE_USER`, `SALESFORCE_PASSWORD`, `SALESFORCE_TOKEN` — já usadas pelo `salesforce_api`.

## 3. O que mudou no fluxo

- O formulário replica os blocos do **Novo Contato: Corretor** (campos mapeados em `corretor_campos.py`).
- **Salvar na planilha Google** anexa uma linha na aba configurada (cria a aba se não existir e preenche o cabeçalho na primeira vez).
- **Criar contato no Salesforce** usa a API (`simple_salesforce`) com o payload mapeado; campos somente leitura no org vão para **Observações** ou só para a planilha.
- Lookups (**Account**, **User**, **Empreendimento**) esperam **Id Salesforce** (15 ou 18 caracteres) quando indicado no rótulo.

## 4. Ajustes no org

Se algum nome de API (`__c`) divergir após atualização do Salesforce, edite `corretor_campos.py` na lista `_campos_def()`.
