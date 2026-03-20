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
    if isinstance(raw, str):
        return json.loads(raw)
    if isinstance(raw, dict):
        return raw
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


def anexar_linha(
    linha: List[str],
    cabecalho: List[str],
    spreadsheet_id: str,
    worksheet_name: str,
    creds_dict: Dict[str, Any],
) -> None:
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


def carimbo_brasilia_iso() -> str:
    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("America/Sao_Paulo")
        return datetime.now(tz).isoformat(timespec="seconds")
    except Exception:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
