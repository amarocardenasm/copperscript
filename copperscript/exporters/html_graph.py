"""Exportador a una página HTML con el grafo interactivo (Cytoscape.js).

=== IMPLEMENTACIÓN DE REFERENCIA (rama spike/v0.1-referencia) ===

Es el "abuelo" de la futura interfaz web local (ADR-002): un solo archivo
HTML que se abre con doble clic y muestra el grafo del caso.

ATAJO DEL PROTOTIPO: Cytoscape.js se carga desde un CDN. Eso rompe RNF2
(funcionar sin internet) y RNF3 (sin recursos externos). En `main` la
librería debe ir incluida dentro del paquete (ADR-006).
"""

from __future__ import annotations

import html
import json
from pathlib import Path

from copperscript.core.store import Caso

_CDN_CYTOSCAPE = "https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.30.2/cytoscape.min.js"

# Un color por tipo de entidad, para distinguirlas de un vistazo.
_COLORES = {
    "domain-name": "#3b82c4",
    "ipv4-addr": "#7a5cc4",
    "ipv6-addr": "#7a5cc4",
    "email-addr": "#c4583b",
    "url": "#6b7280",
    "username": "#2f7a68",
    "user-account": "#5fa58f",
    "identity": "#c49a3b",
    "x-otro": "#9ca3af",
}


def exportar_html(caso: Caso) -> Path:
    """Escribe exports/grafo.html y devuelve su ruta."""
    # Cytoscape recibe "elementos": nodos y aristas en un mismo arreglo JSON.
    elementos = []
    for e in caso.entidades():
        elementos.append(
            {
                "data": {
                    "id": f"n{e.id}",
                    "label": e.valor,
                    "tipo": str(e.tipo),
                    "confianza": e.confianza,
                    "color": _COLORES.get(str(e.tipo), "#9ca3af"),
                }
            }
        )
    for r in caso.relaciones():
        elementos.append(
            {
                "data": {
                    "id": f"r{r.id}",
                    "source": f"n{r.origen_id}",
                    "target": f"n{r.destino_id}",
                    "label": r.tipo,
                }
            }
        )

    nombre = caso.metadatos().get("nombre", "caso")
    # Al meter JSON dentro de <script>, "</" podría cerrar la etiqueta antes
    # de tiempo (y es una vía clásica de inyección). Lo escapamos.
    datos = json.dumps(elementos, ensure_ascii=False).replace("</", "<\\/")
    pagina = _PLANTILLA.replace("__TITULO__", html.escape(nombre))
    pagina = pagina.replace("__CDN__", _CDN_CYTOSCAPE).replace("__DATOS__", datos)

    destino = caso.carpeta_exports / "grafo.html"
    destino.write_text(pagina, encoding="utf-8")
    return destino


_PLANTILLA = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITULO__ · copperscript</title>
<style>
  html, body { margin: 0; height: 100%; font-family: system-ui, sans-serif; background: #f7f5f2; }
  #grafo { position: absolute; inset: 48px 0 0 0; }
  header { height: 48px; display: flex; align-items: center; gap: 12px; padding: 0 16px; }
  header small { color: #6b645c; }
</style>
<script src="__CDN__"></script>
</head>
<body>
<header><strong>__TITULO__</strong><small>Línea punteada = por verificar (confianza &lt; 0.5)</small></header>
<div id="grafo"></div>
<script>
const elementos = __DATOS__;
cytoscape({
  container: document.getElementById("grafo"),
  elements: elementos,
  layout: { name: "cose", animate: false },   // "cose" = layout de fuerzas: los nodos conectados se atraen
  style: [
    { selector: "node", style: {
        "background-color": "data(color)", "label": "data(label)",
        "font-size": 10, "text-valign": "bottom", "text-margin-y": 4,
        "width": "mapData(confianza, 0, 1, 14, 34)",   // más confianza = nodo más grande
        "height": "mapData(confianza, 0, 1, 14, 34)" } },
    { selector: "node[confianza < 0.5]", style: {
        "border-width": 2, "border-style": "dashed", "border-color": "#a8552c" } },
    { selector: "edge", style: {
        "curve-style": "bezier", "target-arrow-shape": "triangle", "width": 1.5,
        "line-color": "#c9c2b8", "target-arrow-color": "#c9c2b8",
        "label": "data(label)", "font-size": 8, "color": "#6b645c" } }
  ]
});
</script>
</body>
</html>
"""
