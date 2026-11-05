"""
MicroAgencia · La agencia que un emprendimiento no puede contratar
Reto del módulo Python para IA · Máster en Inteligencia Artificial · Oscar Solano Brenes

Un dueño de negocio sin agencia responde ocho preguntas sencillas y recibe, en un minuto,
una microestrategia lista para activar: diagnóstico, 3 jugadas del mes, calendario de
contenidos de 14 días con los textos escritos, kit de mensajes de WhatsApp, ideas de
activación de bajo costo y descarga en Word.

Pipeline de agentes (cada uno es una llamada a Gemini con un rol y un contrato JSON):
  1. Estratega   -> diagnóstico, propuesta de valor, cliente ideal, 3 jugadas, 5 activaciones
  2. Planificador-> calendario de 14 días (canal, formato, idea, gancho)
  3. Redactor    -> textos listos para publicar (en paralelo, por semana) + kit de WhatsApp
  4. Revisor     -> comprueba que todo sea activable, barato y sin promesas falsas; corrige

Sin clave de API la app corre en MODO DEMO con un LLM simulado (versión 0 del reto).
"""

from __future__ import annotations

import html
import io
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import streamlit as st

APP_NOMBRE = "MicroAgencia"
BASE_DIR = Path(__file__).parent
MODELOS_RESPALDO = ["gemini-3.8-flash", "gemini-2.0-flash"]
DIAS = 14

OBJETIVOS = {
    "Conseguir mis primeros clientes": "captación",
    "Vender más de lo que ya vendo": "ventas",
    "Que más gente conozca mi negocio": "reconocimiento",
    "Lanzar un producto o servicio nuevo": "lanzamiento",
    "Que los clientes vuelvan y me recomienden": "fidelización",
}
PRESUPUESTOS = ["$0 (solo mi tiempo)", "Hasta $50 al mes", "Hasta $200 al mes", "Más de $200 al mes"]
CANALES = ["Instagram", "Facebook", "WhatsApp", "TikTok", "Local físico", "Página web / tienda online", "Google Maps"]
TONOS = ["Cercano y cálido", "Divertido", "Profesional y confiable", "Premium / elegante"]

CANAL_COLOR = {"Instagram": "#E1306C", "Facebook": "#1877F2", "WhatsApp": "#25D366", "TikTok": "#111111",
               "Local físico": "#F59E0B", "Página web / tienda online": "#0EA5E9", "Google Maps": "#34A853",
               "Email": "#7C3AED", "Alianzas": "#0F766E"}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def _extraer_json(texto: str):
    limpio = re.sub(r"```(?:json)?", "", texto).strip().rstrip("`").strip()
    try:
        return json.loads(limpio)
    except json.JSONDecodeError:
        inicio = min([i for i in (limpio.find("{"), limpio.find("[")) if i >= 0] or [0])
        fin = max(limpio.rfind("}"), limpio.rfind("]")) + 1
        return json.loads(limpio[inicio:fin])


def color_canal(canal: str) -> str:
    for k, v in CANAL_COLOR.items():
        if k.lower() in str(canal).lower():
            return v
    return "#64748B"


# ---------------------------------------------------------------------------
# Cliente LLM: Gemini real o simulado (modo demo)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False, ttl=3600)
def listar_modelos(api_key: str) -> list[str]:
    """Pregunta a la API qué modelos puede usar esta clave (los nombres cambian con el tiempo)."""
    try:
        from google import genai
        cliente = genai.Client(api_key=api_key)
        nombres = []
        for m in cliente.models.list():
            acciones = getattr(m, "supported_actions", None) or []
            if acciones and "generateContent" not in acciones:
                continue
            nombre = m.name.replace("models/", "")
            if "gemini" in nombre and not any(x in nombre for x in ("embedding", "tts", "image", "live", "audio")):
                nombres.append(nombre)
        flash = [n for n in nombres if "flash" in n]
        return list(dict.fromkeys(flash + nombres)) or MODELOS_RESPALDO
    except Exception:
        return MODELOS_RESPALDO


class GeminiLLM:
    """Llamadas a Gemini con salida JSON y razonamiento interno desactivado (más rápido).
    La clave nunca está en el código: viene de st.secrets o de la barra lateral."""

    def __init__(self, api_key: str, modelo: str = MODELOS_RESPALDO[0]):
        from google import genai
        self.cliente = genai.Client(api_key=api_key)
        self.modelo = modelo
        self.sin_thinking = True
        self.llamadas = 0
        self._lock = threading.Lock()

    def _config(self, sistema: str, temperatura: float):
        from google.genai import types
        kw = dict(system_instruction=sistema, temperature=temperatura,
                  response_mime_type="application/json", max_output_tokens=8192)
        if self.sin_thinking:
            kw["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
        return types.GenerateContentConfig(**kw)

    def json(self, sistema: str, usuario: str, temperatura: float = 0.8):
        ultimo_error = None
        for intento in range(3):
            try:
                with self._lock:
                    self.llamadas += 1
                resp = self.cliente.models.generate_content(
                    model=self.modelo, contents=usuario, config=self._config(sistema, temperatura))
                return _extraer_json(resp.text)
            except Exception as e:
                ultimo_error = e
                msg = str(e).lower()
                if self.sin_thinking and ("thinking" in msg or "invalid" in msg or "400" in msg):
                    self.sin_thinking = False
                    continue
                _ = time.sleep(2 * (intento + 1))
        raise RuntimeError(f"Gemini no respondió tras 3 intentos: {ultimo_error}")


class DemoLLM:
    """Simula los 4 agentes sin red ni coste, con contenido plausible a partir del formulario."""

    def __init__(self):
        self.llamadas = 0
        self._lock = threading.Lock()

    def json(self, sistema: str, usuario: str, temperatura: float = 0.8):
        with self._lock:
            self.llamadas += 1
        _ = time.sleep(0.2)
        d = _extraer_json(usuario.split("DATOS:")[-1])
        p = d["perfil"]
        neg, prod, ciudad, cli = p["negocio"], p["producto"], p["ciudad"], p["cliente"]
        dif = p.get("diferencial") or "la atención personal"
        canales = p.get("canales") or ["Instagram", "WhatsApp"]
        c1 = canales[0]; c2 = canales[1] if len(canales) > 1 else canales[0]
        if "ESTRATEGA" in sistema:
            return {
                "diagnostico": f"{neg} vende {prod} en {ciudad} a {cli}. Tiene un diferencial real ({dif}) que todavía no se ve desde fuera. El objetivo del mes ({p['objetivo']}) se consigue haciendo visible ese diferencial donde ya están los clientes, sin gastar en pauta.",
                "propuesta_de_valor": f"{prod} con {dif}, para {cli} de {ciudad} que quieren algo hecho con cuidado y sin complicaciones.",
                "cliente_ideal": {"quien": cli, "que_le_duele": "No sabe a quién comprarle con confianza y no tiene tiempo para comparar.",
                                  "donde_esta": f"En {c1} y {c2}, y en los negocios de su barrio en {ciudad}."},
                "jugadas": [
                    {"nombre": "La prueba social que ya tenés", "canal": c1,
                     "por_que": "Las personas compran lo que ven que otros compraron. Tus clientes actuales son tu mejor anuncio y no cuestan nada.",
                     "pasos": ["Pedí a 5 clientes contentos una foto o una frase sobre " + prod, "Publicá una por día con tu respuesta de agradecimiento", "Fijá la mejor en el perfil"],
                     "costo": "$0", "esfuerzo": "bajo", "metrica": "5 testimonios publicados y cuántas consultas llegan citándolos"},
                    {"nombre": "WhatsApp como mostrador", "canal": "WhatsApp",
                     "por_que": "Es donde el cliente decide. Un mensaje claro de bienvenida y seguimiento cierra ventas que hoy se enfrían.",
                     "pasos": ["Guardá en WhatsApp Business 4 respuestas rápidas (del kit de esta app)", "Respondé cada consulta en menos de 1 hora durante 14 días", "Al tercer día sin respuesta, enviá el mensaje de seguimiento"],
                     "costo": "$0", "esfuerzo": "medio", "metrica": "Consultas respondidas en menos de 1 hora y ventas cerradas por WhatsApp"},
                    {"nombre": "Alianza con un negocio vecino", "canal": "Alianzas",
                     "por_que": "Un negocio que atiende a tu mismo cliente pero no compite te presta su audiencia a cambio de la tuya.",
                     "pasos": ["Elegí 2 negocios de " + ciudad + " con el mismo cliente", "Proponé una promo cruzada de 2 semanas", "Publiquen el mismo día en sus redes"],
                     "costo": "$0 (o una muestra de " + prod + ")", "esfuerzo": "medio", "metrica": "Clientes nuevos que llegan nombrando al aliado"},
                ],
                "activaciones": [
                    {"idea": "Oferta de referido", "como": "Quien trae un amigo recibe un extra en su próxima compra.", "costo": "$0"},
                    {"idea": "Detrás de cámaras", "como": "Un video de 20 segundos mostrando cómo se hace " + prod + ".", "costo": "$0"},
                    {"idea": "Pregunta del día en historias", "como": "Una encuesta sobre qué prefieren tus clientes; usá las respuestas para la próxima oferta.", "costo": "$0"},
                    {"idea": "Tarjeta de 'te esperamos'", "como": "Un mensaje escrito a mano con cada pedido, con tu WhatsApp.", "costo": "Menos de $5"},
                    {"idea": "Google Maps al día", "como": "Fotos nuevas, horario correcto y pedí 3 reseñas esta semana.", "costo": "$0"},
                ],
            }
        if "PLANIFICADOR" in sistema:
            formatos = ["Post con foto", "Historia", "Reel corto", "Carrusel", "Post de texto", "Historia con encuesta", "Mensaje de WhatsApp"]
            ideas = ["Presentación del negocio", "Testimonio de cliente", "Detrás de cámaras", "Oferta de la semana", "Pregunta a la audiencia",
                     "Antes y después", "Tip útil", "Producto estrella", "Historia del fundador", "Mitos y verdades", "Recordatorio de oferta",
                     "Cliente de la semana", "Cómo hacer un pedido", "Resumen y gracias"]
            cal = []
            for i in range(DIAS):
                canal = "WhatsApp" if i in (3, 10) else (c1 if i % 2 == 0 else c2)
                cal.append({"dia": i + 1, "canal": canal, "formato": formatos[i % len(formatos)],
                            "idea": ideas[i], "gancho": f"{ideas[i]}: por qué {prod} de {neg} es distinto"})
            return {"calendario": cal}
        if "REDACTOR" in sistema:
            if "whatsapp" in usuario.lower() and "calendario" not in d:
                return {"whatsapp": [
                    {"momento": "Bienvenida", "mensaje": f"¡Hola! Gracias por escribir a {neg} 😊 Contame qué estás buscando y te ayudo a elegir. Tenemos {prod} con {dif}."},
                    {"momento": "Seguimiento", "mensaje": f"¡Hola de nuevo! ¿Pudiste pensar en lo de {prod}? Si querés, te reservo uno hoy sin compromiso."},
                    {"momento": "Oferta", "mensaje": f"Solo esta semana en {neg}: {prod} con un extra para quienes nos escriben por aquí. ¿Te aparto el tuyo?"},
                    {"momento": "Recordatorio", "mensaje": f"Te recuerdo que tu pedido de {prod} está listo. ¿Pasás hoy o te lo llevamos?"},
                    {"momento": "Pedir reseña", "mensaje": f"¡Gracias por tu compra! Si te gustó, ¿me dejás una reseña en Google? Nos ayuda muchísimo 🙏"},
                ], "oferta": {"nombre": "Semana de bienvenida", "mecanica": f"Primer pedido de {prod} con un extra sorpresa", "vigencia": "14 días", "condicion": "Mencionar la publicación"}}
            copies = []
            for item in d.get("calendario", []):
                copies.append({"dia": item["dia"],
                               "texto": f"{item['idea']} en {neg} ✨ {prod} para {cli} en {ciudad}, con {dif}. {item['gancho']}.",
                               "cta": "Escribinos por WhatsApp y te contamos",
                               "hashtags": [f"#{re.sub(r'[^a-z0-9]', '', neg.lower())}", f"#{re.sub(r'[^a-z0-9]', '', ciudad.lower())}", "#emprendimiento"]})
            return {"copies": copies}
        if "REVISOR" in sistema:
            alertas = []
            texto_todo = json.dumps(d, ensure_ascii=False).lower()
            for claim in ("garantizado", "el mejor", "número uno", "cura"):
                if claim in texto_todo:
                    alertas.append(f"Evitá la promesa '{claim}': no se puede demostrar.")
            return {"puntuacion": 8, "alertas": alertas or ["Todo activable con $0 y el tiempo del dueño."],
                    "dias_a_corregir": [], "ajustes": [{"donde": "Jugada 2", "cambio": "Poné una alarma diaria para revisar WhatsApp a las 9, 13 y 18."}]}
        return {}


# ---------------------------------------------------------------------------
# Agentes
# ---------------------------------------------------------------------------
PROMPT_ESTRATEGA = """Eres el ESTRATEGA de una agencia de marketing pequeña y práctica que atiende a emprendimientos sin presupuesto.
Recibes el perfil de un negocio y devuelves una microestrategia para el próximo mes. Reglas:
- Todo tiene que poder hacerlo el dueño solo, con el presupuesto indicado y sin conocimientos técnicos.
- Nada genérico: usa el nombre del negocio, el producto, la ciudad y el diferencial en cada jugada.
- Prioriza lo gratuito: clientes actuales, WhatsApp, alianzas, Google Maps, contenido propio.
- Lenguaje sencillo, en español, en segunda persona (vos/tú según el país del negocio).
Responde solo con JSON: {"diagnostico": str (3 frases), "propuesta_de_valor": str (1 frase),
"cliente_ideal": {"quien": str, "que_le_duele": str, "donde_esta": str},
"jugadas": [3 de {"nombre": str, "canal": str, "por_que": str, "pasos": [3 str], "costo": str, "esfuerzo": "bajo|medio|alto", "metrica": str}],
"activaciones": [5 de {"idea": str, "como": str (1 frase), "costo": str}]}"""

PROMPT_PLANIFICADOR = """Eres el PLANIFICADOR de contenidos de la misma agencia. A partir del perfil y de las 3 jugadas, armas un
calendario de 14 días realista para un dueño que publica solo. Reglas:
- Usa SOLO los canales que el negocio ya tiene. Alterna formatos sencillos (post con foto, historia, reel corto, carrusel, mensaje de WhatsApp).
- Cada día conecta con una jugada. Incluye 2 días de WhatsApp si el negocio lo usa.
- Ideas concretas y distintas entre sí; nada de "contenido de valor".
Responde solo con JSON: {"calendario": [14 de {"dia": int, "canal": str, "formato": str, "idea": str, "gancho": str}]}"""

PROMPT_REDACTOR = """Eres el REDACTOR de la misma agencia. Escribes textos LISTOS PARA PUBLICAR, que el dueño copia y pega.
Reglas: tono indicado en el perfil; frases cortas; emojis con moderación (ninguno si el tono es premium); sin promesas
que no se puedan demostrar ("garantizado", "el mejor", "número uno", "cura"); sin inventar precios, premios ni cifras;
máximo 600 caracteres por texto; un CTA claro; 3 hashtags locales y del rubro. Idioma y voseo/tuteo según el país.
Responde solo con JSON. Si te piden copies para días del calendario: {"copies": [{"dia": int, "texto": str, "cta": str, "hashtags": [3 str]}]}.
Si te piden el kit de WhatsApp: {"whatsapp": [5 de {"momento": "Bienvenida|Seguimiento|Oferta|Recordatorio|Pedir reseña", "mensaje": str (máx. 300 caracteres)}],
"oferta": {"nombre": str, "mecanica": str, "vigencia": str, "condicion": str}}"""

PROMPT_REVISOR = """Eres el REVISOR de la agencia: el socio práctico que mira el plan antes de entregarlo al dueño. Compruebas que
cada jugada se pueda hacer con el presupuesto y el tiempo indicados, que no haya promesas indemostrables ni datos
inventados, que los textos tengan CTA y cumplan el tono, y que el calendario use solo los canales del negocio.
Responde solo con JSON: {"puntuacion": int 0-10, "alertas": [str], "dias_a_corregir": [int (días cuyo texto hay que reescribir)],
"ajustes": [{"donde": str, "cambio": str}]}"""


@dataclass
class Plan:
    perfil: dict = field(default_factory=dict)
    estrategia: dict = field(default_factory=dict)
    calendario: list = field(default_factory=list)
    copies: dict = field(default_factory=dict)       # dia -> copy
    whatsapp: list = field(default_factory=list)
    oferta: dict = field(default_factory=dict)
    revision: dict = field(default_factory=dict)
    llamadas: int = 0
    segundos: float = 0.0


def _datos(**kw) -> str:
    return "DATOS:" + json.dumps(kw, ensure_ascii=False)


def agente_estratega(llm, perfil):
    return llm.json(PROMPT_ESTRATEGA, "Arma la microestrategia del mes.\n" + _datos(perfil=perfil), 0.7)


def agente_planificador(llm, perfil, jugadas):
    return llm.json(PROMPT_PLANIFICADOR, f"Arma el calendario de {DIAS} días.\n" + _datos(perfil=perfil, jugadas=jugadas), 0.7).get("calendario", [])


def agente_redactor_copies(llm, perfil, calendario):
    return llm.json(PROMPT_REDACTOR, "Escribe los copies de estos días del calendario.\n" + _datos(perfil=perfil, calendario=calendario), 0.9).get("copies", [])


def agente_redactor_whatsapp(llm, perfil, oferta_pistas):
    return llm.json(PROMPT_REDACTOR, "Escribe el kit de WhatsApp (5 mensajes) y una oferta de bienvenida.\n" + _datos(perfil=perfil, jugadas=oferta_pistas), 0.9)


def agente_revisor(llm, perfil, estrategia, calendario, copies, whatsapp):
    return llm.json(PROMPT_REVISOR, "Revisa el plan completo.\n" + _datos(perfil=perfil, estrategia=estrategia, calendario=calendario, copies=copies, whatsapp=whatsapp), 0.1)


def ejecutar_pipeline(llm, perfil: dict, avisar=None) -> Plan:
    t0 = time.time()
    plan = Plan(perfil=perfil)
    if avisar: avisar("estratega", "Diagnosticando el negocio y eligiendo las jugadas del mes…")
    plan.estrategia = agente_estratega(llm, perfil)
    jugadas = plan.estrategia.get("jugadas", [])

    if avisar: avisar("planificador", "Armando el calendario de 14 días…")
    plan.calendario = sorted(agente_planificador(llm, perfil, jugadas), key=lambda x: int(x.get("dia", 0)))[:DIAS]

    if avisar: avisar("redactor", "Escribiendo los textos listos para publicar y el kit de WhatsApp…")
    mitad = len(plan.calendario) // 2 or 1
    trozos = [plan.calendario[:mitad], plan.calendario[mitad:]]
    with ThreadPoolExecutor(max_workers=3) as pool:
        f_copies = [pool.submit(agente_redactor_copies, llm, perfil, t) for t in trozos if t]
        f_wa = pool.submit(agente_redactor_whatsapp, llm, perfil, jugadas)
        for f in as_completed(f_copies + [f_wa]):
            try:
                r = f.result()
            except Exception:
                continue
            if f is f_wa:
                plan.whatsapp = r.get("whatsapp", []); plan.oferta = r.get("oferta", {})
            else:
                for c in r:
                    plan.copies[int(c["dia"])] = c

    if avisar: avisar("revisor", "Revisando que todo sea activable, barato y honesto…")
    try:
        plan.revision = agente_revisor(llm, perfil, plan.estrategia, plan.calendario, list(plan.copies.values()), plan.whatsapp)
    except Exception:
        plan.revision = {"puntuacion": None, "alertas": ["El revisor no pudo completar la revisión."], "dias_a_corregir": [], "ajustes": []}

    # Control determinista + bucle de corrección: textos demasiado largos o marcados por el revisor se reescriben una vez
    malos = {int(x) for x in plan.revision.get("dias_a_corregir", []) if str(x).isdigit()}
    malos |= {d for d, c in plan.copies.items() if len(str(c.get("texto", ""))) > 700}
    if malos:
        if avisar: avisar("redactor", f"Reescribiendo {len(malos)} textos que no pasaron la revisión…")
        dias = [x for x in plan.calendario if int(x["dia"]) in malos]
        try:
            for c in agente_redactor_copies(llm, perfil, dias):
                plan.copies[int(c["dia"])] = c
        except Exception:
            pass
    plan.llamadas = llm.llamadas
    plan.segundos = time.time() - t0
    return plan


# ---------------------------------------------------------------------------
# Exportación
# ---------------------------------------------------------------------------
def plan_a_markdown(plan: Plan) -> str:
    p, e = plan.perfil, plan.estrategia
    out = [f"# Microestrategia de {p['negocio']} · próximos 30 días", "",
           f"**Objetivo:** {p['objetivo']}  ", f"**Presupuesto:** {p['presupuesto']}  ", f"**Canales:** {', '.join(p['canales'])}", "",
           "## Diagnóstico", e.get("diagnostico", ""), "", "## Propuesta de valor", e.get("propuesta_de_valor", ""), ""]
    ci = e.get("cliente_ideal", {})
    out += ["## Cliente ideal", f"- **Quién:** {ci.get('quien', '')}", f"- **Qué le duele:** {ci.get('que_le_duele', '')}", f"- **Dónde está:** {ci.get('donde_esta', '')}", ""]
    out += ["## Las 3 jugadas del mes"]
    for i, j in enumerate(e.get("jugadas", []), 1):
        out += [f"### {i}. {j.get('nombre', '')} · {j.get('canal', '')}", j.get("por_que", ""), ""]
        out += [f"{k}. {paso}" for k, paso in enumerate(j.get("pasos", []), 1)]
        out += ["", f"**Costo:** {j.get('costo', '')} · **Esfuerzo:** {j.get('esfuerzo', '')} · **Cómo sabrás si funcionó:** {j.get('metrica', '')}", ""]
    out += ["## Calendario de 14 días", "", "| Día | Canal | Formato | Idea | Texto listo | CTA |", "|---|---|---|---|---|---|"]
    for item in plan.calendario:
        c = plan.copies.get(int(item["dia"]), {})
        out.append(f"| {item['dia']} | {item['canal']} | {item['formato']} | {item['idea']} | {str(c.get('texto', '')).replace('|', '/')} | {c.get('cta', '')} |")
    out += ["", "## Kit de WhatsApp"]
    for m in plan.whatsapp:
        out += [f"**{m.get('momento', '')}:** {m.get('mensaje', '')}", ""]
    if plan.oferta:
        o = plan.oferta
        out += ["## Oferta de bienvenida", f"**{o.get('nombre', '')}** — {o.get('mecanica', '')}. Vigencia: {o.get('vigencia', '')}. Condición: {o.get('condicion', '')}", ""]
    out += ["## Ideas de activación de bajo costo"]
    for a in e.get("activaciones", []):
        out.append(f"- **{a.get('idea', '')}** ({a.get('costo', '')}): {a.get('como', '')}")
    r = plan.revision
    if r:
        out += ["", "## Revisión del plan", f"Puntuación: {r.get('puntuacion', '—')}/10"]
        out += [f"- ⚠️ {x}" for x in r.get("alertas", [])]
        out += [f"- 🔧 {x.get('donde', '')}: {x.get('cambio', '')}" for x in r.get("ajustes", [])]
    out += ["", f"_Generado con {APP_NOMBRE}._"]
    return "\n".join(out)


def plan_a_docx(plan: Plan) -> bytes:
    from docx import Document
    from docx.shared import Pt, RGBColor
    md = plan_a_markdown(plan)
    doc = Document()
    estilo = doc.styles["Normal"]; estilo.font.name = "Calibri"; estilo.font.size = Pt(11)
    tabla_filas = []
    for linea in md.splitlines():
        if linea.startswith("| Día") or linea.startswith("|---"):
            continue
        if linea.startswith("|"):
            tabla_filas.append([c.strip() for c in linea.strip("|").split("|")]); continue
        if tabla_filas:
            t = doc.add_table(rows=1, cols=6); t.style = "Light Grid Accent 1"
            for i, h in enumerate(["Día", "Canal", "Formato", "Idea", "Texto listo", "CTA"]):
                t.rows[0].cells[i].text = h
            for fila in tabla_filas:
                celdas = t.add_row().cells
                for i, v in enumerate(fila[:6]):
                    celdas[i].text = v
            tabla_filas = []
        if linea.startswith("# "):
            h = doc.add_heading(linea[2:], 0)
        elif linea.startswith("## "):
            doc.add_heading(linea[3:], 1)
        elif linea.startswith("### "):
            doc.add_heading(linea[4:], 2)
        elif linea.startswith("- "):
            doc.add_paragraph(re.sub(r"\*\*", "", linea[2:]), style="List Bullet")
        elif re.match(r"^\d+\. ", linea):
            doc.add_paragraph(re.sub(r"^\d+\. ", "", linea), style="List Number")
        elif linea.strip():
            par = doc.add_paragraph()
            for trozo in re.split(r"(\*\*[^*]+\*\*)", linea):
                if trozo.startswith("**"):
                    par.add_run(trozo.strip("*")).bold = True
                else:
                    par.add_run(trozo.replace("  ", ""))
    buf = io.BytesIO(); doc.save(buf); return buf.getvalue()


# ---------------------------------------------------------------------------
# Estilo
# ---------------------------------------------------------------------------
CSS = """
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
:root{--ink:#0f172a;--muted:#64748b;--line:#e2e8f0;--brand:#4f46e5;--brand2:#7c3aed;--accent:#f59e0b;--ok:#16a34a;}
html,body,[class*="css"],.stApp{font-family:'Inter',-apple-system,'Segoe UI',sans-serif;}
#MainMenu,footer{visibility:hidden;height:0;}
.block-container{padding-top:1rem;padding-bottom:3rem;max-width:1240px;}
section[data-testid="stSidebar"]{background:#fff;border-right:1px solid var(--line);}
section[data-testid="stSidebar"] h2{font-size:.76rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-top:1.2rem;}
.ma-hero{background:radial-gradient(1200px 400px at 10% -20%,rgba(124,58,237,.55),transparent 60%),linear-gradient(120deg,#1e1b4b 0%,#312e81 50%,#4f46e5 100%);
  color:#fff;border-radius:22px;padding:34px 36px;margin-bottom:18px;position:relative;overflow:hidden;}
.ma-hero:after{content:"";position:absolute;right:-80px;bottom:-120px;width:360px;height:360px;border-radius:50%;background:radial-gradient(circle,rgba(245,158,11,.5),transparent 65%);}
.ma-hero .eyebrow{font-size:.74rem;letter-spacing:.14em;text-transform:uppercase;opacity:.8;font-weight:700;}
.ma-hero h1{margin:6px 0 0;font-size:2.4rem;font-weight:900;letter-spacing:-.03em;color:#fff;line-height:1.05;}
.ma-hero p{margin:10px 0 0;opacity:.9;font-size:1.02rem;max-width:720px;}
.ma-steps{display:flex;gap:10px;margin-top:18px;flex-wrap:wrap;}
.ma-step{background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.22);padding:7px 12px;border-radius:999px;font-size:.8rem;font-weight:600;}
.ma-step b{color:#fcd34d;margin-right:6px;}
.ma-agents{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:4px 0 14px;}
.ma-agent{background:#fff;border:1px solid var(--line);border-radius:14px;padding:12px 14px;}
.ma-agent .n{font-weight:700;font-size:.9rem;color:var(--ink);} .ma-agent .d{font-size:.75rem;color:var(--muted);margin-top:2px;}
.ma-agent.on{border-color:var(--brand);box-shadow:0 0 0 3px rgba(79,70,229,.15);} .ma-agent.ok{border-color:#bbf7d0;background:#f0fdf4;}
.ma-agent .st{font-size:.72rem;font-weight:700;margin-top:8px;} .ma-agent.on .st{color:var(--brand);} .ma-agent.ok .st{color:#15803d;} .ma-agent.wait .st{color:#94a3b8;}
.ma-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:6px 0 14px;}
.ma-kpi{background:#fff;border:1px solid var(--line);border-radius:14px;padding:14px 16px;box-shadow:0 1px 2px rgba(15,23,42,.04);}
.ma-kpi .l{font-size:.7rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;font-weight:700;}
.ma-kpi .v{font-size:1.7rem;font-weight:900;color:var(--ink);line-height:1.1;margin-top:2px;} .ma-kpi .s{font-size:.76rem;color:var(--muted);}
.ma-card{background:#fff;border:1px solid var(--line);border-radius:16px;padding:16px 18px;margin-bottom:12px;box-shadow:0 1px 2px rgba(15,23,42,.04);height:100%;}
.ma-card h4{margin:0 0 6px;font-size:1rem;font-weight:800;color:var(--ink);}
.ma-card p{margin:0 0 6px;font-size:.9rem;color:#334155;line-height:1.4;}
.ma-card ol{margin:6px 0 8px 18px;padding:0;font-size:.88rem;color:#334155;} .ma-card li{margin-bottom:3px;}
.ma-tags{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;}
.ma-tag{font-size:.7rem;font-weight:700;padding:3px 9px;border-radius:999px;background:#eef2ff;color:#3730a3;}
.ma-tag.cost{background:#fef3c7;color:#92400e;} .ma-tag.ok{background:#dcfce7;color:#166534;}
.ma-chip{color:#fff;font-size:.68rem;font-weight:700;padding:3px 9px;border-radius:999px;display:inline-block;}
.ma-num{width:34px;height:34px;border-radius:10px;background:linear-gradient(135deg,var(--brand),var(--brand2));color:#fff;font-weight:900;display:inline-flex;align-items:center;justify-content:center;margin-bottom:8px;font-size:1rem;}
.ma-cal{display:grid;grid-template-columns:repeat(7,1fr);gap:8px;margin-bottom:10px;}
.ma-day{background:#fff;border:1px solid var(--line);border-radius:12px;padding:10px;min-height:118px;}
.ma-day .d{font-size:.68rem;color:var(--muted);font-weight:800;letter-spacing:.06em;} .ma-day .i{font-size:.8rem;font-weight:700;color:var(--ink);margin:4px 0 2px;line-height:1.25;}
.ma-day .f{font-size:.7rem;color:var(--muted);}
.ma-copy{background:#fff;border:1px solid var(--line);border-radius:14px;padding:14px 16px;margin-bottom:12px;}
.ma-copy .t{font-size:.92rem;color:var(--ink);line-height:1.45;white-space:pre-wrap;} .ma-copy .c{font-size:.8rem;color:var(--brand);font-weight:700;margin-top:6px;}
.ma-copy .h{font-size:.76rem;color:var(--muted);margin-top:4px;} .ma-copy .top{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;gap:8px;}
.ma-wa{background:#ecfdf5;border:1px solid #bbf7d0;border-radius:16px;padding:14px 16px;margin-bottom:12px;}
.ma-wa .m{font-size:.7rem;color:#166534;font-weight:800;text-transform:uppercase;letter-spacing:.06em;} .ma-wa .t{font-size:.92rem;color:var(--ink);margin-top:4px;line-height:1.45;}
.ma-alert{background:#fffbeb;border:1px solid #fde68a;border-radius:12px;padding:10px 14px;font-size:.86rem;color:#78350f;margin-bottom:8px;}
.ma-fix{background:#eef2ff;border:1px solid #c7d2fe;border-radius:12px;padding:10px 14px;font-size:.86rem;color:#312e81;margin-bottom:8px;}
div[data-testid="stTextArea"] textarea,div[data-testid="stTextInput"] input{border-radius:12px;}
button[kind="primary"]{border-radius:14px;font-weight:800;padding:.7rem 1rem;font-size:1.02rem;}
</style>
"""

AGENTES = [("estratega", "Estratega", "Diagnóstico y 3 jugadas"), ("planificador", "Planificador", "Calendario de 14 días"),
           ("redactor", "Redactor", "Textos listos y WhatsApp"), ("revisor", "Revisor", "Que sea activable y honesto")]


def html_agentes(activo, hechos):
    cards = []
    for clave, nombre, desc in AGENTES:
        if clave in hechos: cls, estado = "ok", "✓ Listo"
        elif clave == activo: cls, estado = "on", "● Trabajando"
        else: cls, estado = "wait", "○ En espera"
        cards.append(f'<div class="ma-agent {cls}"><div class="n">{nombre}</div><div class="d">{desc}</div><div class="st">{estado}</div></div>')
    return f'<div class="ma-agents">{"".join(cards)}</div>'


def html_kpis(items):
    return '<div class="ma-kpis">' + "".join(f'<div class="ma-kpi"><div class="l">{l}</div><div class="v">{v}</div><div class="s">{s}</div></div>' for l, v, s in items) + "</div>"


def esc(x) -> str:
    return html.escape(str(x if x is not None else ""))


def html_jugada(i: int, j: dict) -> str:
    pasos = "".join(f"<li>{esc(p)}</li>" for p in j.get("pasos", []))
    return (f'<div class="ma-card"><div class="ma-num">{i}</div><h4>{esc(j.get("nombre"))}</h4><p>{esc(j.get("por_que"))}</p>'
            f'<ol>{pasos}</ol><p><b>Cómo sabrás si funcionó:</b> {esc(j.get("metrica"))}</p>'
            f'<div class="ma-tags"><span class="ma-chip" style="background:{color_canal(j.get("canal", ""))}">{esc(j.get("canal"))}</span>'
            f'<span class="ma-tag cost">Costo: {esc(j.get("costo"))}</span><span class="ma-tag">Esfuerzo: {esc(j.get("esfuerzo"))}</span></div></div>')


def html_calendario(calendario: list) -> str:
    dias = "".join(
        f'<div class="ma-day"><div class="d">DÍA {esc(x.get("dia"))}</div><span class="ma-chip" style="background:{color_canal(x.get("canal", ""))}">{esc(x.get("canal"))}</span>'
        f'<div class="i">{esc(x.get("idea"))}</div><div class="f">{esc(x.get("formato"))}</div></div>' for x in calendario)
    return f'<div class="ma-cal">{dias}</div>'


def html_copy(item: dict, c: dict) -> str:
    tags = " ".join(esc(h) for h in c.get("hashtags", []))
    return (f'<div class="ma-copy"><div class="top"><span class="ma-chip" style="background:{color_canal(item.get("canal", ""))}">Día {esc(item.get("dia"))} · {esc(item.get("canal"))}</span>'
            f'<span class="ma-tag">{esc(item.get("formato"))}</span></div><div class="t">{esc(c.get("texto"))}</div>'
            f'<div class="c">👉 {esc(c.get("cta"))}</div><div class="h">{tags}</div></div>')


# ---------------------------------------------------------------------------
# Interfaz
# ---------------------------------------------------------------------------
st.set_page_config(page_title=f"{APP_NOMBRE} · tu microestrategia en un minuto", page_icon="🚀", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## Motor de IA")
    try:
        clave_secreta = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        clave_secreta = ""
    clave = clave_secreta or st.text_input("Clave de Gemini (opcional, solo esta sesión)", type="password", help="Gratis en aistudio.google.com. No se guarda.")
    modo_demo = not clave
    if modo_demo:
        modelo = MODELOS_RESPALDO[0]
        st.info("Sin clave: **modo demo** con un LLM simulado. El flujo es real; los textos, de muestra.")
    else:
        modelos = listar_modelos(clave)
        modelo = st.selectbox("Modelo", modelos, index=0)
        otro = st.text_input("…u otro modelo (opcional)", placeholder="p. ej. gemini-3.8-flash")
        if otro.strip():
            modelo = otro.strip()
        st.success(f"Conectado · {modelo}")
    st.markdown("## Cómo funciona")
    st.caption("Cuatro agentes trabajan en cadena: el estratega diagnostica y elige 3 jugadas, el planificador arma 14 días, "
               "el redactor escribe los textos y el kit de WhatsApp, y el revisor comprueba que todo sea activable con tu presupuesto "
               "y sin promesas falsas. Todo lo que sale lo podés hacer vos, sin agencia.")

st.markdown(f"""
<div class="ma-hero"><div class="eyebrow">La agencia que no podés contratar, en tu bolsillo</div>
<h1>🚀 {APP_NOMBRE}</h1>
<p>Contanos tu negocio en ocho preguntas y recibí en un minuto una microestrategia lista para activar: tres jugadas del mes,
un calendario de 14 días con los textos ya escritos, tu kit de WhatsApp e ideas de bajo costo. Pensado 100&nbsp;% en vender, no en la tecnología.</p>
<div class="ma-steps"><span class="ma-step"><b>1</b>Contanos tu negocio</span><span class="ma-step"><b>2</b>Elegí qué querés lograr</span>
<span class="ma-step"><b>3</b>Activá tu plan</span><span class="ma-step">{'Modo demo' if modo_demo else 'Gemini · ' + modelo}</span></div></div>
""", unsafe_allow_html=True)

slot_agentes = st.empty()
plan: Plan | None = st.session_state.get("plan")
slot_agentes.markdown(html_agentes(None, {a[0] for a in AGENTES} if plan else set()), unsafe_allow_html=True)


@st.cache_data
def ejemplo() -> dict:
    ruta = BASE_DIR / "ejemplos" / "negocio_ejemplo.json"
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}


with st.container(border=True):
    st.markdown("#### 1 · Contanos tu negocio")
    if st.button("Cargar un negocio de ejemplo"):
        for k, v in ejemplo().items():
            st.session_state[f"f_{k}"] = v
    c1, c2 = st.columns(2, gap="large")
    with c1:
        negocio = st.text_input("¿Cómo se llama tu negocio?", key="f_negocio", placeholder="Ej.: Pan de Masa Madre La Hornada")
        producto = st.text_input("¿Qué vendés? (producto o servicio principal)", key="f_producto", placeholder="Ej.: panes de masa madre y repostería por encargo")
        ciudad = st.text_input("¿Dónde estás? (ciudad y país)", key="f_ciudad", placeholder="Ej.: Heredia, Costa Rica")
        cliente = st.text_input("¿A quién le vendés? Describilo como lo ves", key="f_cliente", placeholder="Ej.: familias y oficinas del centro que compran por WhatsApp")
    with c2:
        diferencial = st.text_input("¿Qué te hace distinto? (si no lo sabés, dejalo vacío)", key="f_diferencial", placeholder="Ej.: fermentación de 24 horas y entrega el mismo día")
        objetivo = st.selectbox("¿Qué querés lograr este mes?", list(OBJETIVOS), key="f_objetivo")
        presupuesto = st.select_slider("¿Cuánto podés invertir al mes?", PRESUPUESTOS, key="f_presupuesto")
        canales = st.multiselect("¿Qué canales ya usás?", CANALES, key="f_canales")
        tono = st.radio("¿Cómo le hablás a tus clientes?", TONOS, key="f_tono", horizontal=True)
    listo = all([negocio.strip(), producto.strip(), ciudad.strip(), cliente.strip()]) and bool(canales)
    if not listo:
        st.caption("Completá nombre, producto, ciudad, cliente y al menos un canal para activar el botón.")
    lanzar = st.button("🚀 Generar mi microestrategia", type="primary", width="stretch", disabled=not listo)

if lanzar:
    perfil = {"negocio": negocio.strip(), "producto": producto.strip(), "ciudad": ciudad.strip(), "cliente": cliente.strip(),
              "diferencial": diferencial.strip(), "objetivo": objetivo, "tipo_objetivo": OBJETIVOS[objetivo],
              "presupuesto": presupuesto, "canales": canales, "tono": tono}
    llm = DemoLLM() if modo_demo else GeminiLLM(clave, modelo)
    hechos: set = set()
    orden = [a[0] for a in AGENTES]
    barra = st.progress(0.0, "Arrancando…")

    def avisar(agente, texto):
        _ = hechos.update(orden[:orden.index(agente)])
        slot_agentes.markdown(html_agentes(agente, hechos), unsafe_allow_html=True)
        barra.progress({"estratega": .1, "planificador": .35, "redactor": .55, "revisor": .85}[agente], texto)

    try:
        plan = ejecutar_pipeline(llm, perfil, avisar)
        st.session_state["plan"] = plan
        barra.progress(1.0, f"Listo en {plan.segundos:.0f} s")
        slot_agentes.markdown(html_agentes(None, set(orden)), unsafe_allow_html=True)
        _ = time.sleep(0.5); _ = barra.empty()
    except Exception as e:
        _ = barra.empty()
        st.error(f"No pude terminar el plan: {e}. Si dice 429 es la cuota gratuita de Gemini: esperá un minuto y volvé a intentar. "
                 "Si dice 404, elegí otro modelo en la barra lateral.")
        plan = st.session_state.get("plan")

if plan:
    e, p = plan.estrategia, plan.perfil
    st.markdown(f"#### 2 · Tu plan para {esc(p['negocio'])}")
    st.markdown(html_kpis([
        ("Jugadas del mes", str(len(e.get("jugadas", []))), "priorizadas y con pasos"),
        ("Días planificados", str(len(plan.calendario)), "con texto listo"),
        ("Textos listos", str(len(plan.copies) + len(plan.whatsapp)), "para copiar y pegar"),
        ("Revisión", f"{plan.revision.get('puntuacion', '—')}/10", "activable y honesto"),
        ("Generado en", f"{plan.segundos:.0f} s", f"{plan.llamadas} llamadas al modelo"),
    ]), unsafe_allow_html=True)

    t_estr, t_cal, t_txt, t_wa, t_act, t_rev, t_dl = st.tabs(["🧭 Estrategia", "📅 Calendario", "✍️ Textos listos", "💬 WhatsApp", "⚡ Activaciones", "✅ Revisión", "⬇️ Descargar"])

    with t_estr:
        a, b = st.columns([1.3, 1], gap="large")
        with a:
            st.markdown("##### Diagnóstico")
            st.markdown(esc(e.get("diagnostico", "")))
            st.markdown("##### Tu propuesta de valor, en una frase")
            st.markdown(f"> **{esc(e.get('propuesta_de_valor', ''))}**")
        with b:
            ci = e.get("cliente_ideal", {})
            st.markdown('<div class="ma-card"><h4>Tu cliente ideal</h4>'
                        f'<p><b>Quién:</b> {esc(ci.get("quien"))}</p><p><b>Qué le duele:</b> {esc(ci.get("que_le_duele"))}</p>'
                        f'<p><b>Dónde está:</b> {esc(ci.get("donde_esta"))}</p></div>', unsafe_allow_html=True)
        st.markdown("##### Las 3 jugadas del mes")
        cols = st.columns(3, gap="medium")
        for i, j in enumerate(e.get("jugadas", [])[:3], 1):
            cols[i - 1].markdown(html_jugada(i, j), unsafe_allow_html=True)

    with t_cal:
        st.markdown("##### 14 días, un canal y una idea por día")
        st.markdown(html_calendario(plan.calendario[:7]), unsafe_allow_html=True)
        st.markdown(html_calendario(plan.calendario[7:14]), unsafe_allow_html=True)
        df_cal = pd.DataFrame([{**x, "texto": plan.copies.get(int(x["dia"]), {}).get("texto", ""), "cta": plan.copies.get(int(x["dia"]), {}).get("cta", "")} for x in plan.calendario])
        with st.expander("Ver como tabla"):
            st.dataframe(df_cal, width="stretch", hide_index=True)

    with t_txt:
        st.markdown("##### Copiá, pegá y publicá")
        canal_f = st.multiselect("Filtrar por canal", sorted({x["canal"] for x in plan.calendario}), default=sorted({x["canal"] for x in plan.calendario}))
        cols = st.columns(2, gap="medium")
        k = 0
        for item in plan.calendario:
            if item["canal"] not in canal_f:
                continue
            c = plan.copies.get(int(item["dia"]))
            if not c:
                continue
            cols[k % 2].markdown(html_copy(item, c), unsafe_allow_html=True)
            k += 1

    with t_wa:
        st.markdown("##### Tu kit de WhatsApp: guardalo como respuestas rápidas")
        cols = st.columns(2, gap="medium")
        for i, m in enumerate(plan.whatsapp):
            cols[i % 2].markdown(f'<div class="ma-wa"><div class="m">{esc(m.get("momento"))}</div><div class="t">{esc(m.get("mensaje"))}</div></div>', unsafe_allow_html=True)
        if plan.oferta:
            o = plan.oferta
            st.markdown(f'<div class="ma-card"><h4>🎁 Oferta de bienvenida: {esc(o.get("nombre"))}</h4><p>{esc(o.get("mecanica"))}</p>'
                        f'<div class="ma-tags"><span class="ma-tag">Vigencia: {esc(o.get("vigencia"))}</span><span class="ma-tag cost">Condición: {esc(o.get("condicion"))}</span></div></div>', unsafe_allow_html=True)

    with t_act:
        st.markdown("##### Ideas que podés activar esta semana")
        cols = st.columns(3, gap="medium")
        for i, a in enumerate(e.get("activaciones", [])):
            cols[i % 3].markdown(f'<div class="ma-card"><h4>⚡ {esc(a.get("idea"))}</h4><p>{esc(a.get("como"))}</p><div class="ma-tags"><span class="ma-tag cost">{esc(a.get("costo"))}</span></div></div>', unsafe_allow_html=True)

    with t_rev:
        r = plan.revision
        st.markdown(f"##### El revisor le da {r.get('puntuacion', '—')}/10 a este plan")
        for x in r.get("alertas", []):
            st.markdown(f'<div class="ma-alert">⚠️ {esc(x)}</div>', unsafe_allow_html=True)
        for x in r.get("ajustes", []):
            st.markdown(f'<div class="ma-fix">🔧 <b>{esc(x.get("donde"))}:</b> {esc(x.get("cambio"))}</div>', unsafe_allow_html=True)

    with t_dl:
        st.markdown("##### Llevate el plan")
        md = plan_a_markdown(plan)
        d1, d2, d3 = st.columns(3)
        d1.download_button("⬇️ Plan en Word (.docx)", plan_a_docx(plan), f"plan_{re.sub(r'[^a-z0-9]+', '_', p['negocio'].lower())}.docx",
                           "application/vnd.openxmlformats-officedocument.wordprocessingml.document", width="stretch")
        d2.download_button("⬇️ Plan en texto (.md)", md.encode("utf-8"), "plan.md", "text/markdown", width="stretch")
        d3.download_button("⬇️ Calendario (.csv)", df_cal.to_csv(index=False).encode("utf-8-sig"), "calendario.csv", "text/csv", width="stretch")
        with st.expander("Vista previa del plan completo"):
            st.markdown(md)
