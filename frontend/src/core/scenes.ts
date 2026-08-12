/**
 * Mapa de escenas — la inteligencia de digging, en datos.
 *
 * Una escena no es un género: es un conjunto de sellos, de artistas de segunda
 * línea, de jerga interna y de vocabulario en el idioma del lugar. Eso es lo que
 * usa un digger para buscar, y es lo único que devuelve material oscuro.
 *
 * La distinción que manda todo el módulo, y que salió de medir contra la API:
 *
 *   - `populares`: cómo el MUNDO nombra la escena ("japanese city pop", "quiet
 *     storm"). Son carnada de playlists. Medido: `japanese city pop 1982` da
 *     mediana de 178.000 views y 1 solo resultado abajo de 1000, casi todo mixes
 *     de 2 horas. Agregarle "vinyl rip" NO lo arregla (mediana 124.000): el
 *     término popular domina el ranking igual.
 *   - `jerga`: cómo la nombran los que la coleccionan ("modern soul", "private
 *     press", "wamono"). Medido: `modern soul boogie 1982 LP private press` da
 *     mediana de 806 views, 32 de 50 abajo de 1000 y ningún mix.
 *
 * O sea: **para bajar de nivel hay que cambiar el sustantivo de la query, no
 * agregarle adjetivos.** Los sellos, los artistas de segunda línea y el idioma
 * local son sustantivos que solo escribe alguien que ya está adentro.
 *
 * Ver docs/SOURCES.md y los casos de prueba de CLAUDE.md.
 */

export type SceneId =
  | 'city-pop'
  | 'wamono-jazz'
  | 'kankyo'
  | 'mpb'
  | 'samba-jazz'
  | 'brazilian-soul'
  | 'quiet-storm'
  | 'modern-soul'
  | 'soul-jazz'
  | 'spiritual-jazz'
  | 'deep-soul-70s'
  | 'jazz-fusion'
  | 'library'
  | 'italian-ost'
  | 'french-groove'
  | 'latin-psych'

/** Vocabulario en el idioma de la escena. El kanji o el portugués filtran solos. */
export interface VocabularioNativo {
  /** ISO 639-1, por si algún día se usa `relevanceLanguage` en search.list */
  idioma: string
  /** cómo se nombra la escena adentro del país */
  terminos: string[]
  /** cómo se titula un rip en ese idioma ("disco completo", "アルバム") */
  formato: string[]
}

export interface Escena {
  id: SceneId
  nombre: string
  /** texto del usuario que dispara la escena (se matchea normalizado) */
  gatillos: string[]
  /** el nombre popular: carnada de playlists, nunca va solo a una query */
  populares: string[]
  /** jerga de coleccionista: el reemplazo del nombre popular */
  jerga: string[]
  nativo?: VocabularioNativo
  /** sellos de la escena; van entre comillas en la query */
  sellos: string[]
  /** artistas de segunda línea — el long tail real de la escena */
  artistas: string[]
  /** lo hiper-conocido o ya-sampleado: se penaliza en el ranking, no se busca */
  obvios: string[]
  /** ventana donde la escena da lo mejor; de acá sale el año concreto de la query */
  epoca: [number, number]
}

export const ESCENAS: Escena[] = [
  {
    id: 'city-pop',
    nombre: 'city pop japonés',
    gatillos: ['city pop', 'citypop', 'japanese city pop', 'シティポップ', 'japanese aor', 'wamono'],
    populares: ['japanese city pop', 'city pop', '80s japanese'],
    jerga: ['wamono', 'japanese aor', 'japanese boogie', 'japanese funk', 'japanese soul LP'],
    nativo: {
      idioma: 'ja',
      // ordenados de más a menos preciso: '歌謡曲' (kayokyoku) es escena vecina y
      // trae enka de los 50 si sale primero. Medido con la semilla 20260811.
      terminos: ['シティポップ', '和モノ', '和ブギー', 'ニューミュージック', '歌謡曲'],
      formato: ['アルバム', 'レコード', '全曲', '名盤', '帯付き', '自主盤'],
    },
    sellos: [
      'Alfa Records', 'Moon Records', 'Air Records', 'Canyon Records', 'Better Days',
      'Invitation Records', 'For Life Records', 'Trio Records', 'Discomate', 'Panam Records',
      'Vap Records', 'Bourbon Records', 'Yupiteru', 'Eastworld',
      // Nada de majors acá: medido, `"Nippon Columbia" 1982 LP` devuelve el catálogo
      // entero del sello — Handel, enka, tokusatsu — porque el sello no identifica
      // la escena. Un sello sirve como query cuando ES la escena.
    ],
    artistas: [
      'Minako Yoshida', 'Hiroshi Sato', 'Junko Yagami', 'Hitomi Tohyama', 'Kingo Hamada',
      'Makoto Matsushita', 'Naoya Matsuoka', 'Rajie', 'Yurie Kokubu', 'Yasuko Agawa',
      'Nanako Sato', 'Miharu Koshi', 'Piper', 'Mariah', 'Akira Inoue', 'Masayoshi Takanaka',
      'Momoko Kikuchi', 'Kiyotaka Sugiyama', 'Chu Kosaka', 'Yumi Murata', 'Miki Asakura',
      'Kay Ishiguro', 'Tomoko Soryo', 'Yoshiko Sai', 'Toshiki Kadomatsu', 'Hiroshi Kamayatsu',
    ],
    obvios: [
      'Tatsuro Yamashita', 'Mariya Takeuchi', 'Plastic Love', 'Anri', 'Miki Matsubara',
      'Mayonaka no Door', 'Meiko Nakahara', 'Yellow Magic Orchestra', 'Flyday Chinatown',
      'Ryuichi Sakamoto', 'Casiopea', 'Takako Mamiya', '山下達郎', '竹内まりや',
    ],
    epoca: [1978, 1988],
  },
  {
    id: 'wamono-jazz',
    nombre: 'jazz y fusion japonés',
    gatillos: ['japanese jazz', 'wamono jazz', 'japanese fusion', 'japanese jazz funk', '和ジャズ'],
    populares: ['japanese jazz'],
    jerga: ['wamono jazz', 'japanese jazz funk', 'japanese modal', 'japan fusion LP'],
    nativo: {
      idioma: 'ja',
      terminos: ['和ジャズ', 'ジャズファンク', 'フュージョン', '日本のジャズ'],
      formato: ['アルバム', 'レコード', '名盤', '全曲'],
    },
    sellos: [
      'Three Blind Mice', 'East Wind', 'Better Days', 'Baystate', 'Whynot Records',
      'Trio Records', 'Union Jazz', 'Nippon Columbia', 'Paddle Wheel', 'Frasco',
    ],
    artistas: [
      'Masabumi Kikuchi', 'Ryo Kawasaki', 'Takeo Moriyama', 'Fumio Itabashi', 'Hideo Shiraki',
      'Motohiko Hino', 'Terumasa Hino', 'Kohsuke Mine', 'Yasuaki Shimizu', 'Mikio Masuda',
      'Toshiyuki Miyama', 'George Otsuka', 'Shigeharu Mukai', 'Isao Suzuki', 'Jiro Inagaki',
      'Hiromasa Suzuki', 'Norio Maeda', 'Kiyoshi Sugimoto',
    ],
    obvios: ['Sadao Watanabe', 'Toshiko Akiyoshi', 'Hiroshi Suzuki'],
    epoca: [1969, 1983],
  },
  {
    id: 'kankyo',
    nombre: 'ambient japonés',
    gatillos: ['kankyo', 'japanese ambient', 'environmental music', '環境音楽', 'japanese new age'],
    populares: ['japanese ambient'],
    jerga: ['kankyo ongaku', 'japanese new age', 'private press ambient'],
    nativo: {
      idioma: 'ja',
      terminos: ['環境音楽', 'アンビエント', 'ニューエイジ'],
      formato: ['アルバム', 'レコード', '全曲'],
    },
    sellos: ['Misawa Home', 'Green & Water', 'Newsic', 'Sound Process', 'Crescent', 'Balcony'],
    artistas: [
      'Hiroshi Yoshimura', 'Satoshi Ashikawa', 'Yoshio Ojima', 'Toshifumi Hinata',
      'Motohiko Hamase', 'Takashi Kokubo', 'Inoyama Land', 'Yutaka Hirose', 'Masahiro Sugaya',
    ],
    obvios: ['Haruomi Hosono', 'Susumu Yokota'],
    epoca: [1980, 1991],
  },
  {
    id: 'mpb',
    nombre: 'MPB / brasileño 70s',
    gatillos: [
      'mpb', 'brazilian', 'brasil', 'brazil', 'brasileiro', 'clube da esquina',
      'musica popular brasileira',
    ],
    populares: ['brazilian mpb', 'brazilian music', 'bossa nova'],
    jerga: ['MPB', 'clube da esquina', 'samba jazz', 'bolachão', 'disco de vinil MPB'],
    nativo: {
      idioma: 'pt',
      terminos: ['MPB', 'música popular brasileira', 'clube da esquina', 'samba jazz', 'bolachão'],
      formato: ['disco completo', 'álbum completo', 'LP completo', 'vinil', 'raridade', 'compacto'],
    },
    sellos: [
      'Odeon', 'Continental', 'Elenco', 'Copacabana', 'RGE', 'Som Livre', 'Tapecar',
      'Equipe', 'Beverly', 'Chantecler', 'Fermata', 'Rozenblit', 'Top Tape', 'Musicolor',
      'Discos Marcus Pereira', 'Codil', 'Bandeirantes',
    ],
    artistas: [
      'Antonio Adolfo', 'Dom Salvador', 'Joyce', 'Nelson Angelo', 'Luiz Melodia', 'Cassiano',
      'Hyldon', 'Dom Um Romão', 'Toninho Horta', 'Lo Borges', 'Beto Guedes', 'Sérgio Sampaio',
      'Piry Reis', 'Pedro Santos', 'Grupo Um', 'Marku Ribas', 'Ednardo', 'Sueli Costa',
      'Fátima Guedes', 'Evinha', 'Claudette Soares', 'Rosa Maria', 'Tony Bizarro',
      'Carlos Dafé', 'Som Imaginário', 'Quarteto Novo', 'Victor Assis Brasil', 'Danilo Caymmi',
      'Zé Rodrix', 'Miúcha', 'Nana Caymmi', 'Ivan Lins',
    ],
    obvios: [
      'Arthur Verocai', 'Marcos Valle', 'Azymuth', 'Jorge Ben', 'Tim Maia', 'Milton Nascimento',
      'Elis Regina', 'Gal Costa', 'Caetano Veloso', 'Gilberto Gil', 'Novos Baianos',
      'João Gilberto', 'Tom Jobim', 'Sérgio Mendes', 'Raul Seixas', 'Os Mutantes',
    ],
    epoca: [1968, 1980],
  },
  {
    id: 'samba-jazz',
    nombre: 'samba jazz / bossa',
    gatillos: ['samba jazz', 'bossa', 'samba', 'brazilian jazz'],
    populares: ['bossa nova'],
    jerga: ['samba jazz', 'bossa jazz trio', 'brazilian jazz LP', 'som três'],
    nativo: {
      idioma: 'pt',
      terminos: ['samba jazz', 'bossa', 'conjunto', 'trio'],
      formato: ['disco completo', 'LP completo', 'vinil', 'raridade'],
    },
    sellos: ['Elenco', 'Forma', 'Musidisc', 'Equipe', 'RGE', 'Odeon', 'Farroupilha'],
    artistas: [
      'Meirelles', 'Sambalanço Trio', 'Zimbo Trio', 'Som Três', 'Tamba Trio', 'Milton Banana',
      'Cesar Camargo Mariano', 'Bossa Três', 'Ed Lincoln', 'Walter Wanderley', 'Manfredo Fest',
      'Luiz Carlos Vinhas', 'Dom Um Romão', 'Victor Assis Brasil',
    ],
    obvios: ['João Gilberto', 'Stan Getz', 'Tom Jobim', 'Vinicius de Moraes'],
    epoca: [1963, 1976],
  },
  {
    id: 'brazilian-soul',
    nombre: 'black rio / soul brasileño',
    gatillos: ['black rio', 'brazilian soul', 'samba rock', 'brazilian funk'],
    populares: ['brazilian funk'],
    jerga: ['black rio', 'samba rock', 'soul brasileiro', 'baile black', 'brazilian boogie'],
    nativo: {
      idioma: 'pt',
      terminos: ['black rio', 'samba rock', 'soul brasileiro', 'baile'],
      formato: ['disco completo', 'vinil', 'compacto', 'raridade'],
    },
    sellos: ['Top Tape', 'Tapecar', 'RCA Victor', 'Polydor', 'Som Livre', 'Copacabana'],
    artistas: [
      'Copa 7', 'Gerson King Combo', 'Carlos Dafé', 'Hyldon', 'Cassiano', 'Tony Bizarro',
      'Miss Lene', 'Uniao Black', 'Sandra Sá', 'Zezé Motta', 'Robson Jorge',
      'Lincoln Olivetti', 'Marcos Resende', 'Bebeto',
    ],
    obvios: ['Tim Maia', 'Banda Black Rio', 'Jorge Ben', 'Trio Mocotó'],
    epoca: [1971, 1984],
  },
  {
    id: 'quiet-storm',
    nombre: 'quiet storm',
    gatillos: ['quiet storm', 'slow jam', 'smooth soul', 'baby making'],
    populares: ['quiet storm', 'smooth soul', '80s r&b'],
    jerga: [
      'modern soul', 'sweet soul', 'slow jam 45', 'deep soul ballad', 'crossover soul',
      'rare groove',
    ],
    sellos: [
      'Solar Records', 'Tabu Records', 'Salsoul', 'Prelude Records', 'Becket Records',
      'Total Experience', 'Uno Melodic', 'Chocolate City', 'Roadshow Records', 'Venture Records',
      'Source Records', 'Malaco', 'Philadelphia International', 'Cotillion', 'Mirage Records',
      'Sound of New York',
    ],
    artistas: [
      'Michael Wycoff', 'Webster Lewis', 'Norman Connors', 'Phyllis Hyman', 'Jean Carne',
      'Angela Bofill', 'Sylvia Striplin', 'Bobby Lyle', 'Ronnie Laws', 'Al Johnson',
      'Unlimited Touch', 'Positive Force', 'Bernard Wright', 'Gwen Guthrie', 'Melba Moore',
      'Jeffree', 'Rene & Angela', 'Howard Johnson', 'Leon Ware', 'Marlena Shaw',
      'Terry Callier', 'Willie Hutch', 'Deniece Williams', 'Starpoint', 'Kleeer',
    ],
    obvios: [
      'Roy Ayers', 'Patrice Rushen', 'Bobby Caldwell', 'Smokey Robinson', 'Sade',
      'Luther Vandross', 'Anita Baker', 'Isley Brothers', 'Teddy Pendergrass', 'Marvin Gaye',
      'Barry White', 'The Whispers', 'Atlantic Starr', 'Frankie Beverly',
    ],
    epoca: [1977, 1987],
  },
  {
    id: 'modern-soul',
    nombre: 'modern soul / boogie',
    gatillos: ['modern soul', 'boogie', 'private press', '80s soul', 'rare groove', 'street soul'],
    populares: ['80s soul', 'funk'],
    jerga: [
      'modern soul', 'boogie funk', 'private press', 'indie soul 45', 'crossover soul',
      'lowrider soul',
    ],
    sellos: [
      'Salsoul', 'Prelude Records', 'West End Records', 'Becket Records', 'Sam Records',
      'Emergency Records', 'Streetwise', 'Panorama Records', 'Uno Melodic', 'Solar Records',
      'De-Lite Records', 'Chocolate City', 'Profile Records', 'TK Disco',
    ],
    artistas: [
      'Sylvia Striplin', 'Al Johnson', 'Kleeer', 'Aurra', 'Starpoint', 'Unlimited Touch',
      'Direct Current', 'Positive Force', 'Bernard Wright', 'Tom Browne', 'Kashif',
      'Jeffree', 'Universal Robot Band', 'Logg', 'Convertion', 'Sun Palace', 'Ozone',
      'Central Line', 'Atmosfear', 'Light of the World', 'Freeez', 'Beggar & Co',
    ],
    obvios: ['Roy Ayers', 'Patrice Rushen', 'Chic', 'Kool & The Gang', 'Earth Wind & Fire'],
    epoca: [1978, 1986],
  },
  {
    id: 'soul-jazz',
    nombre: 'soul jazz / jazz funk',
    gatillos: ['soul jazz', 'jazz funk', 'organ jazz', 'hammond', 'rare groove jazz'],
    populares: ['jazz funk', 'soul jazz'],
    jerga: ['organ groove', 'jazz funk', 'hammond organ jazz', 'soul jazz LP', 'rare groove jazz'],
    sellos: [
      'Prestige', 'Groove Merchant', 'Muse Records', 'Cadet Records', 'Mainstream Records',
      'Cobblestone', 'Perception Records', 'Flying Dutchman', 'Milestone', 'Catalyst Records',
      'Jazzland', 'Kudu', 'CTI', 'Choice Records',
    ],
    artistas: [
      'Charles Earland', 'Reuben Wilson', 'Johnny Hammond', 'Ronnie Foster', 'Melvin Sparks',
      'Boogaloo Joe Jones', 'Harold Alexander', 'Rusty Bryant', 'Houston Person',
      'Sonny Phillips', 'Leon Spencer', 'Gene Ammons', 'Weldon Irvine', 'Bobbi Humphrey',
      'Gary Bartz', 'Doug Carn', 'Michel Sardaby', 'Eddy Louiss', 'Jef Gilson',
      'Calvin Keys', 'Rudolph Johnson',
    ],
    obvios: [
      'Grant Green', 'Ahmad Jamal', 'Ramsey Lewis', 'Jimmy Smith', 'Lou Donaldson',
      'Herbie Hancock', 'Donald Byrd', 'Bob James', 'Idris Muhammad', 'Cedar Walton',
      'Freddie Hubbard', 'Miles Davis', 'John Coltrane',
    ],
    epoca: [1967, 1977],
  },
  {
    id: 'spiritual-jazz',
    nombre: 'spiritual jazz',
    gatillos: ['spiritual jazz', 'astral', 'modal jazz', 'strata east', 'black jazz'],
    populares: ['spiritual jazz'],
    jerga: ['strata east', 'black jazz records', 'private press jazz', 'modal LP', 'deep spiritual'],
    sellos: [
      'Strata-East', 'Black Jazz', 'Tribe Records', 'Strata Records', 'Black Fire',
      'Nimbus West', 'Dogtown Records', 'Ubiquity', 'India Navigation', 'Survival Records',
    ],
    artistas: [
      'Doug Carn', 'Phil Ranelin', 'Wendell Harrison', 'Clifford Jordan', 'Charles Tolliver',
      'Stanley Cowell', 'Marion Brown', 'Henry Franklin', 'Kellee Patterson', 'Calvin Keys',
      'Rudolph Johnson', 'Walter Bishop Jr', 'Roy Brooks', 'Harold Land', 'Woody Shaw',
      'Horace Tapscott', 'Oneness of Juju', 'Mtume Umoja Ensemble',
    ],
    obvios: ['Pharoah Sanders', 'Alice Coltrane', 'Sun Ra', 'John Coltrane', 'Yusef Lateef'],
    epoca: [1969, 1979],
  },
  {
    id: 'deep-soul-70s',
    nombre: 'soul 70s',
    gatillos: ['70s soul', 'sweet soul', 'deep soul', 'soul ballad', 'philly soul', 'southern soul'],
    populares: ['70s soul', 'classic soul'],
    jerga: ['sweet soul', 'deep soul 45', 'group harmony', 'crossover soul', 'northern soul'],
    sellos: [
      'Hi Records', 'Stax', 'Volt', 'Brunswick', 'Curtom', 'Invictus', 'Hot Wax', 'Sussex',
      'Buddah', 'Avco', 'Alaga', 'Mankind', 'Spring Records', 'Wand', 'Scepter', 'Event',
      'People Records', 'Chelsea Records',
    ],
    artistas: [
      'The Ebonys', 'The Moments', 'Blue Magic', 'The Dells', 'New Birth', 'Sweet Charles',
      'Leroy Hutson', 'Ronnie Dyson', 'Bill Brandon', 'Syl Johnson', 'Little Beaver',
      'Jean Plum', 'Ann Sexton', 'Marion Black', 'The Independents', 'Notations',
      'Natural Four', 'Enchantment', 'Special Delivery', 'Jackie Moore', 'Margie Joseph',
      'Bobby Womack', 'Eddie Kendricks', 'Willie Hutch',
    ],
    obvios: [
      'Marvin Gaye', 'Al Green', 'Curtis Mayfield', 'Isaac Hayes', 'Bill Withers',
      'Donny Hathaway', 'The Temptations', 'Stevie Wonder', 'Aretha Franklin',
      'Otis Redding', 'James Brown', 'The Delfonics',
    ],
    epoca: [1968, 1979],
  },
  {
    id: 'jazz-fusion',
    nombre: 'jazz fusion / AOR instrumental',
    gatillos: ['fusion', 'jazz fusion', 'rhodes fusion', 'electric jazz'],
    populares: ['jazz fusion'],
    jerga: ['rhodes LP', 'electric jazz private press', 'fusion obscure LP', 'jazz funk fusion'],
    sellos: [
      'CTI', 'Kudu', 'Inner City', 'MPS Records', 'Timeless', 'Muse Records', 'Salvation',
      'Baystate', 'Elektra Musician', 'Catalyst Records',
    ],
    artistas: [
      'David Matthews', 'Onaje Allan Gumbs', 'Sonny Fortune', 'Eddie Henderson', 'Ryo Kawasaki',
      'Hal Galper', 'Reggie Lucas', 'Mtume', 'Alphonso Johnson', 'Norman Connors',
      'Jan Hammer', 'Michal Urbaniak', 'Placebo', 'Marc Moulin', 'Cos',
      'Wolfgang Dauner', 'Klaus Doldinger',
    ],
    obvios: [
      'Weather Report', 'Return to Forever', 'Herbie Hancock', 'Chick Corea',
      'Mahavishnu Orchestra', 'Bob James', 'Grover Washington', 'George Benson',
    ],
    epoca: [1971, 1982],
  },
  {
    id: 'library',
    nombre: 'library music',
    gatillos: ['library', 'library music', 'production music', 'kpm', 'de wolfe', 'sonorizzazioni'],
    populares: ['library music'],
    jerga: [
      'KPM 1000 series', 'production music LP', 'sonorizzazioni', "musique d'illustration",
      'underscore library', 'musica per commenti sonori', 'rare library LP',
    ],
    nativo: {
      idioma: 'it',
      terminos: ['sonorizzazioni', 'musica per commenti sonori', 'musiche di scena'],
      formato: ['LP', 'vinile', 'disco completo'],
    },
    sellos: [
      'KPM', 'De Wolfe', 'Bruton Music', 'Chappell', 'Themes International', 'Amphonic',
      'Sonoton', 'Selected Sound', 'Coloursound', 'Conroy', 'Studio G', 'Southern Library',
      'Montparnasse 2000', 'Tele Music', "Musique Pour L'Image", 'Crea Sound', 'Patchwork',
      'Octopus Records', 'Flipper Music', 'Deneb Records', 'Standard Music Library',
    ],
    artistas: [
      'Alan Hawkshaw', 'Keith Mansfield', 'Brian Bennett', 'John Cameron', 'Alan Parker',
      'Syd Dale', 'Johnny Pearson', 'Nino Nardini', 'Roger Roger', 'Janko Nilovic',
      'Sauveur Mallia', 'Bernard Estardy', 'Piero Umiliani', 'Alessandro Alessandroni',
      'Stefano Torossi', 'Amedeo Tommasi', 'Klaus Weiss', 'Peter Thomas', 'Egisto Macchi',
      'Giuliano Sorgini', 'Daniela Casa', 'Sandro Brugnolini', 'Yan Tregger', 'Steve Gray',
      'Duncan Lamont', 'James Clarke', 'David Snell', 'Francis Monkman', 'Trevor Duncan',
      'Barry Stoller', 'Richard Myhill', 'Dave Richmond',
    ],
    obvios: [],
    epoca: [1968, 1980],
  },
  {
    id: 'italian-ost',
    nombre: 'OST italiana',
    gatillos: ['italian', 'italo', 'giallo', 'poliziottesco', 'colonna sonora', 'italian soundtrack'],
    populares: ['italian soundtrack', 'giallo'],
    jerga: ['colonna sonora', 'sonorizzazioni', 'beat italiano', 'italian library LP'],
    nativo: {
      idioma: 'it',
      terminos: ['colonna sonora', 'musica da film', 'sonorizzazioni', 'beat italiano'],
      formato: ['disco completo', 'vinile', 'LP'],
    },
    sellos: [
      'CAM', 'Cinevox', 'Beat Records', 'Fonit Cetra', 'Gemelli', 'Canopo', 'Costanza Records',
      'Lupus', 'Vedette', 'General Music', 'RCA Italiana', 'Dischi Ricordi', 'Cometa',
    ],
    artistas: [
      'Piero Piccioni', 'Armando Trovajoli', 'Luis Bacalov', 'Stelvio Cipriani', 'Riz Ortolani',
      'Gianni Ferrio', 'Nico Fidenco', 'Franco Micalizzi', 'Bruno Nicolai', 'Carlo Savina',
      'Manuel De Sica', 'Berto Pisano', 'Roberto Nicolosi', 'Guido e Maurizio De Angelis',
      'Fred Bongusto', 'Giorgio Gaslini', 'Piero Umiliani', 'Egisto Macchi', 'Marcello Giombini',
    ],
    obvios: ['Ennio Morricone', 'Nino Rota', 'Goblin'],
    epoca: [1967, 1979],
  },
  {
    id: 'french-groove',
    nombre: 'groove francés / OST',
    gatillos: ['french', 'francais', 'française', 'ye-ye', 'french library', 'french soundtrack'],
    populares: ['french music', 'french soundtrack'],
    jerga: ["musique d'illustration", 'sonorisation', 'french library LP', 'jerk'],
    nativo: {
      idioma: 'fr',
      terminos: ['musique de film', 'bande originale', "musique d'illustration", 'sonorisation'],
      formato: ['album complet', 'vinyle', '33 tours', 'disque'],
    },
    sellos: [
      'Tele Music', 'Montparnasse 2000', 'Crea Sound', "Musique Pour L'Image", 'Vogue',
      'Barclay', "Disc'AZ", 'Pathé', 'Riviera', 'Neuilly',
    ],
    artistas: [
      'François de Roubaix', 'Jean-Claude Vannier', 'Michel Colombier', 'Michel Magne',
      'Vladimir Cosma', 'Bernard Estardy', 'Janko Nilovic', 'Roger Roger', 'Nino Nardini',
      'Eddie Warner', 'Jean-Pierre Decerf', 'Sauveur Mallia', 'Yan Tregger', 'Marc Chantereau',
      'Pierre-Alain Dahan', 'Slim Pezin', 'Georges Delerue', 'Jacky Giordano', 'Camille Sauvage',
    ],
    obvios: ['Serge Gainsbourg', 'Michel Legrand', 'Jean-Michel Jarre'],
    epoca: [1968, 1980],
  },
  {
    id: 'latin-psych',
    nombre: 'psych / prog latinoamericano',
    gatillos: [
      'latin psych', 'peruvian', 'peruano', 'rock argentino', 'chilean', 'chileno',
      'cumbia psicodelica', 'latin american psych', 'rock peruano',
    ],
    populares: ['latin psych', 'cumbia'],
    jerga: ['rock peruano', 'psicodelia', 'prog argentino', 'private press latino', 'rareza vinilo'],
    nativo: {
      idioma: 'es',
      terminos: ['psicodelia', 'rock peruano', 'rock argentino', 'rareza'],
      formato: ['disco completo', 'vinilo', 'LP completo', 'álbum completo'],
    },
    sellos: [
      'Discos Fuentes', 'MAG', 'Sono Radio', 'El Virrey', 'Infopesa', 'Odeon Argentina',
      'Music Hall', 'Trova', 'Microfón', 'Talent', 'RCA Victor Argentina', 'Codiscos',
      'Discos Dideca',
    ],
    artistas: [
      'Traffic Sound', 'Los Destellos', 'Laghonia', 'We All Together', 'Los Jaivas',
      'Los Blops', 'Arco Iris', 'Espíritu', 'Alas', 'MIA', 'Invisible', 'Pescado Rabioso',
      'Toncho Pilatos', 'La Revolución de Emiliano Zapata', 'Módulo 1000', 'Nahuatl',
      'El Polen', 'Tarkus', 'Aguaturbia', 'Color Humano', 'Vox Dei', 'Congreso',
    ],
    obvios: ['Santana', 'Los Mirlos', 'Almendra', 'Charly García', 'Sui Generis', 'Los Ángeles Negros'],
    epoca: [1968, 1978],
  },
]

/**
 * Obras y nombres tan sampleados o tan virales que traerlos no es un hallazgo.
 * No se filtran (a veces querés el disco entero y no el corte famoso): se
 * penalizan en el ranking de digging. Ver `queries.ts`.
 */
export const SOBREEXPUESTOS: string[] = [
  'plastic love', 'stay with me', 'mayonaka no door', 'flyday chinatown', 'sparkle',
  'ride on time', 'midnight pretenders', 'telephone number', 'remember summer days',
  'last summer whisper', 'na boca do sol', 'summer madness', 'mas que nada',
  'lovely day', 'inner city blues', 'nautilus', 'apache', 'think about it',
  'synthetic substitution', 'amen brother', 'nas montanhas',
]

const sinAcentos = (s: string): string =>
  s.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase()

/**
 * Detecta qué escenas pide el texto del usuario. Puede devolver varias
 * ("70s brazilian MPB" pega en mpb y samba-jazz): el planificador las usa por
 * orden de fuerza. Devuelve [] cuando no reconoce nada, y ahí se cae al fallback.
 */
export function detectarEscenas(texto: string, extra: string[] = []): Escena[] {
  const hay = sinAcentos([texto, ...extra].join(' '))
  const con: Array<{ escena: Escena; peso: number }> = []

  for (const escena of ESCENAS) {
    let peso = 0
    for (const gatillo of escena.gatillos) {
      const g = sinAcentos(gatillo)
      if (!hay.includes(g)) continue
      // un gatillo de varias palabras es evidencia más fuerte que uno suelto
      peso += g.includes(' ') ? 3 : 2
    }
    // nombrar un sello o un artista de la escena la confirma sola
    for (const sello of escena.sellos) if (hay.includes(sinAcentos(sello))) peso += 4
    for (const artista of escena.artistas) if (hay.includes(sinAcentos(artista))) peso += 4
    if (peso > 0) con.push({ escena, peso })
  }

  return con.sort((a, b) => b.peso - a.peso).map((c) => c.escena)
}

/** Todo lo que conviene evitar de una escena: sus obvios más los globales. */
export function obviosDe(escenas: Escena[]): string[] {
  const propios = escenas.flatMap((e) => e.obvios.map((o) => o.toLowerCase()))
  return Array.from(new Set([...SOBREEXPUESTOS, ...propios]))
}
