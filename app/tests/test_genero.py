# -*- coding: utf-8 -*-
"""El clasificador de genero que etiqueta las sugerencias del hotlist.

Casi todos los casos son errores reales que aparecieron armando la tanda del
28-oct. El mas caro es el del apellido: aparecio dos veces, con dos reglas
distintas, por el mismo motivo — mirar el titulo ENTERO en vez del lado del
tema.
"""
import criterios


class TestGeneroPorCanal:
    def test_el_canal_manda_sobre_el_titulo(self):
        """De un canal del que ya guardo, guarda 16-22% contra 3% del resto:
        quien lo subio es el dato que mas predice."""
        assert criterios.genero_de("Lo que sea", "Krem Soulz") == "SOUL"
        assert criterios.genero_de("Lo que sea", "Five Special Records") == "R&B SOUL"

    def test_un_canal_de_fusion_con_japones_es_city_pop(self):
        g = criterios.genero_de("ミオフー Mio Fou - Picasso", "Music for empty rooms")
        assert g == "CITY POP"

    def test_un_canal_desconocido_no_rompe(self):
        assert criterios.genero_de("X - Rare Soul 45", "Canal Nuevo") == "SOUL"


class TestApellidosQueParecenInstrumentos:
    def test_rhodes_de_apellido_no_define_el_genero(self):
        """Cynthia Rhodes canta, no toca un Fender Rhodes. Caia en JAZZ FUSION
        porque la lista de fusion incluye "rhodes" y se miraba todo el titulo.
        """
        assert criterios.genero_de("Cynthia Rhodes - Finding Out The Hard Way") \
            not in ("JAZZ FUSION", "PIANO")

    def test_rhodes_del_lado_del_tema_si_cuenta(self):
        assert criterios.genero_de("Ken Rhodes - Robyn's Lullaby (Solo Piano)") == "PIANO"


class TestPrioridad:
    def test_un_genero_fuerte_le_gana_a_uno_en_formacion(self):
        """PIANO, DARK y FOLK se estan poblando: son recomendacion, no deben
        robarle temas a lo que Thomas ya trabaja."""
        assert criterios.genero_de("X - Piano Interlude Soul") == "SOUL"

    def test_la_veta_explicita_manda_sobre_todo(self):
        assert criterios.genero_de("X - Rare Soul 45", None, "DARK") == "DARK"

    def test_los_en_formacion_se_reconocen_cuando_no_hay_otro(self):
        assert criterios.genero_de("Luigi Maramotti - Piano Solo") == "PIANO"
        assert criterios.genero_de("X - Acid Folk Dream") == "FOLK"
        assert criterios.genero_de("Y - Melancholic Theme") == "DARK"


class TestSinDato:
    def test_lo_que_no_se_puede_decir_devuelve_None(self):
        assert criterios.genero_de("Alguien - Un Tema Cualquiera") is None

    def test_aguanta_vacio(self):
        assert criterios.genero_de("") is None
        assert criterios.genero_de(None) is None


class TestListas:
    def test_las_listas_coinciden_con_las_de_thomas(self):
        """Si alguien agrega un genero aca y no en la app, la etiqueta sale
        sin color."""
        todas = set(criterios.FUERTES) | set(criterios.EN_FORMACION)
        assert todas == {"SOUL", "R&B SOUL", "80s", "CITY POP", "JAZZ FUSION",
                         "PIANO", "DARK", "FOLK"}

    def test_los_canales_mapeados_apuntan_a_generos_validos(self):
        todas = set(criterios.FUERTES) | set(criterios.EN_FORMACION)
        malos = {c: g for c, g in criterios.CANAL_GEN.items() if g not in todas}
        assert not malos, "canales con genero inexistente: %s" % malos

    def test_parte_tema_separa_bien(self):
        assert criterios.parte_tema("Artista - Tema") == "Tema"
        assert criterios.parte_tema("Artista / Tema") == "Tema"
        assert criterios.parte_tema("Sin separador") == "Sin separador"
