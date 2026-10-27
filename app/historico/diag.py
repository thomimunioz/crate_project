# -*- coding: utf-8 -*-
import sys, os, warnings, subprocess, uuid
warnings.filterwarnings("ignore")
os.chdir(r"G:\Thomi - Mi Carpeta\crate_project\backend")
import numpy as np, librosa
SR, HOP = 22050, 512
for mp3 in sys.argv[1:]:
    tmp = os.path.join(os.environ.get("TEMP","."), uuid.uuid4().hex+".wav")
    subprocess.run(["ffmpeg","-v","quiet","-y","-t","45","-i",mp3,"-ac","1","-ar",str(SR),tmp],check=True)
    y,sr = librosa.load(tmp, sr=SR, mono=True)
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=HOP))
    arm,_ = librosa.decompose.hpss(S)
    f = librosa.fft_frequencies(sr=sr, n_fft=2048)
    banda = (f>=200)&(f<=3500)
    ratio = arm[banda].sum(axis=0)/(arm.sum(axis=0)+1e-9)
    f0,vflag,vprob = librosa.pyin(y,fmin=80,fmax=1000,sr=sr,hop_length=HOP,frame_length=2048,fill_na=np.nan)
    n=min(len(ratio),len(f0)); ratio,f0,vprob=ratio[:n],f0[:n],vprob[:n]
    cents=np.full(n,np.nan); ok=~np.isnan(f0); cents[ok]=1200*np.log2(f0[ok]/55.0)
    vib=np.zeros(n)
    for i in range(n):
        a,b=max(0,i-9),min(n,i+9); seg=cents[a:b][~np.isnan(cents[a:b])]
        if len(seg)>=5: vib[i]=float(np.std(seg))
    p=lambda v: "/".join("%.2f"%np.percentile(v,q) for q in (25,50,75,90))
    print("%-34s ratio %s | vprob %s | vib %s | pyin-voiced %.0f%%" % (
        os.path.basename(mp3)[:34], p(ratio), p(vprob), p(vib), 100*np.mean(vflag[:n])))
    os.remove(tmp)
