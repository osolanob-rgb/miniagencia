# Especificación · MicroAgencia

> Una buena especificación es la que otro asistente de IA podría construir sin hacer preguntas. Es el prompt principal del proyecto y de ella sale la ficha del hito.

## 1. Problema y usuario
- **Quién tiene el problema:** el dueño o la dueña de un emprendimiento pequeño (panadería, salón, taller, servicio profesional, tienda de barrio o en línea) en Centroamérica, que vende por WhatsApp, Instagram o local físico y que no puede contratar una agencia creativa, de marketing o digital.
- **Cómo lo resuelve hoy:** improvisando: publica cuando se acuerda, copia lo que ve en otras cuentas, responde WhatsApp a deshora, no tiene una oferta clara ni sabe qué decir de sí mismo. A veces paga a un sobrino o a un freelance por un par de publicaciones sueltas.
- **Qué le molesta de cómo lo hace hoy:** no sabe por dónde empezar, siente que "le falta estrategia", le cuesta escribir, no tiene tiempo y lo poco que hace no se nota en ventas.
- **Qué parte resuelve la IA:** el trabajo de la agencia que no puede pagar: diagnosticar el negocio, elegir tres jugadas realistas para el mes, armar un calendario de 14 días, escribir los textos y los mensajes de WhatsApp listos para usar y proponer activaciones de bajo costo. **Queda fuera:** la ejecución (publicar, responder, atender), la pauta pagada, el diseño gráfico y cualquier promesa de resultados: la app da el plan y los materiales; el dueño lo activa.

## 2. Qué hace el producto
1. **Entiende el negocio con ocho preguntas sencillas**, sin pedir un brief: nombre, qué vende, dónde, a quién, qué lo hace distinto, objetivo del mes, presupuesto, canales que ya usa y tono.
2. **Genera una microestrategia activable**: diagnóstico, propuesta de valor, cliente ideal, 3 jugadas priorizadas con pasos, costo, esfuerzo y métrica, y 5 ideas de activación de bajo costo.
3. **Entrega los materiales listos**: calendario de 14 días con un texto por día para copiar y pegar, kit de 5 mensajes de WhatsApp, una oferta de bienvenida, y descarga del plan en Word, texto y CSV.

## 3. Entradas y salidas
| El usuario da… | La app devuelve… | Ejemplo |
|---|---|---|
| Nombre, producto, ciudad, cliente, diferencial (opcional) | Diagnóstico en 3 frases, propuesta de valor y perfil del cliente ideal | "La Hornada, panes de masa madre, Heredia" → "Tu diferencial (fermentación de 24 h) no se ve desde fuera; hay que hacerlo visible donde ya están tus clientes" |
| Objetivo del mes, presupuesto, canales, tono | 3 jugadas del mes con 3 pasos, costo, esfuerzo y métrica | "Vender más, $0, Instagram + WhatsApp" → "La prueba social que ya tenés: pedí 5 testimonios…" |
| Lo mismo | Calendario de 14 días (canal, formato, idea) con el texto de cada día y su CTA | "Día 3 · Instagram · Reel corto · Detrás de cámaras" + texto listo |
| Lo mismo | Kit de WhatsApp (bienvenida, seguimiento, oferta, recordatorio, pedir reseña) + oferta de bienvenida | "¡Hola! Gracias por escribir a La Hornada 😊 Contame qué estás buscando…" |
| Lo mismo | Revisión del plan: puntuación, alertas y ajustes; descargas .docx / .md / .csv | "8/10 · Evitá la palabra 'garantizado' en el día 4" |

## 4. La pieza de IA
- **Opción elegida:** API de Gemini (SDK `google-genai`), orquestada como cuatro agentes con salida JSON: estratega, planificador, redactor y revisor.
- **Por qué:** la tarea es razonamiento y escritura creativa en español con instrucciones complejas y salida estructurada; un modelo pequeño de Hugging Face no da esa calidad en CPU, y un RAG no es la pieza central porque no hay documentos del negocio, solo ocho respuestas. Gemini tiene nivel gratuito y modo JSON. El redactor escribe por semanas en paralelo para ganar velocidad y el revisor cierra el bucle: lo que marca se reescribe.
- **Instrucciones para el modelo (system prompt):** cada agente tiene el suyo en `app.py` (`PROMPT_ESTRATEGA`, `PROMPT_PLANIFICADOR`, `PROMPT_REDACTOR`, `PROMPT_REVISOR`). Reglas comunes: todo tiene que poder hacerlo el dueño solo, con el presupuesto indicado; usar el nombre, producto, ciudad y diferencial reales; priorizar lo gratuito; lenguaje sencillo en español (voseo o tuteo según el país); nada de promesas indemostrables ("garantizado", "el mejor", "número uno", "cura"), ni precios, premios o cifras inventados; textos de máximo 600 caracteres con CTA claro.

## 5. Flujo del usuario
1. El usuario entra y ve una cabecera que le explica en tres pasos qué va a recibir, cuatro tarjetas con los agentes en espera y el formulario de ocho preguntas (con un botón para cargar un negocio de ejemplo).
2. Responde las preguntas y pulsa **Generar mi microestrategia**. Ve a los agentes activarse uno a uno y una barra de progreso con lo que está pasando.
3. Recibe en un minuto el plan en siete pestañas: Estrategia, Calendario, Textos listos, WhatsApp, Activaciones, Revisión y Descargar. Copia los textos, guarda los mensajes de WhatsApp como respuestas rápidas y se lleva el plan en Word.

## 6. Restricciones
- Coste cero: capa gratuita de Gemini y despliegue gratuito en Streamlit Community Cloud (ruta A).
- La clave de la API va en secretos (`st.secrets`) o en la barra lateral solo para la sesión; nunca en el código. `secrets.toml` está en `.gitignore`.
- Sin datos personales reales: el negocio de ejemplo es ficticio y la app no guarda nada.
- Lenguaje sencillo, para alguien sin conocimientos técnicos ni de marketing: nada de "KPI", "funnel" o "engagement" en la interfaz.
- Sin clave, la app debe seguir funcionando en modo demo (LLM simulado) para que la URL pública nunca falle.
- Todo lo que proponga debe ser realizable con el presupuesto elegido y por una sola persona.

## 7. Criterios de aceptación
La app está bien si:
| Entrada | Resultado esperado |
|---|---|
| Negocio de ejemplo (La Hornada), objetivo "vender más", $0, Instagram + WhatsApp + Google Maps | En menos de 90 s con Gemini (menos de 10 s en demo): 3 jugadas, 14 días con texto, 5 mensajes de WhatsApp, 5 activaciones y descarga en Word |
| Falta el nombre, el producto, la ciudad, el cliente o no hay ningún canal | El botón queda desactivado y un texto indica qué falta |
| Diferencial vacío | El estratega propone uno a partir del producto y el cliente, sin inventar atributos concretos (premios, cifras) |
| Presupuesto "$0 (solo mi tiempo)" | Ninguna jugada ni activación exige gasto; si alguna lo requiere, el revisor la marca |
| Canales: solo WhatsApp y local físico | El calendario no usa Instagram ni TikTok |
| Tono "Premium / elegante" | Los textos no llevan emojis |
| Un texto supera 700 caracteres o el revisor lo marca | Se reescribe automáticamente una vez antes de mostrarse |
| Se acaba la cuota de Gemini (429) | Tres reintentos con espera; si persiste, mensaje claro: "esperá un minuto y volvé a intentar" |
| El modelo configurado ya no existe (404) | El desplegable muestra los modelos reales de la clave y hay una casilla para escribir otro |
| URL en ventana privada sin clave | La app abre y genera en modo demo sin errores |

## 8. Fuera de alcance (por ahora)
- Publicar directamente en Instagram, Facebook o WhatsApp.
- Generar imágenes o diseños.
- RAG con documentos del negocio (menú, catálogo, reseñas de Google) para que las jugadas y los textos usen datos reales: siguiente paso natural, probado en el ejercicio 3.
- Seguimiento del plan semana a semana (qué se hizo, qué funcionó) y segundo plan a partir de los resultados.
- Varios idiomas.

## 9. Despliegue
- **Ruta:** A (Streamlit Community Cloud), desde un repositorio público de GitHub con `app.py` y `requirements.txt`; la clave en Manage app → Settings → Secrets.
- **Si trabajáis en equipo (opcional):** proyecto individual.
