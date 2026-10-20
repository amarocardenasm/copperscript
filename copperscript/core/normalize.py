"""Normalización: convertir un valor crudo en su clave canónica (ADR-011).

=== IMPLEMENTACIÓN DE REFERENCIA (rama spike/v0.1-referencia) ===

La idea central de la resolución de entidades es simple: dos datos son la
misma entidad si tienen el mismo tipo y la misma CLAVE. La clave es el valor
"limpio", escrito siempre de la misma forma.

    "Juan.Perez@Gmail.com "   ->  "juan.perez@gmail.com"
    "Ejemplo.CL."             ->  "ejemplo.cl"
    "https://GitHub.com/amaro/" -> "https://github.com/amaro"

Regla de oro: la normalización NUNCA debe unir dos cosas que son distintas.
Ante la duda, normalizar menos. Un duplicado se puede fusionar después;
una fusión equivocada contamina todo el caso.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit, urlunsplit

from copperscript.core.models import TipoEntidad


class ValorInvalido(ValueError):
    """El valor no tiene el formato que su tipo exige (ej. una IP con 5 octetos)."""


def normalizar(tipo: TipoEntidad, valor: str) -> str:
    """Devuelve la clave canónica de `valor` según su `tipo`.

    Funciona como un "despachador": mira el tipo y llama a la función
    específica. Usar un dict en vez de una cadena de if/elif hace que
    agregar un tipo nuevo sea agregar una línea.
    """
    # strip() quita espacios y saltos de línea en los extremos. Casi todos
    # los datos que vienen de CSV o de texto pegado los traen.
    valor = valor.strip()
    if not valor:
        raise ValorInvalido("valor vacío")

    funcion = _NORMALIZADORES.get(tipo, _normalizar_generico)
    return funcion(valor)


def _normalizar_email(valor: str) -> str:
    # Técnicamente la parte antes de la @ puede distinguir mayúsculas, pero
    # en la práctica ningún proveedor lo hace. Pasar todo a minúsculas es el
    # estándar de facto en OSINT.
    if valor.count("@") != 1:
        raise ValorInvalido(f"email sin una única @: {valor!r}")
    return valor.lower()


def _normalizar_dominio(valor: str) -> str:
    # 1. Minúsculas: DNS no distingue mayúsculas.
    # 2. Quitar el punto final: "ejemplo.cl." es la forma "absoluta" del
    #    mismo nombre; SpiderFoot y dig a veces la devuelven así.
    # 3. Punycode: "ñandú.cl" y "xn--and-6ma2c.cl" son el mismo dominio.
    #    Lo guardamos siempre en la forma ASCII (la que viaja por la red).
    valor = valor.lower().rstrip(".")
    try:
        return valor.encode("idna").decode("ascii")
    except UnicodeError as error:
        raise ValorInvalido(f"dominio inválido: {valor!r}") from error


def _normalizar_ip(valor: str) -> str:
    # El módulo ipaddress de la librería estándar ya sabe validar y escribir
    # IPs en forma canónica. Para IPv6 es clave: "2001:db8:0:0::1" y
    # "2001:db8::1" son la misma dirección, y .compressed elige una sola forma.
    try:
        return ipaddress.ip_address(valor).compressed
    except ValueError as error:
        raise ValorInvalido(f"IP inválida: {valor!r}") from error


def _normalizar_url(valor: str) -> str:
    # urlsplit separa una URL en 5 partes: esquema, host, ruta, query, fragmento.
    #   https://GitHub.com:443/amaro/?tab=repos#top
    #   esquema=https  host=GitHub.com:443  ruta=/amaro/  query=tab=repos  fragmento=top
    partes = urlsplit(valor)
    if not partes.scheme or not partes.netloc:
        raise ValorInvalido(f"URL sin esquema o sin host: {valor!r}")

    esquema = partes.scheme.lower()
    host = partes.netloc.lower()
    # Quitar el puerto por defecto: https://x.cl:443 es lo mismo que https://x.cl
    if (esquema, host.rsplit(":", 1)[-1]) in {("https", "443"), ("http", "80")}:
        host = host.rsplit(":", 1)[0]

    # La barra final no cambia el recurso en casi ningún sitio de perfiles.
    ruta = partes.path.rstrip("/")

    # El fragmento (#...) nunca llega al servidor: es solo para el navegador.
    # Por eso lo descartamos. La query (?...) SÍ cambia el recurso: se conserva.
    return urlunsplit((esquema, host, ruta, partes.query, ""))


def _normalizar_usuario(valor: str) -> str:
    # "@Amaro_Dev" y "amaro_dev" son el mismo alias en casi todas las redes.
    return valor.lstrip("@").lower()


def _normalizar_generico(valor: str) -> str:
    # Para PERSONA y OTRO no adivinamos nada: dos "Juan Pérez" pueden ser
    # personas distintas. Solo colapsamos espacios repetidos.
    return " ".join(valor.split())


_NORMALIZADORES = {
    TipoEntidad.EMAIL: _normalizar_email,
    TipoEntidad.DOMINIO: _normalizar_dominio,
    TipoEntidad.IPV4: _normalizar_ip,
    TipoEntidad.IPV6: _normalizar_ip,
    TipoEntidad.URL: _normalizar_url,
    TipoEntidad.CUENTA: _normalizar_url,  # una cuenta se identifica por la URL de su perfil
    TipoEntidad.USUARIO: _normalizar_usuario,
}
