"""El caso: una carpeta con una base SQLite, evidencia y exportaciones (ADR-003).

=== IMPLEMENTACIÓN DE REFERENCIA (rama spike/v0.1-referencia) ===
v0.2 explorada aquí: migraciones de esquema, anclas, atribución e hipótesis (ADR-013).

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

from copperscript.core import atribucion, confidence, hipotesis
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
VERSION_ESQUEMA = 2  # ver _MIGRACIONES más abajo

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

# --- MIGRACIONES -------------------------------------------------------------
# _ESQUEMA de arriba es la versión 1 y NO se vuelve a tocar. Cada cambio
# posterior es una migración numerada. ¿Por qué no editar _ESQUEMA y listo?
# Porque los casos que ya existen en el disco de alguien tienen la versión
# vieja: si solo cambiamos el esquema de los casos NUEVOS, los viejos se
# rompen al abrirlos. Con migraciones, cualquier caso (nuevo o viejo) pasa
# por los mismos pasos y termina idéntico. Es lo que hacen Django, Rails,
# Alembic y cualquier proyecto serio con base de datos.
#
# Regla de oro: una migración ya publicada nunca se edita; si hay un error,
# se corrige con una migración NUEVA.
_MIGRACIONES: dict[int, str] = {
    # v2 (ADR-013): atribución con anclas e hipótesis bayesianas.
    2: """
    -- Anclas: entidades que el analista verificó como del objetivo.
    CREATE TABLE anclas (
        entidad_id INTEGER PRIMARY KEY REFERENCES entidades(id),
        nota       TEXT NOT NULL DEFAULT '',
        fecha      TEXT NOT NULL
    );
    -- ALTER TABLE ... ADD COLUMN es de lo poco que SQLite permite cambiar
    -- en una tabla existente. El DEFAULT rellena las filas que ya había.
    ALTER TABLE hipotesis ADD COLUMN prior REAL NOT NULL DEFAULT 0.5;
    -- Evidencias de una hipótesis, cada una con su razón de verosimilitud.
    -- CHECK hace que la base de datos rechace un LR imposible (<= 0).
    CREATE TABLE evidencias_hipotesis (
        id             INTEGER PRIMARY KEY,
        hipotesis_id   INTEGER NOT NULL REFERENCES hipotesis(id),
        descripcion    TEXT NOT NULL,
        lr             REAL NOT NULL CHECK (lr > 0),
        observacion_id INTEGER REFERENCES observaciones(id),
        fecha          TEXT NOT NULL
    );
    CREATE INDEX idx_evid_hipotesis ON evidencias_hipotesis(hipotesis_id);
    """,
}

# Nombre de la "herramienta" cuando el dato lo afirma el propio analista.
HERRAMIENTA_ANALISTA = "analista"


@dataclass
class EvidenciaHipotesis:
    descripcion: str
    lr: float
    decibanes: float


@dataclass
class EvaluacionHipotesis:
    """Una hipótesis con su probabilidad previa, posterior y el desglose."""

    id: int
    texto: str
    estado: str
    prior: float
    posterior: float
    evidencias: list[EvidenciaHipotesis]


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
                    # Se crea en v1 y se migra: así los casos nuevos y los
                    # viejos recorren exactamente el mismo camino.
                    ("version_esquema", "1"),
                ],
            )
        caso._migrar()
        return caso

    @classmethod
    def abrir(cls, carpeta: Path) -> Caso:
        """Abre un caso existente y lo migra a la última versión del esquema."""
        ruta_db = carpeta / ARCHIVO_DB
        if not ruta_db.exists():
            raise CasoNoEncontrado(f"no hay un caso en {carpeta} (falta {ARCHIVO_DB})")
        caso = cls(carpeta, _conectar(ruta_db))
        caso._migrar()
        return caso

    def version_esquema(self) -> int:
        consulta = "SELECT valor FROM meta WHERE clave = 'version_esquema'"
        fila = self._con.execute(consulta).fetchone()
        return int(fila["valor"]) if fila else 1

    def _migrar(self) -> None:
        """Aplica en orden las migraciones que le falten a este caso."""
        actual = self.version_esquema()
        if actual > VERSION_ESQUEMA:
            # Un caso creado con una versión MÁS NUEVA de copperscript: no
            # sabemos qué cambió, así que no lo tocamos.
            raise RuntimeError(
                f"este caso usa el esquema v{actual}, pero esta versión de copperscript "
                f"solo conoce hasta v{VERSION_ESQUEMA}. Actualiza copperscript."
            )
        for version in range(actual + 1, VERSION_ESQUEMA + 1):
            # Cada migración es su propia transacción, junto con el cambio de
            # versión: o se aplica entera y queda registrada, o no pasa nada.
            # executescript no participa de transacciones abiertas, por eso
            # escribimos BEGIN/COMMIT a mano dentro del mismo script.
            try:
                self._con.executescript(
                    "BEGIN;\n"
                    + _MIGRACIONES[version]
                    + f"\nUPDATE meta SET valor = '{version}' WHERE clave = 'version_esquema';\n"
                    + "COMMIT;"
                )
            except sqlite3.Error:
                # Si una sentencia falla, el BEGIN quedó abierto: deshacemos.
                if self._con.in_transaction:
                    self._con.rollback()
                raise

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
        # Sin anclas no hay objetivo conocido: la atribución queda en None
        # ("no aplica"), que es distinto de 0.0 ("no le pertenece").
        atribuciones = self.atribuciones(confianzas) if self._hay_anclas() else None
        return [
            Entidad(
                id=fila["id"],
                tipo=TipoEntidad(fila["tipo"]),
                valor=fila["valor"],
                clave=fila["clave"],
                confianza=confianzas.get(fila["id"], 0.0),
                atribucion=None if atribuciones is None else atribuciones.get(fila["id"], 0.0),
            )
            for fila in filas
        ]

    def buscar(self, tipo: TipoEntidad, valor: str) -> Entidad | None:
        """Busca una entidad por su valor (crudo o no: se normaliza antes de buscar)."""
        # OPTIMIZACIÓN (bitácora, entrada 005): la primera versión llamaba a
        # self.entidades(tipo) y filtraba en Python. Eso recalculaba la
        # confianza de TODO el caso en cada búsqueda: con 40.000 entidades,
        # 150 ms por búsqueda. Ahora: una consulta que usa el índice
        # UNIQUE(tipo, clave) y solo calcula la confianza de esa entidad.
        clave = normalizar(tipo, valor)
        fila = self._con.execute(
            "SELECT * FROM entidades WHERE tipo = ? AND clave = ?", (str(tipo), clave)
        ).fetchone()
        if fila is None:
            return None
        obs = self._con.execute(
            "SELECT c.herramienta, o.confianza_fuente "
            "FROM observaciones o JOIN corridas c ON c.id = o.corrida_id "
            "WHERE o.entidad_id = ?",
            (fila["id"],),
        ).fetchall()
        # La atribución sí necesita el grafo completo (se propaga desde las
        # anclas), así que solo se calcula si hay anclas. Mejora pendiente:
        # cachearla y recalcular solo cuando cambian los datos.
        atribucion_ent = None
        if self._hay_anclas():
            atribucion_ent = self.atribuciones().get(fila["id"], 0.0)
        return Entidad(
            id=fila["id"],
            tipo=TipoEntidad(fila["tipo"]),
            valor=fila["valor"],
            clave=fila["clave"],
            confianza=confidence.combinar((o["herramienta"], o["confianza_fuente"]) for o in obs),
            atribucion=atribucion_ent,
        )

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

    def _confianzas_relaciones(self) -> dict[int, float]:
        """Confianza de cada relación: igual que las entidades, desde sus observaciones."""
        filas = self._con.execute(
            "SELECT o.relacion_id, c.herramienta, o.confianza_fuente "
            "FROM observaciones o JOIN corridas c ON c.id = o.corrida_id "
            "WHERE o.relacion_id IS NOT NULL"
        ).fetchall()
        por_relacion: dict[int, list[tuple[str, float]]] = {}
        for f in filas:
            por_relacion.setdefault(f["relacion_id"], []).append(
                (f["herramienta"], f["confianza_fuente"])
            )
        return {rid: confidence.combinar(obs) for rid, obs in por_relacion.items()}

    # ------------------------------------------------------------------
    # ADR-013 · Objetivo conocido: anclas y atribución
    # ------------------------------------------------------------------

    def anclar(self, tipo: TipoEntidad, valor: str, nota: str = "") -> int:
        """Marca una entidad como verificada por el analista (le pertenece al objetivo).

        Si la entidad no existía, se crea. En ambos casos queda una observación
        de la "herramienta" analista con confianza 1.0: el analista también es
        una fuente, y su afirmación debe quedar registrada como cualquier otra.
        Devuelve el id de la entidad.
        """
        ahora = datetime.now(UTC)
        with self._con:
            corrida_id = self._registrar_corrida(
                Corrida(herramienta=HERRAMIENTA_ANALISTA, fecha=ahora, comando=f"anclar {valor}")
            )
            obs = Observacion(
                entidad=RefEntidad(tipo, valor), confianza_fuente=1.0, atributos={"ancla": True}
            )
            self._registrar_observacion(corrida_id, obs)
            entidad_id, _ = self._obtener_o_crear(obs.entidad)
            # INSERT OR REPLACE: si ya era ancla, actualiza la nota y la fecha.
            self._con.execute(
                "INSERT OR REPLACE INTO anclas (entidad_id, nota, fecha) VALUES (?, ?, ?)",
                (entidad_id, nota, ahora.isoformat()),
            )
        return entidad_id

    def anclas(self) -> set[int]:
        return {f["entidad_id"] for f in self._con.execute("SELECT entidad_id FROM anclas")}

    def _hay_anclas(self) -> bool:
        return self._con.execute("SELECT 1 FROM anclas LIMIT 1").fetchone() is not None

    def atribuciones(self, existencia: dict[int, float] | None = None) -> dict[int, float]:
        """Atribución al objetivo de cada entidad alcanzable desde las anclas."""
        existencia = existencia if existencia is not None else self._confianzas()
        conf_rel = self._confianzas_relaciones()
        aristas = [
            (r.origen_id, r.destino_id, r.tipo, conf_rel.get(r.id, 0.0)) for r in self.relaciones()
        ]
        return atribucion.propagar(self.anclas(), aristas, existencia)

    # ------------------------------------------------------------------
    # ADR-013 · Objetivo desconocido: hipótesis en competencia
    # ------------------------------------------------------------------

    def crear_hipotesis(self, texto: str, prior: float = 0.5) -> int:
        """Registra una hipótesis con su probabilidad previa. Devuelve su id."""
        hipotesis.a_odds(prior)  # valida 0 < prior < 1 antes de tocar la base
        with self._con:
            cursor = self._con.execute(
                "INSERT INTO hipotesis (texto, prior) VALUES (?, ?)", (texto, prior)
            )
        return int(cursor.lastrowid or 0)

    def agregar_evidencia(
        self,
        hipotesis_id: int,
        descripcion: str,
        lr: float,
        observacion_id: int | None = None,
    ) -> None:
        """Suma una evidencia a una hipótesis. lr > 1 apoya, lr < 1 contradice."""
        hipotesis.decibanes(lr)  # valida lr > 0 con un mensaje claro
        with self._con:
            self._con.execute(
                "INSERT INTO evidencias_hipotesis "
                "(hipotesis_id, descripcion, lr, observacion_id, fecha) VALUES (?, ?, ?, ?, ?)",
                (hipotesis_id, descripcion, lr, observacion_id, datetime.now(UTC).isoformat()),
            )

    def evaluar_hipotesis(self, hipotesis_id: int) -> EvaluacionHipotesis:
        """Probabilidad posterior de una hipótesis, con el aporte de cada evidencia."""
        fila = self._con.execute("SELECT * FROM hipotesis WHERE id = ?", (hipotesis_id,)).fetchone()
        if fila is None:
            raise KeyError(f"no existe la hipótesis {hipotesis_id}")
        evidencias = [
            EvidenciaHipotesis(e["descripcion"], e["lr"], round(hipotesis.decibanes(e["lr"]), 2))
            for e in self._con.execute(
                "SELECT * FROM evidencias_hipotesis WHERE hipotesis_id = ? ORDER BY id",
                (hipotesis_id,),
            )
        ]
        return EvaluacionHipotesis(
            id=fila["id"],
            texto=fila["texto"],
            estado=fila["estado"],
            prior=fila["prior"],
            posterior=round(hipotesis.posterior(fila["prior"], [e.lr for e in evidencias]), 6),
            evidencias=evidencias,
        )

    def lista_hipotesis(self) -> list[EvaluacionHipotesis]:
        ids = [f["id"] for f in self._con.execute("SELECT id FROM hipotesis ORDER BY id")]
        return [self.evaluar_hipotesis(i) for i in ids]


def _conectar(ruta: Path) -> sqlite3.Connection:
    con = sqlite3.connect(ruta)
    # row_factory permite leer columnas por nombre: fila["valor"] en vez de fila[2].
    con.row_factory = sqlite3.Row
    # SQLite NO revisa las claves foráneas (REFERENCES) a menos que se lo pidas,
    # conexión por conexión. Es una de las sorpresas clásicas de SQLite.
    con.execute("PRAGMA foreign_keys = ON")
    # WAL (Write-Ahead Logging): los cambios se escriben primero a un archivo
    # aparte (case.sqlite-wal) y luego se integran. Ventajas: escrituras más
    # rápidas y lectores que no se bloquean mientras alguien escribe (útil
    # cuando la web local lea el caso mientras la CLI importa).
    con.execute("PRAGMA journal_mode = WAL")
    # Con WAL, synchronous=NORMAL sigue siendo seguro ante cortes del programa;
    # ante un corte de luz se podría perder la última transacción, pero la base
    # nunca queda corrupta. Es el ajuste recomendado por la documentación de SQLite.
    con.execute("PRAGMA synchronous = NORMAL")
    return con
