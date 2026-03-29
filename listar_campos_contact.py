# -*- coding: utf-8 -*-
"""
Lista todos os campos do objeto Contact no Salesforce (nome de API, label, tipo),
para ajudar a mapear os campos do agente de preenchimento.

Uso:
  - Defina SALESFORCE_USER, SALESFORCE_PASSWORD e (opcional) SALESFORCE_TOKEN.
  - Execute: python listar_campos_contact.py
"""

from salesforce_api import conectar_salesforce


def main() -> None:
    sf = conectar_salesforce()
    if not sf:
        return

    meta = sf.Contact.describe()
    campos = meta["fields"]

    print(f"{'NAME (API)':<40} | {'LABEL':<35} | {'TYPE':<15} | REQUIRED")
    print("-" * 110)
    for campo in campos:
        name = campo["name"]
        label = campo["label"]
        ctype = campo["type"]
        required = (
            "Yes"
            if (not campo["nillable"] and campo["createable"] and not campo["defaultedOnCreate"])
            else "No"
        )
        print(f"{name:<40} | {label:<35} | {ctype:<15} | {required}")


if __name__ == "__main__":
    main()

