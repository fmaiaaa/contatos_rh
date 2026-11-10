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


## Recuperação de falhas e preservação de contatos existentes

A consulta procura CPF com e sem máscara em conjunto e exige identidade compatível
(nome ou e-mail). CPFs ambíguos ou divergentes bloqueiam o envio. Contatos existentes
são somente consultados: a aplicação não muda sua árvore, proprietário ou outros dados,
mesmo quando o proprietário está inativo. Novos contatos recebem a conta
COORDENADORES DV - RJ e o usuário ativo autenticado da integração como OwnerId.

O módulo salesforce_integracao.py valida os campos graváveis e limites via Contact.describe,
o tipo de registro Corretor disponível e as picklists por tipo e seus controladores via UI API.
O CPF é validado pelos dígitos verificadores e enviado sem máscara, conforme verificado na
organização. Identificadores bancários inválidos ou longos são recusados, sem cortar números
ou transformar e-mail em conta bancária. Erros mantêm código, campo e mensagem do Salesforce.
Falhas de naturalidade não substituem a cidade informada por Brasília.

Login e chamadas REST têm timeout de conexão de 10s e leitura de 30s. Uma criação com resposta
incerta é seguida de consulta por CPF antes de qualquer nova criação. Colisão de apelido
permite no máximo três tentativas com novo apelido; duplicidade por e-mail não reutiliza outra
pessoa. A criação é relida para conferir identidade, conta e proprietário antes de confirmar.

O cabeçalho existente no Sheets mantém sua ordem; campos novos são adicionados ao final e a
linha é mapeada pelo nome de coluna. Cabeçalhos humanos e nomes de API permanecem distintos.
Não há substituição de cabeçalho sobre dados históricos. Importações legadas alinham os
blocos pessoal e de API separadamente, exigindo concordância de nome e CPF; ambiguidade é
recusada. Uma falha de status/formatação após append conserva o número da linha na sessão
para evitar outro append na retentativa. A confirmação continua exigindo Salesforce e Sheets.

Validação: `python -m unittest discover -p "test_*.py"` executa 38 regressões isoladas,
incluindo a política de não alterar contatos existentes, respostas perdidas, colisão de apelido,
conflitos de identidade, picklists, limites, cabeçalhos e falha parcial de persistência.
Foram também realizadas autenticação e operações reais de recuperação no Salesforce usando
credenciais locais autorizadas; nenhuma credencial, planilha de pessoas ou relatório individual
é incluído no repositório. O teste automatizado não substitui um teste do formulário no navegador
de produção após o deploy do Streamlit.


## Credenciais Google Sheets em TOML

O carregamento de Secrets aceita agora a seção nativa `[connections.gsheets]`,
com os campos da conta de serviço diretamente em TOML, além de `[google_sheets]`
com campos diretos ou `SERVICE_ACCOUNT_JSON` em string/dicionário. A chave PEM
com sequências literais de nova linha é normalizada sem alterar os Secrets originais.
Credenciais incompletas não iniciam o envio. Não é necessário migrar uma seção
`[connections.gsheets]` válida para JSON.

Antes, esse formato era ignorado, provocando a mensagem genérica ao enviar,
antes mesmo de chamar Salesforce ou Sheets. A regressão foi reproduzida com o
arquivo local autorizado: o parser anterior retornou None; o novo reconheceu a
conta e autenticou de verdade na planilha, lendo os 132 cabeçalhos de
Corretores Nova Base, sem escrever registros no teste.

Falhas de gravação agora distinguem acesso recusado, planilha/aba ausente,
cota, indisponibilidade, rede e configuração. As mensagens incluem um código
GSHEETS para o suporte, sem mostrar credenciais ou a resposta HTTP bruta.
Credenciais ausentes/inválidas também têm mensagem específica.
Validação da correção: 45 testes isolados aprovados, incluindo compatibilidade
TOML/JSON, Secrets como Mapping, PEM, mensagens seguras e códigos de erro HTTP.


## Auditoria completa de limites e regras de Contact (10/11/2026)

O arquivo CAMPOS_CONTACT.md inventaria os 213 campos visíveis ao usuário da API,
com origem, condição de envio, tipo, limite e permissões. O esquema sanitizado em
salesforce_contact_schema.json permite antecipar esses limites nos campos do
formulário, sem autenticar a cada renderização. A validação final continua lendo
Contact.describe e as picklists do tipo Corretor para bloquear divergências recentes.
Falhas de acesso à UI API interrompem a criação; não há fallback para listas globais
que possam aceitar opções proibidas ao tipo de registro.

Agência aceita no máximo 4 caracteres; e-mail 80; observações 500; primeiro nome 40;
sobrenome 80; RG 25; conta 20; nomes de familiares 50. Todos os campos de texto são
validados conforme o metadado, com contagem UTF-16 e limite de armazenamento. O
backend não corta nomes ou textos longos: retorna a correção necessária. Números
validam precisão e escala, rejeitam NaN/infinito/booleanos; inteiros não passam por
float antes do JSON. Datas, booleanos, IDs e objeto de referência são conferidos.
Picklists e dependências são validadas e refletidas nas opções do formulário.

Foram lidas 24 regras de validação, 20 ativas. As 16 aplicáveis à criação de Corretor
foram implementadas em salesforce_regras.py e testadas com cenários de bloqueio.
As 4 com ISCHANGED são de atualização: segundo a documentação Salesforce essa
função retorna falso na criação. Contatos existentes continuam sem alterações.
Cônjuge, CPF/CNPJ, celular, indicação, motivo de não recomendação, inatividade,
reativação, UF e requisitos de CRECI/TTI são considerados conforme cada condição.

Os requisitos de CRECI/TTI ficam visíveis quando exigidos pela atividade, mesmo
com Possui CRECI = Não. Foram removidos CRECI 1, validade/matrícula com data de hoje
e responsável fictício como artifício para satisfazer regras. A atividade Corretor
exige CRECI e validade; Estagiário exige validade, matrícula e responsável. O usuário
precisa informar os dados reais. Origem RH volta a integrar o JSON, pois foi
confirmada como opção gravável no tipo Corretor. O e-mail é consultado antes de criar
para bloquear colisão com outro contato; CPF e apelido preservam os controles e
retentativas anteriores. Exceções de validação mantêm a mensagem específica no
resumo, em vez de serem convertidas em Falha no envio ao Salesforce.

Há 4 regras de duplicidade (2 ativas: CPF e e-mail). Das 10 definições de fluxo
ativas de Contact, 4 executam na criação. Três delas negam acesso a InteractionCustomError;
ApexTrigger também não foi disponibilizado ao usuário. Não é possível prometer uma
reprodução completa de lógica não acessível ou futura. As regras e automações do
servidor continuam sendo executadas pelo Salesforce; o app preserva seus erros,
nunca ignora bloqueios e só confirma sucesso após Salesforce e Sheets.

Validação: 66 testes aprovados; inicialização Streamlit AppTest sem exceções; os
213 campos comparados com a API real sem divergências; 6 casos inválidos bloqueados
com metadados reais, sem inserir ou alterar contatos durante a auditoria.
