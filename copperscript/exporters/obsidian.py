"""Exportador a Obsidian.

=== IMPLEMENTACIÓN DE REFERENCIA (rama spike/v0.1-referencia) ===

Genera una "bóveda" (carpeta de notas Markdown) a partir del caso:

    exports/obsidian/
    ├── domain-name/ejemplo.cl.md
    ├── username/amaro_dev.md
    └── user-account/github.com_amaro_dev.md

Cada nota lleva frontmatter YAML (para el plugin Dataview) y enlaces
[[...]] a sus vecinos, así la vista de grafo de Obsidian muestra el caso.

Recuerda ADR-003: Obsidian es una VISTA. La fuente de verdad es case.sqlite.
Por eso este exportador borra y regenera la carpeta completa cada vez:
editar estas notas a mano no cambia el caso.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from copperscript.core.models import Entidad
from copperscript.core.store import Caso

# Caracteres prohibidos en nombres de archivo (Windows) o con significado
# especial en los enlaces de Obsidian ([[ ]], #, ^, |).
_PROHIBIDOS = re.compile(r'[\\/:*?"<>|#^\[\]]+')

UMBRAL_POR_VERIFICAR = 0.5


def exportar_obsidian(caso: Caso, minimo: float = 0.0) -> Path:
    """Regenera la bóveda y devuelve su carpeta.

    minimo: solo exporta entidades con confianza >= minimo (y, si el caso
    tiene anclas, con atribución >= minimo). Ver OPTIMIZACIÓN más abajo.
    """
    destino = caso.carpeta_exports / "obsidian"
    if destino.exists():
        shutil.rmtree(destino)  # regenerar desde cero: la base de datos manda

    # OPTIMIZACIÓN (bitácora, entrada 005): el perfil mostró que el 70% del
    # tiempo es abrir archivos en el disco, uno por entidad. Eso no se arregla
    # con código más rápido: se arregla escribiendo MENOS archivos. Y es lo
    # útil, además: una bóveda con 40.000 notas es inusable en Obsidian.
    entidades = {
        e.id: e
        for e in caso.entidades()
        if e.confianza >= minimo and (e.atribucion is None or e.atribucion >= minimo)
    }
    nombres = _nombres_unicos(entidades.values())

    # Una sola consulta para todas las relaciones, agrupadas en memoria,
    # en vez de una consulta de vecinos por cada entidad.
    vecinos: dict[int, list[str]] = {}
    for relacion in caso.relaciones():
        if relacion.origen_id in entidades and relacion.destino_id in entidades:
            o, d = relacion.origen_id, relacion.destino_id
            # La flecha indica la dirección real de la relación.
            vecinos.setdefault(o, []).append(f"- {relacion.tipo} → [[{nombres[d]}]]")
            vecinos.setdefault(d, []).append(f"- {relacion.tipo} ← [[{nombres[o]}]]")

    carpetas_creadas: set[Path] = set()
    for entidad in entidades.values():
        carpeta = destino / str(entidad.tipo)
        if carpeta not in carpetas_creadas:  # mkdir una vez por tipo, no por nota
            carpeta.mkdir(parents=True, exist_ok=True)
            carpetas_creadas.add(carpeta)
        nota = carpeta / f"{nombres[entidad.id]}.md"
        nota.write_text(_contenido_nota(entidad, vecinos.get(entidad.id, [])), encoding="utf-8")
    return destino


def _contenido_nota(entidad: Entidad, vecinos: list[str]) -> str:
    por_verificar = str(entidad.confianza < UMBRAL_POR_VERIFICAR).lower()
    # El valor va entre comillas en el YAML: un valor como "no" o "1:2"
    # se interpretaría como booleano u hora si no las lleva.
    valor_yaml = entidad.valor.replace('"', '\\"')
    partes = [
        "---",
        f"tipo: {entidad.tipo}",
        f'valor: "{valor_yaml}"',
        f"confianza: {entidad.confianza}",
        f"por_verificar: {por_verificar}",
        # ADR-013 (spike): solo aparece si el caso tiene anclas.
        *([f"atribucion: {entidad.atribucion}"] if entidad.atribucion is not None else []),
        f"copperscript_id: {entidad.id}",
        "---",
        "",
        f"# {entidad.valor}",
        "",
        "## Relaciones",
        "",
        *(vecinos or ["_Sin relaciones._"]),
        "",
    ]
    return "\n".join(partes)


def _nombres_unicos(entidades) -> dict[int, str]:
    """Nombre de nota por entidad, sin caracteres prohibidos ni repetidos."""
    usados: set[str] = set()
    nombres: dict[int, str] = {}
    for e in entidades:
        valor = re.sub(r"^https?://", "", e.valor)  # las URLs se leen mejor sin esquema
        base = _PROHIBIDOS.sub("_", valor).strip("._ ")[:120] or f"entidad-{e.id}"
        nombre = base if base.lower() not in usados else f"{base} ({e.id})"
        usados.add(nombre.lower())  # en minúsculas: Windows y macOS no distinguen
        nombres[e.id] = nombre
    return nombres
