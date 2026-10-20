"""Interfaz de línea de comandos (ADR-002).

=== IMPLEMENTACIÓN DE REFERENCIA (rama spike/v0.1-referencia) ===

Regla de arquitectura: la CLI NO piensa. Solo lee argumentos, llama al
núcleo y muestra resultados. Toda la lógica vive en core/, importers/ y
exporters/. Así la futura web local puede reutilizar exactamente lo mismo.

Typer construye la CLI a partir de las firmas de las funciones: los
parámetros se vuelven argumentos, y los type hints, validaciones.

Uso:
    copperscript nuevo mi-caso --nombre "Prueba" --objetivo "Huella de amaro_dev"
    copperscript importar mi-caso amaro_dev.csv
    copperscript entidades mi-caso
    copperscript exportar mi-caso obsidian
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from copperscript.core.models import TipoEntidad
from copperscript.core.store import Caso, CasoNoEncontrado
from copperscript.exporters.html_graph import exportar_html
from copperscript.exporters.obsidian import UMBRAL_POR_VERIFICAR, exportar_obsidian
from copperscript.importers import FormatoDesconocido, detectar_importador, obtener_importador

app = typer.Typer(
    help="copperscript: organiza datos OSINT y los muestra como grafo.", no_args_is_help=True
)


class Formato(StrEnum):
    obsidian = "obsidian"
    html = "html"


@app.command()
def nuevo(
    carpeta: Annotated[Path, typer.Argument(help="Carpeta del caso (se crea).")],
    nombre: Annotated[str, typer.Option(help="Nombre del caso.")] = "Caso sin nombre",
    objetivo: Annotated[str, typer.Option(help="Qué se quiere averiguar.")] = "",
    alcance: Annotated[str, typer.Option(help="Qué está permitido investigar y qué no.")] = "",
) -> None:
    """Crea un caso nuevo."""
    try:
        with Caso.crear(carpeta, nombre, objetivo, alcance):
            pass
    except FileExistsError as error:
        _fallar(str(error))
    typer.echo(f"Caso creado en {carpeta}")


@app.command()
def importar(
    carpeta: Annotated[Path, typer.Argument(help="Carpeta del caso.")],
    archivo: Annotated[
        Path, typer.Argument(help="Salida de una herramienta OSINT.", exists=True, dir_okay=False)
    ],
    herramienta: Annotated[
        str | None, typer.Option(help="Forzar el importador (si no, se detecta solo).")
    ] = None,
) -> None:
    """Importa la salida de una herramienta OSINT al caso."""
    try:
        importador = (
            obtener_importador(herramienta) if herramienta else detectar_importador(archivo)
        )
        with Caso.abrir(carpeta) as caso:
            r = caso.importar(archivo, importador)
    except (CasoNoEncontrado, FormatoDesconocido) as error:
        _fallar(str(error))
    typer.echo(
        f"[{r.herramienta}] {r.observaciones} observaciones · "
        f"{r.entidades_nuevas} entidades nuevas · {r.relaciones_nuevas} relaciones nuevas"
        + (f" · {r.descartadas} descartadas" if r.descartadas else "")
    )


@app.command()
def entidades(
    carpeta: Annotated[Path, typer.Argument(help="Carpeta del caso.")],
    tipo: Annotated[TipoEntidad | None, typer.Option(help="Filtrar por tipo.")] = None,
) -> None:
    """Lista las entidades del caso con su confianza."""
    try:
        with Caso.abrir(carpeta) as caso:
            lista = caso.entidades(tipo)
    except CasoNoEncontrado as error:
        _fallar(str(error))
    for e in lista:
        marca = "  (por verificar)" if e.confianza < UMBRAL_POR_VERIFICAR else ""
        # :<14 = alinear a la izquierda en 14 caracteres; :.2f = 2 decimales
        typer.echo(f"{e.tipo:<14} {e.confianza:.2f}  {e.valor}{marca}")
    typer.echo(f"\n{len(lista)} entidades")


@app.command()
def exportar(
    carpeta: Annotated[Path, typer.Argument(help="Carpeta del caso.")],
    formato: Annotated[Formato, typer.Argument(help="obsidian o html.")],
) -> None:
    """Exporta el caso (a exports/ dentro de la carpeta del caso)."""
    try:
        with Caso.abrir(carpeta) as caso:
            destino = (
                exportar_obsidian(caso) if formato is Formato.obsidian else exportar_html(caso)
            )
    except CasoNoEncontrado as error:
        _fallar(str(error))
    typer.echo(f"Exportado en {destino}")


def _fallar(mensaje: str) -> None:
    # err=True escribe en la salida de errores (stderr), no en la normal.
    # Código de salida 1 = "algo falló"; los scripts que llamen a la CLI lo detectan.
    typer.echo(f"Error: {mensaje}", err=True)
    raise typer.Exit(code=1)
