"""Benchmark de copperscript: mide tiempo y memoria con un caso grande sintético.

Uso:
    python -I herramientas/benchmark.py [cantidad_de_usuarios]

Regla de oro de la optimización: no se optimiza a ojo, se MIDE. Este script
genera datos falsos con el formato real de Sherlock y SpiderFoot, los importa
y cronometra cada operación. Se corre antes y después de cada cambio de
rendimiento, y los números se anotan en BITACORA.md.

Los datos son sintéticos: usuarios "usuario00001", dominios .example (un TLD
reservado para documentación por el RFC 2606) e IPs del rango 198.18.0.0/15
(reservado para pruebas de rendimiento por el RFC 2544).
"""

from __future__ import annotations

import csv
import json
import random
import resource
import sys
import tempfile
import time
from pathlib import Path

from copperscript.core.models import TipoEntidad
from copperscript.core.store import Caso
from copperscript.exporters.html_graph import exportar_html
from copperscript.exporters.obsidian import exportar_obsidian
from copperscript.importers.sherlock import ImportadorSherlock
from copperscript.importers.spiderfoot import ImportadorSpiderFoot

SITIOS = ["github.com", "reddit.com/user", "gitlab.com", "keybase.io", "dev.to", "medium.com/@"]


def generar_sherlock(ruta: Path, usuarios: int) -> None:
    with ruta.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            ["username", "name", "url_main", "url_user", "exists", "http_status", "response_time_s"]
        )
        for i in range(usuarios):
            u = f"usuario{i:05d}"
            for sitio in SITIOS:
                estado = "Claimed" if random.random() < 0.5 else "Available"
                w.writerow([u, sitio, f"https://{sitio}", f"https://{sitio}/{u}", estado, 200, 0.3])


def generar_spiderfoot(ruta: Path, usuarios: int) -> None:
    eventos = []
    for i in range(usuarios):
        dom = f"sitio{i:05d}.example"
        sub = f"www.{dom}"
        ip = f"198.18.{(i // 250) % 256}.{i % 250 + 1}"
        mail = f"contacto@{dom}"
        eventos += [
            {"type": "Internet Name", "data": sub, "module": "sfp_dnsresolve", "source": dom},
            {"type": "IP Address", "data": ip, "module": "sfp_dnsresolve", "source": sub},
            {"type": "Email Address", "data": mail, "module": "sfp_email", "source": sub},
            {
                "type": "Username",
                "data": f"usuario{i:05d}",
                "module": "sfp_accounts",
                "source": mail,
            },
        ]
    ruta.write_text(json.dumps(eventos), encoding="utf-8")


def medir(nombre: str, funcion):
    inicio = time.perf_counter()  # perf_counter: el reloj más preciso para medir intervalos
    resultado = funcion()
    print(f"  {nombre:<34} {time.perf_counter() - inicio:8.2f} s")
    return resultado


def main() -> None:
    usuarios = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    random.seed(42)  # semilla fija: los datos son los mismos en cada corrida
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        generar_sherlock(tmp / "sherlock.csv", usuarios)
        generar_spiderfoot(tmp / "spiderfoot.json", usuarios)
        print(f"Caso sintético: {usuarios} usuarios")
        with Caso.crear(tmp / "caso", nombre="benchmark") as caso:
            medir(
                "importar Sherlock",
                lambda: caso.importar(tmp / "sherlock.csv", ImportadorSherlock()),
            )
            medir(
                "importar SpiderFoot",
                lambda: caso.importar(tmp / "spiderfoot.json", ImportadorSpiderFoot()),
            )
            entidades = medir("listar entidades", caso.entidades)
            medir(
                "100 búsquedas",
                lambda: [caso.buscar(TipoEntidad.USUARIO, f"usuario{i:05d}") for i in range(100)],
            )
            medir("anclar 1 usuario", lambda: caso.anclar(TipoEntidad.USUARIO, "usuario00000"))
            medir("listar con atribución", caso.entidades)
            medir("exportar HTML", lambda: exportar_html(caso))
            medir("exportar Obsidian", lambda: exportar_obsidian(caso))
            tamano_db = (tmp / "caso" / "case.sqlite").stat().st_size / 1e6
        # ru_maxrss: memoria máxima usada por el proceso (en KB en Linux).
        pico = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        print(f"  {'entidades / relaciones':<34} {len(entidades)}")
        print(f"  {'tamaño de case.sqlite':<34} {tamano_db:8.1f} MB")
        print(f"  {'memoria máxima del proceso':<34} {pico:8.1f} MB")


if __name__ == "__main__":
    main()
