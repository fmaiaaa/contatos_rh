# -*- coding: utf-8 -*-
"""
Anexa uma linha na planilha Google (gspread + conta de serviço).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# ID padrão da planilha informada pelo usuário
DEFAULT_SPREADSHEET_ID = "1_9x4rfHoP2M47qXJENoD3vMLf_7rWUhNjrU8EtESxy8"
DEFAULT_WORKSHEET_NAME = "Corretores"
# Aba com a lista de nomes de conta para o formulário (coluna de cabeçalho na linha 1)
DEFAULT_GERENTES_WORKSHEET = "Gerentes"
DEFAULT_COL_NOME_CONTA = "Nome da Conta"


def _credenciais_de_secrets(st_secrets: Any) -> Optional[Dict[str, Any]]:
    """Lê JSON da conta de serviço a partir de st.secrets['google_sheets']."""
    if st_secrets is None:
        return None
    try:
        gs = st_secrets.get("google_sheets") if hasattr(st_secrets, "get") else st_secrets["google_sheets"]
    except (KeyError, TypeError):
        return None
    if not gs:
        return None
    raw = gs.get("SERVICE_ACCOUNT_JSON") or gs.get("service_account_json")
    if not raw:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        if s.startswith("\ufeff"):
            s = s.lstrip("\ufeff")
        try:
            parsed = json.loads(s)
        except (json.JSONDecodeError, TypeError, ValueError):
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _cliente_gspread(creds_dict: Dict[str, Any]):
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)


def _col_letter(n: int) -> str:
    """Converte índice de coluna 1-based para letra(s) A, B, ..., Z, AA."""
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def anexar_linha(
    linha: List[str],
    cabecalho: List[str],
    spreadsheet_id: str,
    worksheet_name: str,
    creds_dict: Dict[str, Any],
) -> int:
    """
    Garante que a aba existe, cabeçalho na linha 1 (se vazia) e anexa a linha.
    """
    gc = _cliente_gspread(creds_dict)
    sh = gc.open_by_key(spreadsheet_id)
    try:
        ws = sh.worksheet(worksheet_name)
    except Exception:
        ws = sh.add_worksheet(title=worksheet_name, rows=1000, cols=max(len(cabecalho), 30))

    existing = ws.get_all_values()
    if not existing or not any(cell.strip() for cell in existing[0]):
        ws.update("A1", [cabecalho], value_input_option="USER_ENTERED")
    elif len(existing[0]) < len(cabecalho):
        # Cabeçalho existente mais curto — preenche células faltantes (linha 1)
        pad = existing[0] + [""] * (len(cabecalho) - len(existing[0]))
        for i, h in enumerate(cabecalho):
            if i >= len(pad) or not (pad[i] or "").strip():
                pad[i] = h
        ws.update("A1", [pad[: len(cabecalho)]], value_input_option="USER_ENTERED")

    ws.append_row(linha, value_input_option="USER_ENTERED")
    return len(ws.get_all_values())


def atualizar_status_envio_salesforce(
    spreadsheet_id: str,
    worksheet_name: str,
    creds_dict: Dict[str, Any],
    row_1based: int,
    envio: str,
    log_erro: str,
    link: str,
) -> None:
    """
    Preenche na linha indicada as colunas **Envio?**, **Log / erro** e **Link do contato**
    (cabeçalhos definidos em corretor_campos.cabecalho_planilha).
    """
    gc = _cliente_gspread(creds_dict)
    sh = gc.open_by_key(spreadsheet_id)
    ws = sh.worksheet(worksheet_name)
    headers = ws.row_values(1)
    mapping = {
        "Envio?": envio,
        "Log / erro": (log_erro or "")[:49000],
        "Link do contato": link or "",
    }
    for h, val in mapping.items():
        if h not in headers:
            continue
        col = headers.index(h) + 1
        cell = f"{_col_letter(col)}{row_1based}"
        ws.update(cell, [[val]], value_input_option="USER_ENTERED")


def listar_nomes_conta_aba_gerentes(
    spreadsheet_id: str,
    creds_dict: Dict[str, Any],
    worksheet_name: str = DEFAULT_GERENTES_WORKSHEET,
    column_header: str = DEFAULT_COL_NOME_CONTA,
) -> List[str]:
    """
    Lê a planilha indicada, aba `worksheet_name`, e devolve valores únicos e não vazios
    da coluna cujo cabeçalho (linha 1) coincide com `column_header` (ignora maiúsculas/minúsculas e espaços).
    """
    gc = _cliente_gspread(creds_dict)
    sh = gc.open_by_key(spreadsheet_id)
    ws = sh.worksheet(worksheet_name)
    rows = ws.get_all_values()
    if not rows:
        return []
    headers = [str(h or "").strip() for h in rows[0]]
    target = (column_header or "").strip().lower()
    col_idx = None
    for i, h in enumerate(headers):
        if h.strip().lower() == target:
            col_idx = i
            break
    if col_idx is None:
        return []
    seen: set[str] = set()
    out: List[str] = []
    for r in rows[1:]:
        if col_idx >= len(r):
            continue
        v = str(r[col_idx] or "").strip()
        if not v or v in seen:
            continue
        seen.add(v)
        out.append(v)
    out.sort(key=lambda s: s.casefold())
    return out


def carimbo_brasilia_iso() -> str:
    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("America/Sao_Paulo")
        return datetime.now(tz).isoformat(timespec="seconds")
    except Exception:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
