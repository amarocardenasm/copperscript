"""Exportador a Obsidian.

=== STUB: por implementar. Tests: tests/test_caso.py ===
(Implementación comentada de referencia en la rama spike/v0.1-referencia.)

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

from pathlib import Path

from copperscript.core.store import Caso

UMBRAL_POR_VERIFICAR = 0.5


def exportar_obsidian(caso: Caso) -> Path:
    """Regenera exports/obsidian/ desde cero y devuelve esa carpeta.

    - Una nota por entidad en exports/obsidian/<tipo>/<nombre>.md
    - Frontmatter YAML: tipo, valor (entre comillas), confianza, por_verificar
      (confianza < UMBRAL_POR_VERIFICAR) y copperscript_id.
    - Sección "## Relaciones" con una línea por vecino:
          - tiene_cuenta → [[www.github.com_amaro_dev]]
      (→ si la entidad es el origen de la relación, ← si es el destino).
    - Nombre de nota: el valor sin "http(s)://", con los caracteres
      prohibidos  \\ / : * ? " < > | # ^ [ ]  cambiados por "_".
      Si dos entidades dan el mismo nombre, agregar " (<id>)" a la segunda.
    """
    raise NotImplementedError("exportar_obsidian()")
