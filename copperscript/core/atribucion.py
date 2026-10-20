"""Atribución: ¿cuánto creemos que cada dato le pertenece al objetivo? (ADR-013)

=== EXPLORACIÓN DE LA SPIKE (v0.2) ===

Para un objetivo CONOCIDO, el analista marca anclas: identificadores que
verificó él mismo (su email confirmado, su sitio). Las anclas valen 1.0.
Desde ahí, la atribución se "derrama" por el grafo y se debilita en cada
salto, como el agua que pierde presión en cada tubería:

    atribución(vecino) = min( atribución(actual) × peso del tipo × confianza de la relación,
                              existencia del vecino )

Ejemplo:
    ancla "amaro_dev" (1.0) --tiene_cuenta (peso 0.85, conf 0.4)--> cuenta GitHub (exist. 0.4)
    atribución(GitHub) = min(1.0 × 0.85 × 0.4, 0.4) = 0.34

CORRECCIÓN (bitácora, entrada 003): la primera versión MULTIPLICABA por la
existencia del vecino y daba 0.136. Era doble conteo: la confianza de la
relación y la existencia de la cuenta salen de LA MISMA observación de
Sherlock, así que multiplicarlas castigaba dos veces la misma duda.
Si la relación es cierta, el vecino existe; por eso la existencia no se
multiplica: solo pone un techo (nada puede pertenecer al objetivo con más
certeza de la que tenemos de que existe).

Si hay varios caminos, usamos el MEJOR (máximo producto). Es el algoritmo
de Dijkstra disfrazado: maximizar un producto de números entre 0 y 1 es lo
mismo que minimizar la suma de sus -log. Dijkstra encuentra caminos más
cortos; aquí, "más corto" = "más creíble".

LIMITACIÓN CONOCIDA (anotada en la bitácora): tomar solo el mejor camino
ignora que dos caminos independientes deberían REFORZARSE. Sumarlos con
noisy-OR tampoco es correcto, porque en un grafo con ciclos la misma
evidencia llega por varios lados y se contaría dos veces. Lo correcto sería
inferencia en una red bayesiana (belief propagation), demasiado para la
spike. El máximo es una cota inferior honesta: nunca exagera.
"""

from __future__ import annotations

import heapq
import math
from collections.abc import Iterable

# Cuánta atribución "deja pasar" cada tipo de relación. Son supuestos del
# diseño, no verdades: están aquí, a la vista, para poder discutirlos y
# ajustarlos. Que alguien tenga una cuenta con su alias es una relación
# fuerte; que SpiderFoot haya "descubierto X desde Y" puede ser casi nada
# (un dominio que comparte servidor con miles de otros).
PESOS_RELACION: dict[str, float] = {
    "tiene_cuenta": 0.85,
    "usa_email": 0.85,
    "resuelve_a": 0.5,
    "descubierto_desde": 0.5,
    "relacionado_con": 0.4,
}
PESO_POR_DEFECTO = 0.4

# Por debajo de esto dejamos de propagar: evita recorrer todo el grafo para
# llegar a nodos con atribución 0.0001, que no aportan nada al analista.
UMBRAL_MINIMO = 0.01


def propagar(
    anclas: Iterable[int],
    aristas: Iterable[tuple[int, int, str, float]],
    existencia: dict[int, float],
) -> dict[int, float]:
    """Atribución de cada entidad alcanzable desde las anclas.

    anclas:     ids de entidades verificadas por el analista (valen 1.0).
    aristas:    (origen_id, destino_id, tipo_relacion, confianza_relacion).
    existencia: confianza de existencia de cada entidad (ADR-011).

    La atribución fluye en AMBOS sentidos de una arista: si el alias es del
    objetivo, su cuenta probablemente también; y si la cuenta es suya, el
    alias también. Por eso armamos una lista de vecinos no dirigida.
    """
    vecinos: dict[int, list[tuple[int, float]]] = {}
    for origen, destino, tipo, confianza in aristas:
        factor = PESOS_RELACION.get(tipo, PESO_POR_DEFECTO) * confianza
        vecinos.setdefault(origen, []).append((destino, factor))
        vecinos.setdefault(destino, []).append((origen, factor))

    mejor: dict[int, float] = {}
    # heapq es una cola de prioridad que siempre entrega el MENOR elemento.
    # Guardamos (-atribución, id) para que salga primero la MAYOR atribución.
    cola: list[tuple[float, int]] = []
    for ancla in anclas:
        mejor[ancla] = 1.0
        heapq.heappush(cola, (-1.0, ancla))

    while cola:
        negativo, actual = heapq.heappop(cola)
        valor = -negativo
        if valor < mejor.get(actual, 0.0):
            continue  # ya habíamos llegado a este nodo por un camino mejor
        for vecino, factor in vecinos.get(actual, []):
            # Techo por existencia, no multiplicación (ver CORRECCIÓN arriba).
            candidato = min(valor * factor, existencia.get(vecino, 0.0))
            if candidato > mejor.get(vecino, 0.0) and candidato >= UMBRAL_MINIMO:
                mejor[vecino] = candidato
                heapq.heappush(cola, (-candidato, vecino))

    # Redondeamos para mostrar; math.isclose en los tests compara con tolerancia.
    return {eid: round(v, 6) for eid, v in mejor.items() if not math.isnan(v)}
