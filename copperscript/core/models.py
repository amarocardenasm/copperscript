"""Modelo canónico de copperscript.

Este archivo es el "idioma común" del proyecto (ver ADR-010 del diseño).
Todas las herramientas externas (SpiderFoot, Sherlock, ...) se traducen
a estas clases, y el resto del sistema solo conoce estas clases.

Mapa con el diagrama entidad-relación (02-diagramas, diagrama 4):

    Corrida      -> una ejecución o importación concreta
    Evidencia    -> un archivo guardado por su hash
    RefEntidad   -> "puntero" a una entidad por (tipo, valor), sin id de base de datos
    Observacion  -> lo que un importador afirma haber visto
    Entidad      -> un nodo del grafo, ya guardado y deduplicado
    Relacion     -> una arista del grafo, ya guardada
    Hipotesis    -> una conclusión del analista (v0.2)

Este archivo solo DECLARA datos; no contiene lógica. Por eso está completo
tanto en `main` como en la rama de referencia.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class TipoEntidad(StrEnum):
    """Tipos de entidad. Los valores siguen los nombres de STIX 2.1 cuando existen.

    StrEnum hace que cada miembro sea también un str: TipoEntidad.EMAIL == "email-addr".
    Eso permite guardarlos en SQLite como texto sin conversiones.
    """

    DOMINIO = "domain-name"
    IPV4 = "ipv4-addr"
    IPV6 = "ipv6-addr"
    EMAIL = "email-addr"
    URL = "url"
    USUARIO = "username"  # un alias o "handle", independiente de la plataforma
    CUENTA = "user-account"  # una cuenta concreta en una plataforma (su URL de perfil)
    PERSONA = "identity"
    OTRO = "x-otro"  # el prefijo x- es la convención de STIX para tipos propios


@dataclass(frozen=True)
class RefEntidad:
    """Referencia a una entidad por su tipo y valor crudo.

    Los importadores no conocen los ids de la base de datos, así que se
    refieren a las entidades con esta referencia. frozen=True la vuelve
    inmutable y "hasheable": se puede usar como clave de un dict o en un set.
    """

    tipo: TipoEntidad
    valor: str


@dataclass
class Corrida:
    """Una ejecución de una herramienta o una importación de su archivo."""

    herramienta: str
    fecha: datetime
    version: str | None = None
    comando: str | None = None
    evidencia_sha256: str | None = None  # el archivo crudo del que salió todo
    id: int | None = None  # lo asigna la base de datos al guardar


@dataclass
class Evidencia:
    """Un archivo guardado en evidence/ con su hash SHA-256 como nombre (ADR-004)."""

    sha256: str
    nombre_original: str
    tamano: int
    tipo_mime: str | None = None


@dataclass
class Observacion:
    """Lo que un importador afirma: "vi esta entidad" y, opcionalmente,
    "y está relacionada con esta otra".

    Si `origen` y `relacion` vienen, la observación también afirma la arista:

        origen --relacion--> entidad

    Ejemplo (Sherlock): origen = usuario "amaro_dev",
    relacion = "tiene_cuenta", entidad = cuenta "https://github.com/amaro_dev".
    """

    entidad: RefEntidad
    confianza_fuente: float = 0.5  # 0.0 a 1.0: cuánto confiamos en quien lo afirma
    origen: RefEntidad | None = None
    relacion: str | None = None
    atributos: dict[str, Any] = field(default_factory=dict)


@dataclass
class Entidad:
    """Un nodo del grafo ya guardado. `clave` es el valor normalizado (ADR-011)."""

    id: int
    tipo: TipoEntidad
    valor: str
    clave: str
    confianza: float = 0.0  # calculada a partir de sus observaciones, no se guarda


@dataclass
class Relacion:
    """Una arista del grafo ya guardada."""

    id: int
    origen_id: int
    destino_id: int
    tipo: str


@dataclass
class Hipotesis:
    """Conclusión del analista, apoyada en observaciones (v0.2)."""

    texto: str
    estado: str = "abierta"  # abierta | confirmada | descartada
    id: int | None = None
