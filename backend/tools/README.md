# backend/tools — herramientas de calibración

Scripts que se corren a mano desde `backend/` con el venv. No son parte del server.

## `bpm_calibrate.py` — el BPM medido contra el oído real

Mide `app/dsp.py::bpm_from_onset` contra
`docs/benchmarks/2026-09-19-digging-a-mano/bpm_octave_dataset.json` (247 temas: `raw` = lo que
devolvía el DSP el 19-sep, `final` = octava corregida a oído). Sin esto, cualquier cambio en la
elección de octava se evalúa "a ojo".

```bash
# 1) una vez: bajar los 247 con la misma receta que /analyze y cachear features (~11 min)
python tools/bpm_calibrate.py fetch            # resumible: salta lo que ya está; --limit N por tandas

# 2) las veces que haga falta: evaluar sobre el cache (segundos, sin red)
python tools/bpm_calibrate.py eval             # defaults de dsp.BpmParams
python tools/bpm_calibrate.py eval --fails     # + lista de fallados con sus alternativas
python tools/bpm_calibrate.py eval --variant v1   # el algoritmo del 19-sep, congelado (baseline)
python tools/bpm_calibrate.py eval --sub 0.5 --subsub 0 --backbeat 0 --prior 58 135
python tools/bpm_calibrate.py sweep [--backbeat-sweep]   # grilla de pesos de evidencia
```

### Qué guarda el cache (`tools/cache/`, gitignored)

Features derivadas, **no audio**: `<id>.npy` (envolvente de onset, hop 512), `<id>.mel.npy`
(mel en dB, float16, para envolventes por banda: bombo/caja) y `<id>.json` (ventana real,
duración). ~450 KB por tema (110 MB los 247, casi todo el mel). Los errores de descarga quedan en
`cache/_errors.json` con su `kind`: solo los `unavailable` (video borrado/privado) se saltan en la
próxima corrida (salvo `--retry-errors`); un 403 o corte de red se vuelve a intentar solo. Si falla
el sistema (`toolchain`: falta node/ffmpeg) o YouTube pide bot-check (`blocked`), `fetch` **corta**
sin anotar el id y sale con código 2: no es un dato del video, y seguir golpeando una IP marcada
alarga el bloqueo. Se regenera con `fetch`.

### Qué reporta `eval`

- **backend solo**: `value` vs `final` (acierto = ±3 BPM o ±3%). Es la métrica del backend:
  elige por evidencia, **sin prior de gusto**.
- **con prior en cliente**: lo que sacaría `core/tempo.ts` aplicando `[LO, HI]` sobre
  `alternatives` (si `value` cae afuera y hay una alternativa en octava adentro, la elige).
  Y la variante "prior solo si `ambiguous`".
- errores por tipo (double / half / other), por playlist, por bucket del `raw` del 19-sep,
  conf media de aciertos vs errores, cuánto cubre `ambiguous`, y si el `final` está entre las
  alternativas (techo de lo que el cliente puede recuperar).

### Medido el 20-sep-2026 (defaults actuales)

| | backend solo | prior 58–115 en cliente | prior 58–135 |
|---|---|---|---|
| v1 (19-sep, reproducido sobre este cache) | 126/247 = 51% | 190/247 = 77% | |
| v2 (jerarquía métrica + backbeat) | **185/247 = 74.9%** | **203/247 = 82.2%** | 209/247 = 84.6% |

Por playlist (backend / cliente 58–115): soul 85% / 89%, rnb 83% / 89%, citypop 86% / 90%,
fusion 47% / 61%. `final` entre las alternativas: 98%. `ambiguous` marca el 48% y ahí caen el
76% de los errores; lo que no se marca acierta ~90%. Conf media: 0.78 en aciertos vs 0.66 en
errores (la confianza está calibrada como probabilidad de acierto).

### Lo que no se puede arreglar con evidencia (y por qué el prior va en el cliente)

Un groove con hi-hat en corcheas a 65 BPM (fuerte en 32/65/130, débil en 260) y una balada
sin corcheas a 80 BPM (fuerte en 40/80, débil en 160) tienen **la misma jerarquía de picos**.
Solo el tempo absoluto los distingue, y eso es un prior — del usuario, no del backend. Por
eso el contrato devuelve `alternatives` + `ambiguous` y el cliente decide con su rango
(`core/tempo.ts`, aprendible de `affinity.bpmBuckets`), con provenance `inferred`.

Fusion es el punto flaco: swing y feel de tresillo rompen la jerarquía binaria (errores 3:2)
y sus tempos reales > 115 no se recuperan con un prior de 58–115 (con 58–135 sube a 68%).

### Cuándo re-calibrar

Cada vez que cambie la decisión de tempo en `dsp.py`: correr `eval` antes y después, y subir
`BPM_METHOD`. Si cambian los pesos, re-ajustar la calibración logística de la confianza
(`_CONF_LOGIT_A/B`: el script de ajuste es trivial, ver el historial del harness). Cuando la
UI permita corregir la octava a mano (÷2 / ×2 con `userSet`), ese dato reemplaza al `final`
de este dataset, que lo corrigieron agentes y no Thomas.
