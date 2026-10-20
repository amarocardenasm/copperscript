"""Almacén de evidencia por contenido (ADR-004).

=== IMPLEMENTACIÓN DE REFERENCIA (rama spike/v0.1-referencia) ===

Cada archivo se guarda en <caso>/evidence/ con su hash SHA-256 como nombre.

¿Qué es un hash? Una función que convierte cualquier archivo en una
"huella" de 64 caracteres hexadecimales. Dos propiedades nos importan:
  1. El mismo contenido produce SIEMPRE la misma huella.
  2. Cambiar un solo byte produce una huella completamente distinta.

De ahí salen gratis tres cosas:
  - Deduplicación: importar dos veces el mismo archivo no ocupa doble espacio.
  - Integridad: si alguien altera el archivo, su hash ya no coincide con su nombre.
  - Cadena de custodia: en un informe puedes citar el hash como prueba de qué viste.

Git guarda sus objetos exactamente así (con SHA-1 históricamente).
"""

from __future__ import annotations

import hashlib
import mimetypes
import shutil
from pathlib import Path

from copperscript.core.models import Evidencia

# Leemos el archivo en bloques de 1 MiB en vez de completo: así un video de
# 2 GB no necesita 2 GB de RAM (requisito RNF1: funcionar con 4 GB).
_TAMANO_BLOQUE = 1024 * 1024


def calcular_sha256(ruta: Path) -> str:
    """Hash SHA-256 de un archivo, leyéndolo por bloques."""
    h = hashlib.sha256()
    with ruta.open("rb") as archivo:  # "rb" = leer en binario: el hash es sobre bytes
        # iter(funcion, centinela) llama a la función hasta que devuelva el
        # centinela (b"", fin de archivo). Es un truco idiomático de Python.
        for bloque in iter(lambda: archivo.read(_TAMANO_BLOQUE), b""):
            h.update(bloque)
    return h.hexdigest()


def guardar_evidencia(carpeta_evidencia: Path, ruta: Path) -> Evidencia:
    """Copia `ruta` dentro de `carpeta_evidencia` usando su hash como nombre.

    Si ya existe un archivo con ese hash, no copia nada (deduplicación).
    El original del usuario nunca se modifica ni se mueve.
    """
    sha = calcular_sha256(ruta)
    destino = ruta_evidencia(carpeta_evidencia, sha)
    if not destino.exists():
        # Subcarpetas por los 2 primeros caracteres del hash (ej. evidence/3f/3fa9...).
        # Con miles de archivos, una sola carpeta se vuelve lenta en algunos
        # sistemas de archivos; Git usa la misma técnica.
        destino.parent.mkdir(parents=True, exist_ok=True)
        # Copiamos a un nombre temporal y luego renombramos: si el programa se
        # corta a mitad de la copia, nunca queda un archivo "a medias" con un
        # nombre de hash que no corresponde a su contenido.
        temporal = destino.with_suffix(".tmp")
        shutil.copyfile(ruta, temporal)
        temporal.replace(destino)

    tipo_mime, _ = mimetypes.guess_type(ruta.name)
    return Evidencia(
        sha256=sha,
        nombre_original=ruta.name,
        tamano=ruta.stat().st_size,
        tipo_mime=tipo_mime,
    )


def ruta_evidencia(carpeta_evidencia: Path, sha256: str) -> Path:
    """Dónde vive (o viviría) el archivo con ese hash."""
    return carpeta_evidencia / sha256[:2] / sha256


def verificar_evidencia(carpeta_evidencia: Path, sha256: str) -> bool:
    """True si el archivo existe y su contenido sigue coincidiendo con su hash."""
    ruta = ruta_evidencia(carpeta_evidencia, sha256)
    return ruta.exists() and calcular_sha256(ruta) == sha256
