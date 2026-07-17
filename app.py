"""
BEAM — Workspace de informes radiológicos asistidos por IA (v3.0)

Editor de tres secciones (TÉCNICA / HALLAZGOS / CONCLUSIÓN) con motor de
reformulación por estilos (clínico, académico, conciso, elegante, RSNA,
ESSR, AJR, profesor). El informe es el protagonista: se genera a partir
de un dictado o texto libre y queda como documento editable, no como
hilo de chat.

Novedades v3.0:
  · Arquitectura multi-proveedor — DeepSeek, OpenAI y Gemini, todos vía el
    SDK de OpenAI (Gemini expone un endpoint compatible), intercambiables
    en caliente desde la barra lateral, con una API key independiente por
    proveedor.
  · Rediseño visual completo: sala de lectura oscura con acento ámbar —el
    color de las anotaciones sobre estudios en escala de grises en los
    visores DICOM (Eden PACS, Osirix)— tipografía editorial para el
    identificador de marca y monoespaciada para clasificaciones y datos
    numéricos, textura de grano sutil de placa radiográfica.

Dictado por voz: Web Speech API nativa del navegador (Chrome/Edge). No
requiere ningún paquete ni API key adicional — corre 100% en el cliente.

Requisitos:
    pip install streamlit openai

Ejecutar:
    streamlit run app.py

Configura al menos una API key (DeepSeek, OpenAI o Gemini) desde
"Configuración" en la barra lateral, o vía variables de entorno /
st.secrets: DEEPSEEK_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY.
"""

import json
import os
import re
from typing import Iterator

import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI

# ══════════════════════════════════════════════════════════════════════════
# PROVEEDORES — todos hablan el dialecto OpenAI (Gemini vía su endpoint
# compatible), así que un único cliente sirve para los tres.
# ══════════════════════════════════════════════════════════════════════════

PROVEEDORES = {
    "deepseek": {
        "nombre": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "key_env": "DEEPSEEK_API_KEY",
        "modelo_defecto": "deepseek-chat",
        "modelos": {
            "deepseek-chat": "DeepSeek Chat (V3) — rápido, uso diario",
            "deepseek-reasoner": "DeepSeek Reasoner (R1) — casos complejos",
        },
    },
    "openai": {
        "nombre": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "key_env": "OPENAI_API_KEY",
        "modelo_defecto": "gpt-4.1-mini",
        "modelos": {
            "gpt-4.1-mini": "GPT-4.1 Mini — equilibrado",
            "gpt-4o-mini": "GPT-4o Mini — rápido y económico",
        },
    },
    "gemini": {
        "nombre": "Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "key_env": "GEMINI_API_KEY",
        "modelo_defecto": "gemini-2.5-flash",
        "modelos": {
            "gemini-2.5-flash": "Gemini 2.5 Flash — rápido, multimodal",
            "gemini-2.0-flash": "Gemini 2.0 Flash — estable",
        },
    },
}
ORDEN_PROVEEDORES = ["deepseek", "openai", "gemini"]

# ══════════════════════════════════════════════════════════════════════════
# IDENTIDAD VISUAL
#
# Sala de lectura: casi negro, como un cuarto oscurecido para leer placas.
# Acento ámbar — la convención real de los visores DICOM para superponer
# texto legible sobre imágenes en escala de grises sin "ensuciar" la
# imagen con rojos clínicos. Un cian apagado sirve de segundo acento para
# estados de éxito / confirmación, nunca compite con el ámbar.
# ══════════════════════════════════════════════════════════════════════════

PALETA = {
    "bg": "#08090A",
    "surface": "#131417",
    "surface_alt": "#1A1B1F",
    "surface_raised": "#202126",
    "border": "#25262B",
    "border_soft": "#1B1C20",
    "text": "#ECEDEF",
    "muted": "#8A8D95",
    "muted_dim": "#5C5E64",
    "accent": "#D9A24B",
    "accent_strong": "#E8B569",
    "accent_soft": "#D9A24B1F",
    "accent_soft_2": "#D9A24B0D",
    "cian": "#5FA8A6",
    "cian_soft": "#5FA8A61F",
}

FUENTE_DISPLAY = "'Fraunces', Georgia, serif"
FUENTE_UI = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
FUENTE_MONO = "'JetBrains Mono', ui-monospace, 'SF Mono', Consolas, monospace"

TERMINOLOGIA_CORRECTA = {
    "osteoartritis": "osteoartrosis",
    "ruptura": "desgarro",
    "rasgadura": "desgarro",
}

SYSTEM_PROMPT_BASE = """Eres BEAM, un radiólogo experto redactando informes para un contexto
clínico mexicano. No eres un chatbot: eres el motor de redacción de un workspace de informes.
Cuando recibas hallazgos dictados o escritos por el radiólogo, generas directamente el informe
completo, sin preámbulos, sin confirmaciones, sin explicaciones adicionales — solo el informe.

Usa exclusivamente estas tres secciones, en mayúsculas como encabezado en su propia línea,
en prosa narrativa continua (nunca listas ni fragmentos telegráficos):

TÉCNICA
HALLAZGOS
CONCLUSIÓN

NIVEL DE DETALLE Y CRITERIO CLÍNICO:
- Redacta como lo haría un radiólogo experto (nivel fellow), no como una transcripción literal
  de lo dictado.
- El radiólogo normalmente solo dictará los hallazgos POSITIVOS o relevantes. Completa tú, de
  forma sistemática, la descripción del resto de estructuras evaluadas de rutina en ese tipo de
  estudio (revisión por sistemas / "negativa pertinente"), describiéndolas como normales, EXCEPTO
  cuando el dictado indique lo contrario o la técnica no permita evaluarlas.
- NUNCA inventes hallazgos PATOLÓGICOS no mencionados o claramente implícitos. La inferencia
  permitida es únicamente hacia la normalidad de estructuras no mencionadas explícitamente.
- CONCLUSIÓN debe ser concisa, limitada a lo clínicamente relevante, priorizada, con lenguaje
  de cierre diagnóstico apropiado (correlación clínica, seguimiento, estudios adicionales).

TERMINOLOGÍA ESTRICTA (aplica siempre):
- Usa "osteoartrosis", nunca "osteoartritis".
- Usa "desgarro", nunca "ruptura" o "rasgadura" (tendón/menisco).
- Si el caso involucra sistemas de clasificación (BI-RADS, PI-RADS, TI-RADS, LI-RADS,
  Kellgren-Lawrence, Pfirrmann, Stoller, ICRS, Fleischner, Spetzler-Martin, TOAST, AAST),
  inclúyelos correctamente en CONCLUSIÓN con el grado/categoría correspondiente.

Responde siempre en español, y responde ÚNICAMENTE con el informe (TÉCNICA/HALLAZGOS/CONCLUSIÓN),
sin texto antes ni después.
"""

ESTILOS_REDACCION = {
    "clinico": {
        "nombre": "Clínico directo",
        "descripcion": "Oraciones cortas, datos medibles por delante.",
        "instruccion": (
            "Oraciones cortas (máximo ~20 palabras), voz activa cuando sea posible, cero "
            "adjetivos ornamentales, prioriza datos medibles sobre descripciones narrativas."
        ),
    },
    "academico": {
        "nombre": "Académico",
        "descripcion": "Registro de discusión de caso en sesión clínica.",
        "instruccion": (
            "Oraciones compuestas con conectores subordinantes (dado que, en tanto que, lo cual "
            "sugiere), terminología completa sin abreviar, tono de discusión de caso en sesión "
            "clínica o ateneo."
        ),
    },
    "conciso": {
        "nombre": "Ultra conciso",
        "descripcion": "Mínima extensión posible sin perder datos.",
        "instruccion": (
            "Reduce cada oración a su núcleo informativo. Elimina toda redundancia y frase de "
            "relleno. Objetivo: no más del 60% de la longitud original en caracteres, sin perder "
            "ni un solo dato clínico."
        ),
    },
    "elegante": {
        "nombre": "Elegante",
        "descripcion": "Fluido, con variación de estructura entre oraciones.",
        "instruccion": (
            "Varía la longitud y estructura de las oraciones para evitar monotonía, usa "
            "transiciones fluidas entre ideas, mantiene precisión clínica sin sonar telegráfico "
            "ni sobrecargado."
        ),
    },
    "rsna": {
        "nombre": "Estilo RSNA (Radiology)",
        "descripcion": "Objetivo e impersonal, secuencia anatómica sistemática.",
        "instruccion": (
            "Registro de journal RSNA: objetivo, impersonal, con secuencia anatómica sistemática "
            "(de superior a inferior o de proximal a distal), sin lenguaje coloquial."
        ),
    },
    "essr": {
        "nombre": "Estilo ESSR",
        "descripcion": "Preciso en grados/clasificaciones musculoesqueléticas.",
        "instruccion": (
            "Registro europeo musculoesquelético: preciso en grados y clasificaciones (Goutallier, "
            "ICRS, Pfirrmann, etc.), frases breves y directas, sin narrativa innecesaria."
        ),
    },
    "ajr": {
        "nombre": "Estilo AJR",
        "descripcion": "Contextualiza antes de describir, cierra con implicancia clínica.",
        "instruccion": (
            "Tono editorial de caso ilustrativo: contextualiza brevemente el hallazgo antes de "
            "describirlo en detalle, y cierra con su implicancia clínica explícita."
        ),
    },
    "profesor": {
        "nombre": "Profesor de alta especialidad",
        "descripcion": "Enseña el razonamiento diagnóstico sin extenderse.",
        "instruccion": (
            "Redacta como si enseñaras el caso a un residente: menciona brevemente el "
            "razonamiento diagnóstico detrás del hallazgo principal (por qué esa impresión y no "
            "otra), sin extenderte más de una oración adicional por hallazgo relevante."
        ),
    },
}
ORDEN_ESTILOS = ["clinico", "academico", "conciso", "elegante", "rsna", "essr", "ajr", "profesor"]

NOMBRE_SECCION = {"tecnica": "TÉCNICA", "hallazgos": "HALLAZGOS", "conclusion": "CONCLUSIÓN"}
ETIQUETA_CAPTURA = "Dictado o hallazgos"

st.set_page_config(
    page_title="BEAM · Workspace radiológico",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ══════════════════════════════════════════════════════════════════════════
# CAPA DE PROVEEDORES / GENERACIÓN
# ══════════════════════════════════════════════════════════════════════════

def obtener_secreto(nombre: str) -> str:
    """st.secrets primero, os.environ como respaldo — nunca truena si falta."""
    try:
        if nombre in st.secrets:
            return st.secrets[nombre]
    except Exception:
        pass
    return os.environ.get(nombre, "")


def api_key_activa() -> str:
    proveedor = st.session_state.proveedor_actual
    return st.session_state.api_keys.get(proveedor, "")


def modelo_activo() -> str:
    proveedor = st.session_state.proveedor_actual
    return st.session_state.modelos_por_proveedor.get(
        proveedor, PROVEEDORES[proveedor]["modelo_defecto"]
    )


def obtener_cliente() -> OpenAI:
    proveedor = PROVEEDORES[st.session_state.proveedor_actual]
    return OpenAI(api_key=api_key_activa(), base_url=proveedor["base_url"])


def aplicar_terminologia(texto: str) -> str:
    for incorrecto, correcto in TERMINOLOGIA_CORRECTA.items():
        texto = texto.replace(incorrecto, correcto)
        texto = texto.replace(incorrecto.capitalize(), correcto.capitalize())
    return texto


def generar_informe_stream(dictado: str) -> Iterator[str]:
    cliente = obtener_cliente()
    stream = cliente.chat.completions.create(
        model=modelo_activo(),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_BASE},
            {"role": "user", "content": dictado},
        ],
        temperature=0.2,
        stream=True,
    )
    for fragmento in stream:
        delta = fragmento.choices[0].delta
        texto = getattr(delta, "content", None) or ""
        if texto:
            yield texto


_PATRON_ENCABEZADO = re.compile(
    r"(?im)^\s*(T[ÉE]CNICA|HALLAZGOS|CONCLUSI[ÓO]N)\s*:?\s*$", re.MULTILINE
)


def parsear_informe(texto: str) -> dict:
    partes = {}
    coincidencias = list(_PATRON_ENCABEZADO.finditer(texto))
    for i, m in enumerate(coincidencias):
        clave = m.group(1).upper().replace("TECNICA", "TÉCNICA").replace("CONCLUSION", "CONCLUSIÓN")
        inicio = m.end()
        fin = coincidencias[i + 1].start() if i + 1 < len(coincidencias) else len(texto)
        partes[clave] = texto[inicio:fin].strip()
    return {
        "tecnica": aplicar_terminologia(partes.get("TÉCNICA", "")),
        "hallazgos": aplicar_terminologia(partes.get("HALLAZGOS", "")),
        "conclusion": aplicar_terminologia(partes.get("CONCLUSIÓN", "")),
    }


def reconstruir_informe(informe: dict) -> str:
    return (
        f"TÉCNICA\n{informe.get('tecnica', '').strip()}\n\n"
        f"HALLAZGOS\n{informe.get('hallazgos', '').strip()}\n\n"
        f"CONCLUSIÓN\n{informe.get('conclusion', '').strip()}"
    )


def _prompt_reformulacion_seccion(seccion_nombre: str, seccion_texto: str, estilo_id: str) -> str:
    estilo = ESTILOS_REDACCION[estilo_id]
    return f"""Reescribe exclusivamente la sección {seccion_nombre} de un informe radiológico
siguiendo este estilo:

ESTILO OBJETIVO — {estilo['nombre']}
{estilo['instruccion']}

TEXTO ORIGINAL:
{seccion_texto}

REGLAS NO NEGOCIABLES:
- No agregues, quites ni cambies ningún hallazgo, medida, lateralidad o clasificación.
- Todo dato numérico, categoría (BI-RADS/PI-RADS/TNM/etc.) y lateralidad debe reaparecer idéntico.
- Cambia únicamente: estructura de oración, longitud, conectores, orden de exposición, registro léxico.
- Usa "osteoartrosis" (nunca "osteoartritis") y "desgarro" (nunca "ruptura"/"rasgadura").
- Devuelve SOLO el texto reescrito de la sección, sin encabezados, comillas ni comentarios.

Antes de responder, verifica mentalmente que cada dato clínico del original sigue presente."""


def reformular_seccion(seccion_nombre: str, seccion_texto: str, estilo_id: str) -> str:
    if not seccion_texto.strip():
        return seccion_texto
    cliente = obtener_cliente()
    respuesta = cliente.chat.completions.create(
        model=modelo_activo(),
        messages=[
            {"role": "system", "content": "Eres un editor experto de informes radiológicos en español."},
            {"role": "user", "content": _prompt_reformulacion_seccion(seccion_nombre, seccion_texto, estilo_id)},
        ],
        temperature=0.4,
    )
    return aplicar_terminologia(respuesta.choices[0].message.content.strip())


def _prompt_reformulacion_completa(informe_texto: str, estilo_id: str) -> str:
    estilo = ESTILOS_REDACCION[estilo_id]
    return f"""Reescribe el siguiente informe radiológico COMPLETO siguiendo este estilo:

ESTILO OBJETIVO — {estilo['nombre']}
{estilo['instruccion']}

INFORME ORIGINAL:
{informe_texto}

REGLAS NO NEGOCIABLES:
- Conserva exactamente las tres secciones (TÉCNICA, HALLAZGOS, CONCLUSIÓN) como encabezados
  en mayúsculas, cada una en su propia línea.
- No agregues, quites ni cambies ningún hallazgo, medida, lateralidad o clasificación.
- Todo dato numérico, categoría y lateralidad debe reaparecer idéntico al original.
- Cambia únicamente estructura, longitud, conectores y registro léxico — nunca el contenido clínico.
- Usa "osteoartrosis" (nunca "osteoartritis") y "desgarro" (nunca "ruptura"/"rasgadura").
- Debe leerse como si un radiólogo distinto, con ese estilo particular, hubiera redactado el
  mismo caso — mismo diagnóstico, distinta voz."""


def reformular_informe_completo(informe: dict, estilo_id: str) -> dict:
    cliente = obtener_cliente()
    texto_original = reconstruir_informe(informe)
    respuesta = cliente.chat.completions.create(
        model=modelo_activo(),
        messages=[
            {"role": "system", "content": "Eres un editor experto de informes radiológicos en español."},
            {"role": "user", "content": _prompt_reformulacion_completa(texto_original, estilo_id)},
        ],
        temperature=0.4,
    )
    return parsear_informe(respuesta.choices[0].message.content.strip())


# ══════════════════════════════════════════════════════════════════════════
# ESTADO DE SESIÓN
# ══════════════════════════════════════════════════════════════════════════

def init_estado():
    st.session_state.setdefault(
        "api_keys",
        {p: obtener_secreto(cfg["key_env"]) for p, cfg in PROVEEDORES.items()},
    )
    st.session_state.setdefault(
        "modelos_por_proveedor",
        {p: cfg["modelo_defecto"] for p, cfg in PROVEEDORES.items()},
    )
    # Proveedor inicial: el primero que ya tenga una key disponible.
    if "proveedor_actual" not in st.session_state:
        con_key = [p for p in ORDEN_PROVEEDORES if st.session_state.api_keys.get(p)]
        st.session_state.proveedor_actual = con_key[0] if con_key else ORDEN_PROVEEDORES[0]

    st.session_state.setdefault("dictado_actual", "")
    st.session_state.setdefault("informe", {"tecnica": "", "hallazgos": "", "conclusion": ""})
    st.session_state.setdefault("estilo_ultimo_aplicado", {})


def informe_esta_vacio() -> bool:
    inf = st.session_state.informe
    return not any((inf.get("tecnica"), inf.get("hallazgos"), inf.get("conclusion")))


def limpiar_para_nuevo_estudio():
    st.session_state.dictado_actual = ""
    st.session_state.informe = {"tecnica": "", "hallazgos": "", "conclusion": ""}
    st.session_state.estilo_ultimo_aplicado = {}


# ══════════════════════════════════════════════════════════════════════════
# ESTILO VISUAL
# ══════════════════════════════════════════════════════════════════════════

GOOGLE_FONTS_IMPORT = (
    "@import url('https://fonts.googleapis.com/css2?"
    "family=Fraunces:ital,opsz,wght@0,9..144,500;0,9..144,600;1,9..144,500&"
    "family=Inter:wght@400;500;600;700&"
    "family=JetBrains+Mono:wght@400;500;600&display=swap');"
)

# Textura de grano — imita el ruido de una placa radiográfica revelada.
# SVG feTurbulence codificado inline, aplicado a muy baja opacidad.
_GRANO_SVG = (
    "data:image/svg+xml;utf8,"
    "<svg xmlns='http://www.w3.org/2000/svg'>"
    "<filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.85' "
    "numOctaves='2' stitchTiles='stitch'/></filter>"
    "<rect width='100%25' height='100%25' filter='url(%23n)'/></svg>"
)


def inyectar_estilo():
    p = PALETA
    st.markdown(
        f"""
        <style>
        {GOOGLE_FONTS_IMPORT}

        :root {{
            --bg: {p['bg']}; --surface: {p['surface']}; --surface-alt: {p['surface_alt']};
            --surface-raised: {p['surface_raised']};
            --border: {p['border']}; --border-soft: {p['border_soft']};
            --text: {p['text']}; --muted: {p['muted']}; --muted-dim: {p['muted_dim']};
            --accent: {p['accent']}; --accent-strong: {p['accent_strong']};
            --accent-soft: {p['accent_soft']}; --accent-soft-2: {p['accent_soft_2']};
            --cian: {p['cian']}; --cian-soft: {p['cian_soft']};
        }}

        .stApp {{
            background-color: var(--bg);
            color: var(--text);
            font-family: {FUENTE_UI};
            position: relative;
        }}
        .stApp::before {{
            content: "";
            position: fixed; inset: 0; pointer-events: none; z-index: 0;
            background-image: url("{_GRANO_SVG}");
            opacity: 0.025; mix-blend-mode: overlay;
        }}
        .stApp::after {{
            content: "";
            position: fixed; inset: 0; pointer-events: none; z-index: 0;
            background: radial-gradient(ellipse 80% 55% at 50% -8%, {p['accent']}14, transparent 62%);
        }}
        .main .block-container {{ position: relative; z-index: 1; padding-top: 2.2rem; max-width: 980px; }}

        section[data-testid="stSidebar"] {{
            background-color: var(--surface); border-right: 1px solid var(--border-soft);
        }}
        section[data-testid="stSidebar"] .block-container {{ padding-top: 1.6rem; }}

        /* ── Encabezado / marca ─────────────────────────────────────── */
        .beam-marca {{
            font-family: {FUENTE_DISPLAY}; font-style: italic; font-weight: 600;
            font-size: 1.5rem; color: var(--text); letter-spacing: -0.01em; line-height: 1;
        }}
        .beam-marca span {{ color: var(--accent); font-style: normal; }}
        .beam-tagline {{
            font-size: 0.72rem; color: var(--muted); letter-spacing: 0.02em; margin-top: 3px;
        }}
        .beam-header {{
            display: flex; align-items: flex-start; justify-content: space-between;
            margin-bottom: 26px; padding-bottom: 18px; border-bottom: 1px solid var(--border-soft);
        }}
        .beam-titulo-app {{ font-size: 1.02rem; font-weight: 600; color: var(--text); letter-spacing: -0.01em; }}
        .beam-eyebrow {{
            font-family: {FUENTE_MONO}; font-size: 0.66rem; font-weight: 500; letter-spacing: 0.14em;
            text-transform: uppercase; color: var(--muted-dim); margin-bottom: 4px; display: block;
        }}
        .beam-chip-proveedor {{
            display: inline-flex; align-items: center; gap: 6px;
            font-family: {FUENTE_MONO}; font-size: 0.68rem; font-weight: 500; letter-spacing: 0.03em;
            color: var(--muted); background: var(--surface-alt); border: 1px solid var(--border);
            border-radius: 100px; padding: 5px 12px 5px 9px;
        }}
        .beam-chip-punto {{
            width: 6px; height: 6px; border-radius: 50%; background: var(--accent); flex-shrink: 0;
            box-shadow: 0 0 6px 1px var(--accent-soft);
        }}

        /* ── Inputs base ─────────────────────────────────────────────── */
        textarea, input[type="text"], input[type="password"] {{
            background-color: var(--surface) !important;
            color: var(--text) !important;
            border: 1px solid var(--border) !important;
            border-radius: 12px !important;
            font-family: {FUENTE_UI} !important;
        }}
        textarea:focus, input:focus {{
            border-color: var(--accent) !important;
            box-shadow: 0 0 0 3px var(--accent-soft) !important;
        }}
        [data-testid="stTextArea"] textarea {{ font-size: 0.93rem; line-height: 1.68; }}

        [data-testid="stWidgetLabel"] p {{
            font-family: {FUENTE_MONO} !important;
            font-size: 0.66rem !important; font-weight: 500 !important;
            letter-spacing: 0.12em !important; text-transform: uppercase !important;
            color: var(--muted-dim) !important;
        }}

        /* ── Botones ─────────────────────────────────────────────────── */
        div.stButton > button {{
            background-color: var(--surface-alt); color: var(--text);
            border: 1px solid var(--border); border-radius: 9px;
            font-weight: 500; font-size: 0.84rem; padding: 0.42rem 0.9rem;
            transition: border-color 120ms ease, color 120ms ease, background-color 120ms ease;
        }}
        div.stButton > button:hover {{ border-color: var(--accent); color: var(--accent-strong); }}
        div.stButton > button:disabled {{ opacity: 0.35; }}
        div.stButton > button[kind="primary"] {{
            background-color: var(--accent); color: #14110A; border: 1px solid var(--accent); font-weight: 600;
        }}
        div.stButton > button[kind="primary"]:hover {{
            filter: brightness(1.08); color: #14110A; border-color: var(--accent-strong);
        }}

        div[data-testid="stSelectbox"] > div {{
            background-color: var(--surface); border-radius: 10px; border-color: var(--border) !important;
        }}
        div[data-testid="stSelectbox"] label, div[data-testid="stExpander"] summary p {{ color: var(--muted) !important; }}

        [data-testid="stExpander"] {{
            background-color: var(--surface); border: 1px solid var(--border-soft); border-radius: 12px;
        }}

        hr {{ border-color: var(--border-soft) !important; }}
        ::selection {{ background: var(--accent-soft); color: var(--text); }}

        /* ── Tarjetas ────────────────────────────────────────────────── */
        .beam-tarjeta {{
            background-color: var(--surface); border: 1px solid var(--border-soft);
            border-radius: 16px; padding: 20px 22px 16px 22px; margin-bottom: 16px;
            position: relative; overflow: hidden;
        }}
        .beam-tarjeta-seccion {{ padding-left: 26px; }}
        .beam-tarjeta-seccion::before {{
            content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
            background: linear-gradient(180deg, var(--accent), {p['accent']}55);
        }}
        .beam-caja-captura {{
            background-color: var(--surface); border: 1px solid var(--border-soft);
            border-radius: 18px; padding: 16px 18px 12px 18px; margin-bottom: 26px;
            box-shadow: 0 0 0 1px transparent;
        }}

        .beam-seccion-encabezado {{
            display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 2px;
        }}
        .beam-seccion-badge {{
            font-family: {FUENTE_MONO}; font-size: 0.65rem; color: var(--muted-dim); letter-spacing: 0.04em;
        }}

        .beam-badge {{
            display: inline-block; font-family: {FUENTE_MONO};
            font-size: 0.64rem; font-weight: 500; letter-spacing: 0.06em; text-transform: uppercase;
            color: var(--accent); background: var(--accent-soft);
            border: 1px solid var(--accent-soft); border-radius: 6px; padding: 2px 8px; margin-left: 10px;
            vertical-align: middle;
        }}

        .beam-hint {{ font-size: 0.78rem; color: var(--muted-dim); }}

        .beam-vacio {{
            border: 1px dashed var(--border); border-radius: 16px; padding: 40px 24px;
            text-align: center; color: var(--muted-dim); font-size: 0.85rem; margin-top: 8px;
        }}

        div[data-testid="stTextArea"] textarea::-webkit-scrollbar,
        section[data-testid="stSidebar"]::-webkit-scrollbar {{ width: 8px; }}
        div[data-testid="stTextArea"] textarea::-webkit-scrollbar-thumb {{
            background: var(--border); border-radius: 8px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════
# DICTADO POR VOZ — Web Speech API nativa del navegador
# ══════════════════════════════════════════════════════════════════════════

def widget_dictado_voz(color_acento: str, etiqueta_objetivo: str, height: int = 60):
    html_code = f"""
    <div style="display:flex;align-items:center;gap:10px;font-family:sans-serif;">
      <button id="beam-mic-btn" title="Dictar" style="
          width:40px;height:40px;border-radius:50%;border:1px solid {color_acento}55;cursor:pointer;
          background:{color_acento};display:flex;align-items:center;justify-content:center;
          flex-shrink:0;transition:filter 120ms ease;">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="#14110A">
          <path d="M12 14a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v5a3 3 0 0 0 3 3z"/>
          <path d="M19 11a1 1 0 1 0-2 0 5 5 0 0 1-10 0 1 1 0 1 0-2 0 7 7 0 0 0 6 6.92V21a1 1 0 1 0 2 0v-3.08A7 7 0 0 0 19 11z"/>
        </svg>
      </button>
      <span id="beam-mic-estado" style="font-family:'JetBrains Mono',monospace;font-size:.68rem;
        letter-spacing:.04em;color:#8A8D95;text-transform:uppercase;">Dictar</span>
    </div>
    <style>
      @keyframes beam-pulse {{
        0%   {{ box-shadow: 0 0 0 0 {color_acento}66; }}
        70%  {{ box-shadow: 0 0 0 13px {color_acento}00; }}
        100% {{ box-shadow: 0 0 0 0 {color_acento}00; }}
      }}
      #beam-mic-btn.escuchando {{ animation: beam-pulse 1.3s infinite; }}
      #beam-mic-btn:hover {{ filter: brightness(1.1); }}
    </style>
    <script>
    (function() {{
      const btn = document.getElementById('beam-mic-btn');
      const estado = document.getElementById('beam-mic-estado');
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      const ETIQUETA = {etiqueta_objetivo!r};

      if (!SpeechRecognition) {{
        estado.textContent = 'No soportado';
        btn.disabled = true; btn.style.opacity = 0.4;
        return;
      }}

      function encontrarTextarea() {{
        const doc = window.parent.document;
        const contenedores = doc.querySelectorAll('[data-testid="stTextArea"]');
        for (const c of contenedores) {{
          if (c.innerText.includes(ETIQUETA)) return c.querySelector('textarea');
        }}
        return null;
      }}

      function escribir(texto) {{
        const ta = encontrarTextarea();
        if (!ta) return;
        const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
        setter.call(ta, texto);
        ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
      }}

      const recog = new SpeechRecognition();
      recog.lang = 'es-MX';
      recog.continuous = true;
      recog.interimResults = true;

      let escuchando = false, detenidoManual = false, base = '', finalAcum = '';

      btn.addEventListener('click', function() {{
        escuchando = !escuchando;
        if (escuchando) {{
          detenidoManual = false;
          const ta = encontrarTextarea();
          base = ta ? ta.value : '';
          finalAcum = '';
          recog.start();
          btn.classList.add('escuchando');
          estado.textContent = 'Escuchando…';
        }} else {{
          detenidoManual = true;
          recog.stop();
          btn.classList.remove('escuchando');
          estado.textContent = 'Dictar';
        }}
      }});

      recog.onresult = function(evento) {{
        let interino = '';
        for (let i = evento.resultIndex; i < evento.results.length; i++) {{
          const t = evento.results[i][0].transcript;
          if (evento.results[i].isFinal) finalAcum += t + ' ';
          else interino += t;
        }}
        const separador = base && !base.endsWith(' ') && !base.endsWith('\\n') ? ' ' : '';
        escribir((base + separador + finalAcum + interino).trim());
      }};
      recog.onerror = function(e) {{ estado.textContent = 'Error: ' + e.error; }};
      recog.onend = function() {{ if (escuchando && !detenidoManual) recog.start(); }};
    }})();
    </script>
    """
    components.html(html_code, height=height)


# ══════════════════════════════════════════════════════════════════════════
# COPIAR AL PORTAPAPELES
# ══════════════════════════════════════════════════════════════════════════

def boton_copiar(texto: str, etiqueta: str, key: str):
    texto_js = json.dumps(texto or "")
    html = f"""
    <button id="beam-copy-{key}" style="
        width:100%; background:{PALETA['surface_alt']}; color:{PALETA['text']};
        border:1px solid {PALETA['border']}; border-radius:9px;
        font-size:0.8rem; font-weight:500; padding:8px 10px; cursor:pointer;
        font-family:'Inter',sans-serif; transition:border-color 120ms ease;">{etiqueta}</button>
    <script>
    const b = document.getElementById('beam-copy-{key}');
    b.addEventListener('mouseenter', () => b.style.borderColor = '{PALETA["accent"]}');
    b.addEventListener('mouseleave', () => b.style.borderColor = '{PALETA["border"]}');
    b.addEventListener('click', function() {{
        navigator.clipboard.writeText({texto_js});
        const el = this;
        const original = el.innerText;
        el.innerText = '✓ Copiado';
        el.style.color = '{PALETA["accent_strong"]}';
        setTimeout(() => {{ el.innerText = original; el.style.color = '{PALETA["text"]}'; }}, 1400);
    }});
    </script>
    """
    components.html(html, height=44)


# ══════════════════════════════════════════════════════════════════════════
# BARRA DE CAPTURA (dictado o texto libre)
# ══════════════════════════════════════════════════════════════════════════

def renderizar_barra_captura() -> bool:
    st.markdown('<div class="beam-caja-captura">', unsafe_allow_html=True)

    col_txt, col_mic = st.columns([11, 1])
    with col_txt:
        st.session_state.dictado_actual = st.text_area(
            ETIQUETA_CAPTURA,
            value=st.session_state.dictado_actual,
            height=90,
            placeholder="Dicta o escribe los hallazgos del estudio…",
            key="dictado_actual_widget",
        )
    with col_mic:
        st.markdown("<div style='height:22px;'></div>", unsafe_allow_html=True)
        widget_dictado_voz(PALETA["accent"], etiqueta_objetivo=ETIQUETA_CAPTURA, height=64)

    col_btn, col_hint = st.columns([2, 6])
    with col_btn:
        generar = st.button(
            "Generar informe", type="primary", use_container_width=True,
            disabled=not st.session_state.dictado_actual.strip(),
        )
    with col_hint:
        st.markdown(
            '<div style="height:38px;display:flex;align-items:center;">'
            '<span class="beam-hint">'
            "La IA infiere estructuras normales no dictadas — nunca inventa patología."
            "</span></div>",
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)
    return generar


def generar_y_mostrar():
    contenedor = st.empty()
    acumulado = ""
    try:
        for fragmento in generar_informe_stream(st.session_state.dictado_actual):
            acumulado += fragmento
            contenedor.markdown(
                f'<div class="beam-tarjeta beam-tarjeta-seccion" style="white-space:pre-wrap;'
                f'font-size:0.92rem;line-height:1.65;">{acumulado}<span style="color:var(--accent);">▍</span></div>',
                unsafe_allow_html=True,
            )
        st.session_state.informe = parsear_informe(acumulado)
        contenedor.empty()
        st.rerun()
    except Exception as e:
        contenedor.empty()
        st.error(f"Error al generar el informe: {e}")


# ══════════════════════════════════════════════════════════════════════════
# SECCIONES EDITABLES + REFORMULACIÓN POR ESTILO
# ══════════════════════════════════════════════════════════════════════════

def _fila_reformulacion(clave: str, visible: str):
    col_sel, col_btn, col_copy = st.columns([5, 2, 2])

    with col_sel:
        estilo_id = st.selectbox(
            f"Estilo — {visible}",
            options=ORDEN_ESTILOS,
            format_func=lambda k: f"{ESTILOS_REDACCION[k]['nombre']} · {ESTILOS_REDACCION[k]['descripcion']}",
            key=f"estilo_{clave}",
            label_visibility="collapsed",
        )
    with col_btn:
        aplicar = st.button("Reformular", key=f"reformular_{clave}", use_container_width=True)
    with col_copy:
        boton_copiar(st.session_state.informe.get(clave, ""), "Copiar sección", key=clave)

    if aplicar:
        if not api_key_activa():
            st.error(f"Configura tu API key de {PROVEEDORES[st.session_state.proveedor_actual]['nombre']} en la barra lateral.")
            return
        with st.spinner(f"Reescribiendo {visible.lower()} — estilo {ESTILOS_REDACCION[estilo_id]['nombre']}…"):
            try:
                nuevo_texto = reformular_seccion(
                    NOMBRE_SECCION[clave], st.session_state.informe[clave], estilo_id,
                )
                st.session_state.informe[clave] = nuevo_texto
                st.session_state.estilo_ultimo_aplicado[clave] = estilo_id
                st.rerun()
            except Exception as e:
                st.error(f"No se pudo reformular: {e}")


def renderizar_editor():
    etiquetas = {"tecnica": "Técnica", "hallazgos": "Hallazgos", "conclusion": "Conclusión"}
    alturas = {"tecnica": 90, "hallazgos": 220, "conclusion": 130}

    for clave, visible in etiquetas.items():
        texto_previo = st.session_state.informe.get(clave, "")
        st.markdown('<div class="beam-tarjeta beam-tarjeta-seccion">', unsafe_allow_html=True)
        st.markdown(
            f'<div class="beam-seccion-encabezado"><span></span>'
            f'<span class="beam-seccion-badge">{len(texto_previo)} car.</span></div>',
            unsafe_allow_html=True,
        )
        texto_actual = st.text_area(
            visible,
            value=texto_previo,
            height=alturas[clave],
            key=f"texto_{clave}",
        )
        st.session_state.informe[clave] = texto_actual
        _fila_reformulacion(clave, visible)
        st.markdown("</div>", unsafe_allow_html=True)


def renderizar_barra_inferior():
    st.markdown('<div class="beam-tarjeta">', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns([4, 2, 2, 2])

    with col1:
        estilo_global = st.selectbox(
            "Estilo — informe completo",
            options=ORDEN_ESTILOS,
            format_func=lambda k: f"{ESTILOS_REDACCION[k]['nombre']} · {ESTILOS_REDACCION[k]['descripcion']}",
            key="estilo_global",
            label_visibility="collapsed",
        )
    with col2:
        aplicar_global = st.button("Reformular todo", use_container_width=True)
    with col3:
        boton_copiar(reconstruir_informe(st.session_state.informe), "Copiar informe", key="informe_completo")
    with col4:
        nuevo_estudio = st.button("＋ Nuevo estudio", use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)

    if aplicar_global:
        if not api_key_activa():
            st.error(f"Configura tu API key de {PROVEEDORES[st.session_state.proveedor_actual]['nombre']} en la barra lateral.")
        else:
            with st.spinner(f"Reescribiendo el informe completo — estilo {ESTILOS_REDACCION[estilo_global]['nombre']}…"):
                try:
                    st.session_state.informe = reformular_informe_completo(
                        st.session_state.informe, estilo_global,
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"No se pudo reformular el informe: {e}")

    if nuevo_estudio:
        limpiar_para_nuevo_estudio()
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════
# BARRA LATERAL — proveedor / modelo / API keys
# ══════════════════════════════════════════════════════════════════════════

def renderizar_sidebar():
    with st.sidebar:
        st.markdown(
            '<div class="beam-marca">BE<span>A</span>M</div>'
            '<div class="beam-tagline">Workspace de informes radiológicos</div>',
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height:18px;'></div>", unsafe_allow_html=True)

        st.markdown('<span class="beam-eyebrow">Proveedor de IA</span>', unsafe_allow_html=True)
        proveedor_id = st.selectbox(
            "Proveedor",
            options=ORDEN_PROVEEDORES,
            format_func=lambda p: PROVEEDORES[p]["nombre"],
            index=ORDEN_PROVEEDORES.index(st.session_state.proveedor_actual),
            label_visibility="collapsed",
        )
        st.session_state.proveedor_actual = proveedor_id
        proveedor_cfg = PROVEEDORES[proveedor_id]

        modelo_id = st.selectbox(
            "Modelo",
            options=list(proveedor_cfg["modelos"].keys()),
            format_func=lambda m: proveedor_cfg["modelos"][m],
            index=list(proveedor_cfg["modelos"].keys()).index(
                st.session_state.modelos_por_proveedor.get(proveedor_id, proveedor_cfg["modelo_defecto"])
            ),
            label_visibility="collapsed",
        )
        st.session_state.modelos_por_proveedor[proveedor_id] = modelo_id

        tiene_key = bool(st.session_state.api_keys.get(proveedor_id))
        with st.expander("Configuración", expanded=not tiene_key):
            for p in ORDEN_PROVEEDORES:
                cfg = PROVEEDORES[p]
                nueva_key = st.text_input(
                    f"{cfg['nombre']} API key",
                    value=st.session_state.api_keys.get(p, ""),
                    type="password",
                    placeholder=f"{cfg['key_env']}",
                    key=f"input_key_{p}",
                )
                st.session_state.api_keys[p] = nueva_key

        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
        estado_color = PALETA["accent"] if tiene_key else PALETA["muted_dim"]
        estado_txt = "conectado" if tiene_key else "sin API key"
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:7px;font-family:{FUENTE_MONO};'
            f'font-size:0.68rem;color:var(--muted);">'
            f'<span style="width:6px;height:6px;border-radius:50%;background:{estado_color};"></span>'
            f"{proveedor_cfg['nombre'].upper()} · {estado_txt}</div>",
            unsafe_allow_html=True,
        )

    return modelo_id


# ══════════════════════════════════════════════════════════════════════════
# APLICACIÓN PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════

def main():
    init_estado()
    inyectar_estilo()
    modelo_id = renderizar_sidebar()

    proveedor_nombre = PROVEEDORES[st.session_state.proveedor_actual]["nombre"]
    st.markdown(
        '<div class="beam-header">'
        '<div>'
        '<span class="beam-eyebrow">Nuevo estudio</span>'
        f'<span class="beam-titulo-app">Informe radiológico<span class="beam-badge">v3.0</span></span>'
        "</div>"
        f'<span class="beam-chip-proveedor"><span class="beam-chip-punto"></span>'
        f"{proveedor_nombre.upper()} · {modelo_id}</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    generar = renderizar_barra_captura()
    if generar:
        if not api_key_activa():
            st.error(f"Configura tu API key de {proveedor_nombre} en la barra lateral.")
        else:
            generar_y_mostrar()

    if not informe_esta_vacio():
        renderizar_editor()
        renderizar_barra_inferior()
    else:
        st.markdown(
            '<div class="beam-vacio">El informe aparecerá aquí, en secciones editables, '
            "en cuanto lo generes.</div>",
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
