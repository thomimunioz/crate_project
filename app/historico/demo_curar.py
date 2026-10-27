# -*- coding: utf-8 -*-
"""Curacion a mano de la demo: 10 por genero, elegidos uno por uno.

Esto NO es un ranking automatico. Se midio contra 195 marcas reales de Thomas
que ninguna señal de metadata predice lo que va a guardar (AUC 0.43-0.57, o sea
ruido), y que lo unico que predice es el tier puesto a mano: 🔥 58% vs 👍 38%.
Asi que la seleccion es criterio musical, y el tier es una apuesta explicita.

Criterios al elegir, todos salidos de su feedback:
  * tempo entre ~55 y 105, preferencia por tonalidad menor
  * largo: mas minutos = mas chance de que haya un pasaje sin voz
  * artista NO conocido (el nombre grande se descarta aunque el upload sea oscuro)
  * nada repetido: ni el mismo tema dos veces ni dos del mismo artista
  * en fusion, variedad de paises: era el reclamo de que todo fuera USA y Japon
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
pre = json.load(open(os.path.join(HERE, "demo_pre.json"), encoding="utf-8"))
bpm = json.load(open(os.path.join(HERE, "bpm_cache.json"), encoding="utf-8"))

# id -> (tier, por que). Elegidos a mano mirando titulo, tempo, tonalidad y largo.
PICK = {
 # ---------------- R&B / modern soul de sello chico ----------------
 "rnb": [
  ("Smuv-C - No Body But Your Love", "fuego",
   "61 BPM en menor y es la version de sax: el espacio instrumental ya viene hecho"),
  ("The Elements Of Love - Fade Away", "fuego",
   "7:29 de instrumental a 64 BPM. Con esa duracion hay pasaje seguro"),
  ("C# Sharp With The Love Machine", "fuego",
   "68 BPM en re menor, 6:16, y 265 reproducciones: sello chico de verdad"),
  ("Duane Parham - Litte Miss Hip Pockets (Instrumental)", "fuego",
   "62 BPM en do menor. Autoedicion de Detroit del 85"),
  ("Liora Twani - Sweet Stuff", "fuego",
   "79 BPM en fa menor y 7:10. El tipo de tema que respira"),
  ("Diane White - One Night To Share", "fuego",
   "59 BPM en re menor, 7:16. Lento y oscuro, justo el rango"),
  ("Michael Sterling - Black To Blue", "fuego",
   "63 BPM en fa menor. Modern soul de los 80 sin reedicion conocida"),
  ("Lassiter - Crazy 4 You", "bien",
   "74 BPM en la menor. Dice 'Slow T.V.', que suele ser la version larga"),
  ("Nathan Bartell - Let Me Taste Your Love", "bien",
   "72 BPM en re menor, 5:30"),
  ("Grady Harrell - Love's Destination", "bien",
   "63 BPM, 7:14. Largo y lento, aunque este en mayor"),
 ],
 # ---------------- 80s quiet storm ----------------
 "80s": [
  ("Windy City - I Still Love You", "fuego",
   "50 BPM: el mas lento de toda la tanda. Chicago, 1980"),
  ("Waldo - Love Don't Grow On Trees", "fuego",
   "66 BPM en mi menor, 6:05. Nombre que no figura en ningun lado"),
  ("Mizz - Love Me By Name", "fuego",
   "68 BPM en la# menor. Quiet storm de sello chico"),
  ("D.J. Rogers - How Can I", "fuego",
   "60 BPM en si menor y casi 7 minutos"),
  ("Danny Pearson - Walkin' In The Rain", "fuego",
   "66 BPM en re menor, 6:33"),
  ("Rhythm Machine - Thought My Love Was Fine", "fuego",
   "9:10. A esa duracion el pasaje instrumental es casi seguro"),
  ("First Love - Things Are Not The Same", "bien",
   "73 BPM, 1985, 6:04. Grupo del que no hay casi nada"),
  ("Greg Phillinganes - Forever Now", "bien",
   "72 BPM en do# menor. El disco solista no lo conoce nadie"),
  ("Stargard - Just One Love", "bien",
   "67 BPM, 5:51, 260 reproducciones"),
  ("Esther Williams - Ready For Love", "bien",
   "72 BPM, 5:53"),
 ],
 # ---------------- Soul 70s ----------------
 "soul": [
  ("Midnight Love - Mama's Baby Boy (Instrumental)", "fuego",
   "61 BPM en la# menor, instrumental de 6:16. Casi hecho"),
  ("Doug Payne - She Is on the Money (Instrumental)", "fuego",
   "57 BPM en mi menor. De los mas lentos de la tanda"),
  ("Coast To Coast - Love Is the Same", "fuego",
   "65 BPM en fa# menor, instrumental alternativo"),
  ("Kansas City Express - This Is the Place (Instrumental)", "fuego",
   "74 BPM en do menor. Private press de Kansas City"),
  ("Love Committee - I Wanna Make Love To You", "fuego",
   "69 BPM en fa menor, 5:51. Philly del 70"),
  ("Carletta Sue - You Keep Holding Back On Love", "fuego",
   "72 BPM en fa menor. Modern soul que no reedito nadie"),
  ("Norfolk - You Are My Doll Baby (Instrumental)", "bien",
   "59 BPM, instrumental, 330 reproducciones"),
  ("Crystal Winds - Signs of Winter's Time (Instrumental)", "bien",
   "68 BPM. Grupo de Detroit, private press del 79"),
  ("The Exoutics: Lets Make Love", "bien",
   "60 BPM, 45 oscuro de 1988"),
  ("Shirley Brown: If This Is Goodbye", "bien",
   "60 BPM, 1989. Deep soul tardio"),
 ],
 # ---------------- Japanese city pop ----------------
 "citypop": [
  ("The Round - B2", "fuego",
   "54 BPM en sol menor. Japones de 1985 con 840 reproducciones"),
  ("Morita Doji", "fuego",
   "61 BPM en re menor, 1976. Folk japones oscuro, nunca salio de ahi"),
  ("Michelle Hart - Where Did Love Go", "fuego",
   "70 BPM en mi menor, 1988. AOR japones de los buenos"),
  ("Ryoko Sakaguchi", "fuego",
   "78 BPM en do menor, 1982. Actriz que grabo un disco y listo"),
  ("Curtis Creek Band - City Morning", "fuego",
   "80 BPM en do menor, 1984. El titulo lo dice todo"),
  ("Air Suspension Club Band", "fuego",
   "66 BPM en la menor, 1982, 6:07"),
  ("John Neptune With Arakawa Band", "fuego",
   "12:25 a 75 BPM en la menor. Shakuhachi con banda electrica"),
  ("Yagi", "bien",
   "69 BPM en fa# menor. Ambient japones del 86"),
  ("Masaaki Sakai - Porsche 959", "bien",
   "65 BPM en la menor. Tema de un auto, 1987, raro de verdad"),
  ("Shinsuke Honda", "bien",
   "73 BPM, balearic japones del 85"),
 ],
 # ---------------- Jazz fusion ----------------
 "fusion": [
  ("Osiris - A Story Of Love", "fuego",
   "Bahrein, 1982. 86 BPM en la menor. De las cosas mas raras de la tanda"),
  ("Ihsan Al-Munzer", "fuego",
   "Libano. 99 BPM en la menor. Fusion arabe que no suena a nada conocido"),
  ("Robert Julian Horky - Ouranos", "fuego",
   "Austria. 63 BPM en si menor, 5:50"),
  ("Eternal Moon - Follow The River Down", "fuego",
   "Reino Unido. 58 BPM en re menor. Ambiental y lento"),
  ("Tourniquet - Alone", "fuego",
   "57 BPM en la menor, 1978. Psych de sello chico"),
  ("Pierre Nadeau - Elle", "fuego",
   "Canada, 1976. 65 BPM, instrumental"),
  ("Djama - Zay", "fuego",
   "Francia, 1989. 75 BPM en la menor, instrumental"),
  ("Locksley Hall - What Does A Lonely Heart Do", "bien",
   "65 BPM en la menor, psych norteamericano"),
  ("Arica", "bien",
   "59 BPM en la# menor, 1972, 6:45"),
  ("Rhythm & Bliss - Song Of Earth And Sky", "bien",
   "61 BPM en mi menor, 1979"),
 ],
}


def elegir():
    """Matchea cada pick contra la preseleccion por prefijo de titulo."""
    import unicodedata
    def norm(s):
        s = unicodedata.normalize("NFKD", s.lower())
        return "".join(c for c in s if c.isalnum())
    out, faltan = {}, []
    for g, picks in PICK.items():
        pool = pre.get(g, [])
        elegidos, usados = [], set()
        for frag, tier, why in picks:
            nf = norm(frag)
            hit = None
            for x in pool:
                if x["id"] in usados:
                    continue
                if nf in norm(x["title"]):
                    hit = x
                    break
            if hit is None:
                faltan.append((g, frag))
                continue
            usados.add(hit["id"])
            hit = dict(hit)
            hit["tier"], hit["why"] = tier, why
            elegidos.append(hit)
        out[g] = elegidos
    return out, faltan


if __name__ == "__main__":
    sel, faltan = elegir()
    for g, v in sel.items():
        print("%-8s %2d elegidos" % (g, len(v)))
    if faltan:
        print("\nNO MATCHEARON (revisar el fragmento):")
        for g, f in faltan:
            print("   [%s] %s" % (g, f))
    json.dump(sel, open(os.path.join(HERE, "demo_final.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    print("\ntotal: %d" % sum(len(v) for v in sel.values()))
