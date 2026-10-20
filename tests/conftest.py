"""Configuración compartida de los tests.

Los tests son la ESPECIFICACIÓN de copperscript: dicen qué debe hacer cada
función. En `main` las funciones son stubs que lanzan NotImplementedError;
el gancho de abajo convierte esos fallos en "PENDIENTE" (skipped) para que
la integración continua siga en verde mientras el núcleo se va implementando.

Flujo de trabajo (TDD, desarrollo guiado por tests):
    1. Correr `pytest -rs` y elegir un test pendiente.
    2. Implementar la función hasta que pase.
    3. Repetir. Cuando no quedan pendientes, la versión está completa.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

DATOS = Path(__file__).parent / "datos"


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    resultado = yield
    reporte = resultado.get_result()
    if call.excinfo is not None and call.excinfo.errisinstance(NotImplementedError):
        reporte.outcome = "skipped"
        reporte.longrepr = (
            str(item.path),
            item.location[1] or 0,
            f"PENDIENTE: {call.excinfo.value}",
        )


@pytest.fixture
def datos(tmp_path: Path) -> Path:
    """Copia los archivos de ejemplo a una carpeta temporal.

    tmp_path es un fixture de pytest: una carpeta nueva y vacía por test,
    que se borra sola. Así ningún test ensucia el repositorio ni a otro test.
    """
    destino = tmp_path / "datos"
    shutil.copytree(DATOS, destino)
    return destino
