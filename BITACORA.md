# Bitácora de la hormiga scout 🐜

Esta rama (`spike/v0.1-referencia`) es la **hormiga exploradora** de copperscript: sale antes que el resto, prueba caminos, se equivoca barato y vuelve con información. Nunca se fusiona con `main`; lo que aprende se lleva a `main` como decisiones de diseño (ADR), stubs y tests.

Cada entrada registra qué se hizo, qué se descubrió, qué salió mal y qué cambió en la forma de pensar el proyecto. Los errores se anotan con el mismo cuidado que los aciertos: son la razón de ser de una spike.

**Formato de cada entrada**

- **Qué se hizo**: el avance concreto.
- **Hallazgos**: lo que solo se descubre construyendo.
- **Errores**: qué falló, por qué y cómo se corrigió.
- **Cambios de filosofía**: ideas del diseño que cambiaron.
- **Para main**: qué debe llevarse a `main` y cuándo.
- **Próximos pasos**: hacia dónde explorar.

---

## Entrada 004 · 2026-10-20 · Reconocimiento de otras colonias (ADR-014)

Esta salida no trae código: es **reconocimiento**. Antes de diseñar plantillas configurables, la scout fue a ver cómo lo resolvieron proyectos que llevan años en esto. Se leyó directamente su código y sus esquemas, no resúmenes.

**Qué se hizo**
- Lectura de los esquemas YAML de **FollowTheMoney** (Person, Directorship, Associate, Family, Ownership, Interval), del README de **nomenklatura** y de la plantilla `person` de **MISP objects**.
- ADR-014 registrado en el documento de diseño, con una tabla de referencias e inspiraciones.
- Borrador de plantilla `plantillas/corrupcion.yaml` en el formato propuesto (4 tipos, 8 relaciones). Es YAML válido y sus relaciones solo apuntan a tipos que existen, pero todavía no hay código que la lea.

**Hallazgos**
- **Dos proyectos independientes, la misma lección.** FtM no usa el nombre de pila para comparar personas ("demasiados falsos positivos", dice un comentario en su esquema) y MISP marca el nombre con `disable_correlation`. Es exactamente la regla de la rareza que derivamos con Bayes: un valor común no identifica a nadie. Cuando gente con años de casos reales llega a lo mismo que tu teoría, es buena señal.
- **FtM advierte en mayúsculas que no todo intervalo es una arista**: una sanción toca a una sola entidad y un contrato puede tocar a más de dos. Decisión adoptada: lo que tiene más de dos participantes es una entidad (`contrato`) conectada a cada parte.
- **FtM ya resolvió el importador genérico** (ADR-010): mapea datos tabulares al modelo con archivos de mapeo. Hay que estudiarlo antes de escribir el nuestro.
- **nomenklatura guarda "juicios"** de deduplicación (positivo, negativo, no seguro). Nosotros proponemos fusiones al analista, pero no guardamos su respuesta: la próxima importación volvería a preguntar lo mismo. Hay que agregar una tabla de juicios.
- FtM tiene licencia MIT, compatible con nuestra AGPL. Aun así, no se agrega como dependencia del núcleo: usamos sus conceptos y sus nombres de tipos (para exportar a ese ecosistema), no su librería.

**Cambios de filosofía**
- De "inventar el modelo" a **"tunear un modelo probado"**. Lo que copperscript agrega sobre FtM es justamente lo que FtM no necesita: atribución, LR por relación, terceros y campos sensibles.
- El caso de uso de corrupción obliga a pensar en **terceros** (parientes, cercanos) desde el diseño: en esa plantilla son relaciones marcadas `tercero: true`.

**Para main**
- Nada todavía. ADR-014 depende de ADR-013, que tampoco está en `main`.

**Próximos pasos**
- Cargador y validador de plantillas: leer el YAML, verificar referencias entre tipos, avisar si un tipo se parece a otro existente.
- Reescribir los tipos técnicos actuales como plantilla `base` y probar que los 54 tests siguen pasando sin cambiar el núcleo.
- Tabla de juicios de fusión, inspirada en nomenklatura.

---

## Entrada 003 · 2026-10-20 · Existir no es pertenecer (ADR-013)

**Qué se hizo**
- `core/hipotesis.py`: Bayes en forma de odds y peso de cada evidencia en decibanes.
- `core/atribucion.py`: propagación de la atribución desde las anclas (Dijkstra sobre el máximo producto).
- Primer sistema de **migraciones** del esquema (v1 → v2): tablas `anclas` y `evidencias_hipotesis`, columna `prior` en `hipotesis`.
- Comandos nuevos: `anclar` y `hipotesis nueva | evidencia | ver`. La lista de entidades muestra EXIST y ATRIB por separado.
- Exportadores: atribución en el frontmatter de Obsidian; en el HTML, doble borde para anclas y nodos tenues si casi no se atribuyen al objetivo.
- 17 tests nuevos (54 en total).

**Hallazgos**
- **La migración funcionó en un caso real.** El caso de prueba `demo` se creó con el esquema v1 en la entrada 001; al abrirlo con este código se migró solo a v2, sin perder nada. Por eso los casos nuevos también se crean en v1 y se migran: un solo camino para todos.
- **El analista es una fuente más.** Anclar `amaro_dev` registró una observación de la "herramienta" analista con confianza 1.0, y su existencia subió de 0.82 a 1.00. Es coherente (el analista lo verificó), pero abre una pregunta: ¿el analista puede equivocarse? Por ahora vale 1.0.
- **Hipótesis y grafo viven separados.** La hipótesis "github/amaro_dev y reddit/amaro_dev son la misma persona" llegó a 98.4%, pero el grafo no se enteró: las dos cuentas siguen con la misma atribución. Falta un puente (ver Próximos pasos).
- `executescript` de SQLite no respeta las transacciones abiertas desde Python: confirma lo pendiente antes de ejecutar. Por eso cada migración escribe su propio `BEGIN; ... COMMIT;`.

**Errores**
- **Doble conteo en la atribución.** La primera fórmula era `atribución × peso × confianza de la relación × existencia del vecino`. Resultado: la cuenta de GitHub, conectada directamente al ancla, daba solo 0.136. El problema: la confianza de la relación y la existencia de la cuenta salen **de la misma observación de Sherlock**, así que la misma duda se castigaba dos veces. Corrección: la existencia pasa de factor a **techo** (`min(atribución × peso × conf_relación, existencia)`), y ahora da 0.34.
- **Lección grande: los tests pasaban con la fórmula equivocada.** Yo mismo había escrito `assert github.atribucion == 0.136` calculando a mano con la fórmula mala. Un test verifica lo que crees, no la verdad. El error se vio **mirando la salida real** de la CLI y preguntándose si el número tenía sentido. Los tests no reemplazan el juicio.

**Cambios de filosofía**
- La confianza ya no es una sola: **existencia** (¿el dato existe?) y **atribución** (¿le pertenece al objetivo?) son preguntas distintas. Un dato puede existir con certeza y no tener nada que ver con la persona investigada (la IP: existencia 0.90, atribución 0.06).
- Los pesos por tipo de relación (`tiene_cuenta` 0.85, `descubierto_desde` 0.5…) son **supuestos de diseño**, no verdades. Están a la vista en `PESOS_RELACION` para poder discutirlos. A futuro deberían aprenderse de casos reales.
- Limitación aceptada: solo se usa el mejor camino; dos caminos independientes no se refuerzan. Es una cota inferior honesta (nunca exagera). Lo correcto sería inferencia en una red bayesiana (belief propagation).

**Para main**
- Cuando la v0.1 de `main` esté implementada: portar ADR-013 como stubs + tests. Incluye el campo `atribucion` en `Entidad`, que hoy solo existe aquí.
- Llevar el patrón de migraciones **antes** que cualquier otro cambio de esquema en `main`: es la base de todo lo demás.

**Próximos pasos**
- Puente hipótesis → grafo: una hipótesis confirmada por el analista crea una relación `misma_persona` cuya confianza es la posterior.
- Primer módulo de Markov (v0.3): contar transiciones `tipo → tipo` por herramienta desde las relaciones registradas.
- Importador genérico CSV/JSON con mapeo YAML y extractor de texto (ADR-010).

---

## Entrada 002 · 2026-10-20 · Dos ramas y tests como contrato

**Qué se hizo**
- Separación en dos ramas: `main` (stubs que implementa Amaro) y esta spike (implementación de referencia).
- Los mismos tests viven en ambas ramas. En `main`, `tests/conftest.py` convierte los fallos por `NotImplementedError` en **PENDIENTE**, así la integración continua queda en verde mientras se implementa.

**Errores**
- `CliRunner` de Typer **atrapa las excepciones** de los comandos. El test de la CLI fallaba en vez de quedar pendiente, porque el `NotImplementedError` nunca llegaba a pytest. Corrección: un ayudante `_ejecutar()` que relanza esa excepción.
- El script que generaba los stubs cortó `html_graph.py` en el lugar equivocado: buscaba la primera aparición de `_PLANTILLA`, que estaba **dentro** de la función y no en su definición. Resultado: un archivo con error de sintaxis. Lección: al manipular código como texto, buscar patrones con contexto (`"\n_PLANTILLA = "`), no palabras sueltas.

**Cambios de filosofía**
- Los stubs lanzan `NotImplementedError` en vez de usar `...`: un `...` devuelve `None` en silencio y produce errores confusos; la excepción dice exactamente qué falta.

---

## Entrada 001 · 2026-10-20 · Primera salida: v0.1 completa

**Qué se hizo**
- v0.1 completa: modelo canónico, normalización, confianza noisy-OR, evidencia por hash, caso en SQLite con resolución de entidades, importadores de Sherlock y SpiderFoot, exportadores a Obsidian y HTML, CLI. 37 tests.

**Hallazgos**
- **SpiderFoot tiene dos formatos JSON**, descubiertos leyendo su código fuente: la terminal escribe en `type` la descripción ("Internet Name"); la exportación web escribe el código (`INTERNET_NAME`), con otros nombres de campo y una marca de falso positivo. Si se hubiera asumido uno, la mitad de los usuarios tendría un importador roto.
- **La semilla de un escaneo de SpiderFoot no aparece como evento**: es padre de otros, pero sin tipo propio. Se adivina su tipo por su forma (IP, email o dominio).
- **Sherlock**: el CSV incluye todos los sitios revisados (no solo los encontrados); solo sirven las filas `Claimed`. El TXT no contiene el usuario: está en el nombre del archivo.
- Con Sherlock + SpiderFoot, el alias `amaro_dev` resultó ser el **pivote** que une dos grafos separados (0.40 → 0.82 por corroboración).

**Errores**
- `www.gnu.org` estaba bloqueado desde el entorno de trabajo; el texto oficial de la AGPL se obtuvo del repositorio de licencias que usa GitHub (choosealicense.com) y se verificó completo.
- El formateador `ruff format` partió un comentario al final de una línea larga en tres líneas feas. Lección: los comentarios largos van en su propia línea, arriba del código.

**Atajos conscientes** (deuda técnica declarada)
- Cytoscape.js se carga desde un CDN: rompe "funcionar sin internet" (RNF2) y "sin recursos externos" (RNF3). En `main` debe ir incluido en el paquete.
- `json.load` carga el JSON de SpiderFoot completo en memoria. Para escaneos enormes: lectura en streaming (librería ijson).
- El HTML exportado escapa `</` dentro del JSON para evitar inyección de código (XSS) con datos recolectados de internet. Mantener en `main`.
