# -*- coding: utf-8 -*-
"""TODO lo aprendido del oído de Thomas, en un solo lugar.

Hasta ahora esto vivia desparramado en ocho scripts. Acá se junta para que el
buscador de la app lo aplique solo: Thomas escribe "soul" y sale con los
filtros, los canales que rinden y el orden ya puestos.

Cada regla dice de dónde salió. Nada inventado.
"""
import re, unicodedata

_B = chr(92) + "b"


def rx(*trozos):
    """Alternativa de palabras completas. El borde se construye: escrito a
    mano a traves de un heredoc llega convertido en chr(8) y falla mudo."""
    return re.compile(_B + "(?:" + "|".join(trozos) + ")" + _B, re.I)

# ---------------------------------------------------------------- escenas
# Thomas escribe una palabra; esto la convierte en varias busquedas que
# apuntan a donde realmente aparece lo bueno.
ESCENAS = {
 "soul": ["rare soul 45", "sweet soul private press", "deep soul obscure",
          "modern soul unreleased", "soul instrumental 45", "philly soul rare"],
 "rnb":  ["modern soul boogie 80s", "rnb slow jam rare", "quiet storm obscure",
          "80s soul private press", "modern soul instrumental"],
 "80s":  ["quiet storm 80s rare", "slow jam 1985 obscure", "80s soul ballad rare",
          "boogie slow 1983", "80s rnb private press"],
 "citypop": ["city pop japan rare", "japanese aor 1982", "city pop album track",
             "japanese boogie 80s", "和製シティポップ"],
 "fusion": ["jazz fusion rare mellow", "japanese jazz fusion 1978",
            "soul jazz rhodes instrumental", "crossover jazz obscure",
            "spiritual jazz rare"],
 "library": ["library music rare", "kpm library", "de wolfe library",
             "production music 1974", "library music underscore"],
 "instrumental": ["soul instrumental version 45", "boogie instrumental 12 inch",
                  "modern soul instrumental rare", "off vocal japanese"],
 # --- pedidas por Thomas el 27-oct ---
 "piano": ["rare piano instrumental 70s", "rhodes instrumental obscure",
           "piano ballad private press", "electric piano soul instrumental",
           "piano library music", "jazz piano mellow rare"],
 "folk": ["folk private press rare", "acid folk obscure", "folk psych 70s rare",
          "acoustic folk instrumental", "loner folk private press",
          "folk rock obscure 1972"],
 "dark": ["dark soul minor key", "melancholic instrumental rare",
          "moody library music", "dark jazz obscure", "sombre soul ballad",
          "minor key soul instrumental"],
 "gospel": ["gospel soul private press", "gospel 45 rare", "spiritual soul obscure",
            "gospel funk instrumental"],
 "brasil": ["brazilian soul rare", "mpb obscure 70s", "samba jazz instrumental",
            "brazilian private press", "bossa instrumental rare"],
 "latam": ["latin soul rare", "peru soul 70s", "colombia funk obscure",
           "argentina fusion raro", "latin jazz private press"],
}
def expandir(q):
    """Convierte lo que escribe en varias busquedas."""
    base = q.strip()
    low = quitar_tildes(base)
    extra = []
    for clave, qs in ESCENAS.items():
        if clave in low:
            extra = qs
            break
    if not extra:                       # palabra libre: se le agregan modificadores
        extra = ["%s rare" % base, "%s obscure 45" % base,
                 "%s private press" % base, "%s instrumental" % base]
    return [base] + extra

# ------------------------------------------------- canales, por hit rate medido
# Medido contra 364 marcas reales. El canal es la señal mas fuerte que tenemos.
CANALES = {
 "Krem Soulz": .70, "Five Special Records": .56, "BigPeter1027 Real Music Channel": .43,
 "Casen Fike": .35, "André Navarro II": .33, "skeenery": .33, "On the Rocks Records": .33,
 "Neglected Trax": .30, "JefferyBeats": .28, "Soultwinz": .20,
 "DJ Vinyl Goblin": .15,          # poco, pero lo que pega es lo mejor: 3.75★
 "aaappleknocker": .12,           # mezcla mucho reggae
}
# promedio de estrellas, que NO es lo mismo que el hit rate
ESTRELLAS = {"DJ Vinyl Goblin": 3.75, "Krem Soulz": 3.50, "Casen Fike": 2.80,
             "Soultwinz": 2.00}
BASE = .36                                  # hit rate global

# ------------------------------------------------------- genero de un tema
# Thomas trabaja ocho listas. Las cinco primeras son "lo que venimos
# trabajando" (27-oct: "en hotlist siempre tiene que estar la verdadera
# crema... lo que venimos trabajando es el fuerte"); PIANO, DARK y FOLK
# todavia se estan poblando y entran como recomendacion, en minoria.
FUERTES = ["SOUL", "R&B SOUL", "80s", "CITY POP", "JAZZ FUSION"]
EN_FORMACION = ["PIANO", "DARK", "FOLK"]

# De que sube cada canal. Sale de mirar sus uploads, no de adivinar.
CANAL_GEN = {
 "Krem Soulz": "SOUL", "TheRAREGROOVEMAN": "SOUL", "Soultwinz": "SOUL",
 "Casen Fike": "SOUL", "aaappleknocker": "SOUL", "Athens of The North": "SOUL",
 "mikeejaylovessoul": "SOUL", "DJ Vinyl Goblin": "SOUL",
 "Five Special Records": "R&B SOUL", "skeenery": "R&B SOUL",
 "Neglected Trax": "R&B SOUL", "On the Rocks Records": "R&B SOUL",
 "BigPeter1027 Real Music Channel": "80s",
 "André Navarro II": "CITY POP", "ants kask": "CITY POP",
 "JefferyBeats": "CITY POP",
 "JazzManDean": "JAZZ FUSION", "Cool Breeze": "JAZZ FUSION",
 "Elwood P. Dowd": "JAZZ FUSION", "The Voice of Anton": "JAZZ FUSION",
 "Vinyle Archeologie": "JAZZ FUSION", "foreal": "JAZZ FUSION",
 "Music for empty rooms": "JAZZ FUSION",
 "Rare Samples & Songs Oleg Tsoy": "JAZZ FUSION",
}

JAPON = re.compile(r"[぀-ヿ一-鿿]")
_JP_NOMBRE = rx("yamashita", "ohashi", "kubota", "kadomatsu", "anri", "takeuchi",
                "matsubara", "ohno", "hosono", "sakamoto", "minako", "mariya",
                "taeko", "junko", "akiko", "toshiki", "tatsuro", "casiopea",
                "momoko", "rajie", "miki", "city pop")
_80S = rx("boogie", "quiet storm", "slow jam", "modern soul", "synth",
          "electro", "freestyle", "19(8[0-9])")
_SOUL = rx("soul", "funk", "motown", "philly", "gospel", "rare groove",
           "sweet soul", "deep soul", "northern soul")
_RNB = rx("r ?& ?b", "rnb", "new jack", "slow jam", "ballad", "lovers")
_FUSION = rx("fusion", "jazz", "rhodes", "library", "bossa", "mpb",
             "brazil", "latin", "samba", "spiritual")

# Las tres en formacion solo se reconocen cuando NINGUN genero fuerte pega:
# un soul con la palabra "piano" en el titulo sigue siendo soul. Y la pista
# tiene que estar del lado del TEMA, no del artista: "Rhodes" es apellido
# (Cynthia Rhodes no toca un Fender Rhodes, canta).
_PIANO_G = rx("piano", "rhodes", "wurlitzer", "wurli", "clavinet",
              "harpsichord", "electric piano", "pianist")
_DARK_G = rx("dark", "melancholy", "melancholic", "sombre", "somber", "moody",
             "lament", "sorrow", "mourning", "noir", "requiem", "elegy",
             "haunting", "nocturne", "midnight", "despair", "grief")
_FOLK_G = rx("folk", "acoustic", "acustico", "violao", "troubadour",
             "singer.?songwriter", "loner", "psych folk", "acid folk",
             "fingerstyle", "fingerpicking", "banjo", "mandolin", "pastoral")
_SEPARADOR = re.compile(r"\s(?:[-–—/|:]|‎-)\s")


def parte_tema(titulo):
    """El titulo sin el artista, que es donde valen las pistas de genero."""
    t = titulo or ""
    partes = _SEPARADOR.split(t, 1)
    return partes[1] if len(partes) > 1 else t


def genero_de(titulo, canal=None, veta=None):
    """A que lista de Thomas se parece esto. None si no se puede decir.

    Primero la veta (es explicita), despues el canal (que es el dato que mas
    predice: de un canal del que ya guardo, guarda 16-22% contra 3% del
    resto) y recien al final las palabras del titulo, que es lo mas debil.
    """
    if veta and veta.upper() in EN_FORMACION:
        return veta.upper()
    t = titulo or ""
    if canal and canal in CANAL_GEN:
        g = CANAL_GEN[canal]
        # el canal manda, salvo que el titulo grite otra cosa muy fuerte
        if g == "JAZZ FUSION" and (JAPON.search(t) or _JP_NOMBRE.search(t)):
            return "CITY POP"
        return g
    # Las palabras valen del lado del TEMA. Mirando el titulo entero, un
    # apellido decide el genero: "Cynthia Rhodes - Finding Out The Hard Way"
    # caia en JAZZ FUSION porque _FUSION incluye "rhodes". Ella canta, no toca
    # un Fender. El japones es la excepcion: ahi el nombre del artista SI es
    # la pista que vale.
    nom = parte_tema(t)
    if JAPON.search(t) or _JP_NOMBRE.search(t):
        return "CITY POP"
    if _80S.search(nom):
        return "80s"
    if _RNB.search(nom):
        return "R&B SOUL"
    if _SOUL.search(nom):
        return "SOUL"
    if _FUSION.search(nom):
        return "JAZZ FUSION"
    # recien ahora las que se estan poblando
    if _PIANO_G.search(nom):
        return "PIANO"
    if _FOLK_G.search(nom):
        return "FOLK"
    if _DARK_G.search(nom):
        return "DARK"
    return None


# ------------------------------------------------------------------ descartes
BASURA = re.compile(
    r"karaoke|tutorial|type beat|sample pack|reaction|how to|lyrics? video|megamix|"
    r"\bdj set\b|interview|entrevista|documental|full album|album completo|"
    r"compilation|visualizer|\bmix\b|unboxing|\bshorts?\b|teaser|trailer|"
    r"\bmid[iy]\b|cover by|remake|re-?recorded", re.I)
# me lo marco tres veces: no entra en un beat de 4/4
SEIS_OCHO = re.compile(r"\b6/8\b|\b12/8\b|\bwaltz\b|\bvals\b|\bvalse\b|\bvalzer\b", re.I)
# "este no entra ni a palos, parece una jam de jazz y alguien tocando piano a las chapas"
ORTODOXO = re.compile(r"\b(bebop|be-bop|hard bop|dixieland|swing era|standards?|"
                      r"improvisation|\bjam\b|real book|blue note session|"
                      r"piano trio|solo piano)\b", re.I)
# en soul "dub" es la version sin voz; en REGGAE es un genero entero. 12 colados.
REGGAE = re.compile(
    r"\breggae\b|\bdancehall\b|\broots\b|\briddim\b|\brocksteady\b|\bska\b|"
    r"\bdub ?plate\b|\bdub version\b|\bdub on\b|\blovers rock\b|\bskank\b|"
    r"johnny clarke|janet kay|sugar minott|dub syndicate|chosen few|king tubby|"
    r"scientist|studio one|lee ?perry|augustus pablo|\bjah\b|bob marley|wailers|"
    r"gregory isaacs|horace andy|burning spear|black uhuru|weapon of peace", re.I)
DUB_GENERO = re.compile(r"\|\s*dub\b|,\s*dub\b|\bdub\s*[\|\(\[]|\bdub\s*$", re.I)
# el upload puede tener 200 views y el tema conocerlo todo el mundo
CONOCIDOS = re.compile(
    r"\b(marvin gaye|roberta flack|smokey robinson|stevie wonder|aretha|"
    r"curtis mayfield|al green|barry white|isley|whitney|luther vandross|"
    r"anita baker|\bsade\b|teddy pendergrass|harold melvin|heatwave|con funk shun|"
    r"l\.?t\.?d\.?|bar.?kays|tavares|atlantic starr|klymaxx|millie jackson|"
    r"the spinners|chi.?lites|delfonics|stylistics|o'?jays|earth,? ?wind|"
    r"kool & the gang|commodores|temptations|four tops|gladys knight|"
    r"patti labelle|phyllis hyman|shalamar|george benson|grover washington|"
    r"bob james|roy ayers|donna summer|lonnie liston|azymuth|tatsuro yamashita|"
    r"mariya takeuchi|anri|toshiki kadomatsu|casiopea|ryo fukui|yuji ohno|"
    r"piero umiliani|janko nilovic|monk higgins|gloria ann taylor)\b", re.I)
# Thomas busca material PARA samplear, no hiphop ya hecho. Se colaron Faith
# Evans, Peanut Butter Wolf y Mood Swingaz en la primera corrida del hotlist.
HIPHOP = re.compile(
    r"\bhip ?hop\b|\brap\b|\bboom ?bap\b|\bg-?funk\b|\bbeat ?tape\b|"
    r"peanut butter wolf|stones throw|\bmf ?doom\b|madlib|j ?dilla|"
    r"\bfreestyle\b|\bcypher\b|\bmixtape\b|\bprod\.? by\b", re.I)
# remix moderno: no es una mezcla de epoca, es una version nueva
REMIX_MODERNO = re.compile(r"\bremix\b|\bbootleg\b|\bflip\b|\bmashup\b|"
                           r"\bnightcore\b|slowed|reverb", re.I)

# psych y prog NO son fusion. Por meterlos, esa veta rindio 10%.
NO_FUSION = re.compile(r"\bpsych\b|\bprog\b|\bprogressive rock\b|avantgarde|"
                       r"experimental|\bhip ?hop\b|\brap\b|\bremix\b|\bfolk rock\b", re.I)
# lo que suena a evento y no a cama
EFUSIVO = re.compile(r"\b(disco|dance|party|shake|get down|stomp|hustle|"
                     r"rock ?n ?roll|twist|celebration|workout|march|carnaval)\b", re.I)
# lo que anuncia que hay espacio: su ley de oro
SIN_VOZ = re.compile(r"\binstrumental\b|\(inst\.?\)|\[inst\.?\]|\bdub\b|off ?vocal|"
                     r"オフボーカル|backing track|minus one|"
                     r"\bTV (mix|track|size)\b|\bunderscore\b", re.I)
PIANO = re.compile(r"\bpiano\b|\brhodes\b|\bfender\b|\bwurlitzer\b|\bkeys\b|"
                   r"\bclavinet\b|\bharpsichord\b|\bkeyboard\b", re.I)
OSCURO = re.compile(r"\bdark\b|\bmelanchol\w*|\bsombre\b|\bsomber\b|\bmoody\b|"
                    r"\bsad\b|\blament\b|\bsorrow\b|\bblue\b|\bminor\b|"
                    r"\bshadow\b|\bnight\b|\brain\b|\blonely\b", re.I)
LENTO = re.compile(r"\b(love|rain|night|lonely|alone|dream|tears|cry|sad|blue|slow|"
                   r"ballad|theme|mood|soft|quiet|morning|heart|miss|goodbye|memory|"
                   r"remember|forever|tender|gentle|sweet|angel|star|moon|sky|sea|"
                   r"wind|autumn|silence|lament|nostalgia|prayer|interlude|reverie|"
                   r"romance|serenade|whisper|shadow|velvet|smooth|mellow|warm|"
                   r"peace|still|rhodes|strings|piano)\b", re.I)

def quitar_tildes(s):
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


PRACTICA = re.compile(r"backing track.*\bkey of\b|\bjam track\b|practice track|"
                      r"\bplay ?along\b|\bkaraoke\b|\bbpm\b.*\bloop\b", re.I)

def descartar(t, dur, views, canal=None, genero=None):
    """Devuelve el motivo del descarte, o None si pasa. Cada regla salio de un
    rechazo real que Thomas escribio."""
    if BASURA.search(t): return "basura"
    if PRACTICA.search(t): return "backing track moderno de practica"
    if SEIS_OCHO.search(t): return "6/8, no loopea en 4/4"
    if REGGAE.search(t) or DUB_GENERO.search(t): return "reggae (dub es otro genero ahi)"
    if CONOCIDOS.search(t): return "nombre conocido: el tema lo conoce todo el mundo"
    if HIPHOP.search(t): return "hiphop: material ya usado, no para samplear"
    if REMIX_MODERNO.search(t): return "remix o edit moderno, no es de epoca"
    if genero == "fusion" and (ORTODOXO.search(t) or NO_FUSION.search(t)):
        return "jazz ortodoxo o psych: no es fusion"
    if dur and dur < 165: return "menos de 2:45"
    if dur and dur > 900: return "mas de 15 minutos"
    if views is not None and views > 300000: return "mainstream (>300k)"
    if views is not None and views < 150: return "menos de 150 views: suele ser rip casero"
    return None


def puntuar(t, dur, views, canal=None, anio=None, bpm=None, menor=None):
    """Ordena los que pasaron. No predice el gusto — ninguna señal de metadata
    lo hace (AUC 0.43-0.57 sobre 195 marcas) — pero sube lo que historicamente
    rinde: el canal, el espacio instrumental y la duracion."""
    s = 0.0
    razones = []
    hr = CANALES.get(canal)
    if hr is not None:
        s += (hr - BASE) * 4.0
        if hr >= .5: razones.append("%s rinde %d%%" % (canal, hr * 100))
        elif hr <= .2: razones.append("%s rinde poco (%d%%)" % (canal, hr * 100))
    if ESTRELLAS.get(canal, 0) >= 3.5:
        s += .5; razones.append("de ese canal sale lo mejor puntuado (%.1f★)" % ESTRELLAS[canal])
    if SIN_VOZ.search(t):
        s += 1.5; razones.append("sin voz: el espacio esta garantizado")
    if LENTO.search(t): s += .7
    if PIANO.search(t): s += .6; razones.append("piano o Rhodes")
    if OSCURO.search(t): s += .4
    if EFUSIVO.search(t): s -= 1.2; razones.append("suena a evento, no a cama")
    if dur:
        if dur >= 330: s += .8; razones.append("%d:%02d, hay lugar para un pasaje" % (dur//60, dur%60))
        elif dur >= 240: s += .4
    if views is not None and 150 <= views <= 100000: s += .3
    if anio and 1968 <= anio <= 1990: s += .5
    if bpm:
        b = bpm/2 if bpm > 115 and 55 <= bpm/2 <= 115 else bpm
        if 58 <= b <= 105: s += 1.0; razones.append("%d BPM" % round(b))
        elif b > 115: s -= 1.2; razones.append("%d BPM: muy rapido" % round(b))
    if menor: s += .5; razones.append("tonalidad menor")
    return round(s, 2), razones


# canales de musica generada con IA: 683 temas de 11 artistas inexistentes
VETADOS = {"Winta Groove"}
RATIO_IA = 8.0

def canal_sospechoso(titulos, canal=None):
    if canal and canal in VETADOS:
        return True, "canal vetado: musica generada con IA"
    if len(titulos) < 40:
        return False, ""
    arts = [re.split(r"\s+[-–—]\s+|\s*:\s+", t, 1)[0].strip().lower()[:28]
            for t in titulos]
    r = len(titulos) / max(1, len(set(arts)))
    if r >= RATIO_IA:
        return True, "%d temas de %d artistas: huele a IA" % (len(titulos), len(set(arts)))
    return False, ""
