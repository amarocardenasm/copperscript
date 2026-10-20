"""Hipótesis en competencia con Bayes en forma de odds (ADR-013).

=== EXPLORACIÓN DE LA SPIKE (v0.2) ===

Para un objetivo DESCONOCIDO no hay anclas: hay hipótesis, por ejemplo
"la cuenta anónima X y la cuenta Y son de la misma persona".

Teorema de Bayes en forma de odds (la forma más cómoda para evidencia):

    odds posteriores = odds previas × LR₁ × LR₂ × ...

  - odds = p / (1 - p). Probabilidad 0.75 -> odds 3 ("3 a 1 a favor").
  - LR (likelihood ratio, razón de verosimilitud) de una evidencia =
        P(ver esta evidencia | hipótesis cierta) / P(ver esta evidencia | hipótesis falsa)
    LR = 20: es 20 veces más probable ver esto si la hipótesis es cierta.
    LR = 1: la evidencia no distingue nada. LR < 1: evidencia EN CONTRA.

Ejemplo (el que vimos en el chat):
    usuario raro,  prior 0.6  -> odds 1.5    × 20 × 2 = 60    -> p = 0.98
    usuario común, prior 0.02 -> odds 0.0204 × 20 × 2 = 0.816 -> p = 0.45

Decibanes: 10 · log10(LR). Es la unidad que inventaron Alan Turing y
I. J. Good en Bletchley Park para sumar evidencia al romper Enigma.
Al pasar a logaritmos, las multiplicaciones se vuelven SUMAS: cada
evidencia "suma puntos" y el analista ve cuánto aportó cada una.
    LR 10 -> +10 dB     LR 2 -> +3 dB     LR 0.5 -> -3 dB     LR 1 -> 0 dB

Supuesto peligroso: multiplicar LR asume evidencias INDEPENDIENTES. Dos
cuentas con el mismo avatar Y la misma bio pueden ser una sola evidencia
(alguien copió el perfil completo). Contarla dos veces infla la certeza.
El software no puede detectarlo solo: el analista debe juntar esas
evidencias en una sola con un LR moderado.
"""

from __future__ import annotations

import math
from collections.abc import Iterable


def a_odds(p: float) -> float:
    """Probabilidad -> odds. Exige 0 < p < 1 (con 0 o 1 la evidencia ya no importa)."""
    if not 0.0 < p < 1.0:
        raise ValueError(f"la probabilidad previa debe estar entre 0 y 1 (sin incluirlos): {p}")
    return p / (1.0 - p)


def a_probabilidad(odds: float) -> float:
    """Odds -> probabilidad."""
    return odds / (1.0 + odds)


def decibanes(lr: float) -> float:
    """Peso de una evidencia en decibanes: 10 · log10(LR)."""
    if lr <= 0:
        raise ValueError(f"la razón de verosimilitud debe ser positiva: {lr}")
    return 10.0 * math.log10(lr)


def posterior(prior: float, lrs: Iterable[float]) -> float:
    """Probabilidad posterior de una hipótesis dada su previa y sus evidencias.

    Se suma en logaritmos en vez de multiplicar: con muchas evidencias, el
    producto de odds puede desbordar (1e308 es el máximo de un float) o
    perder precisión. Sumar logaritmos es numéricamente estable.
    """
    log_odds = math.log10(a_odds(prior)) + sum(decibanes(lr) / 10.0 for lr in lrs)
    # Volvemos de logaritmos a odds, acotando para no desbordar en casos extremos.
    log_odds = max(min(log_odds, 300.0), -300.0)
    return a_probabilidad(10.0**log_odds)
