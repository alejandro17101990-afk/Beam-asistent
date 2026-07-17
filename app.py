"""
BEAM — Workspace de informes radiológicos asistidos por IA

Requisitos:
    pip install streamlit openai

Ejecutar:
    streamlit run app.py
"""

import json
import os
import re
from typing import Iterator

import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI

# ══════════════════════════════════════════════════════════════════════════
# PROVEEDORES
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

PALETA = {
    "bg": "#0B0C0E",
    "surface": "#141518",
    "surface_alt": "#1B1C20",
    "border": "#26272B",
    "text": "#EDEDEF",
    "muted": "#8B8D93",
    "accent": "#D9A24B",
    "accent_soft": "#D9A24B26",
}

FUENTE_UI = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"

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
    "clinico": {"nombre": "Clínico directo", "descripcion": "Oraciones cortas, datos medibles por delante.",
        "instruccion": "Oraciones cortas (máximo ~20 palabras), voz activa cuando sea posible, cero adjetivos ornamentales, prioriza datos medibles sobre descripciones narrativas."},
    "academico": {"nombre": "Académico", "descripcion": "Registro de discusión de caso en sesión clínica.",
        "instruccion": "Oraciones compuestas con conectores subordinantes (dado que, en tanto que, lo cual sugiere), terminología completa sin abreviar, tono de discusión de caso en sesión clínica o ateneo."},
    "conciso": {"nombre": "Ultra conciso", "descripcion": "Mínima extensión posible sin perder datos.",
        "instruccion": "Reduce cada oración a su núcleo informativo. Elimina toda redundancia y frase de relleno. Objetivo: no más del 60% de la longitud original en caracteres, sin perder ni un solo dato clínico."},
    "elegante": {"nombre": "Elegante", "descripcion": "Fluido, con variación de estructura entre oraciones.",
        "instruccion": "Varía la longitud y estructura de las oraciones para evitar monotonía, usa transiciones fluidas entre ideas, mantiene precisión clínica sin sonar telegráfico ni sobrecargado."},
    "rsna": {"nombre": "Estilo RSNA (Radiology)", "descripcion": "Objetivo e impersonal, secuencia anatómica sistemática.",
        "instruccion": "Registro de journal RSNA: objetivo, impersonal, con secuencia anatómica sistemática (de superior a inferior o de proximal a distal), sin lenguaje coloquial."},
    "essr": {"nombre": "Estilo ESSR", "descripcion": "Preciso en grados/clasificaciones musculoesqueléticas.",
        "instruccion": "Registro europeo musculoesquelético: preciso en grados y clasificaciones (Goutallier, ICRS, Pfirrmann, etc.), frases breves y directas, sin narrativa innecesaria."},
    "ajr": {"nombre": "Estilo AJR", "descripcion": "Contextualiza antes de describir, cierra con implicancia clínica.",
        "instruccion": "Tono editorial de caso ilustrativo: contextualiza brevemente el hallazgo antes de describirlo en detalle, y cierra con su implicancia clínica explícita."},
    "profesor": {"nombre": "Profesor de alta especialidad", "descripcion": "Enseña el razonamiento diagnóstico sin extenderse.",
        "instruccion": "Redacta como si enseñaras el caso a un residente: menciona brevemente el razonamiento diagnóstico detrás del hallazgo principal (por qué esa impresión y no otra), sin extenderte más de una oración adicional por hallazgo relevante."},
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
    try:
        if nombre in st.secrets:
            return st.secrets[nombre]
    except Exception:
        pass
    return os.environ.get(nombre, "")


def api_key_activa() -> str:
    return st.session_state.api_keys.get(st.session_state.proveedor_actual, "")


def modelo_activo() -> str:
    proveedor = st.session_state.proveedor_actual
    return st.session_state.modelos_por_proveedor.get(proveedor, PROVEEDORES[proveedor]["modelo_defecto"])


def obtener_cliente() -> OpenAI:
    cfg = PROVEEDORES[st.session_state.proveedor_actual]
    return OpenAI(api_key=api_key_activa(), base_url=cfg["base_url"])


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


_PATRON_ENCABEZADO = re.compile(r"(?im)^\s*(T[ÉE]CNICA|HALLAZGOS|CONCLUSI[ÓO]N)\s*:?\s*$", re.MULTILINE)


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


def reformular_seccion(seccion_nombre: str, seccion_texto: str, estilo_id: str) -> str:
    if not seccion_texto.strip():
        return seccion_texto
    estilo = ESTILOS_REDACCION[estilo_id]
    prompt = f"""Reescribe exclusivamente la sección {seccion_nombre} de un informe radiológico
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
- Devuelve SOLO el texto reescrito de la sección, sin encabezados, comillas ni comentarios."""
    cliente = obtener_cliente()
    respuesta = cliente.chat.completions.create(
        model=modelo_activo(),
        messages=[
            {"role": "system", "content": "Eres un editor experto de informes radiológicos en español."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
    )
    return aplicar_terminologia(respuesta.choices[0].message.content.strip())


def reformular_informe_completo(informe: dict, estilo_id: str) -> dict:
    estilo = ESTILOS_REDACCION[estilo_id]
    texto_original = reconstruir_informe(informe)
    prompt = f"""Reescribe el siguiente informe radiológico COMPLETO siguiendo este estilo:

ESTILO OBJETIVO — {estilo['nombre']}
{estilo['instruccion']}

INFORME ORIGINAL:
{texto_original}

REGLAS NO NEGOCIABLES:
- Conserva exactamente las tres secciones (TÉCNICA, HALLAZGOS, CONCLUSIÓN) como encabezados
  en mayúsculas, cada una en su propia línea.
- No agregues, quites ni cambies ningún hallazgo, medida, lateralidad o clasificación.
- Todo dato numérico, categoría y lateralidad debe reaparecer idéntico al original.
- Cambia únicamente estructura, longitud, conectores y registro léxico — nunca el contenido clínico.
- Usa "osteoartrosis" (nunca "osteoartritis") y "desgarro" (nunca "ruptura"/"rasgadura")."""
    cliente = obtener_cliente()
    respuesta = cliente.chat.completions.create(
        model=modelo_activo(),
        messages=[
            {"role": "system", "content": "Eres un editor experto de informes radiológicos en español."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
    )
    return parsear_informe(respuesta.choices[0].message.content.strip())


# ══════════════════════════════════════════════════════════════════════════
# ESTADO
# ══════════════════════════════════════════════════════════════════════════

def init_estado():
    if "api_keys" not in st.session_state:
        st.session_state.api_keys = {p: obtener_secreto(cfg["key_env"]) for p, cfg in PROVEEDORES.items()}
    if "modelos_por_proveedor" not in st.session_state:
        st.session_state.modelos_por_proveedor = {p: cfg["modelo_defecto"] for p, cfg in PROVEEDORES.items()}
    if "proveedor_actual" not in st.session_state:
        con_key = [p for p in ORDEN_PROVEEDORES if st.session_state.api_keys.get(p)]
        st.session_state.proveedor_actual = con_key[0] if con_key else ORDEN_PROVEEDORES[0]
    st.session_state.setdefault("dictado_actual", "")
    st.session_state.setdefault("informe", {"tecnica": "", "hallazgos": "", "conclusion": ""})


def informe_esta_vacio() -> bool:
    inf = st.session_state.informe
    return not any((inf.get("tecnica"), inf.get("hallazgos"), inf.get("conclusion")))


def limpiar_para_nuevo_estudio():
    st.session_state.dictado_actual = ""
    st.session_state.informe = {"tecnica": "", "hallazgos": "", "conclusion": ""}


# ══════════════════════════════════════════════════════════════════════════
# ESTILO VISUAL (CSS simple, sin capas superpuestas ni fuentes externas
# adicionales — solo Google Fonts "Inter", igual que la versión anterior
# que sí funcionaba)
# ══════════════════════════════════════════════════════════════════════════

def inyectar_estilo():
    p = PALETA
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        :root {{
            --bg: {p['bg']}; --surface: {p['surface']}; --surface-alt: {p['surface_alt']};
            --border: {p['border']}; --text: {p['text']}; --muted: {p['muted']};
            --accent: {p['accent']}; --accent-soft: {p['accent_soft']};
        }}

        .stApp {{ background-color: var(--bg); color: var(--text); font-family: {FUENTE_UI}; }}

        section[data-testid="stSidebar"] {{
            background-color: var(--surface); border-right: 1px solid var(--border);
        }}

        .beam-header {{ display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 4px; }}
        .beam-titulo-app {{ font-size: 1.05rem; font-weight: 600; color: var(--text); letter-spacing: -0.01em; }}
        .beam-subtitulo-app {{ font-size: 0.78rem; color: var(--muted); }}

        textarea, input[type="text"], input[type="password"] {{
            background-color: var(--surface) !important;
            color: var(--text) !important;
            border: 1px solid var(--border) !important;
            border-radius: 10px !important;
            font-family: {FUENTE_UI} !important;
        }}
        textarea:focus, input:focus {{
            border-color: var(--accent) !important;
            box-shadow: 0 0 0 3px var(--accent-soft) !important;
        }}
        [data-testid="stTextArea"] textarea {{ font-size: 0.93rem; line-height: 1.65; }}

        [data-testid="stWidgetLabel"] p {{
            font-size: 0.72rem !important; font-weight: 600 !important;
            letter-spacing: 0.1em !important; text-transform: uppercase !important;
            color: var(--muted) !important;
        }}

        div.stButton > button {{
            background-color: var(--surface-alt); color: var(--text);
            border: 1px solid var(--border); border-radius: 8px;
            font-weight: 500; font-size: 0.84rem; padding: 0.4rem 0.9rem;
        }}
        div.stButton > button:hover {{ border-color: var(--accent); color: var(--accent); }}
        div.stButton > button[kind="primary"] {{
            background-color: var(--accent); color: #14110A; border: none; font-weight: 600;
        }}
        div.stButton > button[kind="primary"]:hover {{ filter: brightness(1.08); color: #14110A; }}

        div[data-testid="stSelectbox"] > div {{ background-color: var(--surface); border-radius: 8px; }}
        hr {{ border-color: var(--border) !important; }}

        .beam-tarjeta {{
            background-color: var(--surface); border: 1px solid var(--border);
            border-radius: 14px; padding: 18px 20px; margin-bottom: 14px;
        }}
        .beam-caja-captura {{
            background-color: var(--surface); border: 1px solid var(--border);
            border-radius: 14px; padding: 14px 16px 10px 16px; margin-bottom: 22px;
        }}
        .beam-badge {{
            display: inline-block; font-size: 0.68rem; font-weight: 600;
            letter-spacing: 0.05em; text-transform: uppercase;
            color: var(--accent); background: var(--accent-soft);
            border-radius: 6px; padding: 2px 8px; margin-left: 8px;
        }}
        .beam-chip {{
            display: inline-flex; align-items: center; gap: 6px; font-size: 0.72rem;
            color: var(--muted); background: var(--surface-alt); border: 1px solid var(--border);
            border-radius: 100px; padding: 4px 10px;
        }}
        .beam-punto {{ width: 6px; height: 6px; border-radius: 50%; background: var(--accent); }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════
# DICTADO POR VOZ — Web Speech API nativa del navegador
# ══════════════════════════════════════════════════════════════════════════

def widget_dictado_voz(color_acento: str, etiqueta_objetivo: str, height: int = 56):
    html_code = f"""
    <div style="display:flex;align-items:center;gap:10px;font-family:sans-serif;">
      <button id="beam-mic-btn" title="Dictar" style="
          width:38px;height:38px;border-radius:50%;border:none;cursor:pointer;
          background:{color_acento};display:flex;align-items:center;justify-content:center;
          flex-shrink:0;">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="#14110A">
          <path d="M12 14a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v5a3 3 0 0 0 3 3z"/>
          <path d="M19 11a1 1 0 1 0-2 0 5 5 0 0 1-10 0 1 1 0 1 0-2 0 7 7 0 0 0 6 6.92V21a1 1 0 1 0 2 0v-3.08A7 7 0 0 0 19 11z"/>
        </svg>
      </button>
      <span id="beam-mic-estado" style="font-size:.8rem;color:#8B8D93;">Dictar hallazgos</span>
    </div>
    <style>
      @keyframes beam-pulse {{
        0%   {{ box-shadow: 0 0 0 0 {color_acento}80; }}
        70%  {{ box-shadow: 0 0 0 12px {color_acento}00; }}
        100% {{ box-shadow: 0 0 0 0 {color_acento}00; }}
      }}
      #beam-mic-btn.escuchando {{ animation: beam-pulse 1.3s infinite; }}
    </style>
    <script>
    (function() {{
      const btn = document.getElementById('beam-mic-btn');
      const estado = document.getElementById('beam-mic-estado');
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      const ETIQUETA = {etiqueta_objetivo!r};

      if (!SpeechRecognition) {{
        estado.textContent = 'Dictado no soportado (usa Chrome o Edge)';
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
          estado.textContent = 'Dictar hallazgos';
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
        border:1px solid {PALETA['border']}; border-radius:8px;
        font-size:0.8rem; font-weight:500; padding:7px 10px; cursor:pointer;
        font-family:sans-serif;">{etiqueta}</button>
    <script>
    document.getElementById('beam-copy-{key}').addEventListener('click', function() {{
        navigator.clipboard.writeText({texto_js});
        const el = this;
        const original = el.innerText;
        el.innerText = '✓ Copiado';
        setTimeout(() => {{ el.innerText = original; }}, 1400);
    }});
    </script>
    """
    components.html(html, height=42)


# ══════════════════════════════════════════════════════════════════════════
# BARRA DE CAPTURA
# ══════════════════════════════════════════════════════════════════════════

def renderizar_barra_captura() -> bool:
    st.markdown('<div class="beam-caja-captura">', unsafe_allow_html=True)

    col_txt, col_mic = st.columns([11, 1])
    with col_txt:
        st.session_state.dictado_actual = st.text_area(
            ETIQUETA_CAPTURA,
            value=st.session_state.dictado_actual,
            height=88,
            placeholder="Dicta o escribe los hallazgos del estudio…",
            key="dictado_actual_widget",
        )
    with col_mic:
        st.markdown("<div style='height:22px;'></div>", unsafe_allow_html=True)
        widget_dictado_voz(PALETA["accent"], etiqueta_objetivo=ETIQUETA_CAPTURA, height=60)

    col_btn, col_hint = st.columns([2, 6])
    with col_btn:
        generar = st.button(
            "Generar informe", type="primary", use_container_width=True,
            disabled=not st.session_state.dictado_actual.strip(),
        )
    with col_hint:
        st.markdown(
            '<div style="height:38px;display:flex;align-items:center;">'
            '<span style="font-size:.78rem;color:var(--muted);">'
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
                f'<div class="beam-tarjeta" style="white-space:pre-wrap;font-size:0.92rem;'
                f'line-height:1.6;">{acumulado}▍</div>',
                unsafe_allow_html=True,
            )
        st.session_state.informe = parsear_informe(acumulado)
        contenedor.empty()
        st.rerun()
    except Exception as e:
        contenedor.empty()
        st.error(f"Error al generar el informe: {e}")


# ══════════════════════════════════════════════════════════════════════════
# EDITOR
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
        with st.spinner(f"Reescribiendo {visible.lower()}…"):
            try:
                nuevo_texto = reformular_seccion(NOMBRE_SECCION[clave], st.session_state.informe[clave], estilo_id)
                st.session_state.informe[clave] = nuevo_texto
                st.rerun()
            except Exception as e:
                st.error(f"No se pudo reformular: {e}")


def renderizar_editor():
    etiquetas = {"tecnica": "Técnica", "hallazgos": "Hallazgos", "conclusion": "Conclusión"}
    alturas = {"tecnica": 90, "hallazgos": 220, "conclusion": 130}

    for clave, visible in etiquetas.items():
        st.markdown('<div class="beam-tarjeta">', unsafe_allow_html=True)
        texto_actual = st.text_area(
            visible,
            value=st.session_state.informe.get(clave, ""),
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
            with st.spinner("Reescribiendo el informe completo…"):
                try:
                    st.session_state.informe = reformular_informe_completo(st.session_state.informe, estilo_global)
                    st.rerun()
                except Exception as e:
                    st.error(f"No se pudo reformular el informe: {e}")

    if nuevo_estudio:
        limpiar_para_nuevo_estudio()
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════

def renderizar_sidebar():
    modelo_id = None
    with st.sidebar:
        st.markdown('<div class="beam-titulo-app">BEAM</div>', unsafe_allow_html=True)
        st.markdown('<div class="beam-subtitulo-app">Workspace de informes radiológicos</div>', unsafe_allow_html=True)
        st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

        proveedor_id = st.selectbox(
            "Proveedor de IA",
            options=ORDEN_PROVEEDORES,
            format_func=lambda p: PROVEEDORES[p]["nombre"],
            index=ORDEN_PROVEEDORES.index(st.session_state.proveedor_actual),
        )
        st.session_state.proveedor_actual = proveedor_id
        cfg = PROVEEDORES[proveedor_id]

        modelo_id = st.selectbox(
            "Modelo",
            options=list(cfg["modelos"].keys()),
            format_func=lambda m: cfg["modelos"][m],
            index=list(cfg["modelos"].keys()).index(
                st.session_state.modelos_por_proveedor.get(proveedor_id, cfg["modelo_defecto"])
            ),
        )
        st.session_state.modelos_por_proveedor[proveedor_id] = modelo_id

        tiene_key = bool(st.session_state.api_keys.get(proveedor_id))
        with st.expander("Configuración", expanded=not tiene_key):
            for p in ORDEN_PROVEEDORES:
                pcfg = PROVEEDORES[p]
                st.session_state.api_keys[p] = st.text_input(
                    f"{pcfg['nombre']} API key",
                    value=st.session_state.api_keys.get(p, ""),
                    type="password",
                    placeholder=pcfg["key_env"],
                    key=f"input_key_{p}",
                )

        estado_color = PALETA["accent"] if tiene_key else "#5C5E64"
        estado_txt = "conectado" if tiene_key else "sin API key"
        st.markdown(
            f'<span class="beam-chip"><span class="beam-punto" style="background:{estado_color};"></span>'
            f"{cfg['nombre']} · {estado_txt}</span>",
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
        '<span class="beam-titulo-app">Nuevo estudio<span class="beam-badge">BEAM</span></span>'
        f'<span class="beam-chip"><span class="beam-punto"></span>{proveedor_nombre} · {modelo_id}</span>'
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
            '<p style="color:var(--muted);font-size:.85rem;">'
            "El informe aparecerá aquí, en secciones editables, en cuanto lo generes."
            "</p>",
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
