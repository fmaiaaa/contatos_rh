# -*- coding: utf-8 -*-
"""
Obtém a lista de todos os objetos do Salesforce e executa describe (getattr(sf, nome).describe())
para cada um, salvando o resultado em JSON.

Antes de rodar: SALESFORCE_USER, SALESFORCE_PASSWORD, SALESFORCE_TOKEN.

Uso:
  python salesforce_descrever_todos_objetos.py
  python salesforce_descrever_todos_objetos.py --arquivo saida.json
"""

import argparse
import json
import os
import sys

from salesforce_api import conectar_salesforce


def main():
    parser = argparse.ArgumentParser(description="Lista todos os objetos e descreve cada um (describe)")
    parser.add_argument(
        "--arquivo", "-o",
        default="salesforce_objetos_describe.json",
        help="Arquivo JSON de saída com a lista de objetos e o describe de cada um",
    )
    args = parser.parse_args()

    if not os.environ.get("SALESFORCE_USER") or not os.environ.get("SALESFORCE_PASSWORD"):
        print("❌ Defina SALESFORCE_USER e SALESFORCE_PASSWORD (e SALESFORCE_TOKEN) no CMD antes de rodar.")
        sys.exit(1)

    sf = conectar_salesforce()
    if not sf:
        sys.exit(1)

    print("\n--- Obtendo lista de todos os objetos (describe global) ---")
    try:
        global_describe = sf.describe()
    except Exception as e:
        print(f"❌ Erro ao obter describe global: {e}")
        sys.exit(1)

    sobjects = global_describe.get("sobjects", [])
    nomes = [obj["name"] for obj in sobjects]
    print(f"Total de objetos: {len(nomes)}")

    resultado = {
        "lista_objetos": [
            {"name": obj["name"], "label": obj.get("label"), "custom": obj.get("custom", False)}
            for obj in sobjects
        ],
        "describe_por_objeto": {},
    }

    print("\n--- Executando getattr(sf, nome).describe() para cada objeto ---")
    erros = []
    for i, nome in enumerate(nomes, 1):
        try:
            sobject = getattr(sf, nome)
            meta = sobject.describe()
            resultado["describe_por_objeto"][nome] = meta
            if i % 50 == 0 or i == len(nomes):
                print(f"  {i}/{len(nomes)}: {nome}")
        except Exception as e:
            erros.append((nome, str(e)))
            resultado["describe_por_objeto"][nome] = {"_erro": str(e)}

    if erros:
        print(f"\n⚠️ {len(erros)} objeto(s) falharam no describe:")
        for nome, msg in erros[:20]:
            print(f"  - {nome}: {msg}")
        if len(erros) > 20:
            print(f"  ... e mais {len(erros) - 20}")

    with open(args.arquivo, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n✅ Saída gravada em: {args.arquivo}")
    print(f"   - lista_objetos: {len(resultado['lista_objetos'])} itens")
    print(f"   - describe_por_objeto: {len(resultado['describe_por_objeto'])} itens\n")


if __name__ == "__main__":
    main()
