# -*- coding: utf-8 -*-
"""Las senales de veta y el filtro de prensado.

Casi todos estos casos son falsos positivos reales que aparecieron cavando el
27-oct. Sirven como memoria: cada uno costo una corrida y una revision a mano.
"""
import cavar
import veta


class TestParteTema:
    def test_saca_el_artista(self):
        assert veta.parte_tema("Ken Rhodes - Robyn's Lullaby") == "Robyn's Lullaby"

    def test_aguanta_otros_separadores(self):
        assert veta.parte_tema("Craig Kupka / Electric Piano") == "Electric Piano"
        assert veta.parte_tema("Hozan Yamamoto – Sawanose") == "Sawanose"

    def test_sin_separador_devuelve_todo(self):
        assert veta.parte_tema("SKIP MAHOONEY I NEED YOUR LOVE") == \
               "SKIP MAHOONEY I NEED YOUR LOVE"


class TestSenalPiano:
    def test_rhodes_como_apellido_no_cuenta(self):
        """Cynthia Rhodes canta, no toca un Fender Rhodes. Las pistas de
        instrumento solo valen del lado del TEMA."""
        s, _ = veta.senal("Cynthia Rhodes - Finding Out The Hard Way",
                          None, None, None, "PIANO")
        assert s < 1.0

    def test_rhodes_en_el_tema_si_cuenta(self):
        s, _ = veta.senal("Ken Rhodes - Robyn's Lullaby (Solo Piano) (1974)",
                          None, None, None, "PIANO")
        assert s >= 1.0

    def test_los_canales_de_covers_quedan_afuera(self):
        for t in ("MAXIMO SPODEK, SHE'S MY GIRL, PIANO LOVE SONGS",
                  "Relaxing piano - study music"):
            s, _ = veta.senal(t, None, None, None, "PIANO")
            assert s == 0.0, t


class TestSenalDark:
    def test_la_tonalidad_menor_sola_no_alcanza(self):
        """Media discografia soul esta en menor y no tiene nada de oscura."""
        s, _ = veta.senal("Jerry Warren - I Really Love You",
                          None, True, 118, "DARK")
        assert s < 1.0

    def test_menor_y_lento_si_alcanza(self):
        s, _ = veta.senal("Jerry Warren - I Really Love You",
                          None, True, 82, "DARK")
        assert s >= 1.0

    def test_el_titulo_que_lo_dice_alcanza_solo(self):
        s, _ = veta.senal("X - Melancholic Theme", None, None, None, "DARK")
        assert s >= 1.0


class TestEsDisco:
    """cavar.py busca en YouTube, donde hay mas gente tocando que discos."""

    def test_un_cover_no_es_un_disco(self):
        for t in ("Hey Jude | Wurlitzer Electric Piano | Instrumental Cover",
                  "Rhodes Chord", "Piano lesson for beginners",
                  "Away in a Manger played on 1975 Rhodes"):
            assert not cavar.es_disco({"titulo": t, "canal": "X"}), t

    def test_un_año_o_un_formato_alcanzan(self):
        assert cavar.es_disco({"titulo": "Alguien - Tema (1974)", "canal": "X"})
        assert cavar.es_disco({"titulo": "Alguien - Tema (private press LP)",
                               "canal": "X"})

    def test_sin_ninguna_senal_no_pasa(self):
        assert not cavar.es_disco({"titulo": "Alguien - Tema", "canal": "X"})
