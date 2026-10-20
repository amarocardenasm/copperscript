"""Tests de ADR-013 (solo en la rama spike): migraciones, atribución e hipótesis."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from copperscript.cli import app
from copperscript.core import hipotesis as bayes
from copperscript.core.atribucion import propagar
from copperscript.core.models import TipoEntidad
from copperscript.core.store import _ESQUEMA, VERSION_ESQUEMA, Caso
from copperscript.importers.sherlock import ImportadorSherlock
from copperscript.importers.spiderfoot import ImportadorSpiderFoot

# --- Bayes en forma de odds --------------------------------------------------


def test_posterior_usuario_raro_vs_comun():
    # El ejemplo del chat: la misma evidencia, distinta rareza del alias.
    assert bayes.posterior(0.6, [20, 2]) == pytest.approx(60 / 61)
    assert bayes.posterior(0.02, [20, 2]) == pytest.approx(0.449, abs=0.001)


def test_evidencia_en_contra_baja_la_probabilidad():
    assert bayes.posterior(0.5, [0.25]) == pytest.approx(0.2)


def test_decibanes():
    assert bayes.decibanes(10) == pytest.approx(10)
    assert bayes.decibanes(1) == pytest.approx(0)
    assert bayes.decibanes(0.1) == pytest.approx(-10)


@pytest.mark.parametrize("prior", [0.0, 1.0, -0.1, 1.5])
def test_prior_invalido(prior):
    with pytest.raises(ValueError):
        bayes.posterior(prior, [])


def test_lr_invalido():
    with pytest.raises(ValueError):
        bayes.decibanes(0)


# --- Propagación de atribución ----------------------------------------------


def test_propagar_debilita_con_cada_salto():
    # 1 (ancla) --tiene_cuenta--> 2 --descubierto_desde--> 3 ;  4 suelto
    aristas = [(1, 2, "tiene_cuenta", 1.0), (2, 3, "descubierto_desde", 1.0)]
    existencia = {1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0}
    resultado = propagar({1}, aristas, existencia)
    assert resultado[1] == 1.0
    assert resultado[2] == pytest.approx(0.85)
    assert resultado[3] == pytest.approx(0.85 * 0.5)
    assert 4 not in resultado  # sin camino desde el ancla: nada que atribuir


def test_existencia_es_techo_no_factor():
    # Relación segura (1.0) hacia un nodo dudoso (0.3): la atribución no puede
    # superar la existencia, pero tampoco se multiplica por ella (doble conteo).
    resultado = propagar({1}, [(1, 2, "tiene_cuenta", 1.0)], {1: 1.0, 2: 0.3})
    assert resultado[2] == pytest.approx(0.3)


def test_propagar_elige_el_mejor_camino_y_fluye_en_ambos_sentidos():
    # Dos caminos de 1 a 3: directo débil (0.4) o por 2 (0.85 * 0.85 = 0.72).
    aristas = [
        (1, 3, "relacionado_con", 1.0),
        (2, 1, "tiene_cuenta", 1.0),
        (2, 3, "tiene_cuenta", 1.0),
    ]
    resultado = propagar({1}, aristas, {1: 1.0, 2: 1.0, 3: 1.0})
    assert resultado[3] == pytest.approx(0.85 * 0.85)


# --- Caso: migraciones, anclas e hipótesis -----------------------------------


def test_caso_viejo_se_migra_al_abrirlo(tmp_path: Path):
    # Simulamos un caso creado con la versión 1 (sin tablas de ADR-013).
    carpeta = tmp_path / "viejo"
    (carpeta / "evidence").mkdir(parents=True)
    con = sqlite3.connect(carpeta / "case.sqlite")
    con.executescript(_ESQUEMA)
    con.executemany(
        "INSERT INTO meta VALUES (?, ?)", [("nombre", "Viejo"), ("version_esquema", "1")]
    )
    con.execute("INSERT INTO hipotesis (texto) VALUES ('hipótesis de antes')")
    con.commit()
    con.close()

    with Caso.abrir(carpeta) as caso:
        assert caso.version_esquema() == VERSION_ESQUEMA
        assert caso.anclas() == set()
        # La hipótesis vieja recibió la previa por defecto de la migración.
        assert caso.evaluar_hipotesis(1).prior == 0.5


def test_caso_de_una_version_futura_no_se_toca(tmp_path: Path):
    carpeta = tmp_path / "futuro"
    Caso.crear(carpeta, nombre="Futuro").cerrar()
    con = sqlite3.connect(carpeta / "case.sqlite")
    con.execute("UPDATE meta SET valor = '99' WHERE clave = 'version_esquema'")
    con.commit()
    con.close()
    with pytest.raises(RuntimeError, match="v99"):
        Caso.abrir(carpeta)


@pytest.fixture
def caso_demo(tmp_path: Path, datos: Path):
    with Caso.crear(tmp_path / "caso", nombre="Demo") as caso:
        caso.importar(datos / "amaro_dev.csv", ImportadorSherlock())
        caso.importar(datos / "spiderfoot_cli.json", ImportadorSpiderFoot())
        yield caso


def test_sin_anclas_la_atribucion_no_aplica(caso_demo: Caso):
    assert all(e.atribucion is None for e in caso_demo.entidades())


def test_anclar_y_propagar(caso_demo: Caso):
    caso_demo.anclar(TipoEntidad.USUARIO, "amaro_dev", nota="Confirmado por el cliente")

    usuario = caso_demo.buscar(TipoEntidad.USUARIO, "amaro_dev")
    github = caso_demo.buscar(TipoEntidad.CUENTA, "https://www.github.com/amaro_dev")
    email = caso_demo.buscar(TipoEntidad.EMAIL, "contacto@ejemplo.cl")
    ip = caso_demo.buscar(TipoEntidad.IPV4, "192.0.2.10")
    assert usuario and github and email and ip

    # El analista es una fuente con confianza 1.0: ahora el usuario existe con certeza.
    assert usuario.confianza == 1.0 and usuario.atribucion == 1.0
    # Cuenta: min(ancla × peso tiene_cuenta × conf. relación, existencia) = min(0.34, 0.4)
    # (Antes daba 0.136 por doble conteo; ver bitácora, entrada 003.)
    assert github.atribucion == pytest.approx(0.34)
    # Email (por descubierto_desde, en sentido contrario): min(1 × 0.5 × 0.7, 0.7)
    assert email.atribucion == pytest.approx(0.35)
    # Existir con certeza no significa pertenecer: la IP existe (0.9) pero es lejana.
    assert ip.confianza == pytest.approx(0.9)
    assert ip.atribucion < 0.1


def test_hipotesis_en_el_caso(caso_demo: Caso):
    texto = "reddit/amaro_dev es la misma persona que github/amaro_dev"
    hid = caso_demo.crear_hipotesis(texto, 0.6)
    caso_demo.agregar_evidencia(hid, "Mismo avatar (hash de imagen idéntico)", 20)
    caso_demo.agregar_evidencia(hid, "Actividad en el mismo huso horario", 2)
    ev = caso_demo.evaluar_hipotesis(hid)
    assert ev.posterior == pytest.approx(60 / 61, abs=1e-6)
    assert [e.decibanes for e in ev.evidencias] == [13.01, 3.01]
    with pytest.raises(ValueError):
        caso_demo.agregar_evidencia(hid, "imposible", 0)


def test_cli_anclas_e_hipotesis(tmp_path: Path, datos: Path):
    runner = CliRunner()
    carpeta = str(tmp_path / "caso")
    assert runner.invoke(app, ["nuevo", carpeta]).exit_code == 0
    runner.invoke(app, ["importar", carpeta, str(datos / "amaro_dev.csv")])

    r = runner.invoke(app, ["anclar", carpeta, "username", "amaro_dev", "--nota", "verificado"])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["entidades", carpeta])
    assert "ATRIB" in r.output

    r = runner.invoke(app, ["hipotesis", "nueva", carpeta, "Misma persona", "--prior", "0.02"])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["hipotesis", "evidencia", carpeta, "1", "Mismo avatar", "--lr", "40"])
    assert r.exit_code == 0, r.output
    assert "44.9%" in r.output
    r = runner.invoke(app, ["hipotesis", "ver", carpeta])
    assert "+16.0 dB" in r.output
