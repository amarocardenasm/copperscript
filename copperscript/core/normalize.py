"""Normalización: convertir un valor crudo en su clave canónica (ADR-011).

=== STUB: por implementar. Tests: tests/test_core.py ===
(Implementación comentada de referencia en la rama spike/v0.1-referencia.)

Dos datos son la misma entidad si tienen el mismo tipo y la misma CLAVE.
La clave es el valor "limpio", escrito siempre de la misma forma:

    "Juan.Perez@Gmail.com "     ->  "juan.perez@gmail.com"
    "Ejemplo.CL."               ->  "ejemplo.cl"
    "https://GitHub.com/amaro/" ->  "https://github.com/amaro"

Regla de oro: la normalización NUNCA debe unir dos cosas distintas.
Ante la duda, normalizar menos.
"""

from __future__ import annotations

from copperscript.core.models import TipoEntidad


class ValorInvalido(ValueError):
    """El valor no tiene el formato que su tipo exige (ej. una IP con 5 octetos)."""


def normalizar(tipo: TipoEntidad, valor: str) -> str:
    """Devuelve la clave canónica de `valor` según su `tipo`.

    Reglas por tipo:
      - EMAIL: minúsculas; debe tener exactamente una @.
      - DOMINIO: minúsculas, sin punto final, en punycode ("ñandú.cl" -> "xn--...").
      - IPV4 / IPV6: forma canónica ("2001:DB8:0:0::1" -> "2001:db8::1").
      - URL / CUENTA: esquema y host en minúsculas, sin puerto por defecto,
        sin barra final, sin fragmento (#...); la query (?...) se conserva.
      - USUARIO: sin @ inicial, minúsculas.
      - PERSONA / OTRO: solo colapsar espacios repetidos.

    Lanza ValorInvalido si el valor está vacío o no tiene el formato del tipo.

    Pistas:
      - El módulo `ipaddress` de la librería estándar valida y escribe IPs.
      - `urllib.parse.urlsplit` separa una URL en sus 5 partes.
      - `"texto".encode("idna")` convierte un dominio a punycode.
      - Un dict {tipo: funcion} evita una cadena larga de if/elif.
    """
    raise NotImplementedError("normalizar(): implementar las reglas por tipo")
