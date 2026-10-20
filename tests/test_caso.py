"""Tests del caso completo: importar, resolver entidades, exportar y CLI.

Son tests de INTEGRACIÓN: prueban varias piezas trabajando juntas, igual
que el diagrama 3 ("el viaje de un dato").
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from copperscript.cli import app
from copperscript.core.models import TipoEntidad
from copperscript.core.store import Caso, CasoNoEncontrado
from copperscript.exporters.html_graph import exportar_html
from copperscript.exporters.obsidian import exportar_obsidian
from copperscript.importers.sherlock import ImportadorSherlock
from copperscript.importers.spiderfoot import ImportadorSpiderFoot


@pytest.fixture
def caso(tmp_path: Path):
    with Caso.crear(tmp_path / "caso", nombre="Prueba", objetivo="Huella de amaro_dev") as c:
        yield c  # yield en un fixture: el código después del with se ejecuta al terminar el test


def test_crear_y_abrir_caso(tmp_path: Path):
    carpeta = tmp_path / "caso"
    Caso.crear(carpeta, nombre="Prueba").cerrar()
    assert (carpeta / "case.sqlite").exists()
    assert (carpeta / "evidence").is_dir()
    with Caso.abrir(carpeta) as caso:
        assert caso.metadatos()["nombre"] == "Prueba"


def test_abrir_carpeta_sin_caso(tmp_path: Path):
    with pytest.raises(CasoNoEncontrado):
        Caso.abrir(tmp_path)


def test_importar_guarda_el_crudo_y_crea_el_grafo(caso: Caso, datos: Path):
    resumen = caso.importar(datos / "amaro_dev.csv", ImportadorSherlock())

    assert resumen.herramienta == "sherlock"
    assert resumen.observaciones == 2
    assert resumen.entidades_nuevas == 3  # 1 usuario + 2 cuentas
    assert resumen.relaciones_nuevas == 2
    # El archivo crudo quedó como evidencia.
    assert any(p.is_file() for p in caso.carpeta_evidencia.rglob("*"))
    assert len(caso.entidades(TipoEntidad.CUENTA)) == 2


def test_reimportar_no_duplica(caso: Caso, datos: Path):
    caso.importar(datos / "amaro_dev.csv", ImportadorSherlock())
    segundo = caso.importar(datos / "amaro_dev.txt", ImportadorSherlock())
    # El TXT trae las mismas cuentas con otro formato: nada nuevo.
    assert segundo.entidades_nuevas == 0
    assert segundo.relaciones_nuevas == 0
    assert len(caso.entidades()) == 3


def test_corroboracion_entre_herramientas_sube_la_confianza(caso: Caso, datos: Path):
    caso.importar(datos / "amaro_dev.csv", ImportadorSherlock())
    solo_sherlock = caso.buscar(TipoEntidad.USUARIO, "amaro_dev")
    assert solo_sherlock is not None
    assert solo_sherlock.confianza == pytest.approx(0.4)

    # SpiderFoot también encontró el usuario: dos fuentes independientes.
    caso.importar(datos / "spiderfoot_cli.json", ImportadorSpiderFoot())
    ambos = caso.buscar(TipoEntidad.USUARIO, "@Amaro_Dev")  # se busca normalizando
    assert ambos is not None
    assert ambos.id == solo_sherlock.id  # misma entidad: se resolvió
    assert ambos.confianza == pytest.approx(1 - 0.6 * 0.3)  # noisy-OR de 0.4 y 0.7


def test_vecinos(caso: Caso, datos: Path):
    caso.importar(datos / "amaro_dev.csv", ImportadorSherlock())
    usuario = caso.buscar(TipoEntidad.USUARIO, "amaro_dev")
    assert usuario is not None
    vecinos = list(caso.vecinos(usuario.id))
    assert len(vecinos) == 2
    assert all(rel.tipo == "tiene_cuenta" for rel, _ in vecinos)


def test_exportar_obsidian(caso: Caso, datos: Path):
    caso.importar(datos / "amaro_dev.csv", ImportadorSherlock())
    boveda = exportar_obsidian(caso)
    notas = sorted(p.name for p in boveda.rglob("*.md"))
    assert "amaro_dev.md" in notas
    nota_usuario = next(boveda.rglob("amaro_dev.md")).read_text(encoding="utf-8")
    assert "tipo: username" in nota_usuario
    assert "[[www.github.com_amaro_dev]]" in nota_usuario


def test_exportar_html(caso: Caso, datos: Path):
    caso.importar(datos / "spiderfoot_cli.json", ImportadorSpiderFoot())
    pagina = exportar_html(caso).read_text(encoding="utf-8")
    assert "cytoscape" in pagina
    assert "www.ejemplo.cl" in pagina


def _ejecutar(*argumentos: str):
    """Ejecuta la CLI dentro del test, sin abrir una terminal.

    CliRunner atrapa las excepciones; si la causa fue una función aún no
    implementada, la relanzamos para que el test quede como PENDIENTE.
    """
    resultado = CliRunner().invoke(app, list(argumentos))
    if isinstance(resultado.exception, NotImplementedError):
        raise resultado.exception
    return resultado


def test_cli_flujo_completo(tmp_path: Path, datos: Path):
    carpeta = str(tmp_path / "caso")

    r = _ejecutar("nuevo", carpeta, "--nombre", "Prueba")
    assert r.exit_code == 0, r.output
    r = _ejecutar("importar", carpeta, str(datos / "amaro_dev.csv"))
    assert r.exit_code == 0, r.output
    assert "[sherlock]" in r.output
    r = _ejecutar("entidades", carpeta)
    assert "amaro_dev" in r.output
    r = _ejecutar("exportar", carpeta, "obsidian")
    assert r.exit_code == 0, r.output
