"""El caso: una carpeta con una base SQLite, evidencia y exportaciones (ADR-003).

=== STUB: por implementar. Tests: tests/test_caso.py ===
(Implementación comentada de referencia en la rama spike/v0.1-referencia.)

    mi-caso/
    ├── case.sqlite   <- este módulo
    ├── evidence/     <- core/evidence.py
    └── exports/      <- exporters/

Aquí vive también la RESOLUCIÓN DE ENTIDADES (ADR-011): cuando llega una
observación, decidir si es una entidad nueva o una que ya teníamos.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from copperscript.core.models import Entidad, Observacion, RefEntidad, Relacion, TipoEntidad

if TYPE_CHECKING:  # solo para el editor y ruff; evita importaciones circulares
    from copperscript.importers.base import Importador

ARCHIVO_DB = "case.sqlite"
CARPETA_EVIDENCIA = "evidence"
CARPETA_EXPORTS = "exports"
VERSION_ESQUEMA = 1

# Esquema: la traducción a tablas del diagrama entidad-relación (02-diagramas,
# diagrama 4). Ya está diseñado; lo que falta es usarlo desde los métodos.
_ESQUEMA = """
CREATE TABLE IF NOT EXISTS meta (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidencias (
    sha256          TEXT PRIMARY KEY,
    nombre_original TEXT NOT NULL,
    tamano          INTEGER NOT NULL,
    tipo_mime       TEXT
);
CREATE TABLE IF NOT EXISTS corridas (
    id               INTEGER PRIMARY KEY,
    herramienta      TEXT NOT NULL,
    version          TEXT,
    comando          TEXT,
    fecha            TEXT NOT NULL,
    evidencia_sha256 TEXT REFERENCES evidencias(sha256)
);
CREATE TABLE IF NOT EXISTS entidades (
    id    INTEGER PRIMARY KEY,
    tipo  TEXT NOT NULL,
    valor TEXT NOT NULL,
    clave TEXT NOT NULL,
    UNIQUE (tipo, clave)
);
CREATE TABLE IF NOT EXISTS relaciones (
    id         INTEGER PRIMARY KEY,
    origen_id  INTEGER NOT NULL REFERENCES entidades(id),
    destino_id INTEGER NOT NULL REFERENCES entidades(id),
    tipo       TEXT NOT NULL,
    UNIQUE (origen_id, destino_id, tipo)
);
CREATE TABLE IF NOT EXISTS observaciones (
    id               INTEGER PRIMARY KEY,
    corrida_id       INTEGER NOT NULL REFERENCES corridas(id),
    entidad_id       INTEGER NOT NULL REFERENCES entidades(id),
    relacion_id      INTEGER REFERENCES relaciones(id),
    confianza_fuente REAL NOT NULL,
    atributos        TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS hipotesis (
    id     INTEGER PRIMARY KEY,
    texto  TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'abierta'
);
CREATE TABLE IF NOT EXISTS hipotesis_observaciones (
    hipotesis_id   INTEGER NOT NULL REFERENCES hipotesis(id),
    observacion_id INTEGER NOT NULL REFERENCES observaciones(id),
    PRIMARY KEY (hipotesis_id, observacion_id)
);
-- Índices: aceleran las búsquedas más frecuentes (vecinos de un nodo,
-- observaciones de una entidad). Sin ellos SQLite recorre la tabla entera.
CREATE INDEX IF NOT EXISTS idx_rel_origen  ON relaciones(origen_id);
CREATE INDEX IF NOT EXISTS idx_rel_destino ON relaciones(destino_id);
CREATE INDEX IF NOT EXISTS idx_obs_entidad ON observaciones(entidad_id);
"""


class CasoNoEncontrado(FileNotFoundError):
    """La carpeta no contiene un case.sqlite."""


@dataclass
class ResumenImportacion:
    """Lo que pasó en una importación, para mostrárselo al usuario."""

    corrida_id: int
    herramienta: str
    observaciones: int = 0
    entidades_nuevas: int = 0
    relaciones_nuevas: int = 0
    descartadas: int = 0  # valores inválidos que no se pudieron normalizar


class Caso:
    """Un caso de investigación abierto. Se usa con `with`:

    with Caso.abrir(Path("mi-caso")) as caso:
        for entidad in caso.entidades():
            print(entidad.valor)
    """

    def __init__(self, carpeta: Path, conexion: sqlite3.Connection) -> None:
        # No se llama directamente: usa Caso.crear() o Caso.abrir().
        self.carpeta = carpeta
        self._con = conexion

    # --- Crear, abrir y cerrar ---------------------------------------------

    @classmethod
    def crear(cls, carpeta: Path, nombre: str, objetivo: str = "", alcance: str = "") -> Caso:
        """Crea carpeta, evidence/, exports/ y case.sqlite con el esquema.

        - Lanza FileExistsError si ya hay un caso en esa carpeta.
        - Guarda nombre, objetivo, alcance, fecha de creación y versión del
          esquema en la tabla `meta`.

        Pistas: `conexion.executescript(_ESQUEMA)`; `with conexion:` abre
        una transacción (todo o nada).
        """
        raise NotImplementedError("Caso.crear(): carpetas + esquema + meta")

    @classmethod
    def abrir(cls, carpeta: Path) -> Caso:
        """Abre un caso existente. Lanza CasoNoEncontrado si no hay case.sqlite."""
        raise NotImplementedError("Caso.abrir()")

    def cerrar(self) -> None:
        self._con.close()

    def __enter__(self) -> Caso:
        return self

    def __exit__(self, *_excepcion: object) -> None:
        self.cerrar()

    def metadatos(self) -> dict[str, str]:
        """Contenido de la tabla `meta` como dict."""
        raise NotImplementedError("Caso.metadatos()")

    @property
    def carpeta_evidencia(self) -> Path:
        return self.carpeta / CARPETA_EVIDENCIA

    @property
    def carpeta_exports(self) -> Path:
        return self.carpeta / CARPETA_EXPORTS

    # --- Importar (diagrama 3, "el viaje de un dato") ----------------------

    def importar(self, ruta: Path, importador: Importador) -> ResumenImportacion:
        """Importa un archivo crudo, en el orden del diagrama de flujo:

          1. Guardar el crudo como evidencia ANTES de interpretar nada.
          2. Registrar la corrida (herramienta, fecha, hash del crudo).
          3. Pasar cada observación por `_registrar_observacion`.
             Si una lanza ValorInvalido, contarla como descartada y seguir.

        Toda la importación debe ser UNA transacción: más rápida y, si algo
        falla a la mitad, no queda medio archivo importado.
        """
        raise NotImplementedError("Caso.importar(): evidencia -> corrida -> observaciones")

    def _registrar_observacion(self, corrida_id: int, obs: Observacion) -> tuple[int, int]:
        """Resolución de entidades. Devuelve (entidades nuevas, relaciones nuevas).

        - Obtener o crear la entidad observada.
        - Si hay origen: obtener o crear el origen, registrar que también fue
          observado, y obtener o crear la relación origen -> entidad.
        - Insertar la fila en `observaciones`.
        """
        raise NotImplementedError("Caso._registrar_observacion()")

    def _obtener_o_crear(self, ref: RefEntidad) -> tuple[int, int]:
        """El corazón de ADR-011: misma (tipo, clave normalizada) = misma entidad.

        Devuelve (id, 1 si se creó / 0 si ya existía).
        Guardar `valor` tal como llegó (para mostrar) y `clave` (para comparar).
        """
        raise NotImplementedError("Caso._obtener_o_crear()")

    # --- Consultas ----------------------------------------------------------

    def entidades(self, tipo: TipoEntidad | None = None) -> list[Entidad]:
        """Todas las entidades (o las de un tipo), con su confianza calculada.

        La confianza NO se guarda: se calcula combinando las observaciones de
        cada entidad con core.confidence.combinar (agrupando por herramienta).
        """
        raise NotImplementedError("Caso.entidades()")

    def buscar(self, tipo: TipoEntidad, valor: str) -> Entidad | None:
        """Busca una entidad por su valor (se normaliza antes de buscar)."""
        raise NotImplementedError("Caso.buscar()")

    def relaciones(self) -> list[Relacion]:
        raise NotImplementedError("Caso.relaciones()")

    def vecinos(self, entidad_id: int) -> Iterator[tuple[Relacion, int]]:
        """Relaciones que tocan a una entidad, con el id del otro extremo.

        La usará la web local para "expandir" un nodo (carga por partes, ADR-006).
        """
        raise NotImplementedError("Caso.vecinos()")


def _conectar(ruta: Path) -> sqlite3.Connection:
    """Abre la base de datos lista para usar.

    Pistas:
      - `conexion.row_factory = sqlite3.Row` permite leer fila["valor"].
      - SQLite NO revisa las claves foráneas salvo que se active con
        `PRAGMA foreign_keys = ON`, en cada conexión.
    """
    raise NotImplementedError("_conectar()")
