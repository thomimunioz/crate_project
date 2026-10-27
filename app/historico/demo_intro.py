# -*- coding: utf-8 -*-
"""La explicacion que abre el HTML de la demo. Escrita para alguien que no
conoce el proyecto: un amigo de Thomas, beatmaker, sentado al lado suyo."""

INTRO = """
<div class="intro">
<h2>Qué es esto</h2>
<p>Esto es <b>CRATE</b>, un buscador de samples que Thomas está construyendo. La idea no es
"encontrar música buena" — eso lo hace cualquier playlist. La idea es encontrar
<b>lo que no ibas a encontrar buscando normal</b>: discos de sello chico, autoediciones,
prensados de 500 copias, cosas que están subidas a YouTube con 300 reproducciones y que
nadie sampleó todavía.</p>

<h2>Cómo busca</h2>
<p>No busca por palabras. Buscar <i>"70s soul"</i> en YouTube te devuelve lo mismo que a
todo el mundo, y eso ya está exprimido.</p>
<p>Lo que hace es <b>cavar canales enteros de diggers</b> — tipos que suben rips de sus
propios vinilos, uno por día, hace años. Para esta tanda se listaron
<b>{pool} temas</b> de esos canales, sin gastar un centavo de API: se usa la misma
herramienta que descarga videos, pero pidiéndole solo los títulos.</p>
<p>De esos {pool} quedaron <b>{cand} candidatos</b> después de tirar todo lo que ya
le habíamos mostrado antes, lo que dura menos de 2:45, lo que pasa de 300.000
reproducciones y la basura obvia (karaokes, álbumes enteros, mixes).</p>

<h2>Qué se le mide a cada tema</h2>
<p>A los {medidos} finalistas se les <b>bajó el audio y se los analizó de verdad</b>, no se
leyó la ficha: 45 segundos de cada uno pasados por un analizador que calcula
<b>tempo y tonalidad</b>. Por eso abajo vas a ver "84 BPM · F minor" en temas donde YouTube
no dice nada de eso.</p>
<p>Un detalle: cuando el analizador lee el doble del tempo real (le pasa seguido con las
baladas, cuenta las corcheas en vez de los golpes) el número se pliega a la mitad y se
muestra entre paréntesis lo que había leído. Thomas casi nunca usa nada arriba de
115 BPM, así que eso importa.</p>

<h2>Por qué está ordenado así</h2>
<p>Acá viene la parte honesta. Se midió, contra <b>{marcas} decisiones reales</b> de Thomas
(lo que guardó y lo que descartó, con el motivo escrito), qué señales automáticas
predicen si algo le va a gustar.</p>
<p><b>Ninguna.</b> Año, reproducciones, duración, tempo, tonalidad: todas dieron entre 0,43
y 0,57 en una escala donde <b>0,50 es tirar una moneda</b>. Son ruido.</p>
<p>Lo único que predice de verdad es la <b>curación a mano</b>: los temas marcados 🔥 se
guardan el <b>58%</b> de las veces y los 👍 el <b>38%</b>. Así que estos 50 están
<b>elegidos y escuchados uno por uno</b>, y el ícono es una apuesta, no un cálculo.</p>

<h2>Qué busca Thomas, concretamente</h2>
<p>Hace hiphop <b>drumless</b>, estilo Griselda, Roc Marciano, Boldy James, Dano, Cerounno.
En ese palo no se busca una canción: se busca <b>un pedazo de canción con espacio</b> —
una intro, un pasaje, un momento donde no estén cantando encima. Él lo dijo así:</p>
<blockquote>"no necesito que la canción lo loopee, pero sí necesito que haya espacio
(...) lo importante es que no estén todo el pto tema cantando"</blockquote>
<p>Por eso acá hay preferencia por temas largos, por los que dicen "instrumental", y por
los que arrancan despacio. Y por eso se descartó todo lo que viniera en 6/8 (no entra
en un beat de 4/4) y el jazz muy ortodoxo, tipo trío de piano improvisando: suena
hermoso y es imposible de samplear.</p>

<h2>Cómo usarlo ahora</h2>
<p>Cada título es un link: <b>abrilo</b> y se marca solo como escuchado. Si te gusta,
tildá <b>"lo agregué"</b> y aparecen <b>cinco estrellas</b> para puntuarlo. Si no te gusta,
elegí el motivo en el desplegable — esa es la parte que más sirve, porque cada "no" con
motivo afina la próxima búsqueda.</p>
<p>Al final de la página hay un botón para <b>exportar</b> todo lo marcado. Ese archivo es
el que entrena al sistema.</p>

<h2>Cuánto funciona hoy</h2>
<p>Sin inventar nada: sobre las tandas anteriores el sistema tiene un
<b>38% de acierto</b> — de cada 10 temas que sugiere, Thomas se guarda casi 4.
Cavando a mano él llega al 53%. O sea que <b>todavía rinde por debajo de hacerlo a mano</b>,
y la diferencia está justamente en lo que falta: que la máquina pueda oír dónde hay
espacio instrumental, que hoy no puede.</p>
<p>La veta que mejor rinde es <b>modern soul de sello chico: 56%</b>. La que peor,
jazz fusion: 23%.</p>
</div>
"""
