"""El caso: una carpeta con una base SQLite, evidencia y exportaciones (ADR-003).

=== IMPLEMENTACIÓN DE REFERENCIA (rama spike/v0.1-referencia) ===

    mi-caso/
    ├── case.sqlite   <- este módulo
    ├── evidence/     <- core/evidence.py
    └── exports/      <- exporters/

Aquí vive también la RESOLUCIÓN DE ENTIDADES (ADR-011): cuando llega una
observación, decidimos si es una entidad nueva o una que ya teníamos.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from copperscript.core import confidence
from copperscript.core.evidence import guardar_evidencia
from copperscript.core.models import (
    Corrida,
    Entidad,
    Observacion,
    RefEntidad,
    Relacion,
    TipoEntidad,
)
from copperscript.core.normalize import ValorInvalido, normalizar

if TYPE_CHECKING:  # solo para el editor y ruff; evita importaciones circulares en ejecución
    from copperscript.importers.base import Importador

ARCHIVO_DB = "case.sqlite"
CARPETA_EVIDENCIA = "evidence"
CARPETA_EXPORTS = "exports"
VERSION_ESQUEMA = 1

# El esquema traduce el diagrama entidad-relación a tablas.
# Detalles que conviene notar:
#   - UNIQUE(tipo, clave): la base de datos misma impide duplicados. Aunque
#     nuestro código tuviera un bug, SQLite no dejaría guardar dos veces
#     el mismo email. Defensa en profundidad.
#   - La confianza de una entidad NO se guarda: se calcula desde sus
#     observaciones. Un dato derivado guardado se desincroniza tarde o temprano.
#   - atributos se guarda como texto JSON: flexible sin crear una columna
#     por cada campo raro que traiga cada herramienta.
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
    """Un caso de investigación abierto.

    Se usa idealmente con `with`, que garantiza cerrar la base de datos:

        with Caso.abrir(Path("mi-caso")) as caso:
            for entidad in caso.entidades():
                print(entidad.valor)
    """

    def __init__(self, carpeta: Path, conexion: sqlite3.Connection) -> None:
        # No se llama directamente: usa Caso.crear() o Caso.abrir().
        self.carpeta = carpeta
        self._con = conexion

    # ------------------------------------------------------------------
    # Crear, abrir y cerrar
    # ------------------------------------------------------------------

    @classmethod
    def crear(cls, carpeta: Path, nombre: str, objetivo: str = "", alcance: str = "") -> Caso:
        """Crea la estructura de carpetas y la base de datos de un caso nuevo."""
        if (carpeta / ARCHIVO_DB).exists():
            raise FileExistsError(f"ya existe un caso en {carpeta}")
        for sub in ("", CARPETA_EVIDENCIA, CARPETA_EXPORTS):
            (carpeta / sub).mkdir(parents=True, exist_ok=True)

        caso = cls(carpeta, _conectar(carpeta / ARCHIVO_DB))
        # executescript ejecuta varias sentencias SQL de una vez (el esquema completo).
        caso._con.executescript(_ESQUEMA)
        with caso._con:  # "with conexion" = una transacción: todo o nada
            caso._con.executemany(
                "INSERT INTO meta (clave, valor) VALUES (?, ?)",
                [
                    ("nombre", nombre),
                    ("objetivo", objetivo),
                    ("alcance", alcance),
                    ("creado", datetime.now(UTC).isoformat()),
                    ("version_esquema", str(VERSION_ESQUEMA)),
                ],
            )
        return caso

    @classmethod
    def abrir(cls, carpeta: Path) -> Caso:
        """Abre un caso existente."""
        ruta_db = carpeta / ARCHIVO_DB
        if not ruta_db.exists():
            raise CasoNoEncontrado(f"no hay un caso en {carpeta} (falta {ARCHIVO_DB})")
        return cls(carpeta, _conectar(ruta_db))

    def cerrar(self) -> None:
        self._con.close()

    # __enter__ y __exit__ son los métodos que hacen funcionar a `with`.
    def __enter__(self) -> Caso:
        return self

    def __exit__(self, *_excepcion: object) -> None:
        self.cerrar()

    def metadatos(self) -> dict[str, str]:
        filas = self._con.execute("SELECT clave, valor FROM meta").fetchall()
        return {fila["clave"]: fila["valor"] for fila in filas}

    @property
    def carpeta_evidencia(self) -> Path:
        return self.carpeta / CARPETA_EVIDENCIA

    @property
    def carpeta_exports(self) -> Path:
        return self.carpeta / CARPETA_EXPORTS

    # ------------------------------------------------------------------
    # Importar (el diagrama 3, "el viaje de un dato", vive aquí)
    # ------------------------------------------------------------------

    def importar(self, ruta: Path, importador: Importador) -> ResumenImportacion:
        """Importa un archivo crudo con el importador dado.

        Sigue el orden del diagrama de flujo:
          1. guardar el crudo como evidencia (antes de interpretar nada)
          2. registrar la corrida
          3. pasar cada observación por la resolución de entidades
        """
        evidencia = guardar_evidencia(self.carpeta_evidencia, ruta)

        # Toda la importación es UNA transacción. Ventajas:
        #   - velocidad: SQLite escribe al disco una vez al final, no por fila
        #     (puede ser 100 veces más rápido con miles de filas).
        #   - atomicidad: si el importador falla a la mitad, no queda medio
        #     archivo importado; la base vuelve a como estaba.
        with self._con:
            self._con.execute(
                "INSERT OR IGNORE INTO evidencias (sha256, nombre_original, tamano, tipo_mime) "
                "VALUES (?, ?, ?, ?)",
                (
                    evidencia.sha256,
                    evidencia.nombre_original,
                    evidencia.tamano,
                    evidencia.tipo_mime,
                ),
            )
            corrida_id = self._registrar_corrida(
                Corrida(
                    herramienta=importador.herramienta,
                    fecha=datetime.now(UTC),
                    comando=f"importar {ruta.name}",
                    evidencia_sha256=evidencia.sha256,
                )
            )
            resumen = ResumenImportacion(corrida_id=corrida_id, herramienta=importador.herramienta)
            for observacion in importador.importar(ruta):
                try:
                    nueva_e, nueva_r = self._registrar_observacion(corrida_id, observacion)
                except ValorInvalido:
                    # Un valor basura no debe tumbar la importación entera.
                    # Lo contamos para que el usuario sepa que hubo descartes.
                    resumen.descartadas += 1
                    continue
                resumen.observaciones += 1
                resumen.entidades_nuevas += nueva_e
                resumen.relaciones_nuevas += nueva_r
        return resumen

    def _registrar_corrida(self, corrida: Corrida) -> int:
        cursor = self._con.execute(
            "INSERT INTO corridas (herramienta, version, comando, fecha, evidencia_sha256) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                corrida.herramienta,
                corrida.version,
                corrida.comando,
                corrida.fecha.isoformat(),
                corrida.evidencia_sha256,
            ),
        )
        # lastrowid = el id que SQLite acaba de asignar a la fila insertada.
        return int(cursor.lastrowid or 0)

    def _registrar_observacion(self, corrida_id: int, obs: Observacion) -> tuple[int, int]:
        """Resolución de entidades. Devuelve (entidades nuevas, relaciones nuevas)."""
        nuevas_e = 0
        nuevas_r = 0
        atributos = json.dumps(obs.atributos, ensure_ascii=False, default=str)

        entidad_id, creada = self._obtener_o_crear(obs.entidad)
        nuevas_e += creada

        relacion_id = None
        if obs.origen is not None:
            origen_id, creada = self._obtener_o_crear(obs.origen)
            nuevas_e += creada
            # El origen también queda observado por esta corrida: si Sherlock
            # dice "amaro_dev tiene cuenta en GitHub", está afirmando
            # implícitamente que el usuario amaro_dev existe.
            self._con.execute(
                "INSERT INTO observaciones (corrida_id, entidad_id, confianza_fuente, atributos) "
                "VALUES (?, ?, ?, ?)",
                (corrida_id, origen_id, obs.confianza_fuente, json.dumps({"rol": "origen"})),
            )
            tipo_rel = (obs.relacion or "relacionado_con").strip().lower().replace(" ", "_")
            relacion_id, creada = self._obtener_o_crear_relacion(origen_id, entidad_id, tipo_rel)
            nuevas_r += creada

        self._con.execute(
            "INSERT INTO observaciones "
            "(corrida_id, entidad_id, relacion_id, confianza_fuente, atributos) "
            "VALUES (?, ?, ?, ?, ?)",
            (corrida_id, entidad_id, relacion_id, obs.confianza_fuente, atributos),
        )
        return nuevas_e, nuevas_r

    def _obtener_o_crear(self, ref: RefEntidad) -> tuple[int, int]:
        """El corazón de ADR-011: misma (tipo, clave) = misma entidad.

        Devuelve (id, 1 si se creó / 0 si ya existía).
        """
        clave = normalizar(ref.tipo, ref.valor)
        fila = self._con.execute(
            "SELECT id FROM entidades WHERE tipo = ? AND clave = ?", (str(ref.tipo), clave)
        ).fetchone()
        if fila is not None:
            return int(fila["id"]), 0
        cursor = self._con.execute(
            "INSERT INTO entidades (tipo, valor, clave) VALUES (?, ?, ?)",
            # Guardamos el valor tal como llegó la primera vez (para mostrarlo)
            # y la clave normalizada (para comparar).
            (str(ref.tipo), ref.valor.strip(), clave),
        )
        return int(cursor.lastrowid or 0), 1

    def _obtener_o_crear_relacion(
        self, origen_id: int, destino_id: int, tipo: str
    ) -> tuple[int, int]:
        fila = self._con.execute(
            "SELECT id FROM relaciones WHERE origen_id = ? AND destino_id = ? AND tipo = ?",
            (origen_id, destino_id, tipo),
        ).fetchone()
        if fila is not None:
            return int(fila["id"]), 0
        cursor = self._con.execute(
            "INSERT INTO relaciones (origen_id, destino_id, tipo) VALUES (?, ?, ?)",
            (origen_id, destino_id, tipo),
        )
        return int(cursor.lastrowid or 0), 1

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------

    def entidades(self, tipo: TipoEntidad | None = None) -> list[Entidad]:
        """Todas las entidades (o las de un tipo), con su confianza calculada."""
        if tipo is None:
            filas = self._con.execute("SELECT * FROM entidades ORDER BY tipo, clave").fetchall()
        else:
            filas = self._con.execute(
                "SELECT * FROM entidades WHERE tipo = ? ORDER BY clave", (str(tipo),)
            ).fetchall()
        confianzas = self._confianzas()
        return [
            Entidad(
                id=fila["id"],
                tipo=TipoEntidad(fila["tipo"]),
                valor=fila["valor"],
                clave=fila["clave"],
                confianza=confianzas.get(fila["id"], 0.0),
            )
            for fila in filas
        ]

    def buscar(self, tipo: TipoEntidad, valor: str) -> Entidad | None:
        """Busca una entidad por su valor (crudo o no: se normaliza antes de buscar)."""
        clave = normalizar(tipo, valor)
        return next((e for e in self.entidades(tipo) if e.clave == clave), None)

    def relaciones(self) -> list[Relacion]:
        filas = self._con.execute("SELECT * FROM relaciones ORDER BY id").fetchall()
        return [
            Relacion(
                id=f["id"], origen_id=f["origen_id"], destino_id=f["destino_id"], tipo=f["tipo"]
            )
            for f in filas
        ]

    def vecinos(self, entidad_id: int) -> Iterator[tuple[Relacion, int]]:
        """Relaciones que tocan a una entidad, junto con el id del otro extremo.

        Es lo que usará la web local para "expandir" un nodo (carga por partes, ADR-006).
        """
        filas = self._con.execute(
            "SELECT * FROM relaciones WHERE origen_id = ? OR destino_id = ?",
            (entidad_id, entidad_id),
        )
        for f in filas:
            rel = Relacion(
                id=f["id"], origen_id=f["origen_id"], destino_id=f["destino_id"], tipo=f["tipo"]
            )
            otro = rel.destino_id if rel.origen_id == entidad_id else rel.origen_id
            yield rel, otro

    def _confianzas(self) -> dict[int, float]:
        """Confianza de cada entidad, combinando sus observaciones (core/confidence.py).

        Traemos todas las observaciones con un JOIN y agrupamos en Python.
        Para casos de decenas de miles de filas sigue siendo rápido; si algún
        día no lo es, se puede cachear o calcular en SQL.
        """
        filas = self._con.execute(
            "SELECT o.entidad_id, c.herramienta, o.confianza_fuente "
            "FROM observaciones o JOIN corridas c ON c.id = o.corrida_id"
        ).fetchall()
        por_entidad: dict[int, list[tuple[str, float]]] = {}
        for f in filas:
            por_entidad.setdefault(f["entidad_id"], []).append(
                (f["herramienta"], f["confianza_fuente"])
            )
        return {eid: confidence.combinar(obs) for eid, obs in por_entidad.items()}


def _conectar(ruta: Path) -> sqlite3.Connection:
    con = sqlite3.connect(ruta)
    # row_factory permite leer columnas por nombre: fila["valor"] en vez de fila[2].
    con.row_factory = sqlite3.Row
    # SQLite NO revisa las claves foráneas (REFERENCES) a menos que se lo pidas,
    # conexión por conexión. Es una de las sorpresas clásicas de SQLite.
    con.execute("PRAGMA foreign_keys = ON")
    return con
