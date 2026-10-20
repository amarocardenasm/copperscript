"""Almacén de evidencia por contenido (ADR-004).

=== STUB: por implementar. Tests: tests/test_core.py ===
(Implementación comentada de referencia en la rama spike/v0.1-referencia.)

Cada archivo se guarda en <caso>/evidence/ con su hash SHA-256 como nombre.
Mismo contenido = mismo hash; un byte distinto = hash completamente distinto.
De ahí salen gratis: deduplicación, integridad y cadena de custodia.
"""

from __future__ import annotations

from pathlib import Path

from copperscript.core.models import Evidencia


def calcular_sha256(ruta: Path) -> str:
    """Hash SHA-256 (64 caracteres hexadecimales) del contenido de un archivo.

    Pistas:
      - Módulo `hashlib` de la librería estándar.
      - Abrir en binario ("rb") y leer por bloques (ej. 1 MiB), no todo de una:
        un video de 2 GB no debe necesitar 2 GB de RAM (RNF1).
    """
    raise NotImplementedError("calcular_sha256(): hash leyendo por bloques")


def guardar_evidencia(carpeta_evidencia: Path, ruta: Path) -> Evidencia:
    """Copia `ruta` a `ruta_evidencia(carpeta_evidencia, hash)` y devuelve su Evidencia.

    - Si ya existe un archivo con ese hash, no copia nada (deduplicación).
    - El archivo original del usuario nunca se modifica ni se mueve.

    Pistas:
      - `shutil.copyfile` para copiar.
      - Copiar a un nombre temporal y luego renombrar evita archivos "a medias"
        si el programa se corta durante la copia.
      - `mimetypes.guess_type(nombre)` adivina el tipo MIME por la extensión.
    """
    raise NotImplementedError("guardar_evidencia(): copiar con el hash como nombre")


def ruta_evidencia(carpeta_evidencia: Path, sha256: str) -> Path:
    """Dónde vive (o viviría) el archivo con ese hash.

    Convención (igual que Git): subcarpeta con los 2 primeros caracteres.
        evidence/3f/3fa9c1...
    """
    return carpeta_evidencia / sha256[:2] / sha256


def verificar_evidencia(carpeta_evidencia: Path, sha256: str) -> bool:
    """True si el archivo existe y su contenido sigue coincidiendo con su hash."""
    raise NotImplementedError("verificar_evidencia(): recalcular el hash y comparar")
