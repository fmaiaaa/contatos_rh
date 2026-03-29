# -*- coding: utf-8 -*-
"""
Camadas de segurança para a ficha cadastral (dados sensíveis).

Importante:
- Não existe “bloqueio total” de DevTools/inspeção no navegador (o controle é do usuário).
- O que fazemos: limitar taxa de envio, heurísticas de cliente, endurecimento do servidor
  (config.toml), dissuasão leve no cliente e metadados (noindex).
- Para produção, use HTTPS, WAF (ex.: Cloudflare Bot Fight / reCAPTCHA Enterprise) e políticas
  de privacidade no provedor de hospedagem.
"""

from __future__ import annotations

import os
import time

import streamlit as st

# Janela curta: máximo de tentativas de envio por sessão
_RL_JANELA_S = int(os.environ.get("FICHA_RL_JANELA_S", "600"))  # 10 min
_RL_MAX_JANELA = int(os.environ.get("FICHA_RL_MAX_JANELA", "4"))
_RL_MAX_DIA = int(os.environ.get("FICHA_RL_MAX_DIA", "12"))
# Tempo mínimo (s) entre abrir o formulário e enviar (anti-script imediato)
_TMIN_ENVIO_S = int(os.environ.get("FICHA_TMIN_ENVIO_S", "12"))

_UA_BLOQUEIO_SUBSTR = (
    "curl/",
    "wget/",
    "python-requests",
    "scrapy",
    "aiohttp",
    "httpx",
    "go-http-client",
    "java/",
    "libwww",
    "httpclient",
    "axios/",
)


def _headers() -> dict[str, str]:
    try:
        ctx = getattr(st, "context", None)
        if ctx is None:
            return {}
        hd = getattr(ctx, "headers", None)
        if hd is None:
            return {}
        if isinstance(hd, dict):
            return {str(k): str(v) for k, v in hd.items()}
        return {str(k): str(v) for k, v in dict(hd).items()}
    except Exception:
        return {}


def user_agent() -> str:
    h = _headers()
    return (h.get("User-Agent") or h.get("user-agent") or "").strip()


def user_agent_bloqueado() -> bool:
    if os.environ.get("FICHA_DISABLE_UA_CHECK", "").strip().lower() in ("1", "true", "yes", "on"):
        return False
    ua = user_agent().lower()
    if not ua:
        # Sem User-Agent (Streamlit sem context.headers ou proxy) — só bloqueia se forçado
        return os.environ.get("FICHA_BLOCK_EMPTY_UA", "").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
    return any(s in ua for s in _UA_BLOQUEIO_SUBSTR)


def _agora() -> float:
    return time.time()


def iniciar_sessao_formulario() -> None:
    """Marca o instante em que a sessão passou a usar o fluxo do formulário."""
    ss = st.session_state
    if ss.get("ficha_seg_t0") is None:
        ss["ficha_seg_t0"] = _agora()


def tempo_minimo_envio_ok() -> tuple[bool, str]:
    if os.environ.get("FICHA_DISABLE_TMIN", "").strip().lower() in ("1", "true", "yes", "on"):
        return True, ""
    ss = st.session_state
    t0 = ss.get("ficha_seg_t0")
    if t0 is None:
        iniciar_sessao_formulario()
        t0 = ss.get("ficha_seg_t0")
    try:
        t0f = float(t0)
    except (TypeError, ValueError):
        t0f = _agora()
    dt = _agora() - t0f
    if dt < _TMIN_ENVIO_S:
        return False, (
            f"Por segurança, aguarde alguns segundos antes de enviar "
            f"(mínimo {_TMIN_ENVIO_S}s na página)."
        )
    return True, ""


def limite_taxa_ok() -> tuple[bool, str]:
    """Limita tentativas de envio por sessão (mitiga abuso e scripts)."""
    if os.environ.get("FICHA_DISABLE_RL", "").strip().lower() in ("1", "true", "yes", "on"):
        return True, ""
    ss = st.session_state
    now = _agora()
    ts: list[float] = ss.get("ficha_rl_envios_ts") or []
    if not isinstance(ts, list):
        ts = []
    ts = [float(t) for t in ts if isinstance(t, (int, float))]
    ts = [t for t in ts if now - t < 86400]
    recentes = [t for t in ts if now - t < _RL_JANELA_S]
    if len(recentes) >= _RL_MAX_JANELA:
        return False, "Muitas tentativas de envio em pouco tempo. Aguarde e tente novamente."
    if len(ts) >= _RL_MAX_DIA:
        return False, "Limite diário de tentativas de envio atingido. Tente novamente mais tarde."
    return True, ""


def registrar_tentativa_envio() -> None:
    """Chamar ao processar um clique em Enviar (antes da validação de campos)."""
    ss = st.session_state
    now = _agora()
    ts: list[float] = ss.get("ficha_rl_envios_ts") or []
    if not isinstance(ts, list):
        ts = []
    ts = [float(t) for t in ts if isinstance(t, (int, float)) and now - t < 86400]
    ts.append(now)
    ss["ficha_rl_envios_ts"] = ts


def honeypot_ok() -> bool:
    """Campo oculto: se preenchido, trata como bot (não revelar ao cliente)."""
    v = st.session_state.get("ficha_hp_website")
    if v is None:
        return True
    if isinstance(v, str) and v.strip():
        return False
    return True


def verificar_antes_envio() -> tuple[bool, str]:
    """
    Ordem: UA → tempo mínimo → honeypot (se existir campo) → taxa.
    Ao passar, registra a tentativa na janela de rate limit.
    """
    if user_agent_bloqueado():
        return False, "Acesso não autorizado a partir deste cliente."
    ok, msg = tempo_minimo_envio_ok()
    if not ok:
        return False, msg
    if not honeypot_ok():
        return False, "Não foi possível concluir o envio. Atualize a página e tente novamente."
    ok, msg = limite_taxa_ok()
    if not ok:
        return False, msg
    registrar_tentativa_envio()
    return True, ""


def injetar_cliente_e_meta() -> None:
    """
    Injeta no documento pai (uma vez): meta robots, referrer, dissuasão leve a DevTools.
    Desative com FICHA_DISABLE_CLIENT_HARDENING=1 (útil para debug acessível).
    """
    if os.environ.get("FICHA_DISABLE_CLIENT_HARDENING", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return
    try:
        import streamlit.components.v1 as components
    except ImportError:
        return

    noindex = os.environ.get("FICHA_NOINDEX", "1").strip().lower() not in ("0", "false", "no", "off")

    meta_robots = (
        "var m=document.createElement('meta');m.name='robots';m.content='noindex,nofollow';hd.appendChild(m);"
        if noindex
        else ""
    )
    ref = (
        "var r=document.createElement('meta');r.name='referrer';r.content='strict-origin-when-cross-origin';hd.appendChild(r);"
    )

    html = f"""
<div style="display:none" aria-hidden="true">sec</div>
<script>
(function() {{
  try {{
    var p = window.parent;
    if (!p || p.__fichaSegInit) return;
    p.__fichaSegInit = true;
    var doc = p.document;
    var hd = doc.head;
    if (!hd) return;
    {meta_robots}
    {ref}
    doc.addEventListener('contextmenu', function(e) {{ e.preventDefault(); }}, true);
    doc.addEventListener('keydown', function(e) {{
      if (e.key === 'F12') {{ e.preventDefault(); return false; }}
      if (e.ctrlKey && e.shiftKey && (e.key === 'I' || e.key === 'J' || e.key === 'C')) {{
        e.preventDefault(); return false;
      }}
      if (e.ctrlKey && (e.key === 'u' || e.key === 'U')) {{ e.preventDefault(); return false; }}
    }}, true);
  }} catch (err) {{}}
}})();
</script>
"""
    components.html(html, height=0, scrolling=False)

