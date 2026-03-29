# -*- coding: utf-8 -*-
"""
Lista todos os valores distintos de 'Nome da conta' (Account.Name) no Salesforce.

Uso:
  - Defina SALESFORCE_USER, SALESFORCE_PASSWORD e (opcional) SALESFORCE_TOKEN nas variáveis de ambiente.
  - Execute: python listar_nomes_conta.py

O script:
  - Conecta ao Salesforce usando salesforce_api.conectar_salesforce.
  - Consulta todas as contas em páginas.
  - Coleta os 'Name' em um conjunto (valores únicos).
  - Exibe o total e grava em um CSV (opcional).
"""

import csv
import os
from typing import Set

from salesforce_api import conectar_salesforce


def coletar_nomes_conta(sf) -> Set[str]:
    """Percorre todas as contas e devolve um set com todos os Account.Name distintos."""
    soql = "SELECT Id, Name FROM Account"
    nomes: Set[str] = set()

    print("Executando primeira página da consulta SOQL...")
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

    print("Coletando nomes distintos de Account.Name...")
    nomes = coletar_nomes_conta(sf)
    print(f"\nTotal de valores distintos de 'Nome da conta': {len(nomes)}")

    # Caminho padrão de saída (na mesma pasta do script)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    caminho_csv = os.path.join(base_dir, "account_names_unicos.csv")

    salvar_em_csv(nomes, caminho_csv)
    print(f"Nomes exportados para: {caminho_csv}")


if __name__ == "__main__":
    main()

