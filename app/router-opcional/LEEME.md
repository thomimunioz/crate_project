# claude-code-router — por qué quedó sin instalar

Pediste instalarlo y configurarlo para delegar tareas simples a modelos baratos.
**No lo instalé**, y acá está el porqué, con lo que verifiqué en tu máquina.

## Qué hace realmente

Levanta un proxy local y apunta `ANTHROPIC_BASE_URL` ahí. Claude Code deja de
hablar con Anthropic y le habla al proxy, que reenvía a **otros proveedores**
(DeepSeek, OpenRouter, Gemini, Qwen, Ollama…) según reglas por tipo de tarea.

## Los tres problemas

**1. No hay a dónde rutear sin pagar.** Verificado el 27-oct en tu PC:

| Requisito | Estado |
|---|---|
| Ollama (modelos locales, gratis) | no instalado |
| Keys de DeepSeek / OpenRouter / Gemini / Groq / etc. en `.env` | ninguna |
| Node | v22.16.0 ✓ (lo único que sí está) |

Cada proveedor que soporta es de pago por token. Conseguir una key es
exactamente el *"costo adicional sin autorización"* que me pediste evitar.

**2. No afecta la sesión en la que trabajo.** El router solo aplica a sesiones
nuevas lanzadas con `ccr code`. Una sesión ya abierta no cambia de modelo a
mitad de camino, así que no me habría hecho "delegar automáticamente" nada de
lo de anoche.

**3. Riesgo sobre tu configuración.** Reescribe variables de entorno de Claude
Code. Me pediste explícitamente no romper tu config, y hacerlo sin que pudieras
responder preguntas era la peor combinación.

## Lo que sí te ahorra plata, hoy y gratis

- **Subagentes en modelo barato.** Claude Code ya permite mandar el trabajo
  mecánico (buscar en archivos, listar, resumir) a Haiku, y dejar el caro para
  lo que piensa. No necesita router ni keys.
- **`/model`** para bajar el modelo de la sesión cuando la tarea es simple.
- Lo más caro de este proyecto no es el modelo: son las corridas de yt-dlp y el
  DSP. Esas ya corren gratis en tu máquina.

## Si igual lo querés probar

1. Conseguí una key (DeepSeek es el más barato de los que soporta).
2. `npm install -g @musistudio/claude-code-router`
3. Copiá `config.json` (al lado de este archivo) a `~/.claude-code-router/config.json`
   y poné tu key donde dice `PONE_TU_KEY_ACA`.
4. `ccr code` en vez de `claude`.

La config ya viene con el ruteo armado (barato por defecto, caro para
razonamiento y contexto largo) y con fallback entre proveedores si una cuota se
agota. Decime y lo terminamos de probar juntos.
