# -*- coding: utf-8 -*-
"""
Envio de pendências comerciais por e-mail (Outlook Desktop via win32com).

1. Lê a planilha-fonte (VENDA FACILITADA RJ NOVO OBJETO)
2. Filtra pendências por Fase e email_corretor válido; exclui empreendimentos em EMPREENDIMENTOS_EXCLUIR_ENVIO
   e identificadores já gravados em pendencias_identificadores_email_ja_enviado.json (após cada envio OK)
3. Grava cada pendência na aba "Não Respondidos" da planilha de respostas
4. Envia email via Outlook Desktop com botões "Manter venda" / "Derrubar venda"
5. Quando o destinatário clica, o Apps Script move de "Não Respondidos"
   para "Respondidos" (Resposta: MANTER VENDA | DERRUBAR VENDA; Motivo = justificativa).

Requisitos:
- Outlook desktop aberto e logado
- credentials2.json e authorized_user2.json em config_e_dependencias/
  (se aparecer invalid_grant: apague authorized_user2.json e rode de novo para refazer o login)
"""

import json
import os
import re
import time
import random
from datetime import datetime
from urllib.parse import quote

import win32com.client
import gspread
import pandas as pd

try:
    from google.auth.exceptions import RefreshError as _GoogleRefreshError
except ImportError:
    _GoogleRefreshError = None  # type: ignore[misc, assignment]

# --- CAMINHOS E CONFIG GOOGLE ---

BASE_DIR = r"C:\Users\DE0189769\OneDrive - Direcional Engenharia S A\Documentos Macedo One Drive\Automações - Lucas"
PASTA_CONFIG = os.path.join(BASE_DIR, "config_e_dependencias")

CREDENTIALS_JSON = os.path.join(PASTA_CONFIG, "credentials2.json")
AUTHORIZED_USER_JSON = os.path.join(PASTA_CONFIG, "authorized_user2.json")

SPREADSHEET_FONTE_ID = "18VnKARe8YkOorIR4_2MfxEeF2zXfnrEOYiNXTS_Kv68"
ABA_FONTE = "VENDA FACILITADA RJ NOVO OBJETO"

SPREADSHEET_RESPOSTAS_ID = "1ewtY5GZ3wEmEA3QH6cQM-30OMP5feCLYDiFeVfqHU84"
ABA_NAO_RESPONDIDOS = "Não Respondidos"
ABA_RESPONDIDOS = "Respondidos"

# --- CONFIG ---

MODO_TESTE = False
EMAIL_TESTE = "fmaiaaa102@gmail.com"

APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbz7gxePsUGoWahzl62-mtsh0kaspy8FhW6WS7P_YSq4avIu8UcbGQEh2QErDWoLcFFB/exec"

FASES_ALVO = ["Contrato com pendência comercial", "Em elaboração", "Proposta Aprovada"]
FASES_BLOQUEADAS_ENVIO = ["Contrato comunicado", "Fechado e ganho"]

# Ordem das colunas na aba (14 colunas) — igual a "Respondidos" (Resposta/Motivo vazios até responder)
# Fonte: coluna da planilha de vendas para cada campo após Data + Nome + Resposta + Motivo
COLUNAS_NAO_RESPONDIDOS = [
    "Data de Envio do Email",
    "Nome da Oportunidade",
    "Resposta",
    "Motivo",
    "Email Corretor",
    "Email Proprietário",
    "Email Comercial RJ",
    "Email Gerente",
    "Email Proprietário da Conta",
    "Oportunidade : Imobiliária : Gerente de Vendas",
    "Oportunidade : Imobiliária : Proprietário da conta",
    "Oportunidade : Imobiliária : Proprietário da conta : Gerente",
    "Contato Corretor Proprietario",
    "Proprietário da oportunidade",
]

# Colunas da fonte (após Data, Nome da Oportunidade, Resposta e Motivo vazios)
MAPA_COLUNAS_FONTE = [
    "email_corretor",
    "email_proprietário",
    "email_comercialrj",
    "email_gerente",
    "email_prop_conta",
    "Oportunidade : Imobiliária : Gerente de Vendas",
    "Oportunidade : Imobiliária : Proprietário da conta",
    "Oportunidade : Imobiliária : Proprietário da conta : Gerente",
    "Contato Corretor Proprietario",
    "Proprietário da oportunidade",
]

# Valores enviados na URL do Web App (Apps Script normaliza legado se necessário)
ACAO_MANTER_VENDA = "MANTER VENDA"
ACAO_DERRUBAR_VENDA = "DERRUBAR VENDA"

# Não enviar e-mail de pendência para estas unidades (comparação sem diferenciar maiúsculas).
EMPREENDIMENTOS_EXCLUIR_ENVIO = (
    "Uniq Condomínio Clube",
    "Viva Vida Recanto Clube",
)

_DIR_SCRIPT = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_CONTROLE_ENVIOS = os.path.join(_DIR_SCRIPT, "pendencias_controle_envios.json")


def _empreendimento_bloqueia_envio(val) -> bool:
    """True se o empreendimento está na lista de exclusão (nome exato, ignorando maiúsculas)."""
    s = (str(val).strip() if val is not None and pd.notna(val) else "") or ""
    if not s or s == "#N/A":
        return False
    s_cf = s.casefold()
    for ex in EMPREENDIMENTOS_EXCLUIR_ENVIO:
        if ex.strip().casefold() == s_cf:
            return True
    return False


def _carregar_controle_envios() -> dict:
    """Controle local: histórico de envios por identificador e snapshot de respostas do Sheets."""
    base = {"envios": {}, "respostas": {}}
    path = ARQUIVO_CONTROLE_ENVIOS
    if not os.path.isfile(path):
        return base
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            env = data.get("envios") if isinstance(data.get("envios"), dict) else {}
            rsp = data.get("respostas") if isinstance(data.get("respostas"), dict) else {}
            return {"envios": env, "respostas": rsp}
    except (json.JSONDecodeError, OSError, TypeError):
        pass
    return base


def _salvar_controle_envios(ctrl: dict) -> None:
    payload = {
        "envios": ctrl.get("envios", {}),
        "respostas": ctrl.get("respostas", {}),
    }
    path = ARQUIVO_CONTROLE_ENVIOS
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _agora_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _norm_resposta(val: str) -> str:
    s = (str(val or "").strip().upper())
    if "DERRUBAR" in s:
        return "DERRUBAR VENDA"
    if "MANTER" in s:
        return "MANTER VENDA"
    return s


def _carregar_status_respondidos(gc) -> dict[str, dict]:
    """
    Retorna mapa por Nome da Oportunidade com a última resposta encontrada na aba Respondidos.
    Campos: resposta_norm, resposta_raw, motivo, data_resposta.
    """
    sh = gc.open_by_key(SPREADSHEET_RESPOSTAS_ID)
    ws = sh.worksheet(ABA_RESPONDIDOS)
    rows = ws.get_all_records()
    out: dict[str, dict] = {}
    for r in rows:
        nome_op = str(r.get("Nome da Oportunidade", "")).strip()
        if not nome_op:
            continue
        resposta_raw = str(r.get("Resposta", "")).strip()
        if not resposta_raw:
            continue
        out[nome_op] = {
            "resposta_norm": _norm_resposta(resposta_raw),
            "resposta_raw": resposta_raw,
            "motivo": str(r.get("Motivo", "")).strip(),
            "data_resposta": str(r.get("Data de Envio do Email", "")).strip(),
        }
    return out


def _atualizar_snapshot_respostas(ctrl: dict, status_respondidos: dict[str, dict]) -> None:
    snap = ctrl.setdefault("respostas", {})
    capturado_em = _agora_iso()
    for nome_op, info in status_respondidos.items():
        snap[nome_op] = {
            "resposta_norm": info.get("resposta_norm", ""),
            "resposta_raw": info.get("resposta_raw", ""),
            "motivo": info.get("motivo", ""),
            "data_resposta": info.get("data_resposta", ""),
            "capturado_em": capturado_em,
        }


def _registrar_envio(ctrl: dict, identificador: str, nome_op: str, tipo_email: str) -> int:
    env = ctrl.setdefault("envios", {})
    key = str(identificador).strip() or str(nome_op).strip()
    item = env.setdefault(key, {"identificador": identificador, "nome_oportunidade": nome_op, "historico": []})
    hist = item.setdefault("historico", [])
    hist.append({"enviado_em": _agora_iso(), "tipo_email": tipo_email})
    return len(hist)


def conectar_gspread():
    """Conecta ao Google Sheets via OAuth."""
    if not os.path.isfile(CREDENTIALS_JSON):
        raise FileNotFoundError(f"Credenciais não encontradas: {CREDENTIALS_JSON!r}")
    try:
        return gspread.oauth(
            credentials_filename=CREDENTIALS_JSON,
            authorized_user_filename=AUTHORIZED_USER_JSON,
        )
    except Exception as e:
        is_refresh = _GoogleRefreshError is not None and isinstance(e, _GoogleRefreshError)
        if not is_refresh and "invalid_grant" not in str(e).lower():
            raise
        raise RuntimeError(
            "OAuth Google: token inválido ou expirado (invalid_grant).\n\n"
            f"1) Feche o script e apague este arquivo (ele será recriado no próximo login):\n"
            f"   {AUTHORIZED_USER_JSON}\n"
            "2) Confirme que credentials2.json é o OAuth Client correto (Desktop) no Google Cloud Console.\n"
            "3) Rode o script de novo — o navegador deve abrir para autorizar o acesso ao Sheets.\n"
        ) from e


def carregar_fonte(gc) -> pd.DataFrame:
    """Carrega a aba fonte do Google Sheets."""
    sh = gc.open_by_key(SPREADSHEET_FONTE_ID)
    ws = sh.worksheet(ABA_FONTE)
    df = pd.DataFrame(ws.get_all_records())
    df.columns = [str(c).strip() for c in df.columns]
    return df


def gravar_nao_respondidos(gc, pendencias: pd.DataFrame) -> None:
    """Grava pendências na aba 'Não Respondidos' sem duplicar por Nome da Oportunidade (col B)."""
    sh = gc.open_by_key(SPREADSHEET_RESPOSTAS_ID)
    ws = sh.worksheet(ABA_NAO_RESPONDIDOS)

    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    existentes = ws.get_all_values()
    nomes_existentes = set()
    if len(existentes) > 1:
        for row in existentes[1:]:
            # Col B = Nome da Oportunidade; legado: Identificador na B
            if len(row) > 1:
                nomes_existentes.add(str(row[1]).strip())

    linhas = []
    for _, row in pendencias.iterrows():
        identificador = str(row.get("Identificador", "")).strip()
        if not identificador:
            continue
        nome_op = str(row.get("Nome da oportunidade", "")).strip()
        if not nome_op:
            continue
        if nome_op in nomes_existentes:
            continue

        # [Data, Nome da Oportunidade, Resposta vazio, Motivo vazio, ...emails e campos]
        linha = [agora, nome_op, "", ""]
        for col_fonte in MAPA_COLUNAS_FONTE:
            valor = row.get(col_fonte, "")
            linha.append(str(valor) if pd.notna(valor) and str(valor).strip() else "")
        linhas.append(linha)
        nomes_existentes.add(nome_op)

    if linhas:
        proxima_linha = len(existentes) + 1
        ws.update(f"A{proxima_linha}", linhas, value_input_option="USER_ENTERED")
        print(f"   {len(linhas)} nova(s) linha(s) gravada(s) em '{ABA_NAO_RESPONDIDOS}'")
    else:
        print(f"   Nenhuma nova linha gravada em '{ABA_NAO_RESPONDIDOS}' (todas já existentes).")


COR_AZUL = "#002c5d"
COR_VERMELHO = "#e30613"
EMAIL_EXCLUIDO = "imobrj@direcional.com.br"

# Margem mínima (cartão em relação à borda do cliente de e-mail)
EMAIL_MARGEM_MIN_V = 20
EMAIL_MARGEM_MIN_H = 16

# E-mail: fundo e bordas neutras (evita faixas azul-claro/cinza no Outlook)
EMAIL_BG = "#ffffff"
EMAIL_BORDA_CINZA = "#cccccc"


def validar_email(val) -> str | None:
    s = str(val).strip() if pd.notna(val) else ""
    return s if (s and s != "#N/A" and "@" in s) else None


def validar_texto(val, padrao="Não informado") -> str:
    s = str(val).strip() if pd.notna(val) else ""
    return s if (s and s != "#N/A") else padrao


def formatar_moeda(valor) -> str:
    try:
        if pd.isna(valor) or valor == "#N/A" or str(valor).strip() == "":
            return "R$ 0,00"
        s_val = str(valor).replace("R$", "").strip()
        if "," in s_val and "." in s_val:
            s_val = s_val.replace(".", "").replace(",", ".")
        elif "," in s_val:
            s_val = s_val.replace(",", ".")
        s_val = re.sub(r"[^\d\.\-]", "", s_val)
        v = float(s_val)
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def formatar_linha_destinatarios(nomes: list[str]) -> str:
    """Ex.: 'Destinatários: João, Maria, Anderson e Jacó.' (sem bullets)."""
    limpos = [n.strip() for n in nomes if n and str(n).strip() and str(n).strip() != "Não informado"]
    if not limpos:
        return "Destinatários: Não informado."
    if len(limpos) == 1:
        return f"Destinatários: {limpos[0]}."
    if len(limpos) == 2:
        return f"Destinatários: {limpos[0]} e {limpos[1]}."
    return "Destinatários: " + ", ".join(limpos[:-1]) + " e " + limpos[-1] + "."


def formatar_motivos(motivo_bruto: str) -> str:
    if not motivo_bruto or motivo_bruto == "#N/A":
        return "Não informado"
    lista = re.sub(r'[\[\]"]', "", motivo_bruto).split(",")
    lista = [m.strip() for m in lista if m.strip() not in ("", "#N/A")]
    if len(lista) > 1:
        ultimo = lista.pop()
        return ", ".join(lista) + " e " + ultimo
    elif len(lista) == 1:
        return lista[0]
    return "Não informado"


def extrair_cliente(nome_op: str) -> tuple[str, str]:
    """Extrai identificador e nome do cliente de 'Nome da oportunidade'."""
    if not nome_op or nome_op == "#N/A" or "-" not in nome_op:
        return "N/A", "N/A"
    partes = nome_op.split("-")
    op_id = partes[0].strip()
    cliente = " ".join(partes[1:]).replace("Cliente:", "").replace("-", "").strip()
    return op_id, cliente


def montar_url_resposta(identificador: str, nome_oportunidade: str, acao: str) -> str:
    return (
        f"{APPS_SCRIPT_URL}"
        f"?id={quote(str(identificador))}"
        f"&nome_op={quote(str(nome_oportunidade))}"
        f"&acao={quote(acao)}"
    )


def montar_html_email(linha: pd.Series) -> str:
    """Gera o corpo HTML completo com destinatários, dados da OP, detalhes e botões."""
    identificador = str(linha.get("Identificador", ""))
    nome_op = str(linha.get("Nome da oportunidade", ""))
    empreendimento = str(linha.get("Empreendimento", ""))
    fase = str(linha.get("Fase", ""))

    op_id, cliente_nome = extrair_cliente(nome_op)
    motivos_limpos = formatar_motivos(str(linha.get("Motivo Reserva", "")))

    data_contrato = linha.get("Contrato gerado em")
    if isinstance(data_contrato, datetime):
        data_formatada = data_contrato.strftime("%d/%m/%Y")
    elif isinstance(data_contrato, str) and data_contrato.strip():
        data_formatada = data_contrato
    else:
        data_formatada = "N/A"

    n_corretor = validar_texto(linha.get("Contato Corretor Proprietario"))
    n_prop_op = validar_texto(linha.get("Proprietário da oportunidade"))
    n_gerente = validar_texto(linha.get("Oportunidade : Imobiliária : Gerente de Vendas"))
    n_prop_conta = validar_texto(linha.get("Oportunidade : Imobiliária : Proprietário da conta"))
    nomes_unicos = list(dict.fromkeys(
        [n for n in [n_corretor, n_prop_op, n_gerente, n_prop_conta] if n != "Não informado"]
    ))
    texto_destinatarios = formatar_linha_destinatarios(nomes_unicos)

    # Botões: tabela aninhada + borda escura externa (efeito premium no Outlook)
    _btn_link = (
        "font-size:14px;line-height:22px;font-family:Arial,Helvetica,sans-serif;font-weight:700;"
        "color:#ffffff;text-decoration:none;display:block;text-align:center;letter-spacing:0.12em;"
        "text-transform:uppercase;padding:16px 36px;mso-line-height-rule:exactly;mso-padding-alt:16px 36px;"
    )

    url_manter = montar_url_resposta(identificador, nome_op, ACAO_MANTER_VENDA)
    url_derrubar = montar_url_resposta(identificador, nome_op, ACAO_DERRUBAR_VENDA)

    # Espaço vertical estável entre seções (Outlook respeita height em td)
    def _espaco(h: int) -> str:
        # bgcolor explícito: senão o Outlook mostra o fundo externo como "faixa" / sombra
        return (
            f'<table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" '
            f'style="border-collapse:collapse;mso-table-lspace:0pt;mso-table-rspace:0pt;background-color:{EMAIL_BG};">'
            f'<tr><td height="{h}" bgcolor="{EMAIL_BG}" style="background-color:{EMAIL_BG};font-size:0;line-height:0;'
            f'mso-line-height-rule:exactly;border:0;box-shadow:none;">&nbsp;</td></tr></table>'
        )

    # Células: fundo branco, borda cinza neutra (sem azul-acinzentado tipo #94a3b8 / #cbd5e1)
    _st_lab = (
        f"background-color:{EMAIL_BG};border:1px solid {EMAIL_BORDA_CINZA};"
        "padding:16px 18px;text-align:left;vertical-align:middle;font-family:Arial,Helvetica,sans-serif;"
        f"color:#0f172a;mso-border-alt:solid {EMAIL_BORDA_CINZA} 1px;"
    )
    _st_val = (
        f"background-color:{EMAIL_BG};border:1px solid {EMAIL_BORDA_CINZA};padding:16px 18px;text-align:left;"
        "vertical-align:middle;font-family:Arial,Helvetica,sans-serif;"
        f"mso-border-alt:solid {EMAIL_BORDA_CINZA} 1px;"
    )

    # Títulos de seção: segunda célula com fundo branco (evita barra azul-claro por transparência)
    def _secao_titulo(texto: str) -> str:
        return f"""<table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="margin:0 0 8px;border-collapse:collapse;background-color:{EMAIL_BG};">
  <tr>
    <td width="5" bgcolor="{COR_VERMELHO}" style="font-size:0;line-height:0;mso-line-height-rule:exactly;background-color:{COR_VERMELHO};">&nbsp;</td>
    <td bgcolor="{EMAIL_BG}" style="background-color:{EMAIL_BG};padding:0 0 12px 14px;border-bottom:2px solid {COR_AZUL};">
      <span style="font-family:Arial,Helvetica,sans-serif;font-size:14px;font-weight:bold;color:{COR_AZUL};letter-spacing:0.08em;text-transform:uppercase;mso-line-height-rule:exactly;line-height:20px;">{texto}</span>
    </td>
  </tr>
</table>"""

    # Centralização vertical (equivalente a justify no eixo Y): tabela 100% + td valign="middle"
    _pad_ext = f"{EMAIL_MARGEM_MIN_V}px {EMAIL_MARGEM_MIN_H}px"

    return f"""\
<!DOCTYPE html>
<html lang="pt-BR" xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office" style="margin:0;padding:0;height:100%;">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="x-apple-disable-message-reformatting">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <title>Pendência Comercial</title>
  <style type="text/css">
    html, body {{ margin:0 !important; padding:0 !important; height:100% !important; }}
    .email-fill {{ width:100% !important; min-height:100vh !important; }}
    .email-vmid {{ vertical-align:middle !important; }}
    table, td {{ box-shadow:none !important; }}
  </style>
  <!--[if mso]>
  <noscript>
    <xml>
      <o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings>
    </xml>
  </noscript>
  <![endif]-->
</head>
<body style="margin:0;padding:0;min-height:100%;height:100%;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;background-color:{EMAIL_BG};">
  <table role="presentation" class="email-fill" width="100%" height="100%" border="0" cellspacing="0" cellpadding="0" bgcolor="{EMAIL_BG}" style="width:100%;min-height:100%;min-height:100vh;height:100%;background-color:{EMAIL_BG};border-collapse:collapse;mso-table-lspace:0pt;mso-table-rspace:0pt;">
    <tr>
      <td class="email-vmid" align="center" valign="middle" bgcolor="{EMAIL_BG}" style="padding:{_pad_ext};vertical-align:middle;text-align:center;mso-padding-alt:{_pad_ext};background-color:{EMAIL_BG};">
        <!--[if mso]>
        <table role="presentation" align="center" border="0" cellspacing="0" cellpadding="0" width="600"><tr><td width="600">
        <![endif]-->
        <table role="presentation" width="600" border="0" cellspacing="0" cellpadding="0" align="center" bgcolor="{EMAIL_BG}" style="max-width:600px;width:100%;margin:0 auto;background-color:{EMAIL_BG};border-collapse:collapse;mso-table-lspace:0pt;mso-table-rspace:0pt;border:1px solid {EMAIL_BORDA_CINZA};mso-border-alt:solid {EMAIL_BORDA_CINZA} 1px;">

          <tr>
            <td align="center" bgcolor="{COR_AZUL}" style="background-color:{COR_AZUL};padding:28px 24px 24px 24px;">
              <p style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:19px;font-weight:bold;color:#ffffff;text-align:center;letter-spacing:0.14em;text-transform:uppercase;mso-line-height-rule:exactly;line-height:26px;">
                Pendência Comercial<br/>
                <span style="font-size:13px;letter-spacing:0.2em;font-weight:normal;color:#ffffff;">Venda Facilitada</span>
              </p>
            </td>
          </tr>
          <tr>
            <td height="5" bgcolor="{COR_VERMELHO}" style="font-size:0;line-height:0;mso-line-height-rule:exactly;background-color:{COR_VERMELHO};">&nbsp;</td>
          </tr>

          <tr>
            <td align="left" valign="top" bgcolor="{EMAIL_BG}" style="padding:28px 26px 32px 26px;background-color:{EMAIL_BG};vertical-align:top;">

              <p style="margin:0 0 18px;font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:24px;color:#1f2937;text-align:center;mso-line-height-rule:exactly;">
                Olá, este é um lembrete para a resolução da seguinte <b>Venda Facilitada</b> que consta como pendente:
              </p>

              {_secao_titulo("Ação necessária")}
              {_espaco(12)}
              <p style="margin:0 auto 22px;font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:23px;color:#1f2937;text-align:center;mso-line-height-rule:exactly;max-width:520px;">
                Favor verificar a pendência e selecionar uma das opções abaixo.<br/>
                Ao clicar, será aberto um formulário para informar a <b>justificativa obrigatória</b> da decisão.
              </p>

              <table role="presentation" border="0" cellspacing="0" cellpadding="0" align="center" style="margin:0 auto 24px;border-collapse:collapse;mso-table-lspace:0pt;mso-table-rspace:0pt;background-color:{EMAIL_BG};">
                <tr>
                  <td align="center" valign="middle" style="padding:0 12px 12px 0;vertical-align:middle;">
                    <table role="presentation" border="0" cellspacing="0" cellpadding="0" style="border-collapse:collapse;mso-table-lspace:0pt;mso-table-rspace:0pt;">
                      <tr>
                        <td bgcolor="#0d4f2c" align="center" valign="middle" style="background-color:#0d4f2c;padding:3px;mso-padding-alt:3px;vertical-align:middle;">
                          <table role="presentation" border="0" cellspacing="0" cellpadding="0" width="100%" style="border-collapse:collapse;">
                            <tr>
                              <td align="center" valign="middle" bgcolor="#198754" style="background-color:#198754;vertical-align:middle;min-width:220px;">
                                <a href="{url_manter}" target="_blank" style="{_btn_link}background-color:#198754;">
                                  Manter venda
                                </a>
                              </td>
                            </tr>
                          </table>
                        </td>
                      </tr>
                    </table>
                  </td>
                  <td align="center" valign="middle" style="padding:0 0 12px 12px;vertical-align:middle;">
                    <table role="presentation" border="0" cellspacing="0" cellpadding="0" style="border-collapse:collapse;mso-table-lspace:0pt;mso-table-rspace:0pt;">
                      <tr>
                        <td bgcolor="#5c1018" align="center" valign="middle" style="background-color:#5c1018;padding:3px;mso-padding-alt:3px;vertical-align:middle;">
                          <table role="presentation" border="0" cellspacing="0" cellpadding="0" width="100%" style="border-collapse:collapse;">
                            <tr>
                              <td align="center" valign="middle" bgcolor="#c41e2a" style="background-color:#c41e2a;vertical-align:middle;min-width:220px;">
                                <a href="{url_derrubar}" target="_blank" style="{_btn_link}background-color:#c41e2a;">
                                  Derrubar venda
                                </a>
                              </td>
                            </tr>
                          </table>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>

              <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="margin:0 0 20px;border-collapse:collapse;border:1px solid {EMAIL_BORDA_CINZA};mso-border-alt:solid {EMAIL_BORDA_CINZA} 1px;background-color:{EMAIL_BG};">
                <tr>
                  <td width="5" bgcolor="{COR_VERMELHO}" style="font-size:0;line-height:0;mso-line-height-rule:exactly;background-color:{COR_VERMELHO};">&nbsp;</td>
                  <td valign="middle" align="center" bgcolor="{EMAIL_BG}" style="padding:18px 20px;background-color:{EMAIL_BG};vertical-align:middle;">
                    <p style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:22px;color:{COR_VERMELHO};font-weight:bold;text-align:center;mso-line-height-rule:exactly;">
                      Favor priorizar a tratativa desta unidade para avançarmos com o fechamento.
                    </p>
                  </td>
                </tr>
              </table>

              {_espaco(28)}
              <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="margin:0;border-collapse:collapse;border:1px solid {EMAIL_BORDA_CINZA};mso-border-alt:solid {EMAIL_BORDA_CINZA} 1px;background-color:{EMAIL_BG};">
                <tr>
                  <td width="5" bgcolor="{COR_AZUL}" style="font-size:0;line-height:0;mso-line-height-rule:exactly;background-color:{COR_AZUL};">&nbsp;</td>
                  <td valign="middle" bgcolor="{EMAIL_BG}" style="background-color:{EMAIL_BG};padding:20px 22px;vertical-align:middle;">
                    <p style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:22px;color:#0f172a;text-align:center;mso-line-height-rule:exactly;font-weight:bold;">
                      {texto_destinatarios}
                    </p>
                  </td>
                </tr>
              </table>

              {_espaco(32)}
              {_secao_titulo("Dados da oportunidade")}
              {_espaco(12)}
              <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="margin:0;border-collapse:collapse;border:1px solid {EMAIL_BORDA_CINZA};mso-border-alt:solid {EMAIL_BORDA_CINZA} 1px;font-size:14px;background-color:{EMAIL_BG};">
                <tr>
                  <td width="34%" valign="middle" bgcolor="{EMAIL_BG}" style="{_st_lab}"><b>Cliente</b></td>
                  <td valign="middle" bgcolor="{EMAIL_BG}" style="{_st_val}color:#1f2937;">{op_id} - {cliente_nome}</td>
                </tr>
                <tr>
                  <td width="34%" valign="middle" bgcolor="{EMAIL_BG}" style="{_st_lab}"><b>Motivo(s)</b></td>
                  <td valign="middle" bgcolor="{EMAIL_BG}" style="{_st_val}color:#1f2937;">{motivos_limpos}</td>
                </tr>
              </table>

              {_espaco(36)}
              {_secao_titulo("Detalhes da unidade")}
              {_espaco(12)}
              <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="margin:0;border-collapse:collapse;border:1px solid {EMAIL_BORDA_CINZA};mso-border-alt:solid {EMAIL_BORDA_CINZA} 1px;font-size:14px;background-color:{EMAIL_BG};">
                <tr>
                  <td width="34%" valign="middle" bgcolor="{EMAIL_BG}" style="{_st_lab}"><b>Empreendimento</b></td>
                  <td valign="middle" bgcolor="{EMAIL_BG}" style="{_st_val}color:#1f2937;">{empreendimento}</td>
                </tr>
                <tr>
                  <td width="34%" valign="middle" bgcolor="{EMAIL_BG}" style="{_st_lab}"><b>Unidade</b></td>
                  <td valign="middle" bgcolor="{EMAIL_BG}" style="{_st_val}color:#1f2937;">{identificador}</td>
                </tr>
                <tr>
                  <td width="34%" valign="middle" bgcolor="{EMAIL_BG}" style="{_st_lab}"><b>Fase atual</b></td>
                  <td valign="middle" bgcolor="{EMAIL_BG}" style="{_st_val}color:#1f2937;">
                    <table role="presentation" border="0" cellspacing="0" cellpadding="0" align="left" style="border-collapse:collapse;mso-table-lspace:0pt;mso-table-rspace:0pt;">
                      <tr>
                        <td bgcolor="{COR_VERMELHO}" align="center" valign="middle" style="background-color:{COR_VERMELHO};padding:10px 18px;vertical-align:middle;mso-padding-alt:10px 18px;">
                          <span style="font-family:Arial,Helvetica,sans-serif;font-size:12px;font-weight:bold;color:#ffffff;mso-line-height-rule:exactly;line-height:16px;">{fase}</span>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
                <tr>
                  <td width="34%" valign="middle" bgcolor="{EMAIL_BG}" style="{_st_lab}"><b>Contrato gerado em</b></td>
                  <td valign="middle" bgcolor="{EMAIL_BG}" style="{_st_val}color:#1f2937;">{data_formatada}</td>
                </tr>
                <tr>
                  <td width="34%" valign="middle" bgcolor="{EMAIL_BG}" style="{_st_lab}"><b>Valor real de venda</b></td>
                  <td valign="middle" bgcolor="{EMAIL_BG}" style="{_st_val}color:{COR_AZUL};font-weight:bold;font-size:15px;">{formatar_moeda(linha.get('Valor Real de Venda'))}</td>
                </tr>
              </table>

              {_espaco(36)}
              {_secao_titulo("Ação necessária")}
              {_espaco(14)}
              <p style="margin:0 auto 28px;font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:23px;color:#1f2937;text-align:center;mso-line-height-rule:exactly;max-width:520px;">
                Favor verificar a pendência e selecionar uma das opções abaixo.<br/>
                Ao clicar, será aberto um formulário para informar a <b>justificativa obrigatória</b> da decisão.
              </p>

              <table role="presentation" border="0" cellspacing="0" cellpadding="0" align="center" style="margin:0 auto 32px;border-collapse:collapse;mso-table-lspace:0pt;mso-table-rspace:0pt;background-color:{EMAIL_BG};">
                <tr>
                  <td align="center" valign="middle" style="padding:0 12px 12px 0;vertical-align:middle;">
                    <table role="presentation" border="0" cellspacing="0" cellpadding="0" style="border-collapse:collapse;mso-table-lspace:0pt;mso-table-rspace:0pt;">
                      <tr>
                        <td bgcolor="#0d4f2c" align="center" valign="middle" style="background-color:#0d4f2c;padding:3px;mso-padding-alt:3px;vertical-align:middle;">
                          <table role="presentation" border="0" cellspacing="0" cellpadding="0" width="100%" style="border-collapse:collapse;">
                            <tr>
                              <td align="center" valign="middle" bgcolor="#198754" style="background-color:#198754;vertical-align:middle;min-width:220px;">
                                <a href="{url_manter}" target="_blank" style="{_btn_link}background-color:#198754;">
                                  Manter venda
                                </a>
                              </td>
                            </tr>
                          </table>
                        </td>
                      </tr>
                    </table>
                  </td>
                  <td align="center" valign="middle" style="padding:0 0 12px 12px;vertical-align:middle;">
                    <table role="presentation" border="0" cellspacing="0" cellpadding="0" style="border-collapse:collapse;mso-table-lspace:0pt;mso-table-rspace:0pt;">
                      <tr>
                        <td bgcolor="#5c1018" align="center" valign="middle" style="background-color:#5c1018;padding:3px;mso-padding-alt:3px;vertical-align:middle;">
                          <table role="presentation" border="0" cellspacing="0" cellpadding="0" width="100%" style="border-collapse:collapse;">
                            <tr>
                              <td align="center" valign="middle" bgcolor="#c41e2a" style="background-color:#c41e2a;vertical-align:middle;min-width:220px;">
                                <a href="{url_derrubar}" target="_blank" style="{_btn_link}background-color:#c41e2a;">
                                  Derrubar venda
                                </a>
                              </td>
                            </tr>
                          </table>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>

              <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="margin:0 0 8px;border-collapse:collapse;border:1px solid {EMAIL_BORDA_CINZA};mso-border-alt:solid {EMAIL_BORDA_CINZA} 1px;background-color:{EMAIL_BG};">
                <tr>
                  <td width="5" bgcolor="{COR_VERMELHO}" style="font-size:0;line-height:0;mso-line-height-rule:exactly;background-color:{COR_VERMELHO};">&nbsp;</td>
                  <td valign="middle" align="center" bgcolor="{EMAIL_BG}" style="padding:18px 20px;background-color:{EMAIL_BG};vertical-align:middle;">
                    <p style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:22px;color:{COR_VERMELHO};font-weight:bold;text-align:center;mso-line-height-rule:exactly;">
                      Favor priorizar a tratativa desta unidade para avançarmos com o fechamento.
                    </p>
                  </td>
                </tr>
              </table>

              {_espaco(24)}
              <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="margin:0;border-collapse:collapse;border-top:2px solid {COR_AZUL};mso-border-top-alt:solid {COR_AZUL} 2px;background-color:{EMAIL_BG};">
                <tr>
                  <td align="center" valign="middle" bgcolor="{EMAIL_BG}" style="padding:22px 12px 8px 12px;vertical-align:middle;background-color:{EMAIL_BG};">
                    <p style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:18px;color:#555555;text-align:center;mso-line-height-rule:exactly;">
                      Atenciosamente,<br/><b style="color:{COR_AZUL};">Direcional Engenharia - RJ</b>
                    </p>
                  </td>
                </tr>
              </table>

            </td>
          </tr>
        </table>
        <!--[if mso]>
        </td></tr></table>
        <![endif]-->
      </td>
    </tr>
  </table>
</body>
</html>"""


def montar_html_email_followup_manter(linha: pd.Series) -> str:
    """
    Follow-up para casos já respondidos como MANTER VENDA.
    Mantém layout base e altera o texto de abertura/ação.
    """
    html_base = montar_html_email(linha)
    antigo = (
        "Olá, este é um lembrete para a resolução da seguinte <b>Venda Facilitada</b> que consta como pendente:"
    )
    novo = (
        "Você resolveu <b>manter</b> esta venda anteriormente.<br/>"
        "Houve algum progresso? A decisão mudou?"
    )
    html_base = html_base.replace(antigo, novo)
    antigo2 = (
        "Favor verificar a pendência e selecionar uma das opções abaixo.<br/>\n"
        "                Ao clicar, será aberto um formulário para informar a <b>justificativa obrigatória</b> da decisão."
    )
    novo2 = (
        "Se a decisão mudou, clique em <b>Derrubar venda</b>.<br/>\n"
        "                Se não mudou, clique em <b>Manter venda</b> e registre a atualização."
    )
    return html_base.replace(antigo2, novo2)


def enviar_pendencias() -> None:
    """Fluxo principal: ler fonte → gravar 'Não Respondidos' → enviar emails."""

    if APPS_SCRIPT_URL == "COLE_AQUI_A_URL_DO_APPS_SCRIPT":
        print("❌ Defina a variável APPS_SCRIPT_URL.")
        return

    print("Conectando ao Google Sheets...")
    gc = conectar_gspread()
    controle = _carregar_controle_envios()

    print("Carregando planilha-fonte...")
    df = carregar_fonte(gc)
    print(f"Linhas na aba '{ABA_FONTE}': {len(df)}")
    print("Carregando status de respostas...")
    status_respondidos = _carregar_status_respondidos(gc)
    _atualizar_snapshot_respostas(controle, status_respondidos)
    _salvar_controle_envios(controle)

    mask = (
        df["Fase"].isin(FASES_ALVO)
        & df["email_corretor"].notna()
        & (df["email_corretor"].astype(str).str.strip() != "")
        & (df["email_corretor"].astype(str).str.strip() != "#N/A")
    )
    pendencias = df[mask].copy()

    if pendencias.empty:
        print("✅ Nenhuma pendência encontrada.")
        return

    n_antes_filtros = len(pendencias)
    fase_series = pendencias["Fase"].astype(str).str.strip().str.casefold()
    fases_bloqueadas_cf = {f.strip().casefold() for f in FASES_BLOQUEADAS_ENVIO}
    bloq_fase = fase_series.isin(fases_bloqueadas_cf)
    n_bloq_fase = int(bloq_fase.sum())
    pendencias = pendencias.loc[~bloq_fase].copy()
    col_emp = "Empreendimento"
    if col_emp not in pendencias.columns:
        print(f"⚠️ Coluna '{col_emp}' ausente na fonte — exclusão por empreendimento ignorada.")
        bloq_emp = pd.Series(False, index=pendencias.index)
    else:
        bloq_emp = pendencias[col_emp].map(_empreendimento_bloqueia_envio)
    n_bloq_emp = int(bloq_emp.sum())
    pendencias = pendencias.loc[~bloq_emp].copy()
    respostas_norm = pendencias["Nome da oportunidade"].map(
        lambda n: status_respondidos.get(str(n).strip(), {}).get("resposta_norm", "")
    )
    bloqueia_derrubar = respostas_norm == "DERRUBAR VENDA"
    n_bloq_derrubar = int(bloqueia_derrubar.sum())
    pendencias = pendencias.loc[~bloqueia_derrubar].copy()
    respostas_norm = respostas_norm.loc[pendencias.index]
    pendencias["__tipo_email"] = respostas_norm.map(
        lambda r: "followup_manter" if r == "MANTER VENDA" else "pendencia"
    )
    n_followup_manter = int((pendencias["__tipo_email"] == "followup_manter").sum())

    if n_bloq_emp:
        print(
            f"⏭️  {n_bloq_emp} linha(s) ignorada(s) (empreendimento em {EMPREENDIMENTOS_EXCLUIR_ENVIO})."
        )
    if n_bloq_fase:
        print(
            f"⏭️  {n_bloq_fase} linha(s) ignorada(s) (fase em {FASES_BLOQUEADAS_ENVIO})."
        )
    if n_bloq_derrubar:
        print(
            f"⏭️  {n_bloq_derrubar} linha(s) ignorada(s) (já respondidas como DERRUBAR VENDA na aba '{ABA_RESPONDIDOS}')."
        )

    if pendencias.empty:
        print(
            f"✅ Nenhuma pendência a enviar após filtros "
            f"({n_antes_filtros} na seleção inicial; {n_bloq_fase} por fase; "
            f"{n_bloq_emp} por empreendimento; {n_bloq_derrubar} por DERRUBAR)."
        )
        return

    total = len(pendencias)
    print(
        f"📧 {total} pendência(s) a enviar "
        f"(de {n_antes_filtros} na seleção por fase/e-mail; {n_followup_manter} follow-up(s) para MANTER)."
    )

    print("Gravando na aba 'Não Respondidos'...")
    gravar_nao_respondidos(gc, pendencias)

    print("Conectando ao Outlook Desktop...")
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
    except Exception as e:
        print(f"❌ Não foi possível conectar ao Outlook: {e}")
        print("   Certifique-se de que o Outlook está aberto.")
        return

    email_excluido_lower = EMAIL_EXCLUIDO.strip().lower()

    for i, (_, linha) in enumerate(pendencias.iterrows(), start=1):
        email_corretor = validar_email(linha.get("email_corretor"))
        if not email_corretor:
            continue
        if email_corretor.strip().lower() == email_excluido_lower:
            continue

        destinatario = EMAIL_TESTE if MODO_TESTE else email_corretor
        identificador = str(linha.get("Identificador", ""))
        nome_op = str(linha.get("Nome da oportunidade", ""))
        empreendimento = str(linha.get("Empreendimento", ""))
        tipo_email = str(linha.get("__tipo_email", "pendencia"))
        op_id, cliente_nome = extrair_cliente(nome_op)

        lista_cc_suja = [
            linha.get("email_proprietário"),
            linha.get("email_comercialrj"),
            linha.get("email_gerente"),
            linha.get("email_prop_conta"),
        ]
        lista_cc = list(dict.fromkeys(
            v for mail_raw in lista_cc_suja
            if (v := validar_email(mail_raw))
            and v != email_corretor
            and v.strip().lower() != email_excluido_lower
        ))

        try:
            mail = outlook.CreateItem(0)
            mail.To = destinatario
            if lista_cc and not MODO_TESTE:
                mail.CC = "; ".join(lista_cc)
            if tipo_email == "followup_manter":
                mail.Subject = f"🔄 FOLLOW-UP MANTER: {op_id} - {cliente_nome} - {empreendimento}"
                mail.HTMLBody = montar_html_email_followup_manter(linha)
            else:
                mail.Subject = f"⚠️ PENDÊNCIA: {op_id} - {cliente_nome} - {empreendimento}"
                mail.HTMLBody = montar_html_email(linha)

            time.sleep(random.uniform(1, 4))
            mail.Send()
            qtd = _registrar_envio(controle, identificador, nome_op, tipo_email)
            _salvar_controle_envios(controle)
            print(
                f"[{i}/{total}] ✅ {identificador} → {destinatario} (real: {email_corretor}) "
                f"[tipo={tipo_email}; envio #{qtd}]"
            )

            if i < total:
                pausa = random.randint(15, 30)
                print(f"   Aguardando {pausa}s...")
                time.sleep(pausa)

        except Exception as e_envio:
            print(f"[{i}/{total}] ❌ Erro ({email_corretor}): {e_envio}")

    print(f"\n🚀 {total} e-mail(s) processado(s)!")


if __name__ == "__main__":
    enviar_pendencias()
