# AGENTS.md · MicroAgencia

> Este fichero lo leen los agentes de programación antes de tocar el código. Para Claude Code, un `CLAUDE.md` con una sola línea: `Sigue las instrucciones de AGENTS.md`. Para Gemini CLI, lo mismo con `GEMINI.md`.

## Qué es este proyecto
Una app que hace el trabajo de la agencia que un emprendimiento no puede contratar: a partir de ocho preguntas sencillas sobre el negocio, cuatro agentes de Gemini (estratega, planificador, redactor y revisor) devuelven una microestrategia activable: diagnóstico, 3 jugadas del mes, calendario de 14 días con los textos escritos, kit de WhatsApp, activaciones de bajo costo y descarga en Word.

## Cómo está hecho
- Python 3.12.
- Interfaz: Streamlit (ruta A), en un solo archivo `app.py`, con CSS propio para las tarjetas (`CSS`, `html_*`).
- IA: API de Gemini con el SDK `google-genai`, salida JSON forzada y razonamiento interno desactivado (`thinking_budget=0`; si el modelo lo rechaza, `GeminiLLM` sigue sin él). La lista de modelos sale de la clave (`listar_modelos`); `MODELOS_RESPALDO` es solo el fallback. Sin clave, `DemoLLM` simula los cuatro agentes.
- Pipeline en `ejecutar_pipeline`: estratega → planificador → redactor (dos mitades del calendario y el kit de WhatsApp en paralelo con `ThreadPoolExecutor`) → revisor → reescritura de los días marcados o de textos de más de 700 caracteres.
- Archivos: `app.py`, `requirements.txt`, `README.md`, `especificacion.md`, `ejemplos/negocio_ejemplo.json`, `.streamlit/config.toml`, `.streamlit/secrets.toml.example`.
- La especificación completa está en `especificacion.md`.

## Reglas
- La clave de la API va SIEMPRE en secretos (`st.secrets["GEMINI_API_KEY"]`) o en la barra lateral solo para la sesión. Nunca en el código, en el README ni en el chat. `.streamlit/secrets.toml` está en `.gitignore`.
- Cada llamada a la API va dentro de `try/except` (reintentos en `GeminiLLM.json`) y muestra un mensaje claro para el usuario (`st.error` en el bloque `if lanzar`).
- Textos de la interfaz en español, sencillos, pensados para un dueño de negocio sin conocimientos técnicos ni de marketing: nada de jerga ("KPI", "funnel", "engagement").
- Cada agente es una función `agente_*(llm, ...)` con un prompt en una constante `PROMPT_*` que empieza por su rol en mayúsculas (ESTRATEGA, PLANIFICADOR, REDACTOR, REVISOR). `DemoLLM` enruta por esa palabra: si renombrás un rol, actualizá ambos. Toda función nueva del LLM se implementa en `GeminiLLM` y en `DemoLLM`.
- Nunca llames a `st.*` desde los hilos del pool; los avisos de progreso (`avisar`) se emiten desde el hilo principal.
- `magicEnabled = false` en `config.toml`; aun así, no dejes expresiones sueltas que devuelvan `None` (`time.sleep`, `set.update`): asignalas a `_`.
- Usá `width="stretch"` en vez de `use_container_width` (Streamlit ≥ 1.50).
- Cambios pequeños: uno por petición. Al terminar, explicá qué cambiaste y por qué.
- Si añadís una librería, añadila también a `requirements.txt` y decilo.
- No uses datos personales reales. Para probar, inventá ejemplos (el de `ejemplos/negocio_ejemplo.json` es ficticio).

## Cómo comprobar que funciona
- `streamlit run app.py` en local (con `.streamlit/secrets.toml`, o sin clave para el modo demo), o push y revisar la app en Streamlit Cloud.
- Prueba automática en modo demo (debe terminar sin excepciones, con 3 jugadas, 14 días y 5 mensajes):
  ```bash
  python -c "
  from streamlit.testing.v1 import AppTest
  at = AppTest.from_file('app.py', default_timeout=180).run()
  at.button[0].click().run()
  [b for b in at.button if 'microestrategia' in b.label][0].click().run()
  assert not at.exception, at.exception; print('ok')"
  ```
- Casos de prueba (entrada → lo que esperamos):
  1. Negocio de ejemplo cargado → 3 jugadas, 14 días con texto, 5 mensajes de WhatsApp, descarga en Word.
  2. Presupuesto "$0" y canales solo WhatsApp y local físico → ninguna jugada con gasto y ningún día en Instagram.
  3. Formulario incompleto → el botón queda desactivado y un texto dice qué falta; nunca se llama al modelo.

## Qué no hacer
- No borres ni reescribas el README sin preguntar.
- No cambies el modelo ni la arquitectura de cuatro agentes sin preguntar.
- No hagas push ni despliegues sin que yo lo haya revisado.
- No quites el modo demo: es lo que garantiza que la URL pública funcione sin clave.
