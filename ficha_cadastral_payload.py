# -*- coding: utf-8 -*-
"""
Monta o payload do objeto Contact no Salesforce a partir da ficha cadastral Vendas RJ.

Alinhado aos padrões de `criar_contato_exemplo_completo.py` e `criar_contato_cmd.py`
(campos de API, Record Type Corretor, Regional RJ).

Valores de picklist (ex.: Status_Corretor__c) devem existir no org; ajuste se necessário.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

# Defina o Id do tipo de registro da sua org (ou deixe vazio para omitir RecordTypeId no insert).
RECORD_TYPE_CORRETOR = ""

BASE_URL_CONTACT_VIEW = "https://direcional.lightning.force.com/lightning/r/Contact"


def _split_nome(nome: str) -> tuple[str, str]:
    nome = (nome or "").strip()
    if not nome:
        return "Candidato", "Ficha Vendas RJ"
    parts = nome.split(None, 1)
    if len(parts) == 1:
        return parts[0][:40], parts[0][:80]
    return parts[0][:40], parts[1][:80]


def _somente_digitos(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def montar_payload_salesforce_ficha(dados: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    """
    Retorna (payload ou None, avisos).
    Se e-mail inválido/ausente, retorna (None, [mensagem]).
    """
    avisos: list[str] = []
    email = (dados.get("email") or "").strip()
    if not email or "@" not in email:
        return None, ["Informe um **e-mail válido** no campo **E-mail para contato** (Dados Pessoais)."]

    first, last = _split_nome(str(dados.get("nome_completo") or ""))
    cpf = _somente_digitos(str(dados.get("cpf") or ""))

    cargo_txt = (dados.get("cargo") or "").strip()
    if (dados.get("cargo") or "").strip() == "Outro" and (dados.get("cargo_outro") or "").strip():
        cargo_txt = f"{cargo_txt} — {(dados.get('cargo_outro') or '').strip()}"

    endereco = ", ".join(
        str(x).strip()
        for x in (
            dados.get("rua"),
            dados.get("numero_residencia"),
            dados.get("complemento"),
            dados.get("bairro"),
            dados.get("cidade_residencia"),
            dados.get("cep"),
        )
        if x and str(x).strip()
    )

    desc = (
        f"Ficha Cadastral Direcional Vendas RJ. Indicação: {dados.get('quem_indicou') or '—'}. "
        f"Cargo: {cargo_txt}. Endereço: {endereco or '—'}."
    )[:131072]

    obs = (
        f"INDICAÇÃO: {dados.get('quem_indicou')} | "
        f"RG/UF: {dados.get('rg')} / {dados.get('uf_emissao_rg')} | "
        f"Nasc.: {dados.get('data_nascimento')} {dados.get('cidade_nascimento')}/{dados.get('estado_nascimento')} | "
        f"Escolaridade: {dados.get('escolaridade')} | CRECI: {dados.get('possui_creci')} "
        f"{dados.get('numero_creci') or ''} | "
        f"Banco: {dados.get('banco')} Ag {dados.get('agencia')} Cc {dados.get('conta_digito')} | "
        f"PIX ({dados.get('tipo_pix')}): {dados.get('chave_pix')} | "
        f"PJ: {dados.get('cadastro_pj')} {dados.get('cnpj') or ''} | "
        f"Camisa: {dados.get('tamanho_camisa')} | PCD: {dados.get('pcd')} {dados.get('pcd_especifique') or ''} | "
        f"Gênero: {dados.get('genero')}"
    )[:32768]

    contrato_txt = (
        f"Ficha web Vendas RJ. LGPD aceito. {cargo_txt}. "
        f"CRECI {dados.get('tipo_creci') or ''} validade {dados.get('validade_creci') or ''}."
    )[:32768]

    payload: dict[str, Any] = {
        "FirstName": first,
        "LastName": last,
        "Email": email,
        "Description": desc,
        "Regional__c": "RJ",
        "Observacoes__c": obs,
        "Contrato__c": contrato_txt,
        "Data_da_Entrevista__c": date.today().isoformat(),
    }
    rt = (RECORD_TYPE_CORRETOR or "").strip()
    if rt:
        payload["RecordTypeId"] = rt

    if cpf:
        payload["CPF__c"] = cpf

    # Status — valores comuns no describe (ajuste se o org diferir)
    payload["Status_Corretor__c"] = "Pré credenciado"

    chave = str(dados.get("chave_pix") or "").strip()
    tipo_pix = dados.get("tipo_pix")
    if tipo_pix == "CPF" and cpf:
        payload["Dados_para_PIX__c"] = cpf
    elif chave:
        payload["Dados_para_PIX__c"] = chave[:255]

    if dados.get("possui_creci") == "Sim" and dados.get("numero_creci"):
        raw_creci = _somente_digitos(str(dados.get("numero_creci")))
        if raw_creci:
            try:
                payload["CRECI__c"] = int(raw_creci[:8])
            except ValueError:
                payload["CRECI__c"] = str(dados.get("numero_creci"))[:20]

    # MobilePhone — regra de validação no org (ver salesforce_api.criar_novo_contacto)
    mob = ""
    if tipo_pix == "Telefone":
        mob = _somente_digitos(chave)
    if len(mob) >= 10:
        payload["MobilePhone"] = mob[:11]
    else:
        payload["MobilePhone"] = "21999999999"
        avisos.append(
            "Para o Salesforce, **MobilePhone** foi preenchido com valor padrão. "
            "Informe tipo de PIX **Telefone** e a chave com DDD ou ajuste o contato no org."
        )

    # Remove chaves com None ou string vazia
    limpo = {k: v for k, v in payload.items() if v is not None and (not isinstance(v, str) or v.strip())}
    return limpo, avisos


def url_contact(contact_id: str) -> str:
    return f"{BASE_URL_CONTACT_VIEW}/{contact_id}/view"
