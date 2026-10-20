"""Motor de confianza (ADR-011).

=== IMPLEMENTACIÓN DE REFERENCIA (rama spike/v0.1-referencia) ===

Pregunta: si Sherlock dice que una cuenta existe (confianza 0.4) y Maigret
también (0.6), ¿cuánto confiamos en que existe?

Modelo "noisy-OR" (O ruidoso), clásico en redes bayesianas. Pensemos en la
probabilidad de que TODAS las fuentes se equivoquen a la vez:

    P(Sherlock se equivoca) = 1 - 0.4 = 0.6
    P(Maigret se equivoca)  = 1 - 0.6 = 0.4
    P(ambas se equivocan)   = 0.6 * 0.4 = 0.24     <- si son independientes
    Confianza combinada     = 1 - 0.24 = 0.76

Dos fuentes débiles juntas dan más confianza que cualquiera sola. Eso es
exactamente lo que queremos premiar: la corroboración.

La trampa está en la palabra "independientes". Si importas el MISMO archivo
de Sherlock tres veces, no son tres confirmaciones: es una sola fuente
repetida. Por eso agrupamos por herramienta y de cada una tomamos solo su
observación más fuerte.
"""

from __future__ import annotations

from collections.abc import Iterable


def combinar(observaciones: Iterable[tuple[str, float]]) -> float:
    """Combina pares (herramienta, confianza) en una sola confianza entre 0 y 1.

    >>> combinar([("sherlock", 0.4), ("maigret", 0.6)])
    0.76
    >>> combinar([("sherlock", 0.4), ("sherlock", 0.4)])  # misma fuente: no suma
    0.4
    """
    # Paso 1: la mejor confianza de cada herramienta.
    mejor_por_herramienta: dict[str, float] = {}
    for herramienta, confianza in observaciones:
        # Acotar a [0, 1] por si un importador entrega un valor fuera de rango.
        confianza = min(max(confianza, 0.0), 1.0)
        anterior = mejor_por_herramienta.get(herramienta, 0.0)
        mejor_por_herramienta[herramienta] = max(anterior, confianza)

    # Paso 2: noisy-OR sobre las herramientas distintas.
    prob_todas_se_equivocan = 1.0
    for confianza in mejor_por_herramienta.values():
        prob_todas_se_equivocan *= 1.0 - confianza

    # round() evita resultados como 0.7600000000000001, típicos de los
    # números de punto flotante (los float no representan 0.1 exactamente).
    return round(1.0 - prob_todas_se_equivocan, 6)
