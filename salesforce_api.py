# -*- coding: utf-8 -*-
"""
Módulo de integração com a Salesforce API (simple_salesforce).
Uso: defina SALESFORCE_USER e SALESFORCE_PASSWORD (senha + Security Token, sem espaços).

Uso no PowerShell:
  $env:SALESFORCE_USER="seu_email@direcional.com.br"
  $env:SALESFORCE_PASSWORD="sua_senha" + "token_do_email"
  python salesforce_api.py

Requisitos: pip install simple_salesforce
"""

import os
from simple_salesforce import Salesforce, SalesforceAuthenticationFailed


# IMPORTANTE:
# Opção 1 (recomendada): SALESFORCE_USER, SALESFORCE_PASSWORD (só a senha) e SALESFORCE_TOKEN (Security Token).
# Opção 2: SALESFORCE_USER e SALESFORCE_PASSWORD = senha + Security Token colados (sem espaço).


def conectar_salesforce():
    """
    Estabelece a conexão com o Salesforce utilizando as variáveis de ambiente.
    Preferência: usar SALESFORCE_TOKEN separado; senão, SALESFORCE_PASSWORD pode ser senha+token.
    """
    username = (os.environ.get("SALESFORCE_USER") or "").strip()
    password = (os.environ.get("SALESFORCE_PASSWORD") or "").strip()
    token = (os.environ.get("SALESFORCE_TOKEN") or "").strip()

    try:
        if not username or not password:
            print("❌ Erro: Variáveis de ambiente SALESFORCE_USER ou SALESFORCE_PASSWORD não configuradas.")
            return None

        print(f"Tentando conectar ao Salesforce como: {username}...")

        # Preferir security_token separado (evita erro "You must provide login information or an instance and token")
        if token:
            sf = Salesforce(
                username=username,
                password=password,
                security_token=token,
                domain="login",
            )
        else:
            # Senão, password deve ser senha+token colados
            sf = Salesforce(username=username, password=password, domain="login")

        print("✅ Conexão estabelecida com sucesso!")
        return sf

    except SalesforceAuthenticationFailed as e:
        print("❌ Erro de Autenticação: Verifique usuário, senha e Security Token.")
        print(f"Detalhes: {e}")
        return None
    except Exception as e:
        print(f"❌ Ocorreu um erro inesperado: {e}")
        return None


def listar_todos_os_campos_contato(sf):
    """
    Inspeciona os metadados do objeto Contact para listar todos os campos disponíveis.
    Útil para identificar nomes de API de campos personalizados (__c).
    """
    try:
        print("\n--- Inspecionando Campos do Objeto Contato ---")
        meta = sf.Contact.describe()

        campos = meta["fields"]
        print(f"{'NOME DE API':<40} | {'RÓTULO (LABEL)':<30} | {'TIPO':<15} | {'OBRIGATÓRIO'}")
        print("-" * 100)

        for campo in campos:
            nome_api = campo["name"]
            label = campo["label"]
            tipo = campo["type"]
            obrigatorio = (
                "Sim"
                if (not campo["nillable"] and campo["createable"] and not campo["defaultedOnCreate"])
                else "Não"
            )
            print(f"{nome_api:<40} | {label:<30} | {tipo:<15} | {obrigatorio}")

    except Exception as e:
        print(f"Erro ao descrever objeto: {e}")


def executar_exemplo_soql(sf):
    """
    Exemplo de uma consulta SOQL simples para listar contas.
    """
    try:
        print("\n--- Listando as primeiras 5 Contas ---")
        resultados = sf.query("SELECT Id, Name, Industry FROM Account LIMIT 5")

        for registo in resultados["records"]:
            print(f"ID: {registo['Id']} | Nome: {registo['Name']} | Indústria: {registo.get('Industry', 'N/A')}")

    except Exception as e:
        print(f"Erro ao executar query: {e}")


def criar_novo_contacto(sf, nome, apelido, email, record_type_id=None, celular=None):
    """
    Cria um novo registo de Contacto no Salesforce. (INSERT)
    Celular (MobilePhone) é obrigatório por regra de validação no org; informe para evitar erro.
    """
    try:
        dados_contacto = {
            "FirstName": nome,
            "LastName": apelido,
            "Email": email,
            "Description": "Criado via Automação Python",
        }

        if record_type_id:
            dados_contacto["RecordTypeId"] = record_type_id
        if celular is not None and str(celular).strip():
            dados_contacto["MobilePhone"] = str(celular).strip()

        resultado = sf.Contact.create(dados_contacto)
        print(f"\n✅ Contacto criado com sucesso! ID: {resultado['id']}")
        return resultado["id"]

    except Exception as e:
        print(f"Erro ao criar contacto: {e}")
        return None


def atualizar_contacto(sf, contacto_id, novos_dados):
    """
    Atualiza um contacto existente usando o seu ID. (UPDATE)
    """
    try:
        sf.Contact.update(contacto_id, novos_dados)
        print(f"✅ Contacto {contacto_id} atualizado com sucesso!")
    except Exception as e:
        print(f"Erro ao atualizar contacto: {e}")


def preenchimento_em_massa(sf, lista_contactos):
    """
    Insere vários contactos de uma vez usando a API Bulk. (Massa)
    """
    try:
        print(f"\nIniciando carregamento em massa de {len(lista_contactos)} registos...")
        resultado = sf.bulk.Contact.insert(lista_contactos)
        print("✅ Carregamento em massa concluído!")
        return resultado
    except Exception as e:
        print(f"Erro no carregamento em massa: {e}")
        return None


if __name__ == "__main__":
    sf_instance = conectar_salesforce()

    if sf_instance:
        listar_todos_os_campos_contato(sf_instance)

        # Exemplo de criação usando o RecordTypeId do Corretor (ajuste se necessário)
        # record_type_alvo = "012f1000000n6nN"
        # criar_novo_contacto(sf_instance, "Lucas", "Maia", "lucas.maia@direcional.com.br", record_type_alvo)
