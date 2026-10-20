"""Contrato que cumple todo importador (ADR-010, patrón adaptador).

Un importador traduce la salida de UNA herramienta externa al modelo canónico.
Solo necesita dos cosas:

    detectar(ruta) -> bool                      "¿este archivo es mío?"
    importar(ruta) -> Iterator[Observacion]     "tradúcelo"

Este archivo está completo en ambas ramas: es una DECLARACIÓN del contrato,
no lógica.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path

from copperscript.core.models import Observacion


class Importador(ABC):
    """Clase base abstracta (ABC = Abstract Base Class).

    No se puede instanciar directamente. Cada importador concreto hereda de
    ella y DEBE implementar los métodos marcados con @abstractmethod; si
    olvida uno, Python da error al crearlo. Así el contrato se cumple solo.
    """

    #: Nombre corto de la herramienta. Se guarda en cada corrida y lo usa el
    #: motor de confianza para saber qué observaciones son independientes.
    herramienta: str = ""

    #: Confianza base de la herramienta (0 a 1). Ver ADR-011:
    #: herramientas con muchos falsos positivos parten más bajo.
    confianza_base: float = 0.5

    @abstractmethod
    def detectar(self, ruta: Path) -> bool:
        """True si este importador reconoce el formato del archivo.

        Debe ser BARATO: leer solo el comienzo del archivo, nunca todo.
        Se llama sobre cada importador hasta que uno diga que sí.
        """

    @abstractmethod
    def importar(self, ruta: Path) -> Iterator[Observacion]:
        """Recorre el archivo y entrega observaciones una por una.

        Se usa `yield` (un generador) en vez de devolver una lista: así un
        archivo de 500.000 filas no se carga entero en memoria (RNF1).
        """
