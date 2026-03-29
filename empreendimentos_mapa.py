# -*- coding: utf-8 -*-
"""
Mapa interativo dos empreendimentos Direcional (RJ e região).
Coordenadas obtidas por geocodificação aproximada dos endereços (OpenStreetMap).
"""

from __future__ import annotations

import html
from collections import OrderedDict
from typing import Any

# Empreendimento | Bairro | Endereço completo + lat/lon para o mapa
EMPREENDIMENTOS: list[dict[str, Any]] = [
    {
        "nome": "Conquista Florianópolis",
        "bairro": "Praça Seca",
        "endereco": "R. Florianópolis, 920 - Praça Seca, Rio de Janeiro - RJ, 21321-050",
        "lat": -22.903392,
        "lon": -43.349969,
    },
    {
        "nome": "Conquista Itanhangá Green",
        "bairro": "Itanhangá",
        "endereco": "Estr. de Jacarepaguá, 2757 - Itanhangá, Rio de Janeiro - RJ, 22755-158",
        "lat": -22.988142,
        "lon": -43.326913,
    },
    {
        "nome": "Conquista Norte Clube",
        "bairro": "Inhaúma",
        "endereco": "Estrada Adhemar Bebiano, 3715 - Engenho da Rainha, Rio de Janeiro - RJ, 20766-450",
        "lat": -22.865480,
        "lon": -43.301218,
    },
    {
        "nome": "Conquista Oceânica",
        "bairro": "Niterói",
        "endereco": "Rod. Amaral Peixoto, 0 - Várzea das Mocas, São Gonçalo - RJ, 24753-559",
        "lat": -22.897669,
        "lon": -42.986709,
    },
    {
        "nome": "Conquista Parque Iguaçu",
        "bairro": "Nova Iguaçu",
        "endereco": "Av. Abílio Augusto Távora, 3505 - Palhada, Nova Iguaçu - RJ, 26275-580",
        "lat": -22.761136,
        "lon": -43.459759,
    },
    {
        "nome": "Direcional Conquista Max Norte",
        "bairro": "Pavuna",
        "endereco": "Rua Edgar Loureiro Valdetaro, 162 - Pavuna, Rio de Janeiro - RJ, 21520-760",
        "lat": -22.812193,
        "lon": -43.359281,
    },
    {
        "nome": "Direcional Vert Alcântara",
        "bairro": "São Gonçalo",
        "endereco": "Estr. dos Menezes - Alcantara, São Gonçalo - RJ, 24451-230",
        "lat": -22.821628,
        "lon": -43.006536,
    },
    {
        "nome": "Nova Caxias Fun",
        "bairro": "Duque de Caxias",
        "endereco": "R. Salutaris, 54 - Vila Ouro Preto, Duque de Caxias - RJ, 25065-007",
        "lat": -22.769324,
        "lon": -43.284303,
    },
    {
        "nome": "Nova Caxias Up",
        "bairro": "Duque de Caxias",
        "endereco": "R. Salutaris, 54 - Vila Ouro Preto, Duque de Caxias - RJ, 25065-007",
        "lat": -22.769524,
        "lon": -43.284503,
    },
    {
        "nome": "Reserva do Sol",
        "bairro": "Curicica",
        "endereco": "R. Goianinha, 280 - Curicica, Rio de Janeiro - RJ, 22780-760",
        "lat": -22.950506,
        "lon": -43.380910,
    },
    {
        "nome": "Residencial Jerivá",
        "bairro": "Campo Grande",
        "endereco": "R. Projetada A, 270 - Campo Grande, Rio de Janeiro - RJ, 23040-652",
        "lat": -22.930526,
        "lon": -43.573234,
    },
    {
        "nome": "Residencial Laranjeiras",
        "bairro": "Laranjeiras",
        "endereco": "R. Projetada A, 270 - Campo Grande, Rio de Janeiro - RJ, 23040-652",
        "lat": -22.930726,
        "lon": -43.573434,
    },
    {
        "nome": "Soul Samba (Vert Soul Samba)",
        "bairro": "Inhaúma",
        "endereco": "Estrada Adhemar Bebiano, 2576 - Inhaúma, Rio de Janeiro - RJ, 20766-720",
        "lat": -22.871804,
        "lon": -43.273545,
    },
    {
        "nome": "Viva Vida Realengo",
        "bairro": "Realengo",
        "endereco": "R. Itajaí, n° 15 - Realengo, Rio de Janeiro - RJ, 21730-200",
        "lat": -22.862682,
        "lon": -43.438208,
    },
    {
        "nome": "Viva Vida Recanto Clube",
        "bairro": "Guaratiba",
        "endereco": "Rua Aloés, 300 - Guaratiba, Rio de Janeiro - RJ",
        "lat": -22.965865,
        "lon": -43.649976,
    },
    {
        "nome": "Inn Barra Olímpica",
        "bairro": "Barra Olímpica",
        "endereco": "Estr. dos Bandeirantes, 2856 - Jacarepaguá, Rio de Janeiro - RJ, 22775-110",
        "lat": -22.961105,
        "lon": -43.393837,
    },
    {
        "nome": "UNIQ Condomínio Clube",
        "bairro": "Nova Iguaçu",
        "endereco": "R. Elídio Madeira, 146 - Luz, Nova Iguaçu - RJ, 26260-270",
        "lat": -22.760950,
        "lon": -43.472950,
    },
]


def _popup_html(emp: dict[str, Any]) -> str:
    nome = html.escape(emp["nome"])
    bairro = html.escape(emp["bairro"])
    end = html.escape(emp["endereco"])
    return (
        f'<div style="min-width:220px;max-width:320px;font-family:sans-serif;font-size:13px;">'
        f"<strong>{nome}</strong><br/>"
        f'<span style="color:#64748b;">{bairro}</span><br/><br/>'
        f"{end}</div>"
    )


def _agrupar_por_endereco() -> list[list[dict[str, Any]]]:
    """Empreendimentos no mesmo endereço ficam no mesmo grupo (um pin no mapa)."""
    buckets: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for emp in EMPREENDIMENTOS:
        chave = (emp.get("endereco") or "").strip()
        if chave not in buckets:
            buckets[chave] = []
        buckets[chave].append(emp)
    return list(buckets.values())


def _tooltip_grupo(grupo: list[dict[str, Any]]) -> str:
    """Texto do hover: um nome ou vários separados por · quando compartilham endereço."""
    nomes = [e["nome"] for e in grupo]
    return " · ".join(nomes)


def _popup_html_grupo(grupo: list[dict[str, Any]]) -> str:
    """Popup quando há mais de um empreendimento no mesmo endereço."""
    blocos: list[str] = []
    for emp in grupo:
        nome = html.escape(emp["nome"])
        bairro = html.escape(emp["bairro"])
        blocos.append(f"<strong>{nome}</strong><br/><span style=\"color:#64748b;\">{bairro}</span>")
    end = html.escape(grupo[0]["endereco"])
    sep = '<hr style="margin:10px 0;border:none;border-top:1px solid #e2e8f0;"/>'
    corpo = sep.join(blocos)
    return (
        f'<div style="min-width:220px;max-width:340px;font-family:sans-serif;font-size:13px;">'
        f"{corpo}<br/><br/>{end}</div>"
    )


def criar_folium_mapa() -> Any:
    """Constrói o mapa Folium (zoom +/- no controle; tela cheia via plugin)."""
    import folium
    from folium.plugins import Fullscreen

    grupos = _agrupar_por_endereco()
    lats: list[float] = []
    lons: list[float] = []
    for g in grupos:
        lats.append(sum(e["lat"] for e in g) / len(g))
        lons.append(sum(e["lon"] for e in g) / len(g))
    center_lat = sum(lats) / len(lats)
    center_lon = sum(lons) / len(lons)

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=10,
        tiles="OpenStreetMap",
        control_scale=True,
    )
    Fullscreen(
        position="topright",
        title="Tela cheia",
        title_cancel="Sair da tela cheia",
        force_separate_button=True,
    ).add_to(m)

    for grupo in grupos:
        lat = sum(e["lat"] for e in grupo) / len(grupo)
        lon = sum(e["lon"] for e in grupo) / len(grupo)
        if len(grupo) == 1:
            popup_html = _popup_html(grupo[0])
        else:
            popup_html = _popup_html_grupo(grupo)
        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_html, max_width=360),
            tooltip=_tooltip_grupo(grupo),
        ).add_to(m)

    bounds = [[min(lats), min(lons)], [max(lats), max(lons)]]
    m.fit_bounds(bounds, padding=(24, 24))
    return m


def render_mapa_empreendimentos_streamlit(
    altura_px: int = 420,
    *,
    streamlit_key: str = "mapa_empreendimentos_folium",
) -> None:
    """Exibe o mapa no Streamlit com `streamlit-folium`."""
    try:
        from streamlit_folium import st_folium
    except ImportError:
        import streamlit as st

        st.warning(
            "Para ver o mapa dos empreendimentos, instale: **pip install folium streamlit-folium**"
        )
        return

    m = criar_folium_mapa()
    st_folium(
        m,
        width=None,
        height=altura_px,
        use_container_width=True,
        returned_objects=[],
        key=streamlit_key,
    )
