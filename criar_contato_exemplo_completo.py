# -*- coding: utf-8 -*-
"""
Cria um contato de exemplo no Salesforce com TODOS os campos mapeados da planilha
(DATA DE PREECHIMENTO, IMPULSO, COORDENADOR, REGIONAL, EMAIL, TELEFONE, CPF, etc.).

Antes de rodar, defina no CMD: SALESFORCE_USER, SALESFORCE_PASSWORD, SALESFORCE_TOKEN.

Uso:
  python criar_contato_exemplo_completo.py
"""

import os
import sys

from salesforce_api import conectar_salesforce

BASE_URL_VIEW = "https://direcional.lightning.force.com/lightning/r/Contact"


def dados_exemplo_planilha():
    """
    Retorna um dict com todos os campos da planilha mapeados para os nomes de API do Contact.
    Valores de picklist (Regional__c, Status_Corretor__c) conforme salesforce_objetos_describe.json.
    """
    # Campos que não têm campo direto no Contact vão em Observacoes ou Description
    observacoes_extra = (
        "IMPULSO: Exemplo. "
        "RESPONSÁVEL PELO PROCESSO: Maria Silva. "
        "GERENTE DESIGNADO: (preencher com Id do usuário se necessário). "
        "DIA 1 a DIA 6: Concluído. "
        "TECNORISK: Sim. BV/SALES: Sim. "
        "CURSO TTI (IPA): Concluído. CRECI ESTÁGIO: Estagiário. "
        "DIRIACADEMY: Concluído."
    )

    dados = {
        # Padrão (obrigatórios / validação)
        "FirstName": "Contato",
        "LastName": "Exemplo Completo Planilha",
        "Email": "exemplo.completo.planilha@direcional.com.br",
        "Phone": "3133334444",
        "MobilePhone": "31999999999",
        "Description": "Criado com todos os campos da planilha (exemplo). " + observacoes_extra,
        # Mapeamento planilha -> API
        "Data_da_Entrevista__c": "2025-02-25",       # DATA DE PREECHIMENTO (formato YYYY-MM-DD)
        "Regional__c": "MG",                          # REGIONAL (valores do describe: AC, AL, AM, AP, BA, CE, DF, ES, GO, MA, MG, MS, MT, PA, PE, PI, PR, RJ, RN, RO, RR, RS, SC, SE, SP, TO)
        "CPF__c": "12345678900",                      # CPF
        "Dados_para_PIX__c": "12345678900",          # CHAVE PIX (APENAS CPF)
        "Contrato__c": "Exemplo de contrato. BV/SALES: Sim.",  # CONTRATO (+ BV/SALES em texto)
        "CRECI__c": 12345,                            # N° DO CRECI
        "Status_Corretor__c": "Ativo",                # STATUS (valores do describe: Ativo, Inativo, Pré credenciado, Reativado)
        "Observacoes__c": "COMENTÁRIOS E OBSERVAÇÕES: Contato exemplo com todos os dados da planilha preenchidos.",
    }
    return dados


def main():
    if not os.environ.get("SALESFORCE_USER") or not os.environ.get("SALESFORCE_PASSWORD"):
        print("❌ Defina SALESFORCE_USER e SALESFORCE_PASSWORD (e SALESFORCE_TOKEN) no CMD antes de rodar.")
        sys.exit(1)

    sf = conectar_salesforce()
    if not sf:
        sys.exit(1)

    dados = dados_exemplo_planilha()
    # Remover chaves com valor None ou vazio para não dar erro na API
    dados = {k: v for k, v in dados.items() if v is not None and (not isinstance(v, str) or v.strip())}

    print("Criando contato com todos os campos da planilha (exemplo)...")
    try:
        resultado = sf.Contact.create(dados)
        id_novo = resultado["id"]
        print(f"\n✅ Contato criado com sucesso! ID: {id_novo}")
        print(f"🔗 Abra no Salesforce: {BASE_URL_VIEW}/{id_novo}/view\n")
    except Exception as e:
        print(f"❌ Erro ao criar contacto: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
