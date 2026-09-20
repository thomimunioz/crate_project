"""
Calibración del BPM contra el oído real: docs/benchmarks/2026-09-19-digging-a-mano/bpm_octave_dataset.json
(247 temas: `raw` = lo que devolvía dsp.py el 19-sep, `final` = octava corregida por juicio musical).

Uso (desde backend/, con el venv):

    python tools/bpm_calibrate.py fetch [--limit N] [--ids ID ...] [--retry-errors]
        Baja cada id con la MISMA receta de producción (dsp.download_audio + cut(smart_start, 45))
        y guarda en tools/cache/ (gitignored) lo que hace falta para re-evaluar sin audio:
          <id>.npy      envolvente de onset (float32, hop 512, sr 22050)
          <id>.mel.npy  mel-espectrograma en dB (float16, 128 bandas) -> envolventes por banda
          <id>.json     meta: start, seconds, duration, sr, hop
        Es RESUMIBLE: salta lo que ya está en cache; los errores quedan en cache/_errors.json.
        Solo los "unavailable" (video borrado/privado) se saltan en la próxima corrida (salvo
        --retry-errors); un 403/corte de red se vuelve a intentar solo. Si el error es del
        sistema (toolchain: falta node/ffmpeg) o YouTube pide bot-check ("blocked"), el loop
        CORTA sin anotar el id: no es un dato del video, y seguir golpeando una IP marcada
        alarga el bloqueo. ~5 s por tema.

    python tools/bpm_calibrate.py eval [--variant v1|v2] [--sub W] [--subsub W] [--sup W]
                                       [--backbeat W] [--detrend 0|1] [--ambiguous R]
                                       [--prior LO HI] [--fails]
        Corre el algoritmo sobre el cache y mide:
          - backend solo: `value` vs `final` (acierto = +-3 BPM o +-3%)
          - con prior en el cliente: si `value` cae fuera de [LO, HI] y hay una alternativa
            en octava (x0.5/x2) adentro, el cliente la elige (lo que hará core/tempo.ts);
            y la variante "prior solo si ambiguous".
        `--variant v1` es el algoritmo del 19-sep congelado (baseline: 59% ese día con audio
        distinto; 51% reproducido sobre este cache).

    python tools/bpm_calibrate.py sweep [--backbeat-sweep]
        Grilla sobre los pesos de evidencia (sub / subsub / sup / detrend [/ backbeat]).
        Imprime una tabla: backend solo / con prior / raw<=115 / % ambiguos / conf.

Medido el 20-sep-2026 con los defaults de `dsp.BpmParams` (247 temas, sin prior en el
backend): 185/247 = 74.9% backend solo; 203/247 = 82.2% si el cliente aplica 58-115 sobre
las alternativas; el `final` está entre las alternativas en 242/247 (98%); `ambiguous`
marca el 48% y cubre el 76% de los errores (lo no marcado acierta ~90%).

Criterio de aceptación (escrito a propósito): que el backend SOLO mejore sobre el baseline
sin bajar en ningún bucket de raw, que la conf media de los errores quede por debajo de la
de los aciertos, y que `ambiguous` cubra la mayoría de los errores de octava que queden.
Lo que queda es el límite de la evidencia: un groove con hi-hat en corcheas a 65 y una
balada sin corcheas a 80 tienen la misma jerarquía de picos; solo el tempo absoluto (un
prior) los distingue, y eso es del cliente.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
import warnings
from collections import Counter, defaultdict
from dataclasses import replace
from typing import Any

warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
REPO = os.path.dirname(BACKEND)
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)

import numpy as np  # noqa: E402

from app import dsp  # noqa: E402
from app.models import BpmResult  # noqa: E402

DATASET = os.path.join(REPO, "docs", "benchmarks", "2026-09-19-digging-a-mano", "bpm_octave_dataset.json")
CACHE = os.path.join(HERE, "cache")
ERRORS = os.path.join(CACHE, "_errors.json")
WINDOW_SECONDS = 45
SR = dsp.SR

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]


# ----------------------------------------------------------------------------- dataset / cache


def load_dataset() -> list[dict[str, Any]]:
    with io.open(DATASET, encoding="utf-8") as fh:
        rows = json.load(fh)
    out = []
    for r in rows:
        if r.get("final") is None or r.get("raw") is None:
            continue
        out.append({"id": r["id"], "playlist": r.get("playlist", "?"), "raw": float(r["raw"]),
                    "final": float(r["final"]), "conf": r.get("conf")})
    return out


def _paths(vid: str) -> tuple[str, str, str]:
    return (os.path.join(CACHE, f"{vid}.npy"), os.path.join(CACHE, f"{vid}.mel.npy"),
            os.path.join(CACHE, f"{vid}.json"))


def cached(vid: str) -> bool:
    return all(os.path.exists(p) for p in _paths(vid))


def load_errors() -> dict[str, dict[str, str]]:
    if not os.path.exists(ERRORS):
        return {}
    with io.open(ERRORS, encoding="utf-8") as fh:
        return json.load(fh)


def save_errors(errors: dict[str, dict[str, str]]) -> None:
    os.makedirs(CACHE, exist_ok=True)
    with io.open(ERRORS, "w", encoding="utf-8") as fh:
        json.dump(errors, fh, indent=1, ensure_ascii=False)


def load_features(vid: str) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    onset_p, mel_p, meta_p = _paths(vid)
    onset = np.load(onset_p).astype(np.float32)
    mel = np.load(mel_p).astype(np.float32)
    with io.open(meta_p, encoding="utf-8") as fh:
        meta = json.load(fh)
    return onset, mel, meta


# ----------------------------------------------------------------------------- fetch


def fetch_one(vid: str) -> dict[str, Any]:
    """Misma receta que /analyze: descarga temporal completa -> recorte de 45 s desde
    smart_start -> features -> borrado. Devuelve la meta guardada."""
    from app import ytdl  # noqa: WPS433 - import tardío: solo el fetch necesita la red

    url = f"https://www.youtube.com/watch?v={vid}"
    with dsp.download_audio(url) as audio:
        start = dsp.smart_start(audio.duration)
        frag = audio.cut(start, WINDOW_SECONDS)
        y, sr = dsp.load_fragment(frag)
        S = dsp._logmel(y, sr)
        onset = dsp._onset_envelope(y, sr)
        meta = {"id": vid, "start": frag.start, "seconds": frag.seconds, "duration": frag.source_duration,
                "sr": sr, "hop": dsp._HOP, "n_mels": S.shape[0], "frames": int(onset.size),
                "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "yt_dlp": ytdl.YTDLP_VERSION}
    os.makedirs(CACHE, exist_ok=True)
    onset_p, mel_p, meta_p = _paths(vid)
    np.save(onset_p, onset.astype(np.float32))
    np.save(mel_p, S.astype(np.float16))
    with io.open(meta_p, "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    return meta


# Errores que NO son del video: se corta el loop y no se anota el id (ver docstring).
_ABORT_KINDS = ("toolchain", "blocked")
# Lo único que se salta en corridas siguientes sin --retry-errors: el video no está.
_SKIP_KINDS = ("unavailable",)


def cmd_fetch(args: argparse.Namespace) -> int:
    from app import ytdl

    rows = load_dataset()
    ids = args.ids or [r["id"] for r in rows]
    errors = load_errors()
    pending = [
        v for v in ids
        if not cached(v) and (args.retry_errors or errors.get(v, {}).get("kind") not in _SKIP_KINDS)
    ]
    if args.limit:
        pending = pending[: args.limit]
    done = sum(1 for v in ids if cached(v))
    skipped = sum(1 for v in ids if not cached(v) and v not in pending)
    print(f"dataset={len(ids)} cache={done} errores={len(errors)} pendientes={len(pending)}"
          + (f" (saltados por 'unavailable': {skipped}; --retry-errors los incluye)" if skipped else ""),
          flush=True)
    t0 = time.perf_counter()
    aborted: str | None = None
    for i, vid in enumerate(pending, 1):
        t = time.perf_counter()
        try:
            meta = fetch_one(vid)
            errors.pop(vid, None)
            print(f"[{i}/{len(pending)}] {vid} ok start={meta['start']:.0f} dur={meta['duration']} "
                  f"{time.perf_counter() - t:.1f}s", flush=True)
        except KeyboardInterrupt:
            raise
        except Exception as exc:  # noqa: BLE001 - se clasifica: del video se anota, del sistema corta
            kind = ytdl.error_kind(exc)
            detail = ytdl.blocked_detail(exc) if kind == "blocked" else ytdl.error_text(exc)
            if kind in _ABORT_KINDS:
                aborted = kind
                print(f"[{i}/{len(pending)}] {vid} ABORTO ({kind}): {detail}", flush=True)
                break
            errors[vid] = {"kind": kind, "detail": detail}
            print(f"[{i}/{len(pending)}] {vid} ERROR {kind}: {detail}", flush=True)
        save_errors(errors)
        if i < len(pending) and args.pause > 0:
            time.sleep(args.pause)
    print(f"listo: cache={sum(1 for v in ids if cached(v))}/{len(ids)} errores={len(errors)} "
          f"en {time.perf_counter() - t0:.0f}s", flush=True)
    if aborted:
        print(f"corrida cortada por '{aborted}': arreglá eso y volvé a correr fetch (retoma solo).", flush=True)
        return 2
    return 0


# ----------------------------------------------------------------------------- algoritmos


def v1_from_onset(onset: np.ndarray, sr: int) -> BpmResult:
    """El algoritmo del 19-sep, congelado (reproduce el 59%): beat_track con prior 120,
    plegado a 60-180, candidatos x0.5/x1/x2 y support = ac[lag+-1]/ac[0]."""
    import librosa

    hop = 512
    bpm_min, bpm_max = 60.0, 180.0

    def fold(b: float) -> float:
        while b < bpm_min:
            b *= 2
        while b > bpm_max:
            b /= 2
        return b

    def support(ac: np.ndarray, bpm: float) -> float:
        lag = int(round(60.0 * sr / (hop * bpm)))
        if lag <= 0 or lag >= ac.size:
            return 0.0
        lo, hi = max(1, lag - 1), min(ac.size, lag + 2)
        return float(ac[lo:hi].max() / (ac[0] + 1e-9))

    ac = librosa.autocorrelate(onset)
    tempo, _ = librosa.beat.beat_track(onset_envelope=onset, sr=sr, hop_length=hop)
    base = fold(float(np.atleast_1d(tempo)[0]))
    cands = sorted({round(fold(base * f), 3) for f in (0.5, 1.0, 2.0)})
    scored = sorted(((b, support(ac, b)) for b in cands), key=lambda p: p[1], reverse=True)
    best, fuerza = scored[0]
    second = scored[1][1] if len(scored) > 1 else 0.0
    margen = (fuerza - second) / (fuerza + 1e-9) if fuerza > 0 else 0.0
    conf = float(np.clip(fuerza, 0, 1)) * (0.55 + 0.45 * float(np.clip(margen, 0, 1)))
    return BpmResult(
        value=round(best, 1), confidence=round(float(np.clip(conf, 0.05, 0.98)), 2),
        alternatives=[dsp.BpmAlternative(value=round(b, 1), support=round(s, 3)) for b, s in scored],
        ambiguous=bool(second >= 0.85 * fuerza), method="onset-ac/1",
    )


def run_variant(variant: str, onset: np.ndarray, mel: np.ndarray, params: dsp.BpmParams) -> BpmResult:
    if variant == "v1":
        return v1_from_onset(onset, SR)
    kick = snare = None
    if params.backbeat_weight > 0:
        kick = dsp.onset_from_logmel(mel, SR, dsp.BAND_KICK)
        snare = dsp.onset_from_logmel(mel, SR, dsp.BAND_SNARE)
    return dsp.bpm_from_onset(onset, SR, kick_onset=kick, snare_onset=snare, params=params)


# ----------------------------------------------------------------------------- métricas


def hit(pred: float, final: float) -> bool:
    return abs(pred - final) <= max(3.0, 0.03 * final)


def relation(pred: float, final: float) -> str:
    if hit(pred, final):
        return "ok"
    if hit(pred / 2.0, final):
        return "double"
    if hit(pred * 2.0, final):
        return "half"
    if hit(pred / 4.0, final) or hit(pred * 4.0, final):
        return "x4"
    return "other"


def client_pick(res: BpmResult, lo: float, hi: float) -> tuple[float, str]:
    """Lo que haría core/tempo.ts::foldBpm con un prior [lo, hi]: si `value` ya está adentro,
    queda. Si no, entre las alternativas en relación de octava con `value` que caen adentro,
    la de más support; si no hay ninguna, plegado aritmético (x0.5/x2 hasta entrar)."""
    v = res.value
    if v <= 0:
        # Centinela "sin pulso" de dsp.bpm_from_onset: no hay nada que plegar (y el
        # plegado aritmético con 0 no terminaría nunca).
        return v, "none"
    if lo <= v <= hi:
        return v, "keep"
    octaves = [a for a in res.alternatives
               if lo <= a.value <= hi and any(abs(a.value / v - r) < 0.06 * r for r in (0.5, 2.0, 0.25, 4.0))]
    if octaves:
        best = max(octaves, key=lambda a: a.support)
        return best.value, "alt"
    f = v
    while f > hi:
        f /= 2.0
    while f < lo:
        f *= 2.0
    return f, "fold"


def raw_bucket(raw: float) -> str:
    if raw <= 115:
        return "raw<=115"
    if raw <= 125:
        return "116-125"
    return "raw>125"


def evaluate(rows: list[dict[str, Any]], variant: str, params: dsp.BpmParams, prior: tuple[float, float]) -> dict[str, Any]:
    results = []
    for r in rows:
        if not cached(r["id"]):
            continue
        onset, mel, _meta = load_features(r["id"])
        res = run_variant(variant, onset, mel, params)
        picked, how = client_pick(res, *prior)
        # Variante: el cliente aplica el prior SOLO si el backend marcó ambiguous.
        picked_amb = picked if res.ambiguous else res.value
        results.append({**r, "res": res, "pred": res.value, "rel": relation(res.value, r["final"]),
                        "picked": picked, "how": how, "rel_client": relation(picked, r["final"]),
                        "rel_client_amb": relation(picked_amb, r["final"])})
    n = len(results)
    ok_b = sum(1 for x in results if x["rel"] == "ok")
    ok_c = sum(1 for x in results if x["rel_client"] == "ok")
    ok_ca = sum(1 for x in results if x["rel_client_amb"] == "ok")
    return {"n": n, "results": results, "ok_backend": ok_b, "ok_client": ok_c, "ok_client_amb": ok_ca}


def print_report(ev: dict[str, Any], prior: tuple[float, float], show_fails: bool) -> None:
    n, res = ev["n"], ev["results"]
    if n == 0:
        print("sin cache: corré `fetch` primero")
        return
    print(f"n={n}")
    print(f"backend solo:        {ev['ok_backend']}/{n} = {100 * ev['ok_backend'] / n:.1f}%")
    print(f"con prior {prior[0]:.0f}-{prior[1]:.0f} en cliente: {ev['ok_client']}/{n} = {100 * ev['ok_client'] / n:.1f}%")
    print(f"  (prior solo si ambiguous): {ev['ok_client_amb']}/{n} = {100 * ev['ok_client_amb'] / n:.1f}%")
    print("errores backend:", dict(Counter(x["rel"] for x in res if x["rel"] != "ok")))
    print("errores cliente:", dict(Counter(x["rel_client"] for x in res if x["rel_client"] != "ok")),
          "| cómo eligió:", dict(Counter(x["how"] for x in res)))

    by_pl: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for x in res:
        b = by_pl[x["playlist"]]
        b[0] += 1
        b[1] += x["rel"] == "ok"
        b[2] += x["rel_client"] == "ok"
    print("por playlist (backend / cliente):")
    for pl, (tot, okb, okc) in sorted(by_pl.items()):
        print(f"  {pl:8s} {okb:3d}/{tot:<3d} {100 * okb / tot:5.1f}%   {okc:3d}/{tot:<3d} {100 * okc / tot:5.1f}%")

    by_bk: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for x in res:
        b = by_bk[raw_bucket(x["raw"])]
        b[0] += 1
        b[1] += x["rel"] == "ok"
        b[2] += x["rel_client"] == "ok"
    print("por bucket del raw del 19-sep (backend / cliente):")
    for bk in ("raw<=115", "116-125", "raw>125"):
        if bk in by_bk:
            tot, okb, okc = by_bk[bk]
            print(f"  {bk:8s} {okb:3d}/{tot:<3d} {100 * okb / tot:5.1f}%   {okc:3d}/{tot:<3d} {100 * okc / tot:5.1f}%")

    hits = [x["res"].confidence for x in res if x["rel"] == "ok"]
    miss = [x["res"].confidence for x in res if x["rel"] != "ok"]
    print(f"conf media aciertos={np.mean(hits) if hits else float('nan'):.2f} "
          f"errores={np.mean(miss) if miss else float('nan'):.2f}")
    amb_all = sum(1 for x in res if x["res"].ambiguous)
    amb_miss = sum(1 for x in res if x["res"].ambiguous and x["rel"] != "ok")
    n_miss = len(miss)
    print(f"ambiguous: {amb_all}/{n} = {100 * amb_all / n:.0f}% del total; "
          f"cubre {amb_miss}/{n_miss} errores del backend" + (f" ({100 * amb_miss / n_miss:.0f}%)" if n_miss else ""))
    # ¿El `final` está entre las alternativas? (techo de lo que un cliente puede recuperar)
    in_alts = sum(1 for x in res if any(hit(a.value, x["final"]) for a in x["res"].alternatives))
    print(f"final entre las alternativas: {in_alts}/{n} = {100 * in_alts / n:.0f}%")

    if show_fails:
        print("\nfallados por el backend (id playlist raw final -> pred [conf] alts):")
        for x in sorted(res, key=lambda x: (x["rel"], x["playlist"])):
            if x["rel"] == "ok":
                continue
            alts = " ".join(f"{a.value:.1f}:{a.support:.2f}" for a in x["res"].alternatives[:5])
            print(f"  {x['id']} {x['playlist']:7s} raw={x['raw']:6.1f} final={x['final']:5.1f} -> "
                  f"{x['pred']:6.1f} [{x['res'].confidence:.2f}{' amb' if x['res'].ambiguous else '    '}] "
                  f"{x['rel']:6s} | {alts}")


def params_from_args(args: argparse.Namespace) -> dsp.BpmParams:
    p = dsp.DEFAULT_PARAMS
    for arg, field_name in (("sub", "sub_weight"), ("subsub", "subsub_weight"), ("sup", "sup_weight"),
                            ("backbeat", "backbeat_weight"),
                            ("ambiguous", "ambiguous_ratio"), ("detrend", "detrend")):
        value = getattr(args, arg, None)
        if value is not None:
            p = replace(p, **{field_name: value})
    return p


def cmd_eval(args: argparse.Namespace) -> int:
    rows = load_dataset()
    params = params_from_args(args)
    prior = (args.prior[0], args.prior[1])
    print(f"variant={args.variant} params={params}")
    ev = evaluate(rows, args.variant, params, prior)
    print_report(ev, prior, args.fails)
    return 0


def _summary(ev: dict[str, Any]) -> str:
    res, n = ev["results"], ev["n"]
    amb = sum(1 for x in res if x["res"].ambiguous)
    miss = [x for x in res if x["rel"] != "ok"]
    amb_miss = sum(1 for x in miss if x["res"].ambiguous)
    c_ok = np.mean([x["res"].confidence for x in res if x["rel"] == "ok"]) if n else 0.0
    c_err = np.mean([x["res"].confidence for x in miss]) if miss else float("nan")
    low = sum(1 for x in res if x["raw"] <= 115 and x["rel"] == "ok")
    low_n = sum(1 for x in res if x["raw"] <= 115)
    return (f"{100 * ev['ok_backend'] / n:6.1f}% {100 * ev['ok_client'] / n:7.1f}% | raw<=115 {low:3d}/{low_n:<3d} | "
            f"amb {100 * amb / n:3.0f}% {amb_miss:3d}/{len(miss):<3d} | conf {c_ok:.2f} {c_err:.2f}")


def cmd_sweep(args: argparse.Namespace) -> int:
    rows = load_dataset()
    prior = (args.prior[0], args.prior[1])
    print(f"{'detrend':>7s} {'sub':>5s} {'subsub':>6s} {'sup':>5s} {'bb':>5s} | {'backend':>7s} {'cliente':>7s} | raw<=115 | amb% amb/err | conf ok/err")
    grid: list[dsp.BpmParams] = []
    for dt in (False, True):
        for sub in (0.5, 1.0):
            for subsub in (0.0, 0.25):
                for sup in (0.0, 0.25):
                    for bb in ((0.0, 1.0) if args.backbeat_sweep else (0.0,)):
                        grid.append(replace(dsp.DEFAULT_PARAMS, detrend=dt, sub_weight=sub, subsub_weight=subsub,
                                            sup_weight=sup, backbeat_weight=bb))
    for p in grid:
        ev = evaluate(rows, "v2", p, prior)
        print(f"{str(p.detrend):>7s} {p.sub_weight:5.2f} {p.subsub_weight:6.2f} {p.sup_weight:5.2f} {p.backbeat_weight:5.2f} | "
              + _summary(ev), flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="baja y cachea features (resumible)")
    f.add_argument("--limit", type=int, default=0, help="máximo de ids nuevos en esta corrida (0 = todos)")
    f.add_argument("--ids", nargs="*", help="solo estos ids")
    f.add_argument("--retry-errors", action="store_true", help="reintentar los que fallaron antes")
    f.add_argument("--pause", type=float, default=0.5, help="segundos entre descargas (no gatillar 403)")
    f.set_defaults(fn=cmd_fetch)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--prior", type=float, nargs=2, default=(58.0, 115.0), metavar=("LO", "HI"),
                       help="rango que aplicaría el CLIENTE sobre alternatives (no el backend)")

    e = sub.add_parser("eval", help="evalúa sobre el cache")
    e.add_argument("--variant", choices=("v1", "v2"), default="v2")
    e.add_argument("--sub", type=float, default=None, help="peso de S(l/2)")
    e.add_argument("--subsub", type=float, default=None, help="peso (negativo) de S(l/4)")
    e.add_argument("--sup", type=float, default=None, help="peso de S(2l)")
    e.add_argument("--backbeat", type=float, default=None, help="peso del voto de backbeat por paridad")
    e.add_argument("--ambiguous", type=float, default=None, help="umbral de ambigüedad (ratio 2do/1ro)")
    e.add_argument("--detrend", type=lambda s: s.lower() in ("1", "true", "si", "yes"), default=None)
    e.add_argument("--fails", action="store_true", help="listar los fallados")
    common(e)
    e.set_defaults(fn=cmd_eval)

    s = sub.add_parser("sweep", help="grilla de pesos")
    s.add_argument("--backbeat-sweep", action="store_true", help="incluir backbeat 0/1 en la grilla (más lento)")
    common(s)
    s.set_defaults(fn=cmd_sweep)

    args = ap.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
