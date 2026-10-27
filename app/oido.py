# -*- coding: utf-8 -*-
"""El oído de Thomas, recalibrado con el feedback exportado del 24-oct-2026
(80 temas marcados: 21 guardados, 22 rechazados con motivo).

Lo que ese feedback corrigió, y que las tandas anteriores tenían mal:
  * El quemado es por TEMA, no por artista. Guardó 3 de Ace Spectrum y rechazó
    solo el de los 52 samples; guardó 2 de Yuji Ohno, que yo tenía en lista negra.
  * Rechaza 6/8: necesita 4/4 para loopear.
  * Rechaza jazz ortodoxo / trio de piano / jam ("imposible samplear esto").
  * Rechaza cuando la voz tapa todo; guardó un (Instrumental) explicito.
  * Views: 100k es warning, >300k ya es demasiado conocido. 500 views NO es un
    premio: no necesita que sea una canción perdida en el universo.
"""
import re

# --- loopeabilidad: lo que hace que un tema sirva como loop, no como chop ---
INSTRUMENTAL = re.compile(r"\binstrumental\b|\(inst\.?\)|\[inst\.?\]|\bversion inst|"
                          r"\bbacking\b|\bkaraoke version\b", re.I)
# jazz ortodoxo: lo que rechazo por "jam", "piano a las chapas", "muy ortodoxo"
ORTODOXO = re.compile(
    r"\b(trio|quartet|quintet|sextet|septet|big band|orchestra jazz|bebop|be-bop|"
    r"hard bop|post ?bop|swing|dixieland|standards?|improvisation|impro|jam|"
    r"live at the|blue note|real book)\b", re.I)
# pero si ademas dice fusion/rhodes/electric, NO es ortodoxo: es lo que si quiere
FUSION_OK = re.compile(
    r"\b(fusion|rhodes|fender|electric|moog|synth|syntheti|arp|crossover|"
    r"balearic|ambient|boogie|modern soul|quiet storm|aor|city ?pop|"
    r"soul ?jazz|jazz ?funk|downtempo|mellow)\b", re.I)
# compas 6/8 y afines: no loopea en 4/4
SEIS_OCHO = re.compile(r"\b6/8\b|\b12/8\b|\bwaltz\b|\bvals\b|\bvalse\b|\bvalzer\b|\b3/4\b", re.I)

# --- el abanico de paises: NO es solo USA y Japon ---
PAISES = {
 "brasil": r"\[brazil|\bbrasil|\bmpb\b|bossa|samba ?jazz|\bbrazilian\b",
 "italia": r"\[italy|\bitalian\b|\bitalia\b|rai\b|\bcinevox\b",
 "francia": r"\[france|\bfrench\b|\bfrancia\b|\bvogue\b|\bbarclay\b",
 "alemania": r"\[germany|\bgerman\b|\bMPS\b|\bSABA\b|\bbrd\b",
 "polonia": r"\[poland|\bpolish\b|polskie|polski|\bmuza\b",
 "checo": r"\[czech|\bczech|supraphon|\bslovak",
 "yugo": r"\[yugoslav|\bjugoton\b|\bRTB\b|\bcroatia|\bserbia",
 "urss": r"\[soviet|\[ussr|\[russia|melodiya|мелодия|\[eston|\[latv|\[lith",
 "hungria": r"\[hungar|\bpepita\b|\bqualiton\b",
 "turquia": r"\[turkey|\bturkish\b|\banadolu\b|\btürk",
 "grecia": r"\[greece|\bgreek\b|\bhellenic\b",
 "espana": r"\[spain|\bspanish\b|\bespaña\b|\bbelter\b|\bhispavox\b",
 "latam": r"\[peru|\[colombia|\[chile|\[argentin|\[mexic|\[venezuela|\[uruguay|"
          r"\bcumbia\b|\bbolero\b|\bcriolla\b|\bchicha\b",
 "escandinavia": r"\[sweden|\[norway|\[denmark|\[finland|\bsvensk|\bsuomi\b",
 "israel": r"\[israel|\bhebrew\b|\bisraeli\b",
 "asia": r"\[korea|\[indonesia|\[thai|\[philippin|\[india\b|\bgamelan\b|\bkayo\b",
 "africa": r"\[nigeria|\[ethiopia|\[ghana|\[south africa|\bafrobeat\b|\bethio",
 "japon": r"\[japan|\bjapanese\b|\bcity ?pop\b|\bkayokyoku\b",
 "usa": r"\[us\]|\[usa\]|\bamerican\b",
 "uk": r"\[uk\]|\bbritish\b|\bkpm\b|\bde ?wolfe\b|\bbruton\b",
}
RX_PAIS = {k: re.compile(v, re.I) for k, v in PAISES.items()}

def pais_de(t):
    for k, rx in RX_PAIS.items():
        if rx.search(t):
            return k
    return "?"

def curva_views(v):
    """Antes premiaba lo de 500 views y castigaba desde 150k. Thomas: 100k es
    warning, 300k+ ya es demasiado conocido, y 500 views no es mérito."""
    if v is None:
        return 0.0
    if v > 1_000_000: return -2.2
    if v > 500_000:   return -1.5
    if v > 300_000:   return -0.9
    if v > 100_000:   return -0.35      # warning, no condena
    return 0.0                           # de 0 a 100k: todo igual, sin premio

def loopeabilidad(t, dur):
    """Thomas necesita LOOPS, no chops de dos segundos."""
    s = 0.0
    if INSTRUMENTAL.search(t): s += 1.3
    if SEIS_OCHO.search(t): s -= 1.6
    if ORTODOXO.search(t) and not FUSION_OK.search(t): s -= 1.4
    if FUSION_OK.search(t): s += 0.7
    d = dur or 0
    if d >= 330: s += 0.8               # 5:30+ : hay aire instrumental
    elif d >= 240: s += 0.5
    elif d < 165: s -= 0.6              # menos de 2:45 es casi todo voz
    return s
