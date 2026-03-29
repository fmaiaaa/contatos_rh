# -*- coding: utf-8 -*-
"""
Cria um contato (Corretor) no Salesforce pela API e exibe o Id e a URL para visualizar.

Antes de rodar, defina no CMD:
  set "SALESFORCE_USER=seu_email@direcional.com.br"
  set "SALESFORCE_PASSWORD=sua_senha"
  set "SALESFORCE_TOKEN=token_do_email"

Uso:
  python criar_contato_cmd.py
  python criar_contato_cmd.py --nome João --apelido Silva --email joao@exemplo.com --celular 31999999999
"""

import argparse
import os
import sys

from salesforce_api import conectar_salesforce, criar_novo_contacto

# Record Type "Corretor" (ajuste se o Id for diferente no seu org)
RECORD_TYPE_CORRETOR = "012f1000000n6nN"
BASE_URL_VIEW = "https://direcional.lightning.force.com/lightning/r/Contact"


def main():
    parser = argparse.ArgumentParser(description="Criar contato Corretor no Salesforce e exibir link para visualizar")
    parser.add_argument("--nome", "-n", default="Primeiro", help="Primeiro nome")
    parser.add_argument("--apelido", "-a", default="Sobrenome", help="Sobrenome (obrigatório na API)")
    parser.add_argument("--email", "-e", default="contato.cmd@exemplo.com", help="E-mail")
    parser.add_argument("--celular", "-c", default="31999999999", help="Celular (obrigatório por validação no org)")
    args = parser.parse_args()

    if not os.environ.get("SALESFORCE_USER") or not os.environ.get("SALESFORCE_PASSWORD"):
        print("❌ Defina SALESFORCE_USER e SALESFORCE_PASSWORD (e SALESFORCE_TOKEN) no CMD antes de rodar.")
        sys.exit(1)

    sf = conectar_salesforce()
    if not sf:
        sys.exit(1)

    id_novo = criar_novo_contacto(
        sf,
        nome=args.nome.strip(),
        apelido=args.apelido.strip(),
        email=args.email.strip(),
        record_type_id=None,  # nenhum tipo de registro definido (usa o padrão do usuário)
        celular=args.celular.strip() or "31999999999",
    )
    if not id_novo:
        sys.exit(1)

    url_view = f"{BASE_URL_VIEW}/{id_novo}/view"
    print(f"\n📋 Id do novo contato: {id_novo}")
    print(f"🔗 Abra no Salesforce: {url_view}\n")


if __name__ == "__main__":
    main()
