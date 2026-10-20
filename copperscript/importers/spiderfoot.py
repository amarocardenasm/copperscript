"""Importador de SpiderFoot (github.com/smicallef/spiderfoot).

=== IMPLEMENTACIÓN DE REFERENCIA (rama spike/v0.1-referencia) ===

SpiderFoot exporta JSON de dos formas distintas (revisado en su código fuente):

1. Por terminal:  python3 sf.py -s ejemplo.cl -u passive -o json
   [{"generated": 1700000000, "type": "Internet Name", "data": "www.ejemplo.cl",
     "module": "sfp_dnsresolve", "source": "ejemplo.cl"}, ...]
   OJO: aquí "type" trae la DESCRIPCIÓN legible ("Internet Name"), no el código.

2. Desde la interfaz web (Export -> JSON):
   [{"data": "www.ejemplo.cl", "event_type": "INTERNET_NAME", "module": "...",
     "source_data": "ejemplo.cl", "false_positive": 0, ...}, ...]
   Aquí viene el código ("INTERNET_NAME") y además una marca de falso positivo.

Lección: nunca asumas el formato de una herramienta; ve a su código fuente.
Por eso este importador acepta ambos.

La relación padre -> hijo: cada evento dice de qué dato salió ("source").
Eso es una arista del grafo:

       dominio "ejemplo.cl"  --descubierto_desde-->  dominio "www.ejemplo.cl"

El evento solo trae el VALOR del padre, no su tipo. Para saber el tipo
hacemos dos pasadas: primero anotamos el tipo de cada valor que aparece,
después armamos las relaciones.
"""

from __future__ import annotations

import ipaddress
import json
import re
from collections.abc import Iterator
from pathlib import Path

from copperscript.core.models import Observacion, RefEntidad, TipoEntidad
from copperscript.importers.base import Importador

# Mapeo de tipos de SpiderFoot (código y descripción) a nuestros tipos.
# Los tipos que no están aquí se ignoran en v0.1: SpiderFoot tiene más de
# 170 tipos (puertos, tecnologías, textos crudos...) y meterlos todos al
# grafo lo convertiría en una "bola de pelos".
_TIPOS = {
    "INTERNET_NAME": TipoEntidad.DOMINIO,
    "Internet Name": TipoEntidad.DOMINIO,
    "DOMAIN_NAME": TipoEntidad.DOMINIO,
    "Domain Name": TipoEntidad.DOMINIO,
    "AFFILIATE_INTERNET_NAME": TipoEntidad.DOMINIO,
    "Affiliate - Internet Name": TipoEntidad.DOMINIO,
    "CO_HOSTED_SITE": TipoEntidad.DOMINIO,
    "Co-Hosted Site": TipoEntidad.DOMINIO,
    "IP_ADDRESS": TipoEntidad.IPV4,
    "IP Address": TipoEntidad.IPV4,
    "IPV6_ADDRESS": TipoEntidad.IPV6,
    "IPv6 Address": TipoEntidad.IPV6,
    "EMAILADDR": TipoEntidad.EMAIL,
    "Email Address": TipoEntidad.EMAIL,
    "USERNAME": TipoEntidad.USUARIO,
    "Username": TipoEntidad.USUARIO,
    "HUMAN_NAME": TipoEntidad.PERSONA,
    "Human Name": TipoEntidad.PERSONA,
    "LINKED_URL_INTERNAL": TipoEntidad.URL,
    "Linked URL - Internal": TipoEntidad.URL,
}

_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_RE_DOMINIO = re.compile(r"^(?=.{1,253}$)([a-z0-9-]{1,63}\.)+[a-z]{2,63}\.?$", re.IGNORECASE)


class ImportadorSpiderFoot(Importador):
    herramienta = "spiderfoot"
    confianza_base = 0.7  # mezcla de módulos buenos y ruidosos

    def detectar(self, ruta: Path) -> bool:
        # Barato: miramos solo los primeros 4 KB.
        try:
            with ruta.open(encoding="utf-8") as archivo:
                inicio = archivo.read(4096).lstrip()
        except (UnicodeDecodeError, OSError):
            return False
        return inicio.startswith("[") and '"module"' in inicio and '"data"' in inicio

    def importar(self, ruta: Path) -> Iterator[Observacion]:
        # json.load carga todo el archivo en memoria. Para escaneos enormes
        # (cientos de MB) habría que leerlo en streaming con la librería ijson.
        # Queda anotado como mejora futura; para v0.1 basta.
        with ruta.open(encoding="utf-8") as archivo:
            eventos = json.load(archivo)

        # Pasada 1: qué tipo tiene cada valor que aparece en el escaneo.
        tipo_de_valor: dict[str, TipoEntidad] = {}
        for evento in eventos:
            tipo = _tipo_de(evento)
            if tipo is not None:
                tipo_de_valor.setdefault(str(evento.get("data", "")).strip(), tipo)

        # Pasada 2: una observación por evento, con su arista al padre si podemos.
        for evento in eventos:
            tipo = _tipo_de(evento)
            if tipo is None or evento.get("false_positive"):
                continue
            dato = str(evento.get("data", "")).strip()
            padre = str(evento.get("source") or evento.get("source_data") or "").strip()
            modulo = str(evento.get("module", ""))

            origen = None
            if padre and padre != "ROOT" and padre != dato:
                # Si el padre no apareció como evento propio, es la semilla del
                # escaneo (el objetivo): adivinamos su tipo por su forma.
                tipo_padre = tipo_de_valor.get(padre) or _adivinar_tipo(padre)
                if tipo_padre is not None:
                    origen = RefEntidad(tipo_padre, padre)

            yield Observacion(
                entidad=RefEntidad(tipo, dato),
                origen=origen,
                relacion="descubierto_desde" if origen else None,
                confianza_fuente=self._confianza(modulo),
                atributos={
                    "modulo": modulo,
                    "tipo_spiderfoot": evento.get("type") or evento.get("event_type"),
                },
            )

    def _confianza(self, modulo: str) -> float:
        # Los módulos de DNS consultan directamente la fuente autoritativa:
        # son mucho más confiables que, por ejemplo, el scraping de buscadores.
        if modulo.startswith("sfp_dns"):
            return 0.9
        return self.confianza_base


def _tipo_de(evento: dict) -> TipoEntidad | None:
    clave = evento.get("event_type") or evento.get("type")
    return _TIPOS.get(str(clave)) if clave else None


def _adivinar_tipo(valor: str) -> TipoEntidad | None:
    """Tipo probable de un valor suelto, por su forma. None si no hay certeza."""
    try:
        ip = ipaddress.ip_address(valor)
        return TipoEntidad.IPV4 if ip.version == 4 else TipoEntidad.IPV6
    except ValueError:
        pass
    if _RE_EMAIL.match(valor):
        return TipoEntidad.EMAIL
    if _RE_DOMINIO.match(valor):
        return TipoEntidad.DOMINIO
    return None
