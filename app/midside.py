# -*- coding: utf-8 -*-
"""Detecta voz por MID/SIDE: en casi toda mezcla la voz va al centro, y los
instrumentos abiertos a los lados. mid-side deja el acompanamiento y mata la voz,
asi que donde mid >> side en banda vocal, hay alguien cantando.
No necesita pyin ni heuristicas de vibrato."""
import sys, os, warnings, subprocess, uuid
warnings.filterwarnings("ignore")
os.chdir(r"G:\Thomi - Mi Carpeta\crate_project\backend")
import numpy as np, librosa
SR, HOP, N = 22050, 512, 2048

def analiza(path, segs=150):
    tmp = os.path.join(os.environ.get("TEMP","."), uuid.uuid4().hex+".wav")
    try:
        subprocess.run(["ffmpeg","-v","quiet","-y","-t",str(segs),"-i",path,
                        "-ac","2","-ar",str(SR),tmp],check=True,timeout=140)
        y,sr = librosa.load(tmp, sr=SR, mono=False)
        if y.ndim == 1:
            return None                       # mono de verdad: no sirve mid/side
        L,R = y[0],y[1]
        if np.corrcoef(L,R)[0,1] > 0.999:
            return None                       # estereo falso
        mid,side = (L+R)/2,(L-R)/2
        f = librosa.fft_frequencies(sr=sr,n_fft=N)
        b = (f>=250)&(f<=4000)
        M = np.abs(librosa.stft(mid,n_fft=N,hop_length=HOP))[b].sum(axis=0)
        S = np.abs(librosa.stft(side,n_fft=N,hop_length=HOP))[b].sum(axis=0)
        n = min(len(M),len(S))
        M,S = M[:n],S[:n]
        dom = M/(M+S+1e-9)                    # 0.5 = nada al centro, 1 = todo centro
        rms = librosa.feature.rms(y=mid,hop_length=HOP)[0][:n]
        fuerte = rms > np.percentile(rms,25)
        voz = (dom > np.percentile(dom,55)) & fuerte
        k=15; voz = np.convolve(voz.astype(float),np.ones(k)/k,mode="same")>0.5
        seg,ini=[],None
        for i,v in enumerate(voz):
            if not v and ini is None: ini=i
            elif v and ini is not None: seg.append((ini,i)); ini=None
        if ini is not None: seg.append((ini,len(voz)))
        t=HOP/sr; hs=[(a*t,(b2-a)*t) for a,b2 in seg]
        may = max(hs,key=lambda h:h[1]) if hs else (0,0)
        return {"sin_voz_pct":round(100*float((~voz).mean()),1),
                "hueco_s":round(may[1],1),"en":round(may[0],1),
                "intro_s":round(hs[0][1],1) if hs and hs[0][0]<1 else 0.0,
                "dom_mediana":round(float(np.median(dom)),3)}
    finally:
        if os.path.exists(tmp):
            try: os.remove(tmp)
            except OSError: pass

for p in sys.argv[1:]:
    r = analiza(p)
    nm = os.path.basename(p)[:42]
    print("%-44s %s" % (nm, "MONO, no aplica" if r is None else
        "sin voz %4.1f%% | hueco %5.1fs en %5.1fs | intro %4.1fs | centro %.3f"
        % (r["sin_voz_pct"],r["hueco_s"],r["en"],r["intro_s"],r["dom_mediana"])))
