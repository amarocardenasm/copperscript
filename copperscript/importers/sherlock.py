"""Importador de Sherlock (github.com/sherlock-project/sherlock).

=== STUB: por implementar. Tests: tests/test_importers.py ===
(Implementación comentada de referencia en la rama spike/v0.1-referencia.)

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

from collections.abc import Iterator
from pathlib import Path

from copperscript.core.models import Observacion
from copperscript.importers.base import Importador

_COLUMNAS_CSV = {"username", "url_user", "exists"}
_LINEA_TOTAL = "Total Websites Username Detected On"


class ImportadorSherlock(Importador):
    herramienta = "sherlock"
    confianza_base = 0.4

    def detectar(self, ruta: Path) -> bool:
        """True si es un CSV de Sherlock (cabecera con username, url_user y exists)
        o un TXT de Sherlock (archivo .txt que termina con la línea de total).

        Pista: leer solo la primera línea y, para el TXT, solo el final del archivo.
        """
        raise NotImplementedError("ImportadorSherlock.detectar()")

    def importar(self, ruta: Path) -> Iterator[Observacion]:
        """Una Observacion por cuenta encontrada:

            entidad  = RefEntidad(CUENTA, url_user)
            origen   = RefEntidad(USUARIO, username)
            relacion = "tiene_cuenta"
            confianza_fuente = self.confianza_base
            atributos = {"plataforma": name, "url_plataforma": url_main, ...}

        CSV: solo filas con exists == "Claimed" (usar csv.DictReader).
        TXT: el usuario es el nombre del archivo sin extensión (ruta.stem).
        """
        raise NotImplementedError("ImportadorSherlock.importar()")
