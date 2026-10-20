"""Motor de confianza (ADR-011).

=== STUB: por implementar. Tests: tests/test_core.py ===
(Implementación comentada de referencia en la rama spike/v0.1-referencia.)

Pregunta: si Sherlock dice que una cuenta existe (confianza 0.4) y Maigret
también (0.6), ¿cuánto confiamos en que existe?

Modelo "noisy-OR": calcula la probabilidad de que TODAS las fuentes se
equivoquen a la vez, y réstala de 1.

    P(todas se equivocan) = (1 - 0.4) * (1 - 0.6) = 0.24
    confianza combinada   = 1 - 0.24 = 0.76

Ojo: solo vale para fuentes INDEPENDIENTES. La misma herramienta repetida
cuenta una sola vez (con su observación más fuerte).
"""

from __future__ import annotations

from collections.abc import Iterable


def combinar(observaciones: Iterable[tuple[str, float]]) -> float:
    """Combina pares (herramienta, confianza) en una sola confianza entre 0 y 1.

    combinar([("sherlock", 0.4), ("maigret", 0.6)])   -> 0.76
    combinar([("sherlock", 0.4), ("sherlock", 0.4)])  -> 0.4   (misma fuente)
    combinar([])                                       -> 0.0

    Pistas:
      - Paso 1: un dict {herramienta: mejor confianza}.
      - Paso 2: multiplicar (1 - c) de cada herramienta.
      - Acotar cada confianza a [0, 1] por si un importador se equivoca.
      - round(x, 6) evita resultados como 0.7600000000000001.
    """
    raise NotImplementedError("combinar(): implementar noisy-OR por herramienta")
