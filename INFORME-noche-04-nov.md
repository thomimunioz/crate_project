# Informe de la noche — 4 nov 2026

Buen día. Esto es lo que quedó hecho, lo que encontré de paso, y lo que
queda pendiente.

**Arrancá con el ícono CRATE del escritorio.** Tenés **173 temas** en el
hotlist.

---

## Tus cuatro retoques del sampler

| | Estado |
|---|---|
| Contador de sweetspots muy chiquito | ✅ ahora es una pastilla verde legible |
| El pasaje verde "temblaba" al pasarle el mouse | ✅ |
| "Sin onda" si entrabas por un sweetspot | ✅ |
| Ajuste A-B poco preciso | ✅ **125 veces más fino** |

**Sobre el temblor**, porque la causa es interesante: el hover le cambiaba la
*altura*, así que el borde se movía bajo el mouse, el mouse "salía", volvía a
achicarse, el mouse "entraba"… en bucle. Un hover nunca puede cambiar la
geometría de lo que estás apuntando. Ahora solo cambia el color.

**Sobre la precisión:** arrastrando sobre la barra, un pixel eran ~0,5
segundos. Con eso no cuadrás un kick ni de casualidad. Ahora, **con la onda a
la vista**, el arrastre va a la escala de la onda: **0,004 segundos por
pixel**, medido.

Y dos bugs de fondo que aparecieron buscando eso:
- La firma que evita redibujar los pasajes miraba solo la duración del audio
  propio, que en modo YouTube es **siempre 0**. Si los pasajes se dibujaban
  antes de que el reproductor reportara la duración, se cacheaba un estado
  vacío y **no se dibujaban nunca más**.
- La bolita del cursor tapaba los clicks en los pasajes, justo donde estaba
  sonando.

---

## Las portadas de Instagram — te debo una respuesta honesta

Miré las 11 cuentas que faltaban. **Solo 5 de las 16 muestran portadas de
discos** — las que ya había minado. El resto son flyers de eventos
(`japanjazzfusion`), clips de cultura (`levelsofvibes`), gente tocando covers
(`a_re_1123`) o cuentas de artistas (`milesdavis`, `armandhammernyc`).

Saqué lo que había: **Casiopea**, *Takanaka — Sea Is A Lady*, *Brasilian
Skies*, y *The Cool Notes — You're Never Too Young* (que `a_re_1123` revela
como sample). 5 temas nuevos.

**Conclusión para la próxima:** el rastrillo sirve para *descubrir* cuentas,
pero el valor está concentrado en las que postean portadas. Vale filtrarlas
antes de bajar 132 imágenes.

---

## Un bug que estaba corriendo y no sabíamos

Instalé **ruff** (linter de Python) por primera vez. Encontró algo real:

> `ESCENAS` tenía la clave **`"latam"` dos veces**. La segunda pisaba a la
> primera en silencio, así que *cuban latin*, *peruvian cumbia*, *brazilian
> funk* y *argentine jazz rock* **nunca se cavaron**.

Ahora son 9 queries, las dos listas fusionadas.

De 766 avisos: 760 eran preferencias de estilo, **6 eran problemas reales**.
Configuré ruff con criterio —solo reglas que cazan errores— y lo dejé en
**0**. Entre lo arreglado, dos `shell=True` que eran un riesgo concreto.

---

## El plan de producto

Está en **`docs/PLAN-PRODUCTO-2026-11.md`**. Medido, no estimado.

**El hallazgo principal:** ~2.000 líneas de JavaScript viven dentro de
strings de Python. Sin linter, sin autocompletado, sin tipos. **Los tres bugs
de esta semana los habría cazado un linter de JS en el acto.** Sacarlo a
archivos `.js` y agregar ESLint es lo de mayor impacto y cuesta una tarde.

**Sobre la UI**, tu crítica es justa y tiene causas concretas:
- **14 elementos** con el mismo peso visual en cada fila del hotlist
- Sin escala de espaciado (valores sueltos entre 3 y 13px)
- Densidad constante: escanear 100 y concentrarse en 1 se ven igual
- **8 colores de género** compitiendo en la misma línea

El plan propone escalas reales, jerarquía y responsive. Y dice
explícitamente **no traer Tailwind**: para 2.000 líneas sin build agregaría
más peso del que resuelve.

**Sobre orquestar el LLM:** lo que más pagó en este proyecto no fue una
herramienta sino `CLAUDE.md` al día y los barridos de interfaz. Investigué
Spec Kit, GSD y Traycer — están en el plan, con la advertencia de que casi
todas las comparativas las publican sus propios vendedores y **ninguna mide**
reducción de slop.

---

## Te queda UN comando por correr

`pre-commit` quedó configurado (ruff + los 65 tests + un guardia anti-claves)
pero **no pude activarlo**: instala un hook de git y el sandbox lo bloquea
como cambio permanente, con razón. Corré esto una vez:

```
pre-commit install
```

Desde ahí es imposible commitear algo que rompa los tests.

---

## Pendiente

**Lo que hablamos y no está:**

| | |
|---|---|
| **Canales sampleros de YouTube** | *Loop Diggin'*, *Sample Soul 70*. Tu filtro ya los separa |
| **Huella acústica** | Para Meiko Kaji y los japoneses que no matchean por texto. **Te debo la explicación** |
| **532 vetas sin cavar** | De las 560 que genera el vocabulario |
| **Onboarding tipo Tinder** | Tu idea de anoche, anotada en el plan |

**Del plan, por orden:**
1. Sacar el JS de los strings + ESLint *(una tarde, el de mayor impacto)*
2. Tokens de espaciado y tipografía; bajar el ruido de la fila
3. Responsive

---

**Estado:** 65 tests de Python + 10 barridos de interfaz, todo en verde.
Ruff en 0. Nada pisado en el hotlist.

Apagué la PC como pediste. Hasta mañana.
