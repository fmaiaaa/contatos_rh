# Integração da ficha cadastral

Todos os cadastros da ficha, de RJ e MG, usam a conta Salesforce com nome exato
`COORDENADORES DV - RJ`. A conta deve existir e ser acessível ao usuário da integração.
A aplicação não cria contatos sem resolver essa conta. Regional, unidade e regras
de CRECI continuam sendo informações próprias do profissional.

A seleção de gerente foi retirada. Valores antigos de gerente, AccountId e defaults
não substituem o destino obrigatório. A coluna histórica de gerente na planilha foi
preservada para manter o alinhamento das linhas existentes.

Quando encontra um CPF existente (com ou sem máscara), a ficha atualiza somente seu
AccountId e reaproveita o contato. Também trata o contato retornado pela regra de
duplicidade CPF_Contato. Telefone, apelido e CRECI não identificam uma pessoa com
segurança e não são usados para reaproveitar contatos. Falhas de atualização são
registradas como erro, sem indicar integração concluída.

O endereço de e-mail é normalizado antes de Salesforce e SMTP. Chaves estranhas ao
mapeamento de Contact são descartadas. Falhas transitórias de conexão no login têm
até três tentativas; credenciais recusadas precisam ser corrigidas nos Secrets.

Validação local: `python -m unittest -v test_ficha_integracao`.
Os testes usam clientes simulados e não alteram dados reais.

Esta alteração vale para novos envios e reprocessamentos pela ficha. Não executa
migração em massa dos contatos históricos diretamente no Salesforce.

## Confirmação, planilha e apresentação

O cadastro só abre a conclusão depois do sucesso Salesforce e da gravação na
planilha configurada em `google_sheets.SPREADSHEET_ID` / `WORKSHEET_NAME`.
Falhas Salesforce ficam registradas na planilha sem conclusão ou e-mail de boas-vindas.
Ao reenviar os mesmos dados, a aplicação atualiza a linha de falha existente.
O número da linha é obtido da resposta de append da API, evitando conflitos entre
envios simultâneos. Status e vínculo são confirmados por leitura após a escrita.
Valores são escritos como RAW para preservar zeros iniciais e texto literal.

Após gravar, toda a grade da aba Corretores recebe altura de 32 px, largura de
180 px e texto com CLIP, sem crescimento conforme o conteúdo. O conteúdo integral
permanece na célula. A formatação é aplicada também às linhas já existentes.

Somente a regional de cadastro RJ explicitamente salva no envio abre vídeos/mapa;
MG e regional ausente não recebem essa tela, independentemente da conta Salesforce.
O tema padrão é claro em `.streamlit/config.toml`, com CSS claro também nos menus,
calendários e popups, independentemente da preferência do sistema operacional.

## Nova base e diagnóstico de login

O fluxo principal grava em **Corretores Nova Base**, na mesma planilha configurada.
WORKSHEET_NAME antigo nos Secrets não muda esse destino. Se a aba estiver ausente,
a aplicação cria a aba pelo nome exato. Erros de permissão não redirecionam para a
primeira aba. Os dados das abas anteriores permanecem preservados.

O login usa por padrão o domínio `direcional.my`; pode ser configurado com
`[salesforce] DOMAIN = "direcional.my"` (também aceita URL Salesforce completa).
USER, PASSWORD e TOKEN explícitos nos Secrets substituem os valores antigos do
ambiente. TOKEN vazio também limpa um token antigo.

Falhas de conexão agora mantêm o diagnóstico da autenticação na mensagem de envio
e na retentativa. Credenciais inválidas, usuário bloqueado ou login por API recusado
exigem ajuste no ambiente/na organização Salesforce. Esta alteração não confirma
uma autenticação real sem as credenciais do deploy.
