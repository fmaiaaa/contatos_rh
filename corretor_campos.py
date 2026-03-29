# -*- coding: utf-8 -*-
"""
Layout "Novo Contato: Corretor" — mesma ordem de seções e campos do Salesforce (Lightning).
Mapeamento para API + planilha Google.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

RECORD_TYPE_CORRETOR = "012f1000000n6nN"

# Ordem das seções no Salesforce (não alterar sem checar o layout no org)
SEC_ORDER: Tuple[str, ...] = (
    "Informações para contato",
    "Dados Pessoais",
    "Dados de Usuário",
    "Dados para Contato",
    "Dados Familiares",
    "Dados Bancários Pessoa Física",
    "CRECI/TTI",
    "Contrato e dados PJ",
    "Histórico Equipe",
    "Datas",
    "Dados Integração",
    "Anexos",
    "Preferred Contact Method",
)

SF_OMIT_INSERT = frozenset(
    {
        "Blacklist__c",
        "RetornoIntegracaoContaBancaria__c",
        "C_digo_Pessoa_UAU__c",
        "Corretor_Associado__c",
        "MultiplicadorFinal__c",
        "Contact_ID__c",
        "ErroIntegracaoUAU__c",
        "RetornoIntegracaoPessoa__c",
        "Data_Descredenciamento__c",
    }
)

REGIONAIS = [
    "--Nenhum--",
    "AC",
    "AL",
    "AM",
    "AP",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MG",
    "MS",
    "MT",
    "PA",
    "PE",
    "PI",
    "PR",
    "RJ",
    "RN",
    "RO",
    "RR",
    "RS",
    "SC",
    "SE",
    "SP",
    "TO",
]

ORIGENS = [
    "--Nenhum--",
    "RH",
    "Indicação",
    "Gerente",
    "Diretor",
    "DiRi Talent",
    "Coordenador",
    "Gupy",
    "MARINHA",
    "Creci",
    "Parceria Estácio",
]

STATUS_CORRETOR = ["--Nenhum--", "Ativo", "Inativo", "Pré credenciado", "Reativado"]

SALUTATIONS = ["--Nenhum--", "Sr.", "Sra.", "Dr.", "Dra."]

SEXOS = ["--Nenhum--", "Masculino", "Feminino"]

CAMISETAS = ["--Nenhum--", "PP", "P", "M", "G", "GG", "XGG"]

UNIDADES_NEGOCIO = ["--Nenhum--", "Direcional", "Parceiros (Externo)"]

TIPO_PIX = ["--Nenhum--", "CPF", "CNPJ", "E-mail", "Telefone", "Chave aleatória"]

ESTADOS_UF = [
    "--Nenhum--",
    "AC",
    "AL",
    "AM",
    "AP",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MG",
    "MS",
    "MT",
    "PA",
    "PE",
    "PI",
    "PR",
    "RJ",
    "RN",
    "RO",
    "RR",
    "RS",
    "SC",
    "SE",
    "SP",
    "TO",
]

POSSUI_FILHOS = ["--Nenhum--", "Sim", "Não"]

TIPO_CONTA_BANCARIA = ["--Nenhum--", "Corrente", "Poupança"]

# Picklists Contact (fonte: salesforce_objetos_describe.json — alinhar ao org ao atualizar o describe)
_ESTADO_CIVIL = ["Solteiro", "Casado", "Divorciado", "Viúvo"]
_ESCOLARIDADE = [
    "Ensino Fundamental",
    "Ensino Médio",
    "Superior em Andamento",
    "Superior Completo",
    "Mestrado em Andamento",
    "Mestrado Concluído",
    "Doutorado em Andamento",
    "Doutorado Concluído",
]
_NACIONALIDADE = ["Brasileiro", "Estrangeira", "Espanhola"]
_ATIVIDADE = [
    "Captador",
    "Estagiário",
    "Corretor",
    "Coordenador",
    "Gerente de Vendas",
    "Gerente Regional",
    "Diretor",
    "Gerente",
    "Captador Recruta+",
    "Gerente Recruta+",
    "Corretor N1",
    "Gerente de Vendas N1",
    "Diretor de Vendas",
    "Analista",
    "Assistente",
    "Cliente",
    "Coordenador de Produto",
    "Coordenador de Vendas",
    "Diretor de Incorporação",
    "Gerente Comercial",
    "Gerente de Parcerias",
    "Imobiliária Parceira",
    "Pasteiro (a)",
    "Superintendente",
    "Supervisor",
    "Autônomo Parceiro",
    "Corretor Parceiro",
    "Recepção",
    "Coordenador de Parcerias",
]
_TIPO_CORRETOR = [
    "Direcional Vendas – GRI (CLT)",
    "Direcional Vendas – Autônomos",
    "Parceiros (Externo)",
]
_STATUS_CRECI = [
    "Concluído Provas",
    "Definitivo",
    "Estágio",
    "Matriculado",
    "Pendente",
    "Protocolo Definitivo",
    "Protocolo Estágio",
    "Pendente Prova",
]
_MOTIVO_INATIVIDADE = [
    "Solicitação do Corretor",
    "Solicitação do Gerente de Vendas",
    "Solicitação do Gerente Regional",
    "Solicitação do Diretor",
]
_MOTIVO_DESCREDENCIAMENTO = [
    "Falta de recurso financeiro",
    "Oportunidade CLT",
    "Distância",
    "Relacionamento com o Gestor",
    "Baixa performance",
    "Abandono",
    "Desistente da Incubadora",
    "Mudança de Cidade / Estado",
    "Problemas de Saúde",
    "Concorrência",
    "Comportamento Inadequado",
    "Promoção Interna",
    "Corretor Parceiro",
]
_TIPO_DESLIGAMENTO = ["Ativo", "Passivo"]
_FORNECEDOR_UAU = ["Não", "Sim"]
_BANCO = [
    "001 – Banco do Brasil S.A.",
    "004 - BANCO DO NORDESTE DO BRASIL S.A.",
    "033 – Banco Santander (Brasil) S.A.",
    "070 - BCO BRB SA - BRASILIA",
    "104 – Caixa Econômica Federal",
    "121 - Banco Agiplan",
    "197 – Stone Pagamentos S.A.",
    "208 – Banco BTG Pactual",
    "212 - Banco Original S.A.",
    "218 – Banco Bonsucesso SA",
    "237 – Banco Bradesco S.A.",
    "246 - Banco ABC Brasil S.A.",
    "260 – Banco Nubank",
    "290 – PagSeguro Internt SA",
    "318 - BCO BMG COMERCIAL S.A",
    "323 – Mercado Pago",
    "336 - BANCO C6 S.A.",
    "340 – Super digital",
    "341 – Banco Itaú S.A.",
    "356 – Banco Real S.A. (antigo)",
    "364 - Gerencianet",
    "380 – PicPay",
    "389 – Banco Mercantil do Brasil S.A.",
    "399 – HSBC Bank Brasil S.A. – Banco Múltiplo",
    "403 – CORA SOCIEDADE DE CR",
    "413 – BV",
    "422 – Banco Safra S.A.",
    "453 – Banco Rural S.A.",
    "473 - Banco Caixa Geral - Brasil S.A.",
    "623 – Banco Panamericano S.A",
    "633 – Banco Rendimento S.A.",
    "637 - Bco Sofisa SA.",
    "652 – Itaú Unibanco Holding S.A.",
    "655 – Banco Votorantim S.A.",
    "735 - BANCO POTTENCIAL S.A.",
    "745 – Banco Citibank S.A.",
    "746 - BCO MODAL SA.",
    "748 – BCO COOP. SICREDI SA",
    "756 – Banco SICCOB S.A",
    "77 - BCO INTERMEDIUM SA",
    "79 - Banco Original Agro",
    "92 - BANCO BRK",
    "348 - BANCO XP S.A",
    "679 - CloudWalk Instituição de Pagamento",
    "536 – NEON PAGAMENTOS",
    "335 -  Banco Digio S.A.",
]

ESTADO_CIVIL_OPTS = ["--Nenhum--"] + _ESTADO_CIVIL
ESCOLARIDADE_OPTS = ["--Nenhum--"] + _ESCOLARIDADE
NACIONALIDADE_OPTS = ["--Nenhum--"] + _NACIONALIDADE
ATIVIDADE_OPTS = ["--Nenhum--"] + _ATIVIDADE
TIPO_CORRETOR_OPTS = ["--Nenhum--"] + _TIPO_CORRETOR
STATUS_CRECI_OPTS = ["--Nenhum--"] + _STATUS_CRECI
MOTIVO_INATIVIDADE_OPTS = ["--Nenhum--"] + _MOTIVO_INATIVIDADE
MOTIVO_DESCREDENCIAMENTO_OPTS = ["--Nenhum--"] + _MOTIVO_DESCREDENCIAMENTO
TIPO_DESLIGAMENTO_OPTS = ["--Nenhum--"] + _TIPO_DESLIGAMENTO
FORNECEDOR_UAU_OPTS = ["--Nenhum--"] + _FORNECEDOR_UAU
BANCO_OPTS = ["--Nenhum--"] + _BANCO

PREFERRED_METHOD_OPTS = [
    "Work phone",
    "Home phone",
    "Mobile phone",
    "Work Email",
    "Personal Email",
    "No preference",
    "***",
    "Telefone de Trabalho",
    "Telefone residencial",
    "Celular",
    "Email de trabalho",
    "Email pessoal",
    "Sem preferência",
]

Campo = Dict[str, Any]


def _z(**kw) -> Campo:
    return kw


def _campos_def() -> List[Campo]:
    """
    Ordem idêntica ao formulário Salesforce (Novo Contato: Corretor).
    * = obrigatório no layout (req=True), salvo quando combinado com outro campo.
    """
    return [
        # ——— Informações para contato ———
        _z(
            key="account_name",
            label="Nome da conta *",
            sec="Informações para contato",
            tipo="text",
            sf=None,
            req=False,
            help="Pesquisar Contas — nome exibido na planilha; use Id abaixo para vincular na API.",
        ),
        _z(
            key="account_id",
            label="Nome da conta — Id (Account)",
            sec="Informações para contato",
            tipo="id",
            sf="AccountId",
            req=False,
            help="Id Salesforce da conta (18 caracteres).",
        ),
        _z(
            key="owner_id",
            label="Proprietário do contato",
            sec="Informações para contato",
            tipo="id",
            sf="OwnerId",
            req=False,
            help="Id do usuário proprietário (opcional).",
        ),
        _z(
            key="nome_completo",
            label="Nome completo *",
            sec="Informações para contato",
            tipo="text",
            sf=None,
            req=False,
            help="Se preencher, pode substituir Primeiro nome + Sobrenome (primeira palavra = nome).",
        ),
        _z(
            key="salutation",
            label="Tratamento",
            sec="Informações para contato",
            tipo="select",
            sf="Salutation",
            opcoes=SALUTATIONS,
            req=False,
        ),
        _z(
            key="first_name",
            label="Primeiro Nome",
            sec="Informações para contato",
            tipo="text",
            sf="FirstName",
            req=False,
        ),
        _z(
            key="last_name",
            label="Sobrenome *",
            sec="Informações para contato",
            tipo="text",
            sf="LastName",
            req=False,
        ),
        _z(
            key="apelido",
            label="Apelido *",
            sec="Informações para contato",
            tipo="text",
            sf="Apelido__c",
            req=True,
        ),
        _z(
            key="status_corretor",
            label="Status Corretor *",
            sec="Informações para contato",
            tipo="select",
            sf="Status_Corretor__c",
            opcoes=STATUS_CORRETOR,
            req=True,
        ),
        _z(
            key="regional",
            label="Regional *",
            sec="Informações para contato",
            tipo="select",
            sf="Regional__c",
            opcoes=REGIONAIS,
            req=True,
        ),
        _z(
            key="origem",
            label="Origem *",
            sec="Informações para contato",
            tipo="select",
            sf="Origem__c",
            opcoes=ORIGENS,
            req=True,
        ),
        _z(
            key="sexo",
            label="Sexo *",
            sec="Informações para contato",
            tipo="select",
            sf="Sexo__c",
            opcoes=SEXOS,
            req=True,
        ),
        _z(
            key="indicado_por_id",
            label="Indicado por",
            sec="Informações para contato",
            tipo="id",
            sf="Indicado_por__c",
            req=False,
            help="Pesquisar Pessoas — Id User (18 caracteres).",
        ),
        _z(
            key="camiseta",
            label="Camiseta *",
            sec="Informações para contato",
            tipo="select",
            sf="Camiseta__c",
            opcoes=CAMISETAS,
            req=True,
        ),
        _z(
            key="atividade",
            label="Atividade *",
            sec="Informações para contato",
            tipo="select",
            sf="Atividade__c",
            opcoes=ATIVIDADE_OPTS,
            req=True,
        ),
        _z(
            key="escolaridade",
            label="Escolaridade",
            sec="Informações para contato",
            tipo="select",
            sf="Escolaridade__c",
            opcoes=ESCOLARIDADE_OPTS,
            req=False,
        ),
        _z(
            key="data_entrevista",
            label="Data da Entrevista *",
            sec="Informações para contato",
            tipo="date",
            sf="Data_da_Entrevista__c",
            req=True,
            help="Formato: 31/12/2024",
        ),
        _z(
            key="unidade_negocio",
            label="Unidade Negócio",
            sec="Informações para contato",
            tipo="select",
            sf="Unidade_Negocio__c",
            opcoes=UNIDADES_NEGOCIO,
            req=False,
        ),
        _z(
            key="data_transferencia_parceiro",
            label="Data Transferência Corretor Parceiro",
            sec="Informações para contato",
            tipo="date",
            sf="Data_Transferencia_Corretor_Parceiro__c",
            req=False,
            help="Formato: 31/12/2024",
        ),
        # ——— Dados Pessoais ———
        _z(
            key="birthdate",
            label="Data de nascimento *",
            sec="Dados Pessoais",
            tipo="date",
            sf="Birthdate",
            req=True,
            help="Formato: 31/12/2024",
        ),
        _z(
            key="estado_civil",
            label="Estado Civil *",
            sec="Dados Pessoais",
            tipo="select",
            sf="EstadoCivil__c",
            opcoes=ESTADO_CIVIL_OPTS,
            req=True,
        ),
        _z(key="cpf", label="CPF *", sec="Dados Pessoais", tipo="text", sf="CPF__c", req=True),
        _z(key="pis", label="PIS", sec="Dados Pessoais", tipo="text", sf="PIS__c", req=False),
        _z(
            key="nacionalidade",
            label="Nacionalidade *",
            sec="Dados Pessoais",
            tipo="select",
            sf="Nacionalidade__c",
            opcoes=NACIONALIDADE_OPTS,
            req=True,
        ),
        _z(
            key="naturalidade",
            label="Naturalidade *",
            sec="Dados Pessoais",
            tipo="text",
            sf="Naturalidade__c",
            req=True,
        ),
        _z(key="rg", label="RG *", sec="Dados Pessoais", tipo="text", sf="RG__c", req=True),
        _z(
            key="uf_naturalidade",
            label="UF Naturalidade *",
            sec="Dados Pessoais",
            tipo="select",
            sf="UF_Naturalidade__c",
            opcoes=ESTADOS_UF,
            req=True,
        ),
        _z(
            key="uf_rg",
            label="UF RG *",
            sec="Dados Pessoais",
            tipo="select",
            sf="UF_RG__c",
            opcoes=ESTADOS_UF,
            req=True,
        ),
        _z(
            key="tipo_pix",
            label="Tipo do PIX *",
            sec="Dados Pessoais",
            tipo="select",
            sf="Tipo_do_PIX__c",
            opcoes=TIPO_PIX,
            req=True,
        ),
        _z(
            key="dados_pix",
            label="Dados para PIX *",
            sec="Dados Pessoais",
            tipo="text",
            sf="Dados_para_PIX__c",
            req=True,
        ),
        # ——— Dados de Usuário ———
        _z(
            key="multiplicador_nivel",
            label="Multiplicador de Nível",
            sec="Dados de Usuário",
            tipo="number",
            sf="Multiplicador__c",
            req=False,
        ),
        _z(
            key="usuario_uau",
            label="Usuário UAU",
            sec="Dados de Usuário",
            tipo="text",
            sf="Usu_rio_UAU__c",
            req=False,
        ),
        _z(
            key="multiplicador_regime",
            label="Multiplicador de Regime",
            sec="Dados de Usuário",
            tipo="number",
            sf="Multiplicador_de_Regime__c",
            req=False,
        ),
        # ——— Dados para Contato ———
        _z(key="phone", label="Telefone", sec="Dados para Contato", tipo="text", sf="Phone", req=False),
        _z(
            key="email_direcional",
            label="E-mail Direcional",
            sec="Dados para Contato",
            tipo="text",
            sf="E_mail_Direcional__c",
            req=False,
        ),
        _z(key="mobile", label="Celular", sec="Dados para Contato", tipo="text", sf="MobilePhone", req=False),
        _z(key="email", label="E-mail *", sec="Dados para Contato", tipo="text", sf="Email", req=True),
        _z(
            key="celular_2",
            label="Celular 2",
            sec="Dados para Contato",
            tipo="text",
            sf="Celular_2__c",
            req=False,
        ),
        _z(
            key="other_phone",
            label="Outro telefone",
            sec="Dados para Contato",
            tipo="text",
            sf="OtherPhone",
            req=False,
        ),
        # ——— Dados Familiares ———
        _z(
            key="nome_pai",
            label="Nome do Pai *",
            sec="Dados Familiares",
            tipo="text",
            sf="Nome_do_Pai__c",
            req=True,
        ),
        _z(
            key="possui_filhos",
            label="Possui Filho(s)?",
            sec="Dados Familiares",
            tipo="select",
            sf="Possui_Filho__c",
            opcoes=POSSUI_FILHOS,
            req=False,
        ),
        _z(
            key="nome_mae",
            label="Nome da Mãe *",
            sec="Dados Familiares",
            tipo="text",
            sf="Nome_da_Mae__c",
            req=True,
        ),
        _z(
            key="qtd_filhos",
            label="Quantidade de Filhos",
            sec="Dados Familiares",
            tipo="number",
            sf="Quantidade_de_Filhos__c",
            req=False,
        ),
        _z(
            key="nome_conjuge",
            label="Nome do Cônjuge",
            sec="Dados Familiares",
            tipo="text",
            sf="Nome_do_Conjuge__c",
            req=False,
        ),
        # ——— Dados Bancários Pessoa Física ———
        _z(
            key="banco",
            label="Banco *",
            sec="Dados Bancários Pessoa Física",
            tipo="select",
            sf="Banco__c",
            opcoes=BANCO_OPTS,
            req=True,
        ),
        _z(
            key="conta_bancaria",
            label="Conta Bancária *",
            sec="Dados Bancários Pessoa Física",
            tipo="text",
            sf="Conta_Banc_ria__c",
            req=True,
        ),
        _z(
            key="agencia_bancaria",
            label="Agência Bancária *",
            sec="Dados Bancários Pessoa Física",
            tipo="text",
            sf="Ag_ncia_Banc_ria__c",
            req=True,
        ),
        _z(
            key="retorno_integracao_bancaria",
            label="Retorno integração conta bancária",
            sec="Dados Bancários Pessoa Física",
            tipo="textarea",
            sf="RetornoIntegracaoContaBancaria__c",
            req=False,
            help="Somente leitura no Salesforce — uso informativo na planilha.",
        ),
        _z(
            key="tipo_conta",
            label="Tipo de Conta",
            sec="Dados Bancários Pessoa Física",
            tipo="select",
            sf="Tipo_de_Conta__c",
            opcoes=TIPO_CONTA_BANCARIA,
            req=False,
        ),
        # ——— CRECI/TTI ———
        _z(
            key="data_matricula_tti",
            label="Data Matrícula - TTI",
            sec="CRECI/TTI",
            tipo="date",
            sf="Data_Matricula_TTI__c",
            req=False,
            help="Formato: 31/12/2024",
        ),
        _z(key="tti", label="TTI", sec="CRECI/TTI", tipo="text", sf="TTI__c", req=False),
        _z(
            key="status_creci",
            label="Status CRECI",
            sec="CRECI/TTI",
            tipo="select",
            sf="Status_CRECI__c",
            opcoes=STATUS_CRECI_OPTS,
            req=False,
        ),
        _z(
            key="data_conclusao",
            label="Data de conclusão",
            sec="CRECI/TTI",
            tipo="date",
            sf="Data_de_conclusao__c",
            req=False,
            help="Formato: 31/12/2024",
        ),
        _z(key="creci", label="CRECI", sec="CRECI/TTI", tipo="text", sf="CRECI__c", req=False),
        _z(
            key="observacoes_creci",
            label="Observações",
            sec="CRECI/TTI",
            tipo="textarea",
            sf="Observacoes__c",
            req=False,
        ),
        _z(
            key="validade_creci",
            label="Validade CRECI",
            sec="CRECI/TTI",
            tipo="date",
            sf="Validade_CRECI__c",
            req=False,
            help="Formato: 31/12/2024",
        ),
        _z(
            key="nome_responsavel",
            label="Nome do Responsável",
            sec="CRECI/TTI",
            tipo="text",
            sf="Nome_do_Responsavel__c",
            req=False,
        ),
        _z(
            key="creci_responsavel",
            label="CRECI do Responsável",
            sec="CRECI/TTI",
            tipo="number",
            sf="CRECI_do_Responsavel__c",
            req=False,
        ),
        _z(
            key="tipo_comissionamento",
            label="Tipo de Comissionamento",
            sec="CRECI/TTI",
            tipo="text",
            sf=None,
            req=False,
        ),
        # ——— Contrato e dados PJ (continuação do layout após CRECI) ———
        _z(
            key="tipo_corretor",
            label="Tipo Corretor *",
            sec="Contrato e dados PJ",
            tipo="select",
            sf="Tipo_Corretor__c",
            opcoes=TIPO_CORRETOR_OPTS,
            req=True,
        ),
        _z(
            key="faturamento_comissao",
            label="Faturamento Comissão",
            sec="Contrato e dados PJ",
            tipo="text",
            sf=None,
            req=False,
            help="Gravado na planilha; no SF pode ser somente leitura.",
        ),
        _z(
            key="faturamento_comissao_2",
            label="Faturamento Comissão (2)",
            sec="Contrato e dados PJ",
            tipo="text",
            sf=None,
            req=False,
        ),
        _z(key="cnpj", label="CNPJ", sec="Contrato e dados PJ", tipo="text", sf="CNPJ__c", req=False),
        _z(
            key="razao_social",
            label="Razão Social",
            sec="Contrato e dados PJ",
            tipo="text",
            sf="Razao_Social__c",
            req=False,
        ),
        _z(
            key="fornecedor_uau",
            label="Cadastrado como Fornecedor no UAU?",
            sec="Contrato e dados PJ",
            tipo="select",
            sf="Cadastrado_como_Fornecedor_no_UAU__c",
            opcoes=FORNECEDOR_UAU_OPTS,
            req=False,
        ),
        _z(
            key="contrato_texto",
            label="Contrato",
            sec="Contrato e dados PJ",
            tipo="textarea",
            sf="Contrato__c",
            req=False,
        ),
        _z(
            key="data_contrato",
            label="Data Contrato *",
            sec="Contrato e dados PJ",
            tipo="date",
            sf="Data_Contrato__c",
            req=True,
            help="Formato: 31/12/2024",
        ),
        _z(
            key="data_credenciamento",
            label="Data Credenciamento *",
            sec="Contrato e dados PJ",
            tipo="date",
            sf="Data_Credenciamento__c",
            req=True,
            help="Formato: 31/12/2024",
        ),
        _z(
            key="contrato_observacao",
            label="Contrato (observação / referência)",
            sec="Contrato e dados PJ",
            tipo="textarea",
            sf=None,
            req=False,
            help="Segundo bloco Contrato do layout Salesforce (texto livre).",
        ),
        # ——— Histórico Equipe ———
        _z(
            key="historico_equipe",
            label="Histórico Equipe",
            sec="Histórico Equipe",
            tipo="textarea",
            sf=None,
            req=False,
        ),
        _z(
            key="produto_atuacao_id",
            label="Produto de Atuação",
            sec="Histórico Equipe",
            tipo="id",
            sf="Produto_de_Atuacao__c",
            req=False,
            help="Pesquisar Empreendimentos — Id do empreendimento.",
        ),
        _z(
            key="nao_recomendado_motivo",
            label="Não recomendado - Motivo",
            sec="Histórico Equipe",
            tipo="textarea",
            sf=None,
            req=False,
        ),
        _z(
            key="gerente_anterior_id",
            label="Gerente anterior",
            sec="Histórico Equipe",
            tipo="id",
            sf="GerenteAnterior__c",
            req=False,
            help="Pesquisar Pessoas — Id User.",
        ),
        _z(
            key="motivo_inatividade",
            label="Motivo Inatividade",
            sec="Histórico Equipe",
            tipo="select",
            sf="Motivo_Inatividade__c",
            opcoes=MOTIVO_INATIVIDADE_OPTS,
            req=False,
        ),
        _z(
            key="solicitante_descredenciamento_id",
            label="Solicitante Descredenciamento",
            sec="Histórico Equipe",
            tipo="id",
            sf="Solicitantedescredenciamento__c",
            req=False,
            help="Pesquisar Pessoas — Id User.",
        ),
        _z(
            key="tipo_desligamento",
            label="Tipo de desligamento",
            sec="Histórico Equipe",
            tipo="select",
            sf="Tipo_de_desligamento__c",
            opcoes=TIPO_DESLIGAMENTO_OPTS,
            req=False,
        ),
        _z(
            key="motivo_descredenciamento",
            label="Motivo Descredenciamento",
            sec="Histórico Equipe",
            tipo="select",
            sf="Motivo_Descredenciamento__c",
            opcoes=MOTIVO_DESCREDENCIAMENTO_OPTS,
            req=False,
        ),
        _z(
            key="blacklist_flag",
            label="Blacklist",
            sec="Histórico Equipe",
            tipo="text",
            sf=None,
            req=False,
            help="Notas — campo Blacklist no SF é controlado pelo sistema.",
        ),
        _z(
            key="falso_blacklist",
            label="FalsoBlacklist",
            sec="Histórico Equipe",
            tipo="text",
            sf=None,
            req=False,
        ),
        # ——— Datas ———
        _z(
            key="data_descredenciamento",
            label="Data Descredenciamento",
            sec="Datas",
            tipo="date",
            sf="Data_Descredenciamento__c",
            req=False,
            help="Formato: 31/12/2024",
        ),
        _z(
            key="data_saida",
            label="Data de Saída",
            sec="Datas",
            tipo="date",
            sf="Data_de_Saida__c",
            req=False,
            help="Formato: 31/12/2024",
        ),
        _z(
            key="data_transferencia",
            label="Data de Transferência",
            sec="Datas",
            tipo="date",
            sf="Data_de_Transferencia__c",
            req=False,
            help="Formato: 31/12/2024",
        ),
        _z(
            key="data_reativacao",
            label="Data Reativação",
            sec="Datas",
            tipo="date",
            sf="Data_Reativacao__c",
            req=False,
            help="Formato: 31/12/2024",
        ),
        _z(
            key="data_entrada_recruita",
            label="Data Entrada Recruta+",
            sec="Datas",
            tipo="date",
            sf="Data_Entrada_Recruta__c",
            req=False,
            help="Formato: 31/12/2024",
        ),
        _z(
            key="data_saida_recruita",
            label="Data Saída Recruta+",
            sec="Datas",
            tipo="date",
            sf="Data_Sai_da_Recruta__c",
            req=False,
            help="Formato: 31/12/2024",
        ),
        # ——— Dados Integração ———
        _z(
            key="codigo_pessoa_uau",
            label="Código Pessoa UAU",
            sec="Dados Integração",
            tipo="text",
            sf="C_digo_Pessoa_UAU__c",
            req=False,
        ),
        _z(
            key="erro_integracao_uau",
            label="Erro Integração UAU",
            sec="Dados Integração",
            tipo="textarea",
            sf="ErroIntegracaoUAU__c",
            req=False,
        ),
        _z(
            key="retorno_integracao_pessoa",
            label="Retorno Integração Pessoa",
            sec="Dados Integração",
            tipo="textarea",
            sf="RetornoIntegracaoPessoa__c",
            req=False,
        ),
        # ——— Anexos ———
        _z(key="anexos", label="Anexos", sec="Anexos", tipo="textarea", sf=None, req=False),
        # ——— Preferred Contact Method ———
        _z(
            key="preferred_contact_method",
            label="Preferred Contact Method",
            sec="Preferred Contact Method",
            tipo="multiselect",
            sf="Preferred_Contact_Method__c",
            opcoes=PREFERRED_METHOD_OPTS,
            req=False,
        ),
    ]


CAMPOS: List[Campo] = _campos_def()

_ID_RE = re.compile(r"^[a-zA-Z0-9]{15}(?:[a-zA-Z0-9]{3})?$")


def _norm_picklist(val: Any) -> str:
    """Remove marcador '--Nenhum--' como vazio."""
    s = (str(val).strip() if val is not None else "") or ""
    if s in ("--Nenhum--", "Nenhum"):
        return ""
    return s


def parse_data_br(val: Any) -> Optional[str]:
    if val is None or (isinstance(val, float) and str(val) == "nan"):
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, datetime):
        return val.date().isoformat()
    s = str(val).strip()
    if not s:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _limpa_id(sf_field: str, val: Any) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    if sf_field in ("AccountId", "OwnerId", "Indicado_por__c", "GerenteAnterior__c", "Solicitantedescredenciamento__c"):
        if _ID_RE.match(s):
            return s
    if sf_field == "Produto_de_Atuacao__c" and _ID_RE.match(s):
        return s
    return None


def validar_obrigatorios(dados: Dict[str, Any]) -> List[str]:
    erros: List[str] = []
    for c in CAMPOS:
        if not c.get("req"):
            continue
        k = c["key"]
        v = dados.get(k)
        if c["tipo"] == "multiselect":
            if not v or (isinstance(v, list) and len(v) == 0):
                erros.append(c["label"])
            continue
        if c["tipo"] == "select":
            if not _norm_picklist(v):
                erros.append(c["label"])
            continue
        if v is None or (isinstance(v, str) and not str(v).strip()):
            erros.append(c["label"])
    aid = (dados.get("account_id") or "").strip()
    aname = (dados.get("account_name") or "").strip()
    if not aid and not aname:
        erros.append("Nome da conta *")
    nc = (dados.get("nome_completo") or "").strip()
    fn = (dados.get("first_name") or "").strip()
    ln = (dados.get("last_name") or "").strip()
    if not nc:
        if not ln:
            erros.append("Sobrenome * (ou Nome completo *)")
        if not fn:
            erros.append("Primeiro Nome (ou Nome completo *)")
    return list(dict.fromkeys(erros))


def validar_obrigatorios_secao(sec: str, dados: Dict[str, Any]) -> List[str]:
    """
    Valida apenas campos obrigatórios da seção atual (para bloquear «Avançar» no formulário por etapas).
    Replica a lógica de `validar_obrigatorios` para `c['sec'] == sec` e, na seção
    «Informações para contato», as regras de conta + nome/sobrenome.
    """
    erros: List[str] = []
    for c in CAMPOS:
        if c["sec"] != sec or not c.get("req"):
            continue
        k = c["key"]
        v = dados.get(k)
        if c["tipo"] == "multiselect":
            if not v or (isinstance(v, list) and len(v) == 0):
                erros.append(c["label"])
            continue
        if c["tipo"] == "select":
            if not _norm_picklist(v):
                erros.append(c["label"])
            continue
        if v is None or (isinstance(v, str) and not str(v).strip()):
            erros.append(c["label"])
    if sec == "Informações para contato":
        aid = (dados.get("account_id") or "").strip()
        aname = (dados.get("account_name") or "").strip()
        if not aid and not aname:
            erros.append("Nome da conta *")
        nc = (dados.get("nome_completo") or "").strip()
        fn = (dados.get("first_name") or "").strip()
        ln = (dados.get("last_name") or "").strip()
        if not nc:
            if not ln:
                erros.append("Sobrenome * (ou Nome completo *)")
            if not fn:
                erros.append("Primeiro Nome (ou Nome completo *)")
    return list(dict.fromkeys(erros))


def _aplicar_nome_completo(payload: Dict[str, Any], dados: Dict[str, Any]) -> None:
    nc = (dados.get("nome_completo") or "").strip()
    if not nc:
        return
    fn = (payload.get("FirstName") or "").strip()
    ln = (payload.get("LastName") or "").strip()
    if fn or ln:
        return
    partes = nc.split(None, 1)
    payload["FirstName"] = partes[0]
    payload["LastName"] = partes[1] if len(partes) > 1 else partes[0]


def montar_payload_salesforce(dados: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    payload: Dict[str, Any] = {"RecordTypeId": RECORD_TYPE_CORRETOR}
    avisos: List[str] = []
    extras_obs: List[str] = []

    for c in CAMPOS:
        key = c["key"]
        sf = c.get("sf")
        raw = dados.get(key)

        if key == "nome_completo":
            continue

        if sf is None:
            if raw and str(raw).strip() and key not in ("nome_completo",):
                extras_obs.append(f"{c['label']}: {raw}")
            continue

        if sf in SF_OMIT_INSERT:
            if raw and str(raw).strip():
                extras_obs.append(f"{c['label']}: {raw}")
            continue

        tipo = c["tipo"]

        if tipo == "date":
            iso = parse_data_br(raw)
            if iso:
                payload[sf] = iso
            continue

        if tipo == "id":
            lid = _limpa_id(sf, raw)
            if lid:
                payload[sf] = lid
            elif raw and str(raw).strip():
                avisos.append(f"{c['label']}: valor não parece Id Salesforce — omitido.")
            continue

        if tipo == "number":
            if raw is None or raw == "":
                continue
            try:
                payload[sf] = float(str(raw).replace(",", "."))
            except ValueError:
                avisos.append(f"{c['label']}: número inválido — omitido.")
            continue

        if tipo == "multiselect":
            if isinstance(raw, list) and raw:
                payload[sf] = ";".join(raw)
            continue

        if tipo == "textarea":
            s = (str(raw).strip() if raw is not None else "") or ""
            if s:
                if sf == "Observacoes__c":
                    extras_obs.insert(0, s)
                else:
                    payload[sf] = s
            continue

        if tipo == "select":
            s = _norm_picklist(raw)
            if s:
                payload[sf] = s
            continue

        s = (str(raw).strip() if raw is not None else "") or ""
        if not s:
            continue
        payload[sf] = s

    _aplicar_nome_completo(payload, dados)

    acc = dados.get("account_id")
    acc_txt = dados.get("account_name")
    if (not acc or not str(acc).strip()) and acc_txt and str(acc_txt).strip():
        extras_obs.append(f"Nome da conta (referência): {acc_txt}")

    obs_final = (payload.get("Observacoes__c") or "").strip()
    extra_block = "\n".join(extras_obs)
    if extra_block:
        payload["Observacoes__c"] = (obs_final + "\n" + extra_block).strip() if obs_final else extra_block

    payload = {k: v for k, v in payload.items() if v is not None and v != ""}

    return payload, avisos


def _agora_envio_brasilia() -> tuple[str, str]:
    """Data/hora legível em Brasília e ISO (mesmo instante)."""
    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("America/Sao_Paulo")
        now = datetime.now(tz)
        return now.strftime("%d/%m/%Y %H:%M:%S"), now.isoformat(timespec="seconds")
    except Exception:
        now = datetime.now(timezone.utc)
        return now.strftime("%d/%m/%Y %H:%M:%S"), now.isoformat(timespec="seconds")


def linha_planilha(dados: Dict[str, Any]) -> List[str]:
    data_hora_br, iso = _agora_envio_brasilia()
    row: List[str] = []
    for c in CAMPOS:
        k = c["key"]
        v = dados.get(k)
        if c["tipo"] == "multiselect" and isinstance(v, list):
            row.append("; ".join(v))
        elif v is None:
            row.append("")
        else:
            row.append(str(v))
    row.append(data_hora_br)
    row.append(iso)
    row.append("")  # Envio? — preenchido após tentativa Salesforce
    row.append("")  # Log / erro
    row.append("")  # Link do contato
    return row


def cabecalho_planilha() -> List[str]:
    return [c["label"] for c in CAMPOS] + [
        "Data e hora do envio",
        "Carimbo ISO",
        "Envio?",
        "Log / erro",
        "Link do contato",
    ]


def secoes_ordenadas() -> List[str]:
    presentes = {c["sec"] for c in CAMPOS}
    return [s for s in SEC_ORDER if s in presentes]


def campos_por_secao(sec: str) -> List[Campo]:
    return [c for c in CAMPOS if c["sec"] == sec]
