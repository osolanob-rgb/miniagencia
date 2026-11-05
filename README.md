# 🚀 MicroAgencia

**Enlace a la app:** https://copymaquina-oscar.streamlit.app/ _(o la URL nueva si creás otra app)_
**Repositorio:** https://github.com/TU-USUARIO/microagencia
**Autor:** Oscar Solano Brenes · Reto del módulo Python para IA · Máster en Inteligencia Artificial

La agencia que un emprendimiento no puede contratar, en el bolsillo del dueño: ocho preguntas sencillas y, en un minuto, una microestrategia lista para activar.

## Pitch
1. Miles de emprendimientos venden por WhatsApp, Instagram o un local de barrio sin poder pagar una agencia, y su dueño improvisa: publica cuando se acuerda, no sabe qué decir de sí mismo y lo poco que hace no se nota en ventas.
2. MicroAgencia le hace ocho preguntas sencillas y le devuelve en un minuto una microestrategia activable: tres jugadas del mes con pasos, un calendario de 14 días con los textos ya escritos, su kit de WhatsApp, ideas de bajo costo y el plan en Word.
3. La IA aporta lo que no se consigue sin ella: cuatro agentes de Gemini que hacen el trabajo de estratega, planificador, redactor y revisor sobre ese negocio concreto, con su nombre, su producto y su ciudad, y que descartan promesas falsas y gastos que el dueño no puede asumir.
4. _[Completar tras la prueba: qué aprendí probándola con un dueño de negocio o como usuario, y qué cambié.]_
5. El siguiente paso es un RAG con el menú, el catálogo o las reseñas de Google del negocio, para que las jugadas y los textos usen datos reales en lugar de solo las ocho respuestas; en el ejercicio 3 probé ese mismo RAG con fragmentos propios y funciona con una base vectorial de diez documentos.

## El problema
El dueño de un emprendimiento pequeño no puede contratar una agencia creativa, de marketing o digital, y el marketing lo hace a ratos y sin método: copia lo que ve, responde WhatsApp a deshora, no tiene una oferta clara ni una propuesta de valor. Le falta estrategia, tiempo y alguien que le escriba. Merece la pena resolverlo porque el costo de un mes de agencia equivale a varias semanas de ventas de ese negocio, y porque lo que necesita para empezar es poco y concreto: tres jugadas, catorce días de contenido y cinco mensajes.

## Qué hace la app
1. El dueño responde ocho preguntas (nombre, qué vende, dónde, a quién, qué lo hace distinto, objetivo del mes, presupuesto, canales y tono). Hay un botón para cargar un negocio de ejemplo.
2. Pulsa **Generar mi microestrategia** y ve a los cuatro agentes trabajar.
3. Recibe el plan en pestañas: **Estrategia** (diagnóstico, propuesta de valor, cliente ideal y 3 jugadas con pasos, costo, esfuerzo y métrica), **Calendario** (14 días en cuadrícula), **Textos listos** (uno por día, con CTA y hashtags, para copiar y pegar), **WhatsApp** (5 mensajes y una oferta de bienvenida), **Activaciones** (5 ideas de bajo costo), **Revisión** (puntuación, alertas y ajustes) y **Descargar** (Word, texto y CSV).

## La pieza de IA
- **Qué usa:** la API de Gemini (modelo `gemini-3.8-flash` por defecto; el desplegable muestra los modelos reales de la clave), orquestada como cuatro agentes con salida JSON: estratega, planificador, redactor (en paralelo, por semanas) y revisor, con un bucle que reescribe lo que el revisor marca.
- **Por qué esa opción:** es razonamiento y escritura en español con instrucciones complejas y salida estructurada; Gemini tiene nivel gratuito y modo JSON. Un RAG no es la pieza central porque no hay documentos, solo ocho respuestas.
- **Qué pasa si falla:** cada llamada tiene tres reintentos con espera; si persiste, un mensaje claro ("si dice 429 es la cuota: esperá un minuto"; "si dice 404, elegí otro modelo"). Sin clave, la app corre en modo demo con un LLM simulado, así que la URL nunca falla.

## Cómo la he construido
- **Herramientas:** Claude (Anthropic) como agente de programación, en chat, con los cuadernos del curso cargados; GitHub y Streamlit Community Cloud para el despliegue.
- **Fichero de contexto del agente:** [`AGENTS.md`](AGENTS.md).
- **Prompts clave:**
  1. «Quiero que me ayudes a ejecutar este ejercicio por completo y me des lo necesario para publicarlo en Streamlit.»
  2. «¿Puedes hacer que la app, con agentes, esté enfocada en crear altos volúmenes de copies para campañas de marketing de performance contra un brief cargado?»
  3. «Me generó este error, ¿qué debo corregir? Dame el paso a paso.» (con la captura del 404 de Gemini)
  4. «Está un poco lento, no ha generado los copies, ¿qué puedo mejorar? Y quiero que visualmente se vea mucho mejor, más tipo app.»
  5. «Metámosle mucha inversión visual a esto, porque la idea es que a nivel de proyecto quede como una máquina estratégico-creativa para emprendimientos que no tienen la capacidad de contratar una agencia: microestrategias, recomendaciones, contenidos e ideas que puedan activar de manera simple, 100 % pensado en el negocio.»
- **Qué delegué al agente y qué revisé a mano:** delegué el código, el pipeline en paralelo, el CSS, el LLM simulado y la documentación. Revisé y decidí a mano el giro del producto (de agencia a emprendimiento), las ocho preguntas del formulario, las reglas de los agentes (priorizar lo gratuito, nada de promesas falsas, lenguaje sin jerga), el negocio de ejemplo, el umbral de 700 caracteres, la elección del modelo y cada prueba en la URL desplegada.

## Prueba y mejora
| Quién la probó | Qué probó | Qué pasó | Qué cambié |
|---|---|---|---|
| Yo como usuario (versión anterior, Copymáquina) | Brief de ejemplo con Gemini | Error 404: el modelo ya no existía para cuentas nuevas | Lista de modelos consultada a la API, con casilla para escribir otro |
| Yo como usuario | Misma corrida con el modelo correcto | Varios minutos sin terminar (llamadas en serie) | Lotes en paralelo, razonamiento interno desactivado, rastreador de agentes |
| Yo como usuario | Uso general | Parecía un formulario y el usuario real (un dueño de negocio) no sabe escribir un brief | Giro a MicroAgencia: ocho preguntas guiadas, salida activable (jugadas, calendario, textos, WhatsApp) y rediseño visual |
| _[un compañero]_ | | | |

## Ejecutar en local (opcional)
```bash
pip install -r requirements.txt
# Poné la clave en .streamlit/secrets.toml (ver secrets.toml.example) o pegala en la barra lateral
streamlit run app.py
```

## Capturas
_[La app funcionando, la app ante un caso límite, un momento del trabajo con la IA y la prueba. Sin ninguna clave a la vista.]_
