"""Importador de SpiderFoot (github.com/smicallef/spiderfoot).

=== STUB: por implementar. Tests: tests/test_importers.py ===
(Implementación comentada de referencia en la rama spike/v0.1-referencia.)

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

from collections.abc import Iterator
from pathlib import Path

from copperscript.core.models import Observacion, TipoEntidad
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


class ImportadorSpiderFoot(Importador):
    herramienta = "spiderfoot"
    confianza_base = 0.7  # mezcla de módulos buenos y ruidosos

    def detectar(self, ruta: Path) -> bool:
        """True si los primeros 4 KB empiezan con "[" y contienen "module" y "data"."""
        raise NotImplementedError("ImportadorSpiderFoot.detectar()")

    def importar(self, ruta: Path) -> Iterator[Observacion]:
        """Una Observacion por evento con tipo conocido (ver _TIPOS).

        - Aceptar ambos formatos: clave "type" o "event_type"; "source" o "source_data".
        - Saltar eventos con false_positive verdadero.
        - Dos pasadas: (1) anotar el tipo de cada valor; (2) crear observaciones
          con origen = padre y relacion = "descubierto_desde".
        - Si el padre no aparece como evento (es la semilla), adivinar su tipo
          por su forma (IP, email o dominio). Si no se puede, sin origen.
        - Confianza 0.9 para módulos "sfp_dns*", si no self.confianza_base.
        - atributos = {"modulo": ..., "tipo_spiderfoot": ...}
        """
        raise NotImplementedError("ImportadorSpiderFoot.importar()")
