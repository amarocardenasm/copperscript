"""Tests de los importadores: detección de formato y traducción al modelo canónico."""

from __future__ import annotations

from pathlib import Path

import pytest

from copperscript.core.models import TipoEntidad
from copperscript.importers import FormatoDesconocido, detectar_importador
from copperscript.importers.sherlock import ImportadorSherlock
from copperscript.importers.spiderfoot import ImportadorSpiderFoot


@pytest.mark.parametrize(
    ("archivo", "herramienta"),
    [
        ("amaro_dev.csv", "sherlock"),
        ("amaro_dev.txt", "sherlock"),
        ("spiderfoot_cli.json", "spiderfoot"),
        ("spiderfoot_web.json", "spiderfoot"),
    ],
)
def test_detecta_el_importador_correcto(datos: Path, archivo, herramienta):
    assert detectar_importador(datos / archivo).herramienta == herramienta


def test_formato_desconocido(tmp_path: Path):
    raro = tmp_path / "notas.txt"
    raro.write_text("esto no es de ninguna herramienta\n", encoding="utf-8")
    with pytest.raises(FormatoDesconocido):
        detectar_importador(raro)


def test_sherlock_csv_solo_importa_cuentas_encontradas(datos: Path):
    obs = list(ImportadorSherlock().importar(datos / "amaro_dev.csv"))
    assert [o.entidad.valor for o in obs] == [
        "https://www.github.com/amaro_dev",
        "https://www.reddit.com/user/amaro_dev",
    ]
    primera = obs[0]
    assert primera.entidad.tipo is TipoEntidad.CUENTA
    assert primera.origen is not None
    assert (primera.origen.tipo, primera.origen.valor) == (TipoEntidad.USUARIO, "amaro_dev")
    assert primera.relacion == "tiene_cuenta"
    assert primera.atributos["plataforma"] == "GitHub"
    assert primera.confianza_fuente == pytest.approx(0.4)


def test_sherlock_txt_toma_el_usuario_del_nombre_del_archivo(datos: Path):
    obs = list(ImportadorSherlock().importar(datos / "amaro_dev.txt"))
    assert len(obs) == 2
    assert all(o.origen is not None and o.origen.valor == "amaro_dev" for o in obs)


def test_spiderfoot_cli_traduce_tipos_y_padres(datos: Path):
    obs = list(ImportadorSpiderFoot().importar(datos / "spiderfoot_cli.json"))
    # El puerto abierto no está mapeado en v0.1: se ignora.
    assert len(obs) == 4
    ip = next(o for o in obs if o.entidad.tipo is TipoEntidad.IPV4)
    assert ip.entidad.valor == "192.0.2.10"
    assert ip.origen is not None
    assert (ip.origen.tipo, ip.origen.valor) == (TipoEntidad.DOMINIO, "www.ejemplo.cl")
    assert ip.confianza_fuente == pytest.approx(0.9)  # módulo de DNS
    # El padre del primer evento es la semilla "ejemplo.cl": su tipo se adivina.
    www = next(o for o in obs if o.entidad.valor == "www.ejemplo.cl")
    assert www.origen is not None and www.origen.tipo is TipoEntidad.DOMINIO


def test_spiderfoot_web_ignora_falsos_positivos(datos: Path):
    obs = list(ImportadorSpiderFoot().importar(datos / "spiderfoot_web.json"))
    assert [o.entidad.valor for o in obs] == ["www.ejemplo.cl"]
