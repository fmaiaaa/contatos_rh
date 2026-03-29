# -*- coding: utf-8 -*-
"""
Lista oportunidades (OPs) no RJ, Direcional, que viraram venda (ganhas no Salesforce).

Critérios típicos:
  - IsWon = true, IsClosed = true
  - Regional__c = 'RJ' (ajuste se o org usar outro campo)
  - Opcional: filtro por nome de conta (padrão DIRECIONAL VENDAS RJ%)

Se o resultado for 0, use --diagnostico para ver contagens e amostras de nomes de conta.

Uso (PowerShell) — pasta salesforce:
  cd salesforce
  $env:SALESFORCE_USER=... ; $env:SALESFORCE_PASSWORD=... ; $env:SALESFORCE_TOKEN=...
  python listar_oportunidades_vendas_rj_direcional.py
  python listar_oportunidades_vendas_rj_direcional.py --diagnostico
  python listar_oportunidades_vendas_rj_direcional.py --csv vendas_rj.csv
  python listar_oportunidades_vendas_rj_direcional.py --fechamento-desde 2024-01-01 --limite 50

Por padrão só imprime até --limite linhas no console (evita dezenas de milhares de linhas).
  --limite 0  imprime tudo (não recomendado). Para lista completa use --csv.

Requisitos: pip install simple_salesforce
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from salesforce_api import conectar_salesforce

# --- Filtros (edite se o org usar outros valores) ---
PADRAO_CONTA_DIRECIONAL_RJ = "DIRECIONAL VENDAS RJ%"
# Mais tolerante: qualquer conta que tenha DIRECIONAL e RJ no nome
PADRAO_CONTA_AMPLIO = "%DIRECIONAL%RJ%"
REGIONAL_RJ = "RJ"

_DATA_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _data_soql(s: str) -> str:
    """SOQL: CloseDate >= YYYY-MM-DD (literal de data, sem aspas)."""
    t = (s or "").strip()
    if not _DATA_ISO.match(t):
        raise ValueError(f"Data inválida (use YYYY-MM-DD): {s!r}")
    return t


def _escapar_soql_literal(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "\\'")


def montar_soql(
    filtro_conta: str,
    fechamento_desde: str | None = None,
    limite: int | None = None,
) -> str:
    """
    filtro_conta:
      - "nenhum" — só ganhas + RJ regional
      - "prefixo" — LIKE DIRECIONAL VENDAS RJ%
      - "amplo" — LIKE %DIRECIONAL%RJ%
    fechamento_desde: YYYY-MM-DD (CloseDate >= ...)
    limite: se > 0, acrescenta LIMIT no SOQL
    """
    reg_rj = _escapar_soql_literal(REGIONAL_RJ)
    base = f"""
        SELECT
            Id,
            Name,
            StageName,
            CloseDate,
            Amount,
            AccountId,
            Account.Name,
            Regional__c,
            RegionalComercial__c,
            IsWon,
            IsClosed
        FROM Opportunity
        WHERE IsWon = true
          AND IsClosed = true
          AND (Regional__c = '{reg_rj}' OR RegionalComercial__c = '{reg_rj}')
    """.strip().replace("\n", " ")

    if fechamento_desde:
        base += f" AND CloseDate >= {_data_soql(fechamento_desde)}"

    if filtro_conta == "prefixo":
        p = _escapar_soql_literal(PADRAO_CONTA_DIRECIONAL_RJ)
        base += f" AND Account.Name LIKE '{p}'"
    elif filtro_conta == "amplo":
        p = _escapar_soql_literal(PADRAO_CONTA_AMPLIO)
        base += f" AND Account.Name LIKE '{p}'"

    base += " ORDER BY CloseDate DESC"
    if limite is not None and limite > 0:
        base += f" LIMIT {int(limite)}"
    return base


def where_para_contagem(filtro_conta: str, fechamento_desde: str | None = None) -> str:
    """Mesmo filtro do montar_soql, sem SELECT (para totalSize)."""
    reg_rj = _escapar_soql_literal(REGIONAL_RJ)
    w = (
        f"IsWon = true AND IsClosed = true "
        f"AND (Regional__c = '{reg_rj}' OR RegionalComercial__c = '{reg_rj}')"
    )
    if fechamento_desde:
        w += f" AND CloseDate >= {_data_soql(fechamento_desde)}"
    if filtro_conta == "prefixo":
        p = _escapar_soql_literal(PADRAO_CONTA_DIRECIONAL_RJ)
        w += f" AND Account.Name LIKE '{p}'"
    elif filtro_conta == "amplo":
        p = _escapar_soql_literal(PADRAO_CONTA_AMPLIO)
        w += f" AND Account.Name LIKE '{p}'"
    return w


def contar_oportunidades(sf, where_sql: str) -> int:
    """
    Total de oportunidades que batem com o WHERE (sem COUNT() agregado).
    Usa totalSize do REST API — mais confiável que expr0 com simple_salesforce.
    """
    soql = f"SELECT Id FROM Opportunity WHERE {where_sql} LIMIT 1"
    r = sf.query(soql.replace("\n", " ").strip())
    return int(r.get("totalSize", 0))


def rodar_diagnostico(sf) -> None:
    print("\n=== Diagnóstico (contagens no org) ===\n")
    print("  (contagem via SELECT Id ... LIMIT 1 + totalSize)\n")

    ganhas = "IsWon = true AND IsClosed = true"
    consultas = [
        ("Oportunidades ganhas (total)", ganhas),
        ("Ganhas com Regional__c = RJ", f"{ganhas} AND Regional__c = 'RJ'"),
        ("Ganhas com RegionalComercial__c = RJ", f"{ganhas} AND RegionalComercial__c = 'RJ'"),
        (
            "Ganhas com (Regional OU Reg.Comercial) = RJ [filtro principal]",
            f"{ganhas} AND (Regional__c = 'RJ' OR RegionalComercial__c = 'RJ')",
        ),
        (
            "Ganhas com Account.Name LIKE 'DIRECIONAL VENDAS RJ%'",
            f"{ganhas} AND Account.Name LIKE '{_escapar_soql_literal(PADRAO_CONTA_DIRECIONAL_RJ)}'",
        ),
        (
            "Ganhas RJ (OU reg.) E prefixo conta DIRECIONAL VENDAS RJ",
            f"{ganhas} AND (Regional__c = 'RJ' OR RegionalComercial__c = 'RJ') AND Account.Name LIKE '{_escapar_soql_literal(PADRAO_CONTA_DIRECIONAL_RJ)}'",
        ),
        (
            "Ganhas com nome conta amplo %DIRECIONAL%RJ%",
            f"{ganhas} AND Account.Name LIKE '{_escapar_soql_literal(PADRAO_CONTA_AMPLIO)}'",
        ),
    ]

    for titulo, where_sql in consultas:
        try:
            n = contar_oportunidades(sf, where_sql)
            print(f"  {n:8}  — {titulo}")
        except Exception as e:
            print(f"  (erro)  — {titulo}: {e}")

    filtro_amostra = (
        f"{ganhas} AND (Regional__c = 'RJ' OR RegionalComercial__c = 'RJ')"
    )
    n_filtro = contar_oportunidades(sf, filtro_amostra)

    # Amostra de nomes de conta em ganhas + RJ (para ver o padrão real)
    print("\n=== Amostra: até 15 contas distintas (ganhas + Regional OU Reg.Comercial RJ) ===\n")
    print(f"  Total de OPs com esse filtro: {n_filtro}\n")
    try:
        soql_amostra = f"""
            SELECT Account.Name
            FROM Opportunity
            WHERE {filtro_amostra}
            ORDER BY CloseDate DESC
            LIMIT 200
        """.strip().replace("\n", " ")
        r = sf.query_all(soql_amostra)
        vistos: set[str] = set()
        for rec in r.get("records", []):
            acc = rec.get("Account") or {}
            nome = (acc.get("Name") or "").strip()
            if nome and nome not in vistos:
                vistos.add(nome)
                print(f"  - {nome}")
                if len(vistos) >= 15:
                    break
        if not vistos:
            print("  (nenhum registro com RJ em Regional/Reg.Comercial — conferir picklists no org)")
    except Exception as e:
        print(f"  Erro na amostra: {e}")

    print("\n=== Dica ===")
    print("  Se 'Ganhas com Regional RJ' > 0 mas --conta-prefixo listar 0, o nome da conta no org")
    print("  não segue o prefixo DIRECIONAL VENDAS RJ — use a amostra ou --filtro-conta amplo.\n")


DEFAULT_LIMITE_CONSOLE = 200

_CSV_COLUNAS = (
    "Id",
    "Name",
    "StageName",
    "CloseDate",
    "Amount",
    "AccountId",
    "Account.Name",
    "Regional__c",
    "RegionalComercial__c",
    "IsWon",
    "IsClosed",
)


def _flatten_opp(rec: dict) -> dict[str, object]:
    acc = rec.get("Account") or {}
    return {
        "Id": rec.get("Id"),
        "Name": rec.get("Name"),
        "StageName": rec.get("StageName"),
        "CloseDate": rec.get("CloseDate"),
        "Amount": rec.get("Amount"),
        "AccountId": rec.get("AccountId"),
        "Account.Name": acc.get("Name"),
        "Regional__c": rec.get("Regional__c"),
        "RegionalComercial__c": rec.get("RegionalComercial__c"),
        "IsWon": rec.get("IsWon"),
        "IsClosed": rec.get("IsClosed"),
    }


def _exportar_csv(caminho: str, registros: list[dict]) -> None:
    with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(_CSV_COLUNAS), extrasaction="ignore")
        w.writeheader()
        for rec in registros:
            w.writerow(_flatten_opp(rec))


def main() -> int:
    ap = argparse.ArgumentParser(description="Lista OPs ganhas RJ / Direcional")
    ap.add_argument(
        "--diagnostico",
        action="store_true",
        help="Só imprime contagens e amostra de nomes de conta (não lista completa).",
    )
    ap.add_argument(
        "--filtro-conta",
        choices=("nenhum", "prefixo", "amplo"),
        default="nenhum",
        help=(
            "nenhum= só ganhas+RJ regional (recomendado se prefixo zerar); "
            "prefixo=DIRECIONAL VENDAS RJ%%; amplo=%%DIRECIONAL%%RJ%%"
        ),
    )
    ap.add_argument(
        "--conta-prefixo",
        action="store_true",
        help="Atalho: mesmo que --filtro-conta prefixo (compatibilidade).",
    )
    ap.add_argument(
        "--fechamento-desde",
        metavar="YYYY-MM-DD",
        default=None,
        help="Só OPs com CloseDate >= esta data (ex.: 2024-01-01).",
    )
    ap.add_argument(
        "--limite",
        type=int,
        default=DEFAULT_LIMITE_CONSOLE,
        metavar="N",
        help=(
            f"Máximo de linhas no console (padrão {DEFAULT_LIMITE_CONSOLE}). "
            "Use 0 para listar todas no terminal (pode ser enorme)."
        ),
    )
    ap.add_argument(
        "--csv",
        nargs="?",
        const="vendas_rj_oportunidades.csv",
        default=None,
        metavar="ARQUIVO",
        help="Exporta todos os registros do filtro para CSV (sem LIMIT). Caminho opcional.",
    )
    args = ap.parse_args()

    filtro = args.filtro_conta
    if args.conta_prefixo:
        filtro = "prefixo"

    fechamento = (args.fechamento_desde or "").strip() or None
    if fechamento:
        try:
            _data_soql(fechamento)
        except ValueError as e:
            print(e)
            return 1

    sf = conectar_salesforce()
    if not sf:
        return 1

    if args.diagnostico:
        rodar_diagnostico(sf)
        return 0

    label_filtro = {
        "nenhum": "ganhas + (Regional__c OU RegionalComercial__c) = RJ; sem filtro extra no nome da conta",
        "prefixo": "ganhas + RJ regional + conta LIKE DIRECIONAL VENDAS RJ%",
        "amplo": "ganhas + RJ regional + conta LIKE %DIRECIONAL%RJ%",
    }[filtro]

    where_cnt = where_para_contagem(filtro, fechamento)
    try:
        n_org = contar_oportunidades(sf, where_cnt)
    except Exception as e:
        print(f"Erro ao contar registros: {e}")
        return 1

    print(f"Total no org (filtro): {n_org}  ({label_filtro})\n")

    if args.csv:
        soql_csv = montar_soql(filtro, fechamento, limite=None)
        try:
            resultado_csv = sf.query_all(soql_csv)
        except Exception as e:
            print(f"Erro na consulta (CSV): {e}")
            return 1
        regs_csv = resultado_csv.get("records", [])
        try:
            _exportar_csv(args.csv, regs_csv)
        except OSError as e:
            print(f"Erro ao gravar CSV: {e}")
            return 1
        print(f"CSV gravado: {os.path.abspath(args.csv)}  ({len(regs_csv)} linhas)\n")

    lim_console = None if args.limite == 0 else args.limite
    soql = montar_soql(filtro, fechamento, limite=lim_console)
    print("SOQL (console):\n", soql, "\n")
    print("-" * 100)

    try:
        resultado = sf.query_all(soql)
    except Exception as e:
        print(f"Erro na consulta: {e}")
        return 1

    registros = resultado.get("records", [])
    total_imp = len(registros)
    if lim_console and n_org > total_imp:
        print(
            f"Impresso no console: {total_imp} de {n_org} "
            f"(use --limite 0 para tudo no terminal, ou --csv para exportar tudo).\n"
        )
    else:
        print(f"Linhas no console: {total_imp}\n")

    if total_imp == 0 and n_org == 0:
        print(
            "Nenhum registro. Rode:  python listar_oportunidades_vendas_rj_direcional.py --diagnostico\n"
        )
        return 0

    for i, rec in enumerate(registros, start=1):
        acc = rec.get("Account") or {}
        nome_conta = acc.get("Name") or ""
        print(
            f"{i:5} | Id: {rec.get('Id')} | Nome OP: {rec.get('Name')}\n"
            f"      Conta: {nome_conta} | Fase: {rec.get('StageName')} | "
            f"Fechamento: {rec.get('CloseDate')} | Valor: {rec.get('Amount')} | "
            f"Regional: {rec.get('Regional__c')} | Reg.Comercial: {rec.get('RegionalComercial__c')}"
        )
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
