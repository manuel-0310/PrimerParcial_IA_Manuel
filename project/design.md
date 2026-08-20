# Diseño del agente

Este documento debe completarse **antes** de la implementación principal del agente.

Use sus propias palabras y notación. No reemplace este archivo por una transcripción
del enunciado. Las subsecciones existen para que no se le olvide una decisión;
usted decide el contenido.

El entorno, según las propiedades vistas en clase, es totalmente observable,
determinista, secuencial, estático, discreto y de agente único. Bajo esas
condiciones la solución es un **plan completo** y el marco correcto es la
búsqueda clásica. Justifique cada componente con ese marco (AIMA, cap. 3).

> **Dónde está en el código:** Estado → `state.py` · Acciones → `actions.py` ·
> constantes derivadas → `problem.py` · Estrategia → `search.py` · traducción
> al contrato → `translate.py`.

---

## Estado

### Definición formal

Escriba la tupla de estado. Cada componente debe ser una variable que el robot
necesita para saber qué podrá hacer después.

```text
s = ⟨ zone, battery,
      payload_unique, payload_materials,
      ground_unique, ground_materials,
      doors_open, panels_repaired, stations_online ⟩
```

| Campo | Tipo | Qué representa |
|---|---|---|
| `zone` | id | Zona actual del robot. |
| `battery` | int `[0, battery_max]` | Batería actual. |
| `payload_unique` | `frozenset(id)` | Llaves/herramientas cargadas. |
| `payload_materials` | tupla de int | Cuántas unidades de cada tipo de material se llevan. Son fungibles (§2.2): se cuentan, no se identifican. |
| `ground_unique` | `frozenset(id, zone)` | Dónde está cada llave/herramienta **aún relevante** que no se lleva encima. |
| `ground_materials` | `frozenset(type, zone, count)` | Igual, para las unidades que quedan en el suelo. |
| `doors_open`, `panels_repaired`, `stations_online` | `frozenset(id)` | Cambios permanentes del entorno — **monótonos** (§2.4): un id nunca sale una vez entra. |

### Por qué cada variable es necesaria

Criterio de clase (`Applicable`): una variable pertenece al estado **si y solo si**
dos configuraciones que difieran en ella pueden diferir en las acciones legales
futuras o en su resultado.

Pase ese filtro con cada variable. En particular:

- la **batería** forma parte de la situación física (§2.1 del enunciado);
- la **posición de los objetos** no se deduce del escenario inicial si el robot
  puede soltarlos (`DROP`);
- los cambios permanentes (puertas, paneles, estaciones) condicionan el futuro.

| Variable | Acciones futuras que decide |
|---|---|
| `zone` | Qué corredores, objetos, puertas, paneles y estaciones están al alcance. |
| `battery` | Si una acción de costo `c` sigue siendo legal (`battery ≥ c`). Misma zona con distinta carga = futuros distintos: uno paga un corredor caro, el otro no. |
| `payload_*` | Qué `DROP` son legales, cuánto hueco queda para el próximo `PICKUP`, y si `OPEN_DOOR`/`REPAIR` son legales — exigen el objeto **encima**, no cerca. |
| `ground_*` | Un objeto soltado fuera de su zona de origen solo se recoge desde donde quedó. |
| `doors_open` | Qué `MOVE` cruzan un corredor con puerta. |
| `panels_repaired` | Qué `REPAIR` faltan y qué estaciones tienen cumplido `requires.panels_ok`. |
| `stations_online` | Dependencias entre estaciones, y la prueba de meta. |

### Qué información se deriva y NO se almacena

Peso de la carga, grafo de corredores, costos, capacidad, batería máxima, etc.
Si se puede calcular a partir del estado y de las constantes del escenario, no
es una variable de estado.

- **Peso cargado**: `Σ weight(o)` del payload, calculado al vuelo.
- **Constantes del escenario** (corredores, costos, `cargo_capacity`,
  `battery_max`, `requires` de paneles y estaciones): idénticas en todo el
  árbol, viven una sola vez en `Problem`, no por nodo.
- **Índices auxiliares** (qué puerta abre cada llave, qué paneles usan cada
  herramienta, qué zona tiene cargador): se precomputan porque se consultan en
  cada expansión, pero son derivados.

### Qué pertenece al historial de búsqueda y no al estado físico

`g(n)`, el padre y la acción que trajo aquí describen *cómo llegó*, no *dónde
está*. Viven en el **Nodo**. Si se meten en el estado, CLOSED no puede reconocer
la misma situación física alcanzada por dos rutas.

En el código la separación es literal: `State` es la tupla de 9 campos de
arriba; `Node` es otra clase con `state`, `parent`, `action` y `g`. Dos rutas
de distinto costo hasta la misma zona, con la misma carga y el mismo entorno,
son **un estado** en **dos Nodos** — y eso es justo lo que permite a CLOSED
podar la segunda. Si `g`/`parent`/`action` vivieran en `State`, cada ruta
sería un "estado" nuevo, CLOSED nunca acertaría un hit y Graph Search
degeneraría a Tree Search.

### Cuándo dos configuraciones son el mismo estado

Materiales equivalentes por tipo (§2.2): no les ponga ids artificiales.
Estructuras canónicas (conjuntos, contadores) para que `==` y el hash coincidan
con la equivalencia física. Sin eso Graph Search explota.

Mismo estado ⟺ sus 9 campos son iguales. Tres decisiones hacen que esa igualdad
estructural coincida con la equivalencia física, sin escribir un `__eq__` a mano:

1. **`frozenset`**: el orden en que se recogieron dos llaves no distingue nada.
2. **Conteos por tipo**: llevar "el primer FUSE" o "el segundo" es la misma
   situación. `payload_materials` guarda *cuántos*, con el tipo dado por su
   posición fija en la tupla (orden alfabético, no el orden de lectura del JSON).
3. **Canonicalización de objetos muertos** (siguiente subsección): dos mundos
   que solo difieren en dónde quedó algo que ya no sirve colapsan a uno.

Así `State` es un `NamedTuple` de campos hasheables, Python deriva
`__eq__`/`__hash__` correctos, y CLOSED reconoce el mismo mundo sin importar la
ruta ni el orden de las acciones.

### Relevancia: objetos que ya no cambian el futuro

Los cambios del entorno son **monótonos** (una puerta abierta no se cierra).
Pregúntese: una llave cuya puerta ya está abierta, o una herramienta cuyo panel
ya está reparado, ¿sigue distinguiendo estados si solo cambia *dónde* está en
el suelo? Si no habilita ninguna acción futura, incluirla multiplica el espacio
con permutaciones de objetos muertos. Justifique si las ignora y por qué eso
no pierde el óptimo.

Un objeto está **muerto** cuando ninguna acción futura puede necesitarlo:

| Objeto | Muerto ⟺ |
|---|---|
| Llave | Su puerta ya está abierta (y no vuelve a cerrarse). |
| Herramienta | **Todos** los paneles que la requieren están reparados. No basta "ya se usó": no se consume y puede hacer falta en otro panel. |
| Material | Ningún panel pendiente lo requiere. |

Tres podas se apoyan en esa noción:

1. **No se genera `PICKUP` de un objeto muerto** — cargar peso que no habilita
   nada no aparece en ningún plan óptimo.
2. **No se genera `PICKUP` de material sobrante** (`has_enough_material`): cada
   `REPAIR` consume exactamente una unidad, así que si ya se llevan tantas como
   paneles pendientes lo piden, una más es irrelevante. Es la misma idea de
   "muerto" aplicada a la *cantidad*.
3. **Los muertos tirados en el suelo se olvidan del estado** (`canonicalize`).
   Si `PICKUP` ya no los va a generar, *dónde* quedaron no cambia ninguna acción
   futura ni la meta. Sin esta poda, cada llave gastada partiría el espacio en
   tantas ramas como zonas donde pudo quedar.

Las tres son *sound* por el mismo argumento: un plan que alcanza `Goal(s)` no
necesita un objeto muerto ni una unidad sobrante, luego ningún plan de costo
mínimo usa lo que dejamos de generar. Un objeto muerto **en el payload** sí se
conserva: ahí todavía ocupa capacidad y por tanto condiciona el futuro.

---

## Acciones

Defina las acciones **internas** del agente (nombres libres). Para cada una:
precondiciones, efectos, costo. Toda acción del mundo exige además
`batería ≥ costo`.

Puede usar una tabla:

```text
Acción | Precondiciones | Efectos | Costo
```

`free(s) = cargo_capacity − Σ weight(payload)` se deriva del estado.

| Acción interna | Precondiciones | Efectos | Costo | Op. del contrato |
|---|---|---|---|---|
| `MOVE(z→z')` | Existe corredor `z→z'`; si tiene puerta, está abierta | `zone := z'` | `cost` del corredor | `MOVE` |
| `PICKUP(o)` | `o` está en `zone`; `o` es relevante (no muerto, y si es material aún hace falta); `weight(o) ≤ free(s)` | `o` pasa de `ground_*` a `payload_*` | `pickup` | `PICKUP` |
| `DROP(o)` | `o ∈ payload_*` **y** se dispara la regla reactiva de abajo | `o` pasa a `ground_*` en la zona actual | `drop` | `DROP` |
| `OPEN_DOOR(d)` | Robot en un extremo de `d`; `d` cerrada; su llave en `payload_unique` | `doors_open += d` | `interact` | `INTERACT`/`OPEN_DOOR` |
| `REPAIR(p)` | Robot en zona de `p`; `p` dañado; herramienta requerida encima; ≥1 unidad del material requerido | `panels_repaired += p`; material `−= 1`; la herramienta **no** se consume | `interact` | `INTERACT`/`REPAIR` |
| `ACTIVATE(e)` | Robot en zona de `e`; `e` offline; `requires.panels_ok ⊆ panels_repaired`; `requires.stations_online ⊆ stations_online` | `stations_online += e` | `interact` | `INTERACT`/`ACTIVATE` |
| `RECHARGE` | Hay cargador en la zona; `battery < battery_max`; `battery ≥ costo` | `battery := battery_max` | `recharge` | `INTERACT`/`RECHARGE` |

Los nombres internos son libres y **no** son valores del contrato: las cuatro
últimas se emiten como `op: "INTERACT"` con el nombre en el campo `action`,
nunca como `op` de nivel superior (`CONTRATO.md` §3.4). Esa traducción vive
aislada en `translate.py`, así la capa visual no influye en la lógica del agente.

### `Applicable` interno vs legalidad del contrato

El simulador dice cuándo un paso es **legal**. Su generador de sucesores dice
qué acciones son **relevantes para buscar**. No tienen que ser el mismo conjunto.

El contrato **permite** `DROP` en cualquier zona si el objeto está en la carga.
Si su agente genera ese `DROP` en cada estado con carga, el espacio deja de ser
«5 zonas y unas tareas» y pasa a ser «en cuál de las 5 zonas quedó cada objeto».
Eso no se arregla cambiando `cargo_capacity` ni apagando la batería: el escenario
es la fuente de verdad y el profesor probará otras instancias.

Usted puede (y se espera que) restrinja `DROP` —y cualquier otra acción— a los
casos que un plan **óptimo** podría necesitar. Justifique que ningún plan de
costo mínimo usa una acción que usted dejó de generar.

**Regla única y reactiva.** Se genera `DROP(o)` si y solo si, **en la zona
actual**, hay un `PICKUP` aplicable de un objeto relevante `o'` que ahora no
cabe (`free(s) < weight(o') ≤ cargo_capacity`). En una frase: *se suelta solo
cuando hace falta el hueco, nunca por si acaso.*

Cuando dispara, se elige qué ofrecer:

1. Si hay algún objeto **muerto** cargado → solo se ofrece soltar muertos.
2. Si no queda peso muerto → se ramifica sobre cada objeto **vivo** cargado.

Siempre en la zona actual: nunca se genera un `MOVE` cuyo único fin sea ir a
soltar algo, ni se elige zona de descarga. Así la ramificación de `DROP` queda
acotada por `cargo_capacity`, no por «objetos × zonas».

*Preferir muertos no pierde el óptimo*: soltar un muerto nunca obliga a volver
por él, mientras que soltar uno vivo puede costar un `PICKUP` posterior. Si hay
peso muerto, soltarlo es siempre al menos tan bueno.

*Por qué no soltar un objeto en cuanto muere* (era la opción intuitiva, y es
incorrecta): **optimalidad** — si el hueco nunca vuelve a hacer falta, ese
`DROP` es costo puro perdido; **completitud** — si en ese instante la batería
está apurada, forzar un `DROP` innecesario puede volverlo inaplicable y dar un
`FAILURE` espurio en una instancia que sí tenía solución.

**Límite reconocido.** Por ser reactiva, la regla no "aparca" un objeto en una
zona de paso *antes* de entrar a un callejón sin salida donde hará falta el
hueco: suelta ya dentro y obliga a un viaje de vuelta evitable. El agente sigue
siendo **completo** y **óptimo dentro del espacio de sucesores que genera**,
pero en esa topología no garantizo el óptimo **global**. Cerrarlo exigiría
analizar antes el grafo de corredores; prefiero declarar el límite a afirmar una
garantía que no se sostiene.

---

## Modelo de transición

```text
s  --a-->  s'     solo si a ∈ Applicable(s)
```

`Result` es determinista y parcial. Qué puede cambiar: zona, carga/suelo,
batería, entorno persistente. Qué se preserva. Si canonicaliza el estado tras
una acción, dígalo aquí.

`Result` es **parcial** (solo sobre `Applicable(s)`, como la `ψ` de clase) y
**determinista**. Todo campo no listado se preserva (frame axiom):

| Acción | Qué cambia |
|---|---|
| `MOVE` | `zone`; `battery −= costo` |
| `PICKUP` | El objeto pasa de `ground_*` a `payload_*`; `battery −= costo` |
| `DROP` | El objeto pasa de `payload_*` a `ground_*` **en la zona actual**; `battery −= costo` |
| `OPEN_DOOR` | `doors_open += puerta`. La llave sigue en el payload: no desaparece, solo queda muerta |
| `REPAIR` | `panels_repaired += panel`; una unidad del material **se consume**; la herramienta intacta |
| `ACTIVATE` | `stations_online += estación` |
| `RECHARGE` | `battery := battery_max`. El costo es **precondición**, no se resta del resultado |

**Sí se canonicaliza**, y solo donde hace falta: las transiciones que pueden
*matar* un objeto (`OPEN_DOOR`, `REPAIR`) y la que deja algo en el suelo
(`DROP`) pasan por `canonicalize`, que olvida los muertos tirados. Así, el
instante en que una puerta se abre es también el instante en que su llave deja
de partir el espacio de estados. Las demás no pueden crear un muerto en el
suelo y se saltan ese paso.

---

## Prueba de meta

```text
Goal(s) ⟺ scenario.goal.stations_online ⊆ s.stations_online
```

La misión se verifica sobre el **estado final del mundo**, no sobre haber
ejecutado una lista de tareas. ¿Las puertas y los paneles son parte de la meta
o solo medios?

La meta mira **solo** `stations_online`, y como subconjunto: basta que estén
online las que pide el escenario.

Puertas y paneles son **medios, no fines**. Una puerta se abre porque hay que
cruzarla; un panel se repara porque una estación lo exige en
`requires.panels_ok`. Si una instancia trajera una puerta que no hace falta
cruzar, el plan óptimo la ignoraría y seguiría siendo válido. Ahí está la
diferencia que pide el enunciado: el agente no lleva lista de pendientes, solo
comprueba el mundo.

---

## Función de costo

```text
g(n) = g(parent(n)) + cost(a)        con  g(raíz) = 0
```

Debe ser la suma de los **costos oficiales** del escenario (no el número de
pasos). Explique por qué minimizar pasos no es lo mismo que minimizar costo
en este mundo (hay corredores baratos y caros).

`cost(a)` sale siempre del escenario (`CONTRATO.md` §5): el `cost` del corredor
para `MOVE`, y el `action_costs` correspondiente para el resto. Nunca se
inventa ni se normaliza a 1. Es aditiva sobre el camino, como la definición de
costo de camino de clase.

Minimizar pasos **no** es minimizar costo porque los costos son heterogéneos:
en el demo los corredores valen entre 3 y 12 (`Z2↔Z5` cuesta 12; `Z4↔Z5`, 3), y
un `INTERACT` cuesta 2 frente al 1 de un `PICKUP`. Un plan con **menos
acciones** que use el corredor caro puede costar más que otro con más acciones
que rodee barato. Por eso la frontera se ordena por `g(n)` y no por
profundidad: es la diferencia entre UCS y BFS, y el motivo de que BFS aquí no
sea óptimo.

---

## Estrategia de búsqueda

Elija una estrategia **vista en clase** y justifíquela con las propiedades
reales del problema (costos heterogéneos, plan de menor costo, espacio finito).

Discuta:

- completitud
- optimalidad (¿la prueba de meta se hace al extraer o al generar?)
- costo de camino
- tiempo y espacio (el `b` peligroso no es el grado del mapa: es cuántos
  `DROP`/`PICKUP` genera por estado)
- cuándo se rompen las garantías (costos 0 o negativos, estados mal
  canonicalizados, OPEN que no se vacía)

Graph Search exige una lista CLOSED sobre estados **canónicos**. Explique cómo
evita reexplorar la misma situación física.

**Elección: Uniform-Cost Search sobre Graph Search.** El entorno es de certeza,
así que la solución es un plan completo calculado antes de mover un actuador.
Dentro de ese marco los costos son heterogéneos y positivos: BFS solo garantiza
optimalidad con costo uniforme y DFS no la tiene; UCS sí garantiza el plan de
**menor costo**, que es literalmente el criterio de la misión.

| Criterio | Evaluación |
|---|---|
| **Completitud** | Sí. Ramificación finita (grado de la zona + objetos relevantes + a lo sumo `cargo_capacity` `DROP`), espacio canónico finito, y todo costo `≥ ε > 0` (el mínimo real es 1). Son las tres condiciones del teorema de UCS. |
| **Optimalidad** | Sí, con la prueba de meta **al extraer** y con la dominancia como forma generalizada del *parent discarding*. Salvo el límite del `DROP` reactivo ya documentado. |
| **Costo de camino** | `g(n)` de la sección anterior. Se expande siempre el menor `g` pendiente: la búsqueda avanza en anillos de costo, no de profundidad. |
| **Tiempo y espacio** | `O(b^{1+⌊C*/ε⌋})` en el peor caso. Aquí manda `b`, y el `b` peligroso no es el grado del mapa (2–3 corredores por zona) sino cuántos `PICKUP`/`DROP` se generan por estado — acotado por las podas de arriba. |
| **Se rompe si…** | hay costos 0 o negativos (no ocurre); la canonicalización omite algo relevante y CLOSED fusiona estados distintos; o la topología adversa del `DROP`. |

**La meta se prueba al EXTRAER, no al generar.** Es la diferencia entre devolver
*un* plan y devolver el *más barato*: al generar se aceptaría la primera rama
que llegue, que puede ser cara; al extraer, la meta solo se acepta cuando es el
nodo de menor `g` pendiente, y por el invariante de Dijkstra ya no existe
camino más barato hacia ella.

**CLOSED** es un `dict` indexado por el estado canónico (sin la batería, ver
abajo). Antes de expandir se comprueba si ese mundo ya se alcanzó igual o
mejor; si sí, se descarta sin expandir. La misma comprobación se aplica al
generar hijos — no por corrección, sino para no encolar basura.

**Nota de implementación (OPEN).** Como todos los costos son enteros positivos,
OPEN no necesita un heap: son *buckets* indexados por `g`, extrayendo siempre
del más bajo no vacío. Produce el mismo orden de expansión que UCS con
operaciones O(1) en vez de O(log n): es una optimización de estructura de
datos, no un cambio de estrategia ni de garantías.

### Batería como recurso

La batería **sí** va en el estado (§2.1). Eso no implica explorar todos los
paseos que solo gastan energía. Si dos caminos llegan a la **misma**
configuración del mundo (zona, carga, suelo, entorno) y uno trae **más batería
residual** a un **costo menor o igual**, el otro no puede mejorar ningún plan
futuro: está dominado. Tratar cada nivel de batería como un mundo distinto,
sin esa observación, hace que UCS recorra detours inútiles hasta agotar
memoria. Justifique cómo CLOSED aprovecha (o no) esta dominancia.

CLOSED **sí** la aprovecha, y es lo que hace viable la búsqueda. La clave son
los otros 8 campos, **excluyendo `battery`**: "el mismo mundo salvo cuánta
carga queda". Por cada clave se guarda la **frontera de Pareto** de los pares
`(g, battery)` vistos, y un nodo se descarta si ya hay una entrada con `g' ≤ g`
**y** `battery' ≥ battery`. Si no está dominado, se añade: así conviven
"llegué más barato pero con menos batería" y "llegué más caro pero lleno", que
son futuros genuinamente distintos.

**Por qué es correcto.** Si `A` domina a `B`, `A` puede replicar cualquier
continuación de `B` acción por acción: ambos pagan lo mismo y `A` parte con
batería mayor o igual, luego si `B` puede pagar una acción, `A` también. El
caso a mirar de cerca es `RECHARGE`, la única acción que exige tener *poca*
batería (`battery < battery_max`): si `B` recarga y `A` llega ahí ya lleno, `A`
no puede recargar — pero tampoco lo necesita, y se ahorra el costo, terminando
igual o mejor. Fuera de ese caso la batería nunca *deshabilita* nada: las demás
acciones solo piden `battery ≥ costo`. Luego ningún estado dominado alcanza un
plan mejor que el que lo domina, y podarlo es seguro.

Además, la frontera de cada clave está acotada por `battery_max + 1` entradas,
lo que también acota el espacio.

---

## Formulación y tamaño del espacio (obligatorio)

El mapa visible es pequeño. El espacio de estados **no** lo es, si se formula
mal. Responda con sus palabras:

1. ¿Por qué «5 zonas, ~10 objetos, capacidad 3» puede generar millones de nodos
   en un UCS ingenuo?
2. ¿Qué papel tiene `DROP` en esa explosión?
3. ¿Qué podas o abstracciones aplicó y por qué **no pierden el óptimo**
   (*sound*)?
4. ¿Por qué **no** es solución subir la capacidad, bajar las estaciones o
   ignorar la batería?

**1. Por qué explota.** Porque el estado no es "dónde está el robot" sino "cómo
está el mundo entero". Si `DROP` puede dejar cualquier objeto en cualquier
zona, la posición de cada objeto móvil es una variable con `zonas + 1` valores.
Con 5 zonas y 9 objetos son `6⁹ ≈ 10⁷` configuraciones de "dónde quedó cada
cosa", y eso **multiplica** con la zona del robot, la batería (~101 valores) y
los subconjuntos de puertas, paneles y estaciones (`2³·2³·2³ = 512`): del orden
de `10¹²`–`10¹³`. Las cinco habitaciones son una parte diminuta del problema.

**2. El papel de `DROP`.** Es el único componente **exponencial en el número de
objetos**: convierte "dónde está cada cosa" en un producto cartesiano. Lo demás
crece acotado por las constantes del escenario. Por eso el cuello de botella no
es el algoritmo ni el tamaño del mapa, sino cuántos `DROP` genera `Applicable`.

**3. Podas aplicadas, y por qué son *sound*.**

| Poda | Qué elimina | Por qué no pierde el óptimo |
|---|---|---|
| `DROP` reactivo | Soltar "por si acaso" y elegir zona de descarga | Un `DROP` que no libera espacio necesario solo añade costo (salvo el caso de callejón ya documentado) |
| Preferir soltar muertos | La rama "soltar algo vivo" cuando hay peso muerto | Soltar un muerto nunca obliga a volver por él |
| No recoger muertos | `PICKUP` de lo que ya no sirve | Ningún plan futuro lo necesita |
| No recoger material de sobra | Unidades por encima de la demanda pendiente | Cada `REPAIR` consume una; la extra no habilita nada |
| Olvidar muertos en el suelo | Permutaciones de objetos inertes | Si no se van a recoger, dónde quedaron no cambia nada |
| Dominancia de batería | Mundos idénticos con peor `(g, batería)` | Un dominado no alcanza un plan mejor que el que lo domina |

El espacio efectivo baja a un orden tratable: zona × payloads que caben en la
capacidad × subconjuntos reales de puertas/paneles/estaciones, con `ground_*`
casi siempre en su forma inicial porque los `DROP` solo aparecen donde el
espacio aprieta. En la práctica UCS visita bastante menos, porque solo expande
nodos con `g(n) ≤` el costo óptimo.

**4. Por qué no vale tocar el escenario.** No ataca la causa. Subir
`cargo_capacity` de hecho **empeora** el fondo del problema (caben más objetos
a la vez, más combinaciones de qué llevar); solo logra que *esta* instancia no
necesite `DROP`. Bajar estaciones o ignorar la batería resuelve el demo y deja
intacta la explosión `(zonas+1)^objetos` en cualquier otra instancia. Y el
escenario es la fuente de verdad: el profesor probará otras posiciones, costos
y casos sin solución. Un agente que solo termina porque se le suavizó el JSON
no está resolviendo el problema de IA (`CONTRATO.md` §6).
