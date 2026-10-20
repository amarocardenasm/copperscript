"""Importador de Sherlock (github.com/sherlock-project/sherlock).

=== IMPLEMENTACIÓN DE REFERENCIA (rama spike/v0.1-referencia) ===

Sherlock busca un nombre de usuario en cientos de sitios. Produce dos formatos:

1. CSV (con la opción --csv). Una fila por sitio revisado:

       username,name,url_main,url_user,exists,http_status,response_time_s
       amaro_dev,GitHub,https://www.github.com/,https://www.github.com/amaro_dev,Claimed,200,0.31

   "exists" puede ser Claimed (encontrado), Available (no existe), Unknown...
   Solo nos interesan las filas Claimed.

2. TXT (por defecto), con el nombre <usuario>.txt. Una URL por línea y al
   final un total:

       https://www.github.com/amaro_dev
       https://www.reddit.com/user/amaro_dev
       Total Websites Username Detected On : 2

Cómo lo traducimos al modelo canónico:

       usuario "amaro_dev"  --tiene_cuenta-->  cuenta "https://www.github.com/amaro_dev"

Confianza base BAJA (0.4): Sherlock tiene muchos falsos positivos, porque hay
sitios que responden "existe" para cualquier nombre. Esos datos quedan como
"por verificar" hasta que otra herramienta independiente los confirme.
"""

from __future__ import annotations

import csv
from collections.abc import Iterator
from pathlib import Path

from copperscript.core.models import Observacion, RefEntidad, TipoEntidad
from copperscript.importers.base import Importador

_COLUMNAS_CSV = {"username", "url_user", "exists"}
_LINEA_TOTAL = "Total Websites Username Detected On"


class ImportadorSherlock(Importador):
    herramienta = "sherlock"
    confianza_base = 0.4

    def detectar(self, ruta: Path) -> bool:
        primera = _primera_linea(ruta)
        if primera is None:
            return False
        # Formato CSV: la cabecera trae las columnas que necesitamos.
        columnas = {c.strip() for c in primera.split(",")}
        if _COLUMNAS_CSV <= columnas:  # <= entre sets significa "es subconjunto de"
            return True
        # Formato TXT: termina con la línea de total.
        if ruta.suffix.lower() == ".txt":
            return any(linea.startswith(_LINEA_TOTAL) for linea in _ultimas_lineas(ruta))
        return False

    def importar(self, ruta: Path) -> Iterator[Observacion]:
        primera = _primera_linea(ruta) or ""
        if "url_user" in primera:
            yield from self._importar_csv(ruta)
        else:
            yield from self._importar_txt(ruta)

    def _importar_csv(self, ruta: Path) -> Iterator[Observacion]:
        # newline="" es lo que pide el módulo csv: así maneja él los saltos de
        # línea, incluidos los que vienen dentro de un campo entre comillas.
        with ruta.open(newline="", encoding="utf-8") as archivo:
            for fila in csv.DictReader(
                archivo
            ):  # DictReader: cada fila es un dict por nombre de columna
                if (fila.get("exists") or "").strip().lower() != "claimed":
                    continue
                yield self._observacion(
                    usuario=fila["username"],
                    url=fila["url_user"],
                    atributos={
                        "plataforma": fila.get("name"),
                        "url_plataforma": fila.get("url_main"),
                        "http_status": fila.get("http_status"),
                    },
                )

    def _importar_txt(self, ruta: Path) -> Iterator[Observacion]:
        # En el TXT el usuario no aparece dentro del archivo: está en el nombre.
        # "amaro_dev.txt" -> stem = "amaro_dev"
        usuario = ruta.stem
        with ruta.open(encoding="utf-8") as archivo:
            for linea in archivo:
                linea = linea.strip()
                if linea.startswith(("http://", "https://")):
                    yield self._observacion(usuario=usuario, url=linea, atributos={})

    def _observacion(self, usuario: str, url: str, atributos: dict) -> Observacion:
        return Observacion(
            entidad=RefEntidad(TipoEntidad.CUENTA, url),
            origen=RefEntidad(TipoEntidad.USUARIO, usuario),
            relacion="tiene_cuenta",
            confianza_fuente=self.confianza_base,
            atributos=atributos,
        )


def _primera_linea(ruta: Path) -> str | None:
    try:
        with ruta.open(encoding="utf-8") as archivo:
            return archivo.readline().strip()
    except (UnicodeDecodeError, OSError):
        return None  # binario o ilegible: claramente no es de Sherlock


def _ultimas_lineas(ruta: Path, cantidad: int = 3) -> list[str]:
    # Leemos solo el final del archivo (los últimos 4 KB) para que detectar
    # sea barato aunque el archivo sea grande.
    with ruta.open("rb") as archivo:
        archivo.seek(0, 2)  # 2 = desde el final; nos dice el tamaño
        tamano = archivo.tell()
        archivo.seek(max(0, tamano - 4096))
        cola = archivo.read().decode("utf-8", errors="ignore")
    lineas = [linea.strip() for linea in cola.splitlines() if linea.strip()]
    return lineas[-cantidad:]
