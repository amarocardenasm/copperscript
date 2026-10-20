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
from copperscript.core.normalize import ValorInvalido
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
    con_atribucion = any(e.atribucion is not None for e in lista)
    if con_atribucion:
        typer.echo(f"{'TIPO':<14} {'EXIST':>5}  {'ATRIB':>5}  VALOR")
    for e in lista:
        marca = "  (por verificar)" if e.confianza < UMBRAL_POR_VERIFICAR else ""
        # :<14 = alinear a la izquierda en 14 caracteres; :.2f = 2 decimales
        atrib = f"{e.atribucion:>5.2f}  " if e.atribucion is not None else ""
        typer.echo(f"{e.tipo:<14} {e.confianza:>5.2f}  {atrib}{e.valor}{marca}")
    typer.echo(f"\n{len(lista)} entidades")
    if con_atribucion:
        typer.echo("EXIST = ¿existe?   ATRIB = ¿le pertenece al objetivo? (desde las anclas)")


@app.command()
def anclar(
    carpeta: Annotated[Path, typer.Argument(help="Carpeta del caso.")],
    tipo: Annotated[TipoEntidad, typer.Argument(help="Tipo de la entidad.")],
    valor: Annotated[str, typer.Argument(help="Valor verificado (ej. un email confirmado).")],
    nota: Annotated[str, typer.Option(help="Cómo lo verificaste.")] = "",
) -> None:
    """Marca un dato como verificado: le pertenece al objetivo (ADR-013)."""
    try:
        with Caso.abrir(carpeta) as caso:
            caso.anclar(tipo, valor, nota)
    except (CasoNoEncontrado, ValorInvalido) as error:
        _fallar(str(error))
    typer.echo(f"Ancla registrada: {valor}")


# Un sub-grupo de comandos: `copperscript hipotesis nueva|evidencia|ver`.
hipotesis_app = typer.Typer(help="Hipótesis en competencia con Bayes (ADR-013).")
app.add_typer(hipotesis_app, name="hipotesis")


@hipotesis_app.command("nueva")
def hipotesis_nueva(
    carpeta: Annotated[Path, typer.Argument(help="Carpeta del caso.")],
    texto: Annotated[str, typer.Argument(help="La hipótesis, en una frase.")],
    prior: Annotated[float, typer.Option(help="Probabilidad previa, entre 0 y 1.")] = 0.5,
) -> None:
    """Registra una hipótesis con su probabilidad previa."""
    try:
        with Caso.abrir(carpeta) as caso:
            hid = caso.crear_hipotesis(texto, prior)
    except (CasoNoEncontrado, ValueError) as error:
        _fallar(str(error))
    typer.echo(f"Hipótesis #{hid} creada (previa {prior:.2f})")


@hipotesis_app.command("evidencia")
def hipotesis_evidencia(
    carpeta: Annotated[Path, typer.Argument(help="Carpeta del caso.")],
    hipotesis_id: Annotated[int, typer.Argument(help="Número de la hipótesis.")],
    descripcion: Annotated[str, typer.Argument(help="Qué se observó.")],
    lr: Annotated[float, typer.Option(help="Razón de verosimilitud: >1 apoya, <1 contradice.")],
) -> None:
    """Agrega una evidencia a una hipótesis."""
    try:
        with Caso.abrir(carpeta) as caso:
            caso.agregar_evidencia(hipotesis_id, descripcion, lr)
            ev = caso.evaluar_hipotesis(hipotesis_id)
    except (CasoNoEncontrado, ValueError, KeyError) as error:
        _fallar(str(error))
    typer.echo(f"Hipótesis #{hipotesis_id}: ahora {ev.posterior:.1%}")


@hipotesis_app.command("ver")
def hipotesis_ver(carpeta: Annotated[Path, typer.Argument(help="Carpeta del caso.")]) -> None:
    """Muestra cada hipótesis con su probabilidad y el aporte de cada evidencia."""
    try:
        with Caso.abrir(carpeta) as caso:
            lista = caso.lista_hipotesis()
    except CasoNoEncontrado as error:
        _fallar(str(error))
    for h in lista:
        typer.echo(f"#{h.id} {h.texto}")
        typer.echo(f"    previa {h.prior:.1%}  ->  posterior {h.posterior:.1%}")
        for e in h.evidencias:
            # :+6.1f muestra siempre el signo: +13.0 dB a favor, -3.0 dB en contra.
            typer.echo(f"    {e.decibanes:+6.1f} dB  (LR {e.lr:g})  {e.descripcion}")
    if not lista:
        typer.echo('Sin hipótesis. Crea una con: copperscript hipotesis nueva CASO "texto"')


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
