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
