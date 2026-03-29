# -*- coding: utf-8 -*-
"""
Lista todos os valores distintos de 'Nome da conta' (Account.Name) no Salesforce
que contenham o padrão 'DIRECIONAL VENDAS RJ - EQUIPE ...'.

Uso:
  - Defina SALESFORCE_USER, SALESFORCE_PASSWORD e (opcional) SALESFORCE_TOKEN nas variáveis de ambiente.
  - Execute: python listar_nomes_conta_direcional_vendas_rj.py

O script:
  - Conecta ao Salesforce usando salesforce_api.conectar_salesforce.
  - Executa uma SOQL filtrada por Name LIKE 'DIRECIONAL VENDAS RJ - EQUIPE %',
    paginando com query_more caso haja muitas linhas.
  - Coleta os 'Name' em um conjunto (valores únicos).
  - Exibe o total e grava em um CSV (account_names_direcional_vendas_rj.csv).
"""

import csv
import os
from typing import Set

from salesforce_api import conectar_salesforce


PADRAO_NAME = "DIRECIONAL VENDAS RJ - EQUIPE %"


def coletar_nomes_conta_filtrados(sf) -> Set[str]:
    """Percorre as contas cujo Name bate com o padrão e devolve um set com os Names distintos."""
    soql = f"""
        SELECT Id, Name
        FROM Account
        WHERE Name LIKE '{PADRAO_NAME}'
    """
    nomes: Set[str] = set()

    print("Executando primeira página da consulta SOQL filtrada...")
    res = sf.query(soql)

    while True:
        registros = res.get("records", [])
        for acc in registros:
            nome = acc.get("Name")
            if nome:
                nomes.add(str(nome).strip())

        if res.get("done"):
            break

        next_url = res.get("nextRecordsUrl")
        if not next_url:
            break

        print(f"Carregando próxima página ({len(nomes)} nomes únicos coletados até agora)...")
        res = sf.query_more(next_url, True)

    return nomes


def salvar_em_csv(nomes: Set[str], caminho_csv: str) -> None:
    """Salva os nomes únicos em um CSV simples, uma linha por valor."""
    os.makedirs(os.path.dirname(caminho_csv), exist_ok=True)
    with open(caminho_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["AccountName"])
        for nome in sorted(nomes):
            writer.writerow([nome])


def main() -> None:
    sf = conectar_salesforce()
    if not sf:
        return

    print(f"Coletando nomes de contas com Name LIKE '{PADRAO_NAME}'...")
    nomes = coletar_nomes_conta_filtrados(sf)
    print(f"\nTotal de valores distintos de 'Nome da conta' com esse padrão: {len(nomes)}")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    caminho_csv = os.path.join(base_dir, "account_names_direcional_vendas_rj.csv")

    salvar_em_csv(nomes, caminho_csv)
    print(f"Nomes exportados para: {caminho_csv}")


if __name__ == "__main__":
    main()

