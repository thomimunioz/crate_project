"""Red de pesca LatAm: soul / jazz fusion / 80s melancólico. ytsearch + Mix, sin quota."""
import json, os, subprocess
from concurrent.futures import ThreadPoolExecutor
YT = r"G:\Thomi - Mi Carpeta\crate_project\backend\.venv\Scripts\yt-dlp.exe"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "latam_pool.json")

Q = {
"ar70": ["Alas banda argentina 1976 album", "Alas Mimi Kokoro 1983", "Bubu Anabelas 1978", "Crucis 1976 instrumental",
  "Espiritu Crisalida 1975", "Contraluz grupo argentino 1977", "Pastoral 1974 argentina", "Rodolfo Alchourron instrumental",
  "Jorge Navarro piano jazz argentino 1970s", "MIA Musicos Independientes Asociados 1977", "MIA Cornonstipicum 1978",
  "Litto Nebbia Melopea instrumental 1970s", "Arco Iris Sudamerica 1972", "Aquelarre 1973 argentina instrumental",
  "Color Humano 1973 instrumental", "Alma y Vida balada 1972", "Invisible Durazno Sangrando 1975",
  "Nito Mestre Desconocidos de Siempre 1976", "Raul Porchetto 1974 argentina", "La Maquina de Hacer Pajaros 1977 instrumental",
  "Materia Gris argentina 1973", "Santiago Giacobbe organo argentina", "Bernardo Baraj saxo argentina",
  "Gustavo Bergalli jazz argentino 1970s", "Sergio Mihanovich jazz argentino", "Chango Farias Gomez Musicos del Centro",
  "Dino Saluzzi 1982 instrumental", "Rodolfo Mederos 1977 tango fusion", "Jorge Pinchevsky violin argentina",
  "Pedro y Pablo Conesa 1970", "Alejandro Lerner 1983 instrumental", "Moris 1970 argentina", "Miguel Abuelo Nada 1973",
  "Daniel Homer guitarra argentina", "Ricardo Lew guitarra jazz argentino", "Nestor Astarita bateria jazz argentino",
  "Gustavo Santaolalla Arco Iris 1974", "Soluna argentina 1978", "Polifemo 1976 argentina", "Tantor argentina 1979"],
"ar80": ["Virus Superficies de Placer 1987", "Los Encargados Daniel Melero 1983", "Metropoli banda argentina 1985",
  "Clap banda argentina 1985", "Sueter 1983 argentina", "Don Cornelio y la Zona 1987", "Friccion Consumacion o Consumo 1986",
  "Juana La Loca argentina 1986", "Celeste Carballo 1982", "Pedro Aznar Contemplacion 1984", "Spinetta Bajo Belgrano 1983 instrumental",
  "Spinetta Madre en Anos Luz 1984", "GIT 1984 argentina", "Zas banda argentina 1982", "Man Ray argentina 1988",
  "Los Twist La Dicha en Movimiento lento", "Charly Garcia Piano Bar instrumental", "Charly Garcia Tango 1986 Pedro Aznar",
  "Fito Paez Del 63 1984", "Baglietto Tiempos Dificiles 1983", "Alfredo Casero no", "Los Pillos argentina 1988",
  "Autobus argentina 1986", "Marilina Ross 1982", "Nacha Guevara orquesta 1980", "Miguel Zavaleta Sueter",
  "Pastoral 1980 argentina", "Lito Vitale Quinteto 1985", "Verdades Clandestinas Pedro Aznar", "Charly Garcia Clics Modernos instrumental"],
"br70": ["Dom Salvador Abolicao 1973", "Tenorio Jr Embalo 1964", "Luiz Carlos Vinhas O Som Psicodelico 1968",
  "Victor Assis Brasil Esperanto 1970", "Nelson Angelo e Joyce 1972", "Novelli Nega 1976", "Pedro Santos Krishnanda 1968",
  "Cassiano Imagem e Som 1971", "Hyldon Na Rua Na Chuva Na Fazenda 1975", "Tim Maia Racional 1975", "Marku Ribas 1973",
  "Emilio Santiago 1975", "Luiz Eca A Pessoa 1970", "Tamba Trio 1968", "Som Tres Edison Machado 1970",
  "Quarteto Novo 1967", "Lo Borges 1972", "Toninho Horta Terra dos Passaros 1980", "Ivan Lins Modo Livre 1974",
  "Joyce Feminina 1980", "Danilo Caymmi 1977", "Ze Rodrix 1973", "O Terco 1973 brasil", "Som Imaginario 1970",
  "Marcos Valle Vontade de Rever Voce 1981", "Azymuth Light as a Feather 1979", "Wagner Tiso 1978 instrumental",
  "Jorge Ben Africa Brasil instrumental", "Milton Nascimento Minas 1975 instrumental", "Flavio Venturini 1980",
  "Guilherme Vergueiro 1977", "Paulo Moura Confusao Urbana 1976", "Hermeto Pascoal Slaves Mass 1977",
  "Eumir Deodato 1973 instrumental", "Dori Caymmi 1980", "Claudio Roditi brasil jazz", "Sergio Mendes Primal Roots 1972"],
"br80": ["Marina Lima 1983 brasil", "Zizi Possi 1982", "Ritchie Voo de Coracao 1983", "Ed Motta 1990 brasil",
  "Djavan Luz 1982", "Gilberto Gil Raca Humana 1984", "Guilherme Arantes 1982", "Lulu Santos 1984 lento",
  "Sandra Sa 1982 brasil", "Luiz Melodia 1980", "Tim Maia 1983 balada", "Jorge Vercillo no", "Cauby Peixoto 1983",
  "Simone 1982 brasil", "Nana Caymbi 1980", "Roupa Nova instrumental 1984", "Lincoln Olivetti arranjos 1983",
  "Robson Jorge Lincoln Olivetti instrumental", "Cassiano 1982", "Marcos Valle 1983 brasil", "Ivan Lins 1983 balada",
  "Edson Frederico 1980", "Banda Black Rio 1980", "Miucha 1980", "Joao Bosco 1982 instrumental"],
"uy": ["Eduardo Mateo Cuerpo y Alma 1984", "Eduardo Mateo Mateo y Trasante 1976", "El Kinto Eduardo Mateo",
  "Hugo Fattoruso 1970s uruguay", "Opa Magic Time 1977", "Jaime Roos 1984 uruguay", "Fernando Cabrera 1984",
  "Totem uruguay 1971 instrumental", "Dino uruguay balada 1972", "Leo Masliah 1983", "Pippo Spera uruguay",
  "Ruben Rada Radeces 1977", "Gustavo Ripa guitarra uruguay", "Urbano Moraes uruguay 1972", "Musica Rara uruguay"],
"pe_cl": ["Telegraph Avenue peru 1971", "Traffic Sound Virgin 1970", "Laghonia Glue 1970", "We All Together peru 1972",
  "El Polen Cholo 1973", "Pax peru 1972", "Gerardo Manuel peru 1971", "Los Angeles Negros balada 1970",
  "Congreso Terra Incognita 1975", "Los Blops 1971 chile", "Fulano chile 1987", "Tumulto chile 1974",
  "Panal chile 1971", "Aguaturbia chile 1970", "Electrodomesticos chile 1986", "Santiago del Nuevo Extremo 1980",
  "Cristian Crisosto chile fusion", "Inti Illimani instrumental 1976", "Los Jaivas Alturas de Machu Picchu instrumental",
  "Jorge Gonzalez chile 1980s", "Matraz chile fusion", "Quilapayun instrumental 1974"],
"co_ve_mx": ["Vytas Brenner Ofrenda 1973", "Aldemaro Romero Onda Nueva 1971", "Gerry Weil The Message 1971",
  "Frank Quintero venezuela 1980", "Miguel Angel Fuster venezuela", "Pablo Schneider venezuela",
  "Lucho Bermudez instrumental orquesta balada", "Siglo Cero colombia 1976", "Genesis colombia 1974",
  "Ana y Jaime colombia 1969", "Los Yetis colombia 1968", "Toncho Pilatos 1973 mexico", "Nahuatl mexico 1974",
  "El Ritual mexico 1971", "Sacbe mexico 1977", "Eugenio Toussaint mexico jazz", "Juan Jose Calatayud piano mexico",
  "Tino Contreras jazz mexicano 1960s", "Enrique Nery piano mexicano", "Chac Mool mexico 1980",
  "Via Lactea mexico 1976", "Cecilia Toussaint 1984 mexico", "Jaime Lopez mexico 1980s", "Los Dug Dugs Smog 1972",
  "Armando Manzanero instrumental orquesta", "Carlos Lyra en Mexico 1970"],
"balada": ["balada instrumental latinoamericana 1974 orquesta cuerdas", "tema instrumental argentino 1976 piano cuerdas",
  "Los Angeles Negros instrumental", "Leonardo Favio 1970 orquesta", "Sandro orquesta instrumental 1971",
  "musica incidental television argentina 1970s", "biblioteca musical argentina library 1975",
  "Victor Schlichter library argentina", "Adrian Otero no", "soul argentino 1974 raro", "soul brasileiro 1973 raro balada",
  "jazz fusion sudamericano 1978 raro instrumental", "latin jazz melancolico 1977 rhodes", "MPB instrumental melancolico 1976 rhodes"],
}

SEEDS = {"67z1qaTatss": "Raíces – Los Habitantes de la Rutina", "MNesfOtfVUw": "Grupo Encuentro – Siracusa",
         "s00MmHFu-jI": "Adalberto Cevasco – Dos Modos de Ser", "bDDOsZuFXIA": "Oscar Moro – Mirada Azul",
         "hi5Th8TSEW8": "Marcio Montarroyos – Carioca", "1xwy92jXTYA": "Nivaldo Ornelas – Querubins e Serafins"}

def run(args, timeout=150):
    r = subprocess.run([YT, "--flat-playlist", "--no-warnings", "--print",
                        "%(id)s|||%(title)s|||%(uploader)s|||%(channel_id)s|||%(duration)s|||%(view_count)s"] + args,
                       capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    out = []
    for l in r.stdout.splitlines():
        p = l.split("|||")
        if len(p) < 6 or not p[0]: continue
        out.append({"id": p[0], "title": p[1], "uploader": None if p[2] == "NA" else p[2],
                    "channel_id": None if p[3] == "NA" else p[3],
                    "dur": int(float(p[4])) if p[4] not in ("NA", "") else None,
                    "views": int(float(p[5])) if p[5] not in ("NA", "") else None})
    return out

pool = {}
def add(items, layer, via):
    for it in items:
        e = pool.setdefault(it["id"], {**it, "layer": layer, "via": []})
        if via not in e["via"]: e["via"].append(via)

def search(arg):
    layer, q = arg
    try: return layer, q, run([f"ytsearch10:{q}"])
    except Exception: return layer, q, []

tasks = [(layer, q) for layer, qs in Q.items() for q in qs]
with ThreadPoolExecutor(6) as ex:
    for layer, q, items in ex.map(search, tasks):
        add(items, layer, q)
print("tras", len(tasks), "búsquedas:", len(pool))

def mix(arg):
    vid, nombre = arg
    try: return nombre, run([f"https://www.youtube.com/watch?v={vid}&list=RD{vid}"], timeout=120)[:150]
    except Exception: return nombre, []
with ThreadPoolExecutor(3) as ex:
    for nombre, items in ex.map(mix, SEEDS.items()):
        add(items, "mix", f"Mix de {nombre}")
        print("mix", nombre, len(items))

json.dump(pool, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print("pool total:", len(pool), "→", OUT)
