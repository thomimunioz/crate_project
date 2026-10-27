# -*- coding: utf-8 -*-
"""Los filtros medidos contra el oido de Thomas.

Cada caso de aca salio de un rechazo real anotado en alguna tanda, no de lo
que a alguien le parece. Si uno de estos empieza a fallar, el buscador volvio
a dejar pasar algo que el ya habia dicho que no.
"""
import criterios


class TestDescartar:
    """descartar() devuelve el motivo (string) o None si el tema pasa."""

    def test_pasa_lo_que_tiene_que_pasar(self):
        assert criterios.descartar(
            "Luigi Maramotti - Piano Solo (1974)", 320, 4200, "Krem Soulz") is None

    def test_karaoke_y_tutoriales_son_basura_universal(self):
        for t in ("Como tocar esto - TUTORIAL piano",
                  "Someone - My Song (Karaoke Version)",
                  "Free Type Beat - boom bap 90s"):
            assert criterios.descartar(t, 300, 5000, "X"), "deberia descartar: %s" % t

    def test_los_muy_cortos_no_sirven_para_samplear(self):
        # medido: lo de menos de 2:45 casi nunca se guarda
        assert criterios.descartar("Alguien - Tema", 90, 5000, "X")

    def test_lo_mainstream_no_se_guarda_aunque_encaje(self):
        # Whitney, Isleys, Patti Austin: encajaban y no los guardo nunca
        motivo = criterios.descartar("Whitney Houston - Greatest Love", 300,
                                     40_000_000, "X")
        assert motivo

    def test_pocas_visitas_no_es_merito(self):
        """Dentro de una veta curada lo de menos de 1k views se guardo al 2%:
        era OST, karaoke y mal titulado. No premiar la obscuridad del upload."""
        assert criterios.descartar("Alguien - Tema", 300, 12, "X")


class TestPuntuar:
    def test_devuelve_puntaje_y_razones_legibles(self):
        pts, razones = criterios.puntuar(
            "Someone - Theme (Instrumental)", 380, 3000, "Krem Soulz", 1976)
        assert isinstance(pts, float)
        assert isinstance(razones, list)
        assert all(isinstance(r, str) and r for r in razones)

    def test_lo_instrumental_puntua_mas_que_lo_cantado(self):
        """La ley de oro: necesita huecos sin voz para loopear."""
        con, _ = criterios.puntuar("A - Tema (Instrumental)", 380, 3000, None, 1976)
        sin, _ = criterios.puntuar("A - Tema", 380, 3000, None, 1976)
        assert con > sin

    def test_un_canal_que_rinde_puntua_mas(self):
        """Medido: de un canal del que ya guardo, guarda 16-22% contra 3%."""
        bueno, _ = criterios.puntuar("A - Tema", 380, 3000, "Krem Soulz", 1976)
        otro, _ = criterios.puntuar("A - Tema", 380, 3000, "Canal Cualquiera", 1976)
        assert bueno > otro


class TestExpandir:
    def test_una_palabra_se_convierte_en_varias_busquedas(self):
        qs = criterios.expandir("soul")
        assert len(qs) > 1
        assert all(isinstance(q, str) and q for q in qs)

    def test_lo_que_no_conoce_no_lo_rompe(self):
        assert criterios.expandir("asdfghjkl")


class TestQuitarTildes:
    def test_normaliza_para_comparar(self):
        assert criterios.quitar_tildes("Antônio Carlos") == \
               criterios.quitar_tildes("Antonio Carlos")

    def test_aguanta_vacio(self):
        assert criterios.quitar_tildes("") == ""
