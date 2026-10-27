# -*- coding: utf-8 -*-
"""Funciones puras del servidor. No levanta el servidor ni toca crate.db.

El test de `servible` es de regresion de SEGURIDAD: el 27-oct el servidor
servia la carpeta entera del proyecto, asi que http://127.0.0.1:7777/.env
entregaba las once claves a cualquier cosa corriendo en la maquina. Si alguien
vuelve a aflojar esa lista blanca, esto tiene que ponerse rojo.
"""
import crate_server as srv


class TestListaBlanca:
    def test_no_sirve_los_secretos(self):
        for ruta in ("/.env", "/.env.local", "/.git/config", "/crate.db",
                     "/app/slskd_key.txt", "/app/crate_server.py",
                     "/.gitignore", "/backend/.env"):
            assert not srv.servible(ruta), "NO deberia servir %s" % ruta

    def test_sirve_lo_que_la_app_necesita(self):
        for ruta in ("/mi-crate.html", "/estilo.css", "/app.js",
                     "/tapa.jpg", "/icono.png", "/fuente.woff2"):
            assert srv.servible(ruta), "deberia servir %s" % ruta

    def test_la_extension_se_mira_sin_importar_mayusculas(self):
        assert srv.servible("/MI-CRATE.HTML")

    def test_un_punto_adelante_alcanza_para_bloquear(self):
        assert not srv.servible("/carpeta/.env")

    def test_la_lista_blanca_no_tiene_extensiones_peligrosas(self):
        """Las dos capas (dotfile + extension) se tapan los agujeros entre si,
        asi que una se puede aflojar sin que se note. Esto mira la lista en si.
        """
        prohibidas = {".env", ".db", ".py", ".yml", ".yaml", ".json", ".txt",
                      ".sqlite", ".sqlite3", ".key", ".pem", ".bak", ".log"}
        malas = prohibidas & set(srv.SERVIBLE)
        assert not malas, "estas extensiones no pueden servirse: %s" % sorted(malas)


class TestPartir:
    def test_separa_artista_y_tema(self):
        assert srv.partir("Roy Ayers - Everybody Loves The Sunshine") == \
               ("Roy Ayers", "Everybody Loves The Sunshine")

    def test_limpia_el_ruido_tipico_de_youtube(self):
        art, nom = srv.partir(
            "T. Yamashita - Sparkle (1982) [Vinyl Rip] HQ (Official Audio)")
        assert art == "T. Yamashita"
        assert "1982" not in (nom or "")
        assert "Vinyl" not in (nom or "")

    def test_sin_separador_no_inventa_artista(self):
        art, nom = srv.partir("Un titulo cualquiera sin guion")
        assert art is None
        assert nom

    def test_aguanta_vacio(self):
        assert srv.partir("") == (None, None)


class TestOrdenarArchivos:
    def respuesta(self, *archivos):
        return {"responses": [{"username": "u", "hasFreeUploadSlot": True,
                               "files": list(archivos)}]}

    def test_el_flac_va_antes_que_el_mp3(self):
        d = self.respuesta(
            {"filename": "a\\x.mp3", "size": 5_000_000, "bitRate": 320},
            {"filename": "a\\x.flac", "size": 30_000_000})
        out = srv.ordenar_archivos(d)
        assert out[0]["ext"] == "flac"

    def test_descarta_lo_que_no_es_audio(self):
        d = self.respuesta({"filename": "a\\tapa.jpg", "size": 100},
                           {"filename": "a\\x.flac", "size": 30_000_000})
        assert [f["ext"] for f in srv.ordenar_archivos(d)] == ["flac"]

    def test_trae_los_bytes_exactos_para_poder_pedirla(self):
        """slskd necesita el tamaño exacto; los MB redondeados no sirven."""
        d = self.respuesta({"filename": "a\\x.flac", "size": 31_457_280})
        assert srv.ordenar_archivos(d)[0]["bytes"] == 31_457_280

    def test_sin_resultados_no_explota(self):
        assert srv.ordenar_archivos({}) == []


class TestBajadasPlanas:
    def test_aplana_usuario_directorio_archivo(self):
        d = [{"username": "pepe", "directories": [{"files": [
            {"filename": "m\\sub\\tema.flac", "size": 2_097_152,
             "bytesTransferred": 1_048_576, "state": "InProgress"}]}]}]
        out = srv.bajadas_planas(d)
        assert out == [{"usuario": "pepe", "nombre": "tema.flac",
                        "estado": "InProgress", "pct": 50.0, "mb": 2.0}]

    def test_un_archivo_de_tamano_cero_no_divide_por_cero(self):
        d = [{"username": "p", "directories": [{"files": [
            {"filename": "x.mp3", "size": 0, "state": "Queued"}]}]}]
        assert srv.bajadas_planas(d)[0]["pct"] == 0.0

    def test_cola_vacia(self):
        assert srv.bajadas_planas([]) == []
        assert srv.bajadas_planas(None) == []
