# Inventário completo de campos — Contact / Salesforce

Consulta ao Salesforce em 10/11/2026. Inventário dos 213 campos visíveis para o usuário da integração, confrontado com o fluxo de criação da ficha cadastral.

## Como interpretar

- “Sim” indica que o campo pode integrar o JSON enviado na criação; opcionais vazios são omitidos.
- Para contatos já existentes, nenhum campo é alterado: o aplicativo apenas confirma a identidade e aproveita o vínculo.
- “Não enviado” não significa necessariamente vazio no registro: padrões, fórmulas, fluxos ou outras integrações podem preenchê-lo.
- A lista corresponde aos campos retornados por Contact.describe para o usuário da integração; campos ocultos por permissão não podem ser inventariados com essa credencial.
- A documentação corresponde à versão corrigida nesta auditoria; “Sim” considera tanto os campos informados quanto os derivados pela integração.

## Cobertura

- Sim, automático/derivado: **14** campos.
- Sim, quando informado: **38** campos.
- Não enviado: **119** campos.
- Não; padrão do Salesforce: **22** campos.
- Sim, conforme cadastro/condição: **7** campos.
- Não; controlado pelo Salesforce: **13** campos.

## Todos os campos do objeto

### 1. ID da conta — `AccountId`

- **Na integração:** Sim, automático/derivado.
- **Origem/condição:** Resolvido pelo nome COORDENADORES DV - RJ; não usa gerente escolhido ou conta antiga.
- **Tipo e limite:** reference; 18 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 2. Agência Bancária — `Ag_ncia_Banc_ria__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: Agência Bancária * [agencia_bancaria].
- **Tipo e limite:** string; 4 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 3. Apelido — `Apelido__c`

- **Na integração:** Sim, automático/derivado.
- **Origem/condição:** Gerado incrementalmente a partir do primeiro nome e regional; único, com retentativa por colisão.
- **Tipo e limite:** string; 50 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 4. Nome do assistente — `AssistantName`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** string; 40 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 5. Telefone do assistente — `AssistantPhone`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** phone; 40 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 6. Assunto — `Assunto__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 7. Atividade — `Atividade__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: Função na operação * [atividade].
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 8. Aumento de Família — `AumentoFamilia__c`

- **Na integração:** Não; padrão do Salesforce.
- **Origem/condição:** Não enviado pela integração; o metadado informa valor padrão na criação.
- **Tipo e limite:** boolean; Conforme tipo.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 9. Região / Bairro de Interesse 2 — `BairroInteresse2__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 10. Região / Bairro de Interesse 3 — `BairroInteresse3__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 11. Região / Bairro de Interesse — `BairroInteresse__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 12. Banco — `Banco__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: Banco * [banco].
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 13. Data de nascimento — `Birthdate`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: Data de nascimento * [birthdate].
- **Tipo e limite:** date; Conforme tipo.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 14. Blacklist — `Blacklist__c`

- **Na integração:** Não enviado.
- **Origem/condição:** O campo é excluído explicitamente do payload de criação.
- **Tipo e limite:** boolean; Conforme tipo.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 15. Bypass Validação Endereço Bora Vender — `Bypass_Validacao_Endereco_Bora_Vender__c`

- **Na integração:** Não; padrão do Salesforce.
- **Origem/condição:** Não enviado pela integração; o metadado informa valor padrão na criação.
- **Tipo e limite:** boolean; Conforme tipo.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 16. CNPJ — `CNPJ__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** string; 18 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 17. CPF — `CPF__c`

- **Na integração:** Sim, conforme cadastro/condição.
- **Origem/condição:** CPF informado, validado pelos dígitos verificadores; enviado com 11 dígitos sem máscara.
- **Tipo e limite:** string; 14 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 18. CRECI — `CRECI__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: CRECI [creci]. Enviado quando a situação/atividade exige CRECI; campos exigidos ficam visíveis. Não há CRECI, datas ou responsável fictícios.
- **Tipo e limite:** double; precisão 18, escala 0.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 19. CRECI do Responsável — `CRECI_do_Responsavel__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: CRECI do Responsável [creci_responsavel]. Enviado quando a situação/atividade exige CRECI; campos exigidos ficam visíveis. Não há CRECI, datas ou responsável fictícios.
- **Tipo e limite:** double; precisão 18, escala 0.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 20. Código Pessoa UAU — `C_digo_Pessoa_UAU__c`

- **Na integração:** Não enviado.
- **Origem/condição:** O campo é excluído explicitamente do payload de criação.
- **Tipo e limite:** double; precisão 18, escala 0.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 21. Cadastrado como Fornecedor no UAU? — `Cadastrado_como_Fornecedor_no_UAU__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha. O usuário da integração não pode gravar esse campo na criação.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 22. Camiseta — `Camiseta__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: Camiseta * [camiseta].
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 23. Celular 2 — `Celular_2__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** phone; 40 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 24. Cidade de Interesse 2 — `CidadeInteresse2__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 25. Cidade de Interesse 3 — `CidadeInteresse3__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 26. Cidade de Interesse — `CidadeInteresse__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 27. Conta Bancária — `Conta_Banc_ria__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: Conta Bancária * [conta_bancaria].
- **Tipo e limite:** string; 20 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 28. Contact ID — `Contact_ID__c`

- **Na integração:** Não enviado.
- **Origem/condição:** O campo é excluído explicitamente do payload de criação.
- **Tipo e limite:** string; 1300 caracteres.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 29. Contrato — `Contrato__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** textarea; 500 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 30. Faturamento Comissão — `Corretor_Associado__c`

- **Na integração:** Não enviado.
- **Origem/condição:** O campo é excluído explicitamente do payload de criação.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 31. Corretor BLIP — `Corretor_BLIP__c`

- **Na integração:** Não; padrão do Salesforce.
- **Origem/condição:** Não enviado pela integração; o metadado informa valor padrão na criação.
- **Tipo e limite:** boolean; Conforme tipo.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 32. Corretor GA — `Corretor_GA__c`

- **Na integração:** Não; padrão do Salesforce.
- **Origem/condição:** Não enviado pela integração; o metadado informa valor padrão na criação.
- **Tipo e limite:** boolean; Conforme tipo.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 33. Corretor SDR — `Corretor_SDR__c`

- **Na integração:** Não; padrão do Salesforce.
- **Origem/condição:** Não enviado pela integração; o metadado informa valor padrão na criação.
- **Tipo e limite:** boolean; Conforme tipo.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 34. Criado pelo ID — `CreatedById`

- **Na integração:** Não; controlado pelo Salesforce.
- **Origem/condição:** A integração não inclui esse campo no insert; é calculado ou controlado pela plataforma.
- **Tipo e limite:** reference; 18 caracteres.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 35. Data de criação — `CreatedDate`

- **Na integração:** Não; controlado pelo Salesforce.
- **Origem/condição:** A integração não inclui esse campo no insert; é calculado ou controlado pela plataforma.
- **Tipo e limite:** datetime; Conforme tipo.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 36. Dados para PIX — `Dados_para_PIX__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: Dados para PIX * [dados_pix].
- **Tipo e limite:** string; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 37. Data do Agendamento — `DataAgendamento__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** datetime; Conforme tipo.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 38. Data do Encerramento — `DataEncerramento__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** date; Conforme tipo.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 39. Data Contrato — `Data_Contrato__c`

- **Na integração:** Sim, automático/derivado.
- **Origem/condição:** Data do envio em Brasília, preenchida automaticamente.
- **Tipo e limite:** date; Conforme tipo.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 40. Data Credenciamento — `Data_Credenciamento__c`

- **Na integração:** Sim, automático/derivado.
- **Origem/condição:** Data do envio em Brasília, preenchida automaticamente.
- **Tipo e limite:** date; Conforme tipo.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 41. Data Descredenciamento — `Data_Descredenciamento__c`

- **Na integração:** Não enviado.
- **Origem/condição:** O campo é excluído explicitamente do payload de criação.
- **Tipo e limite:** date; Conforme tipo.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 42. Data Entrada Recruta+ — `Data_Entrada_Recruta__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** date; Conforme tipo.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 43. Data Matrícula - TTI — `Data_Matricula_TTI__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: Data Matrícula - TTI [data_matricula_tti]. Enviado quando a situação/atividade exige CRECI; campos exigidos ficam visíveis. Não há CRECI, datas ou responsável fictícios.
- **Tipo e limite:** date; Conforme tipo.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 44. Data Reativação — `Data_Reativacao__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** date; Conforme tipo.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 45. Data Saída Recruta+ — `Data_Sai_da_Recruta__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** date; Conforme tipo.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 46. Data Transferência Corretor Parceiro — `Data_Transferencia_Corretor_Parceiro__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** date; Conforme tipo.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 47. Data da Entrevista — `Data_da_Entrevista__c`

- **Na integração:** Sim, automático/derivado.
- **Origem/condição:** Data do envio em Brasília, preenchida automaticamente.
- **Tipo e limite:** date; Conforme tipo.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 48. Data de Saída — `Data_de_Saida__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** date; Conforme tipo.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 49. Data de Transferência — `Data_de_Transferencia__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** date; Conforme tipo.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 50. Data de conclusão — `Data_de_conclusao__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: Data de conclusão [data_conclusao]. Enviado quando a situação/atividade exige CRECI; campos exigidos ficam visíveis. Não há CRECI, datas ou responsável fictícios.
- **Tipo e limite:** date; Conforme tipo.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 51. Departamento — `Department`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** string; 80 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 52. Descrição — `DescricaoAtividade__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** textarea; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 53. Descrição do contato — `Description`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** textarea; 32000 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 54. Detalhe - Outras Motivações — `DetalheOutrasMotivacoes__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** string; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 55. Downgrade — `Downgrade__c`

- **Na integração:** Não; padrão do Salesforce.
- **Origem/condição:** Não enviado pela integração; o metadado informa valor padrão na criação.
- **Tipo e limite:** boolean; Conforme tipo.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 56. E-mail Direcional — `E_mail_Direcional__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** email; 80 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 57. Email — `Email`

- **Na integração:** Sim, conforme cadastro/condição.
- **Origem/condição:** E-mail corporativo informado, saneado e validado; máximo de 80 caracteres.
- **Tipo e limite:** email; 80 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 58. Data da devolução do email — `EmailBouncedDate`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** datetime; Conforme tipo.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 59. Motivo da devolução do email — `EmailBouncedReason`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** string; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 60. Email Campanhas Comerciais — `Email_Campanhas_Comerciais__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** string; 100 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 61. Empreendimento de Interesse 2 — `EmpreendimentoInteresse2__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 62. Empreendimento de Interesse 3 — `EmpreendimentoInteresse3__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 63. Empreendimento de Interesse — `EmpreendimentoInteresse__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 64. Bairro — `EnderecoResidencialBairro__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: Bairro * [endereco_bairro].
- **Tipo e limite:** string; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 65. CEP — `EnderecoResidencialCEP__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: CEP * [endereco_cep].
- **Tipo e limite:** string; 9 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 66. Cidade — `EnderecoResidencialCidade__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: Cidade * [endereco_cidade].
- **Tipo e limite:** string; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 67. Complemento — `EnderecoResidencialComplemento__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: Complemento [endereco_complemento].
- **Tipo e limite:** string; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 68. Estado — `EnderecoResidencialEstado__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: Estado (UF) * [endereco_estado].
- **Tipo e limite:** string; 2 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 69. Logradouro — `EnderecoResidencialLogradouro__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: Logradouro * [endereco_logradouro].
- **Tipo e limite:** string; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 70. Número — `EnderecoResidencialNumero__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: Número * [endereco_numero].
- **Tipo e limite:** string; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 71. Endereço Form — `Endereco_Form__c`

- **Na integração:** Não; controlado pelo Salesforce.
- **Origem/condição:** A integração não inclui esse campo no insert; é calculado ou controlado pela plataforma.
- **Tipo e limite:** string; 1300 caracteres.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 72. Erro Integração UAU — `ErroIntegracaoUAU__c`

- **Na integração:** Não enviado.
- **Origem/condição:** O campo é excluído explicitamente do payload de criação.
- **Tipo e limite:** textarea; 32768 caracteres.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 73. Escolaridade — `Escolaridade__c`

- **Na integração:** Sim, conforme cadastro/condição.
- **Origem/condição:** Valor informado; o enriquecimento aplica o padrão configurado quando ausente.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 74. Estado Civil — `EstadoCivil__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: Estado Civil * [estado_civil].
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 75. Faixa Etária — `FaixaEtaria__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 76. Fax comercial — `Fax`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** phone; 40 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 77. File Path — `FilePath__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** string; 100 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 78. Finalidade da Compra — `Finalidade_da_Compra__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 79. Primeiro Nome — `FirstName`

- **Na integração:** Sim, automático/derivado.
- **Origem/condição:** Derivado da primeira palavra do Nome completo; limite de 40 caracteres.
- **Tipo e limite:** string; 40 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 80. Identidade de gênero — `GenderIdentity`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 81. Gênero Natural — `GeneroNatural__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 82. Gerente anterior — `GerenteAnterior__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** reference; 18 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 83. Gerente de Vendas Id — `GerenteDeVendasId__c`

- **Na integração:** Não; controlado pelo Salesforce.
- **Origem/condição:** A integração não inclui esse campo no insert; é calculado ou controlado pela plataforma.
- **Tipo e limite:** string; 1300 caracteres.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 84. Gerente de vendas — `GerenteDeVendas__c`

- **Na integração:** Não; controlado pelo Salesforce.
- **Origem/condição:** A integração não inclui esse campo no insert; é calculado ou controlado pela plataforma.
- **Tipo e limite:** boolean; Conforme tipo.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 85. Gerente Desativado — `Gerente_Desativado__c`

- **Na integração:** Não; padrão do Salesforce.
- **Origem/condição:** Não enviado pela integração; o metadado informa valor padrão na criação.
- **Tipo e limite:** boolean; Conforme tipo.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 86. Recusa de email — `HasOptedOutOfEmail`

- **Na integração:** Não; padrão do Salesforce.
- **Origem/condição:** Não enviado pela integração; o metadado informa valor padrão na criação.
- **Tipo e limite:** boolean; Conforme tipo.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 87. Telefone residencial — `HomePhone`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** phone; 40 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 88. ID do contato — `Id`

- **Na integração:** Não; controlado pelo Salesforce.
- **Origem/condição:** A integração não inclui esse campo no insert; é calculado ou controlado pela plataforma.
- **Tipo e limite:** id; 18 caracteres.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 89. Idade — `Idade__c`

- **Na integração:** Não; controlado pelo Salesforce.
- **Origem/condição:** A integração não inclui esse campo no insert; é calculado ou controlado pela plataforma.
- **Tipo e limite:** double; precisão 18, escala 0.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 90. Identidade de gênero — `Identidade_de_g_nero__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 91. Imob alterada — `ImobAlterada__c`

- **Na integração:** Não; padrão do Salesforce.
- **Origem/condição:** Não enviado pela integração; o metadado informa valor padrão na criação.
- **Tipo e limite:** boolean; Conforme tipo.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 92. Indicado por — `Indicado_por__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** reference; 18 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 93. ID do Indivíduo — `IndividualId`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** reference; 18 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 94. Excluído — `IsDeleted`

- **Na integração:** Não; controlado pelo Salesforce.
- **Origem/condição:** A integração não inclui esse campo no insert; é calculado ou controlado pela plataforma.
- **Tipo e limite:** boolean; Conforme tipo.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 95. Email devolvido — `IsEmailBounced`

- **Na integração:** Não; padrão do Salesforce.
- **Origem/condição:** Não enviado pela integração; o metadado informa valor padrão na criação.
- **Tipo e limite:** boolean; Conforme tipo.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 96. Conta pessoal — `IsPersonAccount`

- **Na integração:** Não; padrão do Salesforce.
- **Origem/condição:** Não enviado pela integração; o metadado informa valor padrão na criação.
- **Tipo e limite:** boolean; Conforme tipo.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 97. Importante — `IsPriorityRecord`

- **Na integração:** Não; padrão do Salesforce.
- **Origem/condição:** Não enviado pela integração; o metadado informa valor padrão na criação.
- **Tipo e limite:** boolean; Conforme tipo.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 98. J Pró Passado — `JProPassado__c`

- **Na integração:** Não; padrão do Salesforce.
- **Origem/condição:** Não enviado pela integração; o metadado informa valor padrão na criação.
- **Tipo e limite:** double; precisão 3, escala 0.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 99. Chave Data.com — `Jigsaw`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** string; 20 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 100. Jigsaw Contact ID — `JigsawContactId`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha. O usuário da integração não pode gravar esse campo na criação.
- **Tipo e limite:** string; 20 caracteres.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 101. J Pró Atual — `JornadaPro__c`

- **Na integração:** Não; padrão do Salesforce.
- **Origem/condição:** Não enviado pela integração; o metadado informa valor padrão na criação.
- **Tipo e limite:** double; precisão 3, escala 0.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 102. Última atividade — `LastActivityDate`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha. O usuário da integração não pode gravar esse campo na criação.
- **Tipo e limite:** date; Conforme tipo.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 103. Data da última solicitação do Stay-in-Touch — `LastCURequestDate`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha. O usuário da integração não pode gravar esse campo na criação.
- **Tipo e limite:** datetime; Conforme tipo.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 104. Data do último salvamento do Stay-in-Touch — `LastCUUpdateDate`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha. O usuário da integração não pode gravar esse campo na criação.
- **Tipo e limite:** datetime; Conforme tipo.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 105. Última modificação pelo ID — `LastModifiedById`

- **Na integração:** Não; controlado pelo Salesforce.
- **Origem/condição:** A integração não inclui esse campo no insert; é calculado ou controlado pela plataforma.
- **Tipo e limite:** reference; 18 caracteres.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 106. Data da última modificação — `LastModifiedDate`

- **Na integração:** Não; controlado pelo Salesforce.
- **Origem/condição:** A integração não inclui esse campo no insert; é calculado ou controlado pela plataforma.
- **Tipo e limite:** datetime; Conforme tipo.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 107. Sobrenome — `LastName`

- **Na integração:** Sim, automático/derivado.
- **Origem/condição:** Derivado do restante do Nome completo; se há uma palavra, usa essa palavra; limite de 80.
- **Tipo e limite:** string; 80 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** sim.

### 108. Última data citada — `LastReferencedDate`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha. O usuário da integração não pode gravar esse campo na criação.
- **Tipo e limite:** datetime; Conforme tipo.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 109. Data da última visualização — `LastViewedDate`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha. O usuário da integração não pode gravar esse campo na criação.
- **Tipo e limite:** datetime; Conforme tipo.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 110. Origem do lead — `LeadSource`

- **Na integração:** Não; padrão do Salesforce.
- **Origem/condição:** Não enviado pela integração; o metadado informa valor padrão na criação.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 111. Link Google Maps — `Link_Google_Maps_Contato__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha. O usuário da integração não pode gravar esse campo na criação.
- **Tipo e limite:** url; 255 caracteres.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 112. Endereço de correspondência — `MailingAddress`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha. O usuário da integração não pode gravar esse campo na criação.
- **Tipo e limite:** address; Conforme tipo.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 113. Cidade de correspondência — `MailingCity`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** string; 40 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 114. País de correspondência — `MailingCountry`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** string; 80 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 115. Mailing Geocode Accuracy — `MailingGeocodeAccuracy`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 40 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 116. Latitude de correspondência — `MailingLatitude`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** double; precisão 18, escala 15.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 117. Longitude de correspondência — `MailingLongitude`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** double; precisão 18, escala 15.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 118. CEP de correspondência — `MailingPostalCode`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** string; 20 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 119. Estado/Província de correspondência — `MailingState`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** string; 80 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 120. Rua de correspondência — `MailingStreet`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** textarea; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 121. ID do registro mestre — `MasterRecordId`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha. O usuário da integração não pode gravar esse campo na criação.
- **Tipo e limite:** reference; 18 caracteres.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 122. Matrimônio — `Matrimonio__c`

- **Na integração:** Não; padrão do Salesforce.
- **Origem/condição:** Não enviado pela integração; o metadado informa valor padrão na criação.
- **Tipo e limite:** boolean; Conforme tipo.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 123. Melhor horário de atendimento — `MelhorHorarioAtendimento__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 124. Celular — `MobilePhone`

- **Na integração:** Sim, conforme cadastro/condição.
- **Origem/condição:** Celular informado e normalizado; pode usar telefone alternativo válido conforme o resolvedor do app.
- **Tipo e limite:** phone; 40 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 125. Motivo Descredenciamento — `Motivo_Descredenciamento__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 126. Motivo Inatividade — `Motivo_Inatividade__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 127. Motivo — `Motivo__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 128. Mudança de Cidade — `MudancaCidade__c`

- **Na integração:** Não; padrão do Salesforce.
- **Origem/condição:** Não enviado pela integração; o metadado informa valor padrão na criação.
- **Tipo e limite:** boolean; Conforme tipo.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 129. Multiplicador Final Calculado — `MultiplicadorFinal__c`

- **Na integração:** Não enviado.
- **Origem/condição:** O campo é excluído explicitamente do payload de criação.
- **Tipo e limite:** double; precisão 18, escala 6.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 130. Multiplicador de Nível — `Multiplicador__c`

- **Na integração:** Sim, automático/derivado.
- **Origem/condição:** Regra da atividade: Captador 0,9; demais atividades previstas 1,0.
- **Tipo e limite:** double; precisão 8, escala 6.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 131. Multiplicador de Regime — `Multiplicador_de_Regime__c`

- **Na integração:** Sim, automático/derivado.
- **Origem/condição:** Valor automático 1,0.
- **Tipo e limite:** double; precisão 8, escala 6.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 132. Nacionalidade — `Nacionalidade__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: Nacionalidade * [nacionalidade].
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 133. Nome completo — `Name`

- **Na integração:** Não; controlado pelo Salesforce.
- **Origem/condição:** A integração não inclui esse campo no insert; é calculado ou controlado pela plataforma.
- **Tipo e limite:** string; 121 caracteres.
- **Gravável na criação:** não; **obrigatório pelo metadado:** sim.

### 134. Não recomendado - Motivo — `Nao_recomendado_Motivo__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** textarea; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 135. Naturalidade — `Naturalidade__c`

- **Na integração:** Sim, automático/derivado.
- **Origem/condição:** Valor derivado pela lógica atual de capital da UF de naturalidade.
- **Tipo e limite:** string; 50 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 136. Nome da Mãe — `Nome_da_Mae__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: Nome da Mãe * [nome_mae].
- **Tipo e limite:** string; 50 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 137. Nome do Cônjuge — `Nome_do_Conjuge__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: Nome do Cônjuge [nome_conjuge]. Enviado quando Estado Civil = Casado.
- **Tipo e limite:** string; 50 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 138. Nome do Pai — `Nome_do_Pai__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: Nome do Pai * [nome_pai].
- **Tipo e limite:** string; 50 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 139. Nome do Responsável — `Nome_do_Responsavel__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: Nome do Responsável [nome_responsavel]. Enviado quando a situação/atividade exige CRECI; campos exigidos ficam visíveis. Não há CRECI, datas ou responsável fictícios.
- **Tipo e limite:** string; 50 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 140. Número de Filhos — `NumeroFilhos__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 141. Número de Quartos — `NumeroQuartos__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 142. Número de Vagas — `NumeroVagas__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 143. Observações — `Observacoes__c`

- **Na integração:** Sim, conforme cadastro/condição.
- **Origem/condição:** Texto informado, referências do cadastro e registro da automação. Limite total de 500 caracteres.
- **Tipo e limite:** textarea; 500 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 144. Operação — `Opera_o__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** double; precisão 1, escala 0.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 145. Oportunidades Fechadas e Ganhas — `OportunidadesFechadasGanhas__c`

- **Na integração:** Não; controlado pelo Salesforce.
- **Origem/condição:** A integração não inclui esse campo no insert; é calculado ou controlado pela plataforma.
- **Tipo e limite:** double; precisão 18, escala 0.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 146. Orgão Expedidor — `Orgao_Expedidor__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** string; 60 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 147. Orientação sexual — `Orientacao_sexual__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 148. Origem — `Origem__c`

- **Na integração:** Sim, automático/derivado.
- **Origem/condição:** Constante RH, validada na picklist do tipo Corretor.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 149. Outro endereço — `OtherAddress`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha. O usuário da integração não pode gravar esse campo na criação.
- **Tipo e limite:** address; Conforme tipo.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 150. Outra cidade — `OtherCity`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** string; 40 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 151. Outro país — `OtherCountry`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** string; 80 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 152. Other Geocode Accuracy — `OtherGeocodeAccuracy`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 40 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 153. Outra latitude — `OtherLatitude`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** double; precisão 18, escala 15.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 154. Outra longitude — `OtherLongitude`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** double; precisão 18, escala 15.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 155. Outro telefone — `OtherPhone`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** phone; 40 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 156. Outro CEP — `OtherPostalCode`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** string; 20 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 157. Outro estado/província — `OtherState`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** string; 80 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 158. Outra rua — `OtherStreet`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** textarea; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 159. Outras Motivações — `OutrasMotivacoes__c`

- **Na integração:** Não; padrão do Salesforce.
- **Origem/condição:** Não enviado pela integração; o metadado informa valor padrão na criação.
- **Tipo e limite:** boolean; Conforme tipo.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 160. ID do proprietário — `OwnerId`

- **Na integração:** Sim, automático/derivado.
- **Origem/condição:** Usuário ativo autenticado da integração; desconsidera proprietário de snapshots antigos.
- **Tipo e limite:** reference; 18 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 161. PIS — `PIS__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** string; 50 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 162. PIX — `PIX__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** textarea; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 163. Telefone comercial — `Phone`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: Telefone [phone].
- **Tipo e limite:** phone; 40 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 164. URL da foto — `PhotoUrl`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha. O usuário da integração não pode gravar esse campo na criação.
- **Tipo e limite:** url; 255 caracteres.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 165. Possui Imóvel Próprio? — `PossuiImovelProprio__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 166. Possui Veículo Próprio? — `PossuiVeiculoProprio__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 167. Possui Filho(s)? — `Possui_Filho__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: Possui Filho(s)? [possui_filhos].
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 168. Possui deficiência? — `Possui_deficiencia__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** multipicklist; 4099 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 169. Preferred Contact Method — `Preferred_Contact_Method__c`

- **Na integração:** Sim, conforme cadastro/condição.
- **Origem/condição:** Opções informadas; se vazio, padrão conforme celular/e-mail disponível.
- **Tipo e limite:** multipicklist; 4099 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 170. Produto de Atuação — `Produto_de_Atuacao__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** reference; 18 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 171. Profissão — `Profissao__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 172. Projeto impulso — `ProjetoImpulso__c`

- **Na integração:** Não; padrão do Salesforce.
- **Origem/condição:** Não enviado pela integração; o metadado informa valor padrão na criação.
- **Tipo e limite:** boolean; Conforme tipo.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 173. Quantidade de Filhos — `Quantidade_de_Filhos__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: Quantidade de Filhos [qtd_filhos].
- **Tipo e limite:** double; precisão 3, escala 0.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 174. RG — `RG__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: RG * [rg].
- **Tipo e limite:** string; 25 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 175. Razão Social — `Razao_Social__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** string; 50 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 176. ID do tipo de registro — `RecordTypeId`

- **Na integração:** Sim, automático/derivado.
- **Origem/condição:** Tipo de registro Corretor disponível para o usuário da API, consultado no Salesforce.
- **Tipo e limite:** reference; 18 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 177. Recusa de Telefone — `RecusaTelefone__c`

- **Na integração:** Não; padrão do Salesforce.
- **Origem/condição:** Não enviado pela integração; o metadado informa valor padrão na criação.
- **Tipo e limite:** boolean; Conforme tipo.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 178. Regional — `Regional__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: Regional * [regional].
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 179. Renda — `Renda__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 180. Reporta-se ao ID — `ReportsToId`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** reference; 18 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 181. Retorno integração conta bancária — `RetornoIntegracaoContaBancaria__c`

- **Na integração:** Não enviado.
- **Origem/condição:** O campo é excluído explicitamente do payload de criação.
- **Tipo e limite:** textarea; 32768 caracteres.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 182. Retorno Integração Pessoa — `RetornoIntegracaoPessoa__c`

- **Na integração:** Não enviado.
- **Origem/condição:** O campo é excluído explicitamente do payload de criação.
- **Tipo e limite:** textarea; 32768 caracteres.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 183. Tratamento — `Salutation`

- **Na integração:** Sim, conforme cadastro/condição.
- **Origem/condição:** Derivado do campo Sexo, quando Masculino/Feminino.
- **Tipo e limite:** picklist; 40 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 184. Sexo — `Sexo__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: Sexo * [sexo].
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 185. Solicitante Descredenciamento — `Solicitantedescredenciamento__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** reference; 18 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 186. Status CRECI — `Status_CRECI__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: Status CRECI [status_creci]. Enviado quando a situação/atividade exige CRECI; campos exigidos ficam visíveis. Não há CRECI, datas ou responsável fictícios.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 187. Status Corretor — `Status_Corretor__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: Status Corretor * [status_corretor].
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 188. Status — `Status__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 189. Modstamp do sistema — `SystemModstamp`

- **Na integração:** Não; controlado pelo Salesforce.
- **Origem/condição:** A integração não inclui esse campo no insert; é calculado ou controlado pela plataforma.
- **Tipo e limite:** datetime; Conforme tipo.
- **Gravável na criação:** não; **obrigatório pelo metadado:** não.

### 190. TTI — `TTI__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** date; Conforme tipo.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 191. Telefone Adicional — `TelefoneAdicional__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** phone; 40 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 192. Telefone comercial — `TelefoneComercial__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** string; 24 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 193. Tipo de Trabalho — `TipoTrabalho__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 194. Tipo CRECI — `Tipo_CRECI__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 195. Tipo Corretor — `Tipo_Corretor__c`

- **Na integração:** Sim, automático/derivado.
- **Origem/condição:** Derivado da rede/unidade informada (Direcional, Riva ou parceira).
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 196. Tipo — `Tipo__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 197. Tipo de Conta — `Tipo_de_Conta__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: Tipo de Conta [tipo_conta].
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 198. Tipo de desligamento — `Tipo_de_desligamento__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 199. Tipo do PIX — `Tipo_do_PIX__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: Tipo do PIX * [tipo_pix].
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 200. Cargo — `Title`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** string; 128 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 201. UF Naturalidade — `UF_Naturalidade__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: UF Nascimento * [uf_naturalidade].
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 202. UF RG — `UF_RG__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: UF RG * [uf_rg].
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 203. Unidade Negocio — `Unidade_Negocio__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: Fará parte de qual rede? * [unidade_negocio].
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 204. Upgrade — `Upgrade__c`

- **Na integração:** Não; padrão do Salesforce.
- **Origem/condição:** Não enviado pela integração; o metadado informa valor padrão na criação.
- **Tipo e limite:** boolean; Conforme tipo.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 205. Faturamento Comissão — `Usu_rio_Associado__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 206. Usuário UAU — `Usu_rio_UAU__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** string; 25 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 207. Vai Compor Renda — `VaiComporRenda__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 208. Validade CRECI — `Validade_CRECI__c`

- **Na integração:** Sim, quando informado.
- **Origem/condição:** Origem no formulário: Validade CRECI [validade_creci]. Enviado quando a situação/atividade exige CRECI; campos exigidos ficam visíveis. Não há CRECI, datas ou responsável fictícios.
- **Tipo e limite:** date; Conforme tipo.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 209. Se considera da etnia — `etnia__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** picklist; 255 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 210. Created by Tuvis — `whatslly__Created_by_Whatslly__c`

- **Na integração:** Não; padrão do Salesforce.
- **Origem/condição:** Não enviado pela integração; o metadado informa valor padrão na criação.
- **Tipo e limite:** boolean; Conforme tipo.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 211. Last WhatsApp Message Time — `whatslly__Last_WhatsApp_Message_Time__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** datetime; Conforme tipo.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 212. Tuvis Person Id — `whatslly__Whatslly_Person_Id__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** string; 18 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

### 213. Tuvis Threads ID — `whatslly__Whatslly_Threads_ID__c`

- **Na integração:** Não enviado.
- **Origem/condição:** Sem origem/mapeamento no fluxo atual da ficha.
- **Tipo e limite:** string; 50 caracteres.
- **Gravável na criação:** sim; **obrigatório pelo metadado:** não.

## Dados da ficha sem um campo direto em Contact

Estes dados podem permanecer na planilha ou ser agregados às observações; não constituem um campo independente no objeto Contact.

- **Regional de Cadastro *** — chave `regional_cadastro`; seção Informações para contato.
- **Nome completo *** — chave `nome_completo`; seção Dados Pessoais.
- **Possui CRECI? *** — chave `possui_creci`; seção CRECI/TTI.
- **Tipo de Comissionamento** — chave `tipo_comissionamento`; seção CRECI/TTI.

## Regras e automações auditadas

- 24 regras de validação identificadas: 20 ativas, das quais 16 se aplicam à criação e 4 são condicionadas a alterações de registros existentes.
- 4 regras de duplicidade identificadas: 2 ativas (CPF e e-mail) e 2 inativas.
- 10 fluxos ativos associados a Contact: 4 executam na criação (um somente na criação e três também em atualização).
- As condições internas de três fluxos de criação retornaram INSUFFICIENT_ACCESS para InteractionCustomError. A leitura de ApexTrigger também não foi disponibilizada ao usuário da API. Essas automações continuam sob autoridade do Salesforce.
- O aplicativo nunca indica conclusão antes de confirmar a criação/reutilização no Salesforce e a persistência no Sheets.

## Referências técnicas

- [Metadados de objetos e campos](https://developer.salesforce.com/docs/platform/api/guide/sforce-api-calls-describesobjects-describesobjectresult.html)
- [ValidationRule na Tooling API](https://developer.salesforce.com/docs/platform/api-tooling/references/tooling-objects/tooling-validationrule.html)
- [ISCHANGED: falso na criação de registros](https://help.salesforce.com/s/articleView?id=platform.customize_functions_ischanged.htm&language=en_US&type=5)

## Todas as regras de validação inventariadas

- **`BlackList_CNPJ`** — Ativa: validada na criação. Mensagem: CNPJ Inválido.
- **`BlackList_CPF`** — Ativa: validada na criação. Mensagem: CPF Inválido
- **`CNPJ_Obrigatorio`** — Ativa: validada na criação. Mensagem: Favor inserir o CNPJ do corretor(a).
- **`CRECICoretor`** — Ativa: validada na criação. Mensagem: Favor inserir o CRECI do corretor(a).
- **`CRECI_Obrigatorio_Matriculado`** — Inativa: não aplicada. Mensagem: Obrigatório inserir o CRECI do responsável.
- **`Campo_origem_indicacao`** — Ativa: validada na criação. Mensagem: Favor informar o usuário que realizou a indicação.
- **`Celular_obrigatorio`** — Ativa: validada na criação. Mensagem: Favor informar o Celular.
- **`Data_de_saida_obrigatorio`** — Ativa: validada na criação. Mensagem: Campo obrigatório para corretor "Inativo"
- **`Informar_Motivo_Antecedente`** — Ativa: validada na criação. Mensagem: Favor informar o motivo da não recomendação.
- **`Informar_Motivo_Inatividade`** — Ativa: atualização, fora do fluxo de criação. Mensagem: Favor inserir o motivo da inatividade.
- **`MatriculaTTI_Estagiario`** — Ativa: validada na criação. Mensagem: Campo obrigatório para Estagiário.
- **`Motivo_Descredenciamento`** — Ativa: atualização, fora do fluxo de criação. Mensagem: Para Inativar este cadastro é obrigatório preencher os seguintes campos:  data de Descredenciamento, data de Saida, Motivo Descredenciamento,Solicitante do descredenciamento e  Motivo Inatividade.
- **`Obrigatorio_Casado`** — Ativa: validada na criação. Mensagem: Campo obrigatório para estado civil: Casado(a)
- **`Reativacao_corretor`** — Ativa: validada na criação. Mensagem: A data de reativação do corretor é obrigatório na reativação.
- **`Reativar_corretor`** — Ativa: atualização, fora do fluxo de criação. Mensagem: Corretor inativo so poderá ser reativado
- **`Responsavel_obrigatorio_estagiario`** — Ativa: validada na criação. Mensagem: Campo obrigatório para Estagiário.
- **`Solicitante_Descredenciamento`** — Inativa: não aplicada. Mensagem: Campo obrigatório para corretor inativo.
- **`VR02_Contato_DescredenciamentoInvalido`** — Ativa: atualização, fora do fluxo de criação. Mensagem: Data de descredenciamento não pode ser anterior à data de credenciamento ou à data de reativação.
- **`Valida_CPF_CNPJ`** — Ativa: validada na criação. Mensagem: Preencha CPF ou CNPJ
- **`Validacao_CNPJ_Imob`** — Inativa: não aplicada. Mensagem: O CNPJ deve conter exatamente 14 números (sem pontos ou barras) e não pode ser uma sequência de números iguais.
- **`Validade_CRECI`** — Ativa: validada na criação. Mensagem: Favor inserir a data de validade do CRECI.
- **`Verifica_CNPJ`** — Inativa: não aplicada. Mensagem: Por favor, insira um CNPJ válido. Formato: XX.XXX.XXX/XXXX-XX
- **`Verifica_CPF`** — Ativa: validada na criação. Mensagem: Por favor, insira um CPF válido. Formato: XXX.XXX.XXX-XX
- **`Verifica_UF`** — Ativa: validada na criação. Mensagem: Digite uma das opções: 'AC, AL, AM, AP, BA, CE, DF, ES, GO, MA, MG, MS, MT, PA, PB, PE, PI, PR, RJ, RN, RO, RR, RS, SC, SE, SP, TO', ambas as letras maiúsculas.

## Validação desta versão

- 66 testes automatizados aprovados.
- 213 campos confrontados novamente com a API real: nenhuma divergência nos tipos, limites, precisão, escala e permissões.
- Seis exemplos inválidos bloqueados pelo validador usando metadados reais: agência, e-mail, observações, primeiro nome, CRECI e multiplicador.
- Inicialização e renderização do Streamlit aprovadas em AppTest com Secrets em memória.
- Nenhum contato criado ou alterado durante esta auditoria; a validação completa do formulário no navegador de produção depende do deploy.
