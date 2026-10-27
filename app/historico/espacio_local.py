# -*- coding: utf-8 -*-
"""Verifica que el detector de espacio funcione, sobre MP3 locales.
No valida el gusto de Thomas (eso necesita su feedback); valida el CODIGO."""
import sys, os, warnings, subprocess, uuid
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(r"G:\Thomi - Mi Carpeta\crate_project\backend")
import numpy as np, librosa
from espacio import voz_por_frame, huecos, SR, HOP, VENTANA

for mp3 in sys.argv[1:]:
    tmp = os.path.join(os.environ.get("TEMP", "."), uuid.uuid4().hex + ".wav")
    try:
        subprocess.run(["ffmpeg", "-v", "quiet", "-y", "-t", str(VENTANA), "-i", mp3,
                        "-ac", "1", "-ar", str(SR), tmp], check=True, timeout=140)
        y, sr = librosa.load(tmp, sr=SR, mono=True)
        voz, n = voz_por_frame(y, sr)
        hs = huecos(voz, sr)
        may = max(hs, key=lambda h: h[1]) if hs else (0, 0)
        intro = hs[0][1] if hs and hs[0][0] < 1.0 else 0.0
        print("%-46s sin voz %4.1f%% | hueco mayor %4.1fs en %4.1fs | intro %4.1fs | huecos>=8s: %d"
              % (os.path.basename(mp3)[:46], 100 * float((~voz).mean()),
                 may[1], may[0], intro, sum(1 for _, d in hs if d >= 8)))
    except Exception as e:
        print("%-46s ERROR %s" % (os.path.basename(mp3)[:46], str(e)[:50]))
    finally:
        if os.path.exists(tmp):
            try: os.remove(tmp)
            except OSError: pass
