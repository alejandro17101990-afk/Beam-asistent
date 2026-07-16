"""
BEAM — Asistente Conversacional de Interpretación Radiológica
Interfaz de chat (estilo ChatGPT / Claude / Gemini) para dictado, redacción
y edición iterativa de informes radiológicos estructurados
(TÉCNICA / HALLAZGOS / CONCLUSIÓN).

Modelo de generación: DeepSeek (deepseek-chat / deepseek-reasoner), vía API
compatible con OpenAI (base_url distinto).

Dictado por voz: 100% en el navegador, usando la Web Speech API nativa de
Chrome/Edge (webkitSpeechRecognition). No requiere ningún paquete de Python
adicional ni ninguna API key: el reconocimiento corre del lado del cliente
y el texto se escribe en tiempo real en el cuadro de chat.

Estilo personalizado: puedes subir un informe propio (.docx o .txt) como
plantilla; BEAM lo usará como referencia de tu estilo de redacción.

Requisitos:
    pip install streamlit openai python-docx

Ejecutar:
    streamlit run app.py
"""

import os
import io
import datetime

import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI

try:
    from docx import Document
    DOCX_DISPONIBLE = True
except ImportError:
    DOCX_DISPONIBLE = False

# ──────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN GENERAL
# ──────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="BEAM · Asistente Radiológico",
    page_icon="🩻",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
MODELOS_DEEPSEEK = {
    "deepseek-chat": "DeepSeek Chat (V3)",
    "deepseek-reasoner": "DeepSeek Reasoner (R1)",
}

TERMINOLOGIA_CORRECTA = {
    "osteoartritis": "osteoartrosis",
    "ruptura": "desgarro",
    "rasgadura": "desgarro",
}

SYSTEM_PROMPT = """Eres BEAM, un asistente conversacional experto en redacción e interpretación
de informes radiológicos, equivalente a un radiólogo con amplia experiencia clínica en un
contexto mexicano. Trabajas dentro de un chat continuo: el radiólogo puede dictar un estudio,
pedirte que generes el informe, y luego pedirte ajustes, ampliaciones, correcciones de estilo,
comparaciones con estudios previos, explicaciones sobre clasificaciones, reformulaciones
alternativas, o cualquier otra consulta relacionada con el caso. Responde siempre en español.

CUANDO GENERES UN INFORME RADIOLÓGICO, usa exclusivamente estas tres secciones, en mayúsculas
como encabezado, en prosa narrativa continua (nunca listas ni fragmentos telegráficos):

TÉCNICA
HALLAZGOS
CONCLUSIÓN

NIVEL DE DETALLE Y CRITERIO CLÍNICO (muy importante):
- Redacta como lo haría un radiólogo experto dictando un caso completo, no como una simple
  transcripción de lo que el usuario dictó.
- El radiólogo normalmente solo te dictará los hallazgos POSITIVOS o relevantes. A partir de
  ahí, debes completar tú, de forma sistemática, la descripción del resto de las estructuras
  que se evalúan de rutina en ese tipo de estudio y región anatómica (revisión por sistemas /
  "negativa pertinente"), describiéndolas como normales, EXCEPTO cuando el dictado indique
  lo contrario o cuando la técnica descrita no permita evaluarlas (en cuyo caso acláralo).
  Por ejemplo: si te dictan solo "quiste renal derecho de 2 cm" en un estudio de abdomen,
  la sección HALLAZGOS debe además describir de forma normal el resto de estructuras
  habitualmente evaluadas en ese estudio (hígado, vía biliar, páncreas, bazo, riñón
  contralateral, retroperitoneo, etc., según la modalidad y el protocolo), no limitarse a
  mencionar únicamente el quiste.
- NUNCA inventes hallazgos PATOLÓGICOS que no estén mencionados o claramente implícitos en el
  dictado. La inferencia permitida es únicamente hacia la normalidad de estructuras no
  mencionadas explícitamente, nunca hacia nuevas patologías.
- La CONCLUSIÓN debe ser concisa y limitarse a los hallazgos clínicamente relevantes (no repitas
  ahí la revisión de estructuras normales); prioriza por relevancia clínica cuando haya más de
  un hallazgo, y usa lenguaje de cierre diagnóstico apropiado (correlación clínica, sugerencias
  de seguimiento o estudios adicionales cuando corresponda).

Reglas terminológicas estrictas (aplican siempre, en informes y en conversación):
- Usa "osteoartrosis", nunca "osteoartritis".
- Usa "desgarro", nunca "ruptura" o "rasgadura" (tendón/menisco).
- Mantén un registro clínico formal, preciso y conciso.
- Si el dictado o el caso involucra sistemas de clasificación (BI-RADS, PI-RADS, TI-RADS,
  LI-RADS, Kellgren-Lawrence, Pfirrmann, Stoller, ICRS, Fleischner, Spetzler-Martin, TOAST, AAST),
  inclúyelos correctamente en la CONCLUSIÓN, con el grado/categoría correspondiente.

REFORMULACIONES Y ALTERNATIVAS: si el radiólogo pide "alternativas", "otras opciones" u
"otras formas de redactar" para HALLAZGOS, CONCLUSIÓN, o el informe completo, genera 2 o 3
versiones distintas, numeradas claramente (Opción 1, Opción 2, ...), que preserven exactamente
el mismo contenido clínico (mismos hallazgos, mismo grado/categoría de clasificación si aplica)
mostrando solo variación de estilo, orden y construcción de las frases — nunca cambies ni el
diagnóstico ni el sentido clínico entre opciones.

CUANDO CONVERSES (ediciones, dudas, comparaciones, explicaciones): responde de forma directa y
clínica, sin preámbulos innecesarios. Si el radiólogo pide un cambio sobre un informe ya
generado (que no sea una solicitud explícita de alternativas), entrega el informe completo
actualizado (no solo el fragmento cambiado), salvo que pida explícitamente solo una explicación.

Si el mensaje del usuario es claramente un dictado (texto libre describiendo un estudio de
imagen), genera directamente el informe estructurado y detallado, sin pedir confirmación.
"""

# ──────────────────────────────────────────────────────────────────────────
# TEMAS DE COLOR Y TIPOGRAFÍAS
# ──────────────────────────────────────────────────────────────────────────

TEMAS = {
    "Dorado (original)": {
        "accent": "#E8B84B", "bg": "#111112", "surface": "#18181B",
        "border": "#2A2A2E", "text": "#E8E8E8", "muted": "#9A9A9E",
    },
    "Esmeralda": {
        "accent": "#34D399", "bg": "#0F1512", "surface": "#161C19",
        "border": "#233029", "text": "#E5EFE9", "muted": "#8FA79B",
    },
    "Zafiro": {
        "accent": "#5B9DF9", "bg": "#0E1116", "surface": "#161A21",
        "border": "#232838", "text": "#E6EAF2", "muted": "#8C97AD",
    },
    "Violeta": {
        "accent": "#B893F0", "bg": "#131018", "surface": "#1B1622",
        "border": "#2C2436", "text": "#ECE6F2", "muted": "#A497AF",
    },
    "Grafito claro": {
        "accent": "#C6922A", "bg": "#F7F7F5", "surface": "#FFFFFF",
        "border": "#E3E3E0", "text": "#1A1A1A", "muted": "#6B6B68",
    },
}

FUENTES = {
    "Inter (sans, default)": "'Inter', sans-serif",
    "Space Grotesk (sans)": "'Space Grotesk', sans-serif",
    "Sistema (estilo Söhne/SF)": "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    "JetBrains Mono (mono)": "'JetBrains Mono', monospace",
    "IBM Plex Mono (mono)": "'IBM Plex Mono', monospace",
}

GOOGLE_FONTS_IMPORT = (
    "@import url('https://fonts.googleapis.com/css2?"
    "family=Inter:wght@400;500;600;700&"
    "family=Space+Grotesk:wght@400;500;600;700&"
    "family=JetBrains+Mono:wght@400;500;600&"
    "family=IBM+Plex+Mono:wght@400;500;600&"
    "display=swap');"
)

# ──────────────────────────────────────────────────────────────────────────
# ESTADO DE SESIÓN
# ──────────────────────────────────────────────────────────────────────────

def _init_estado():
    if "mensajes" not in st.session_state:
        st.session_state.mensajes = [
            {
                "role": "assistant",
                "content": (
                    "Hola, soy **BEAM**. Dicta o pega la descripción de un estudio y te "
                    "genero el informe (TÉCNICA / HALLAZGOS / CONCLUSIÓN). También puedes "
                    "pedirme ajustes, comparaciones o dudas sobre clasificaciones, todo en "
                    "esta misma conversación."
                ),
            }
        ]
    st.session_state.setdefault("deepseek_api_key", os.environ.get("DEEPSEEK_API_KEY", ""))
    st.session_state.setdefault("plantilla_texto", "")
    st.session_state.setdefault("tema_nombre", "Dorado (original)")
    st.session_state.setdefault("fuente_nombre", "Inter (sans, default)")
    st.session_state.setdefault(
        "color_acento_custom", TEMAS[st.session_state.get("tema_nombre", "Dorado (original)")]["accent"]
    )


def aplicar_terminologia(texto: str) -> str:
    for incorrecto, correcto in TERMINOLOGIA_CORRECTA.items():
        texto = texto.replace(incorrecto, correcto)
        texto = texto.replace(incorrecto.capitalize(), correcto.capitalize())
    return texto


def obtener_cliente_deepseek() -> OpenAI:
    return OpenAI(api_key=st.session_state.deepseek_api_key, base_url=DEEPSEEK_BASE_URL)


# ──────────────────────────────────────────────────────────────────────────
# ESTILO — TEMA DINÁMICO (COLOR + TIPOGRAFÍA)
# ──────────────────────────────────────────────────────────────────────────

def inyectar_estilo(tema: dict, fuente_css: str):
    st.markdown(
        f"""
        <style>
        {GOOGLE_FONTS_IMPORT}

        :root {{
            --accent: {tema['accent']};
            --bg: {tema['bg']};
            --surface: {tema['surface']};
            --border: {tema['border']};
            --text: {tema['text']};
            --muted: {tema['muted']};
        }}

        .stApp {{
            background-color: var(--bg);
            color: var(--text);
            font-family: {fuente_css};
        }}

        section[data-testid="stSidebar"] {{
            background-color: var(--surface);
            border-right: 1px solid var(--border);
        }}

        h1, h2, h3, .titulo-beam {{
            font-family: {fuente_css};
        }}

        .titulo-beam {{
            font-weight: 700;
            font-size: 1.7rem;
            color: var(--accent);
            letter-spacing: 0.5px;
        }}
        .subtitulo-beam {{
            color: var(--muted);
            font-size: 0.85rem;
            margin-bottom: 1.2rem;
        }}

        [data-testid="stChatMessage"] {{
            background-color: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            font-family: {fuente_css};
            font-size: 0.94rem;
            line-height: 1.65;
            color: var(--text);
        }}

        div.stButton > button, div.stDownloadButton > button {{
            background-color: var(--accent);
            color: var(--bg);
            border: none;
            border-radius: 8px;
            font-weight: 600;
            font-family: {fuente_css};
        }}
        div.stButton > button:hover, div.stDownloadButton > button:hover {{
            filter: brightness(1.1);
            color: var(--bg);
        }}

        [data-testid="stChatInput"] textarea {{
            font-family: {fuente_css};
        }}

        .swatch-preview {{
            display: inline-block;
            width: 14px; height: 14px;
            border-radius: 4px;
            margin-right: 6px;
            vertical-align: middle;
            border: 1px solid var(--border);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────────
# DICTADO POR VOZ — WEB SPEECH API NATIVA DEL NAVEGADOR (SIN INSTALAR NADA)
# ──────────────────────────────────────────────────────────────────────────

def widget_dictado_voz(color_acento: str):
    """Ícono de micrófono con animación en vivo. Usa `webkitSpeechRecognition`
    (Chrome/Edge) para transcribir en tiempo real y escribe el resultado
    directamente en el cuadro de chat de Streamlit. No requiere backend."""
    html_code = f"""
    <div id="beam-mic-wrap" style="display:flex;align-items:center;gap:10px;
         font-family:sans-serif;padding:4px 2px 10px 2px;">
      <button id="beam-mic-btn" title="Dictar" style="
          width:46px;height:46px;border-radius:50%;border:none;cursor:pointer;
          background:{color_acento};display:flex;align-items:center;justify-content:center;
          flex-shrink:0;">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="#111">
          <path d="M12 14a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v5a3 3 0 0 0 3 3z"/>
          <path d="M19 11a1 1 0 1 0-2 0 5 5 0 0 1-10 0 1 1 0 1 0-2 0 7 7 0 0 0 6 6.92V21a1 1 0 1 0 2 0v-3.08A7 7 0 0 0 19 11z"/>
        </svg>
      </button>
      <span id="beam-mic-estado" style="font-size:.85rem;color:#9A9A9E;">
        Toca para dictar por voz
      </span>
    </div>

    <style>
      @keyframes beam-pulse {{
        0%   {{ box-shadow: 0 0 0 0 {color_acento}80; }}
        70%  {{ box-shadow: 0 0 0 14px {color_acento}00; }}
        100% {{ box-shadow: 0 0 0 0 {color_acento}00; }}
      }}
      #beam-mic-btn.escuchando {{
        animation: beam-pulse 1.3s infinite;
      }}
    </style>

    <script>
    (function() {{
      const btn = document.getElementById('beam-mic-btn');
      const estado = document.getElementById('beam-mic-estado');
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

      if (!SpeechRecognition) {{
        estado.textContent = 'Tu navegador no soporta dictado por voz (usa Chrome o Edge).';
        btn.disabled = true;
        btn.style.opacity = 0.4;
        return;
      }}

      const recog = new SpeechRecognition();
      recog.lang = 'es-MX';
      recog.continuous = true;
      recog.interimResults = true;

      let escuchando = false;
      let detenidoManualmente = false;
      let transcriptoFinal = '';

      function setTextoStreamlit(texto) {{
        try {{
          const doc = window.parent.document;
          const textarea = doc.querySelector('[data-testid="stChatInput"] textarea');
          if (!textarea) return;
          const setter = Object.getOwnPropertyDescriptor(
            window.HTMLTextAreaElement.prototype, 'value'
          ).set;
          setter.call(textarea, texto);
          textarea.dispatchEvent(new Event('input', {{ bubbles: true }}));
        }} catch (e) {{ console.error('BEAM voz:', e); }}
      }}

      recog.onresult = function(evento) {{
        let interino = '';
        for (let i = evento.resultIndex; i < evento.results.length; i++) {{
          const texto = evento.results[i][0].transcript;
          if (evento.results[i].isFinal) {{
            transcriptoFinal += texto + ' ';
          }} else {{
            interino += texto;
          }}
        }}
        setTextoStreamlit((transcriptoFinal + interino).trim());
      }};

      recog.onerror = function(e) {{
        estado.textContent = 'Error de reconocimiento: ' + e.error;
      }};

      recog.onend = function() {{
        if (escuchando && !detenidoManualmente) {{
          recog.start();  // el navegador a veces cierra solo; lo reanuda
        }}
      }};

      btn.addEventListener('click', function() {{
        escuchando = !escuchando;
        if (escuchando) {{
          detenidoManualmente = false;
          transcriptoFinal = '';
          setTextoStreamlit('');
          recog.start();
          btn.classList.add('escuchando');
          estado.textContent = 'Escuchando… toca de nuevo para detener';
        }} else {{
          detenidoManualmente = true;
          recog.stop();
          btn.classList.remove('escuchando');
          estado.textContent = 'Toca para dictar por voz';
        }}
      }});
    }})();
    </script>
    """
    components.html(html_code, height=64)


# ──────────────────────────────────────────────────────────────────────────
# PLANTILLA DE ESTILO DEL RADIÓLOGO
# ──────────────────────────────────────────────────────────────────────────

def extraer_texto_plantilla(archivo) -> str:
    """Extrae el texto de un informe subido como referencia de estilo (.docx o .txt)."""
    nombre = archivo.name.lower()
    if nombre.endswith(".docx"):
        if not DOCX_DISPONIBLE:
            raise RuntimeError("Instala `python-docx` para leer archivos .docx.")
        documento = Document(archivo)
        parrafos = [p.text for p in documento.paragraphs if p.text.strip()]
        return "\n".join(parrafos)
    return archivo.read().decode("utf-8", errors="ignore")


def es_informe(texto: str) -> bool:
    """Determina si un mensaje del asistente contiene un informe estructurado completo."""
    t = texto.upper()
    return "HALLAZGOS" in t and "CONCLUSIÓN" in t


def construir_system_prompt() -> str:
    prompt = SYSTEM_PROMPT
    plantilla = st.session_state.get("plantilla_texto", "")
    if plantilla:
        fragmento = plantilla[:6000]
        prompt += (
            "\n\nEl radiólogo ha compartido uno de sus informes previos como referencia de su "
            "estilo personal de redacción (vocabulario habitual, orden interno de las secciones, "
            "nivel de detalle, giros de frase). Adapta la redacción de TÉCNICA, HALLAZGOS y "
            "CONCLUSIÓN a ese estilo siempre que sea coherente con las reglas terminológicas "
            "anteriores, sin copiar datos clínicos de este ejemplo (corresponde a otro paciente, "
            "es solo una referencia de forma):\n\n"
            f"--- EJEMPLO DE ESTILO DEL RADIÓLOGO ---\n{fragmento}\n--- FIN DEL EJEMPLO ---"
        )
    return prompt


# ──────────────────────────────────────────────────────────────────────────
# GENERACIÓN DE RESPUESTA (CHAT, CON STREAMING, DEEPSEEK)
# ──────────────────────────────────────────────────────────────────────────

def generar_respuesta(modelo: str):
    cliente = obtener_cliente_deepseek()

    historial_api = [{"role": "system", "content": construir_system_prompt()}] + [
        {"role": m["role"], "content": m["content"]} for m in st.session_state.mensajes
    ]

    stream = cliente.chat.completions.create(
        model=modelo,
        messages=historial_api,
        temperature=0.2,
        stream=True,
    )

    def generador():
        for fragmento in stream:
            delta = fragmento.choices[0].delta
            texto = getattr(delta, "content", None) or ""
            if texto:
                yield texto

    return generador


# ──────────────────────────────────────────────────────────────────────────
# INTERFAZ PRINCIPAL
# ──────────────────────────────────────────────────────────────────────────

def main():
    _init_estado()

    tema_seleccionado = TEMAS[st.session_state.tema_nombre].copy()
    tema_seleccionado["accent"] = st.session_state.color_acento_custom
    fuente_css = FUENTES[st.session_state.fuente_nombre]
    inyectar_estilo(tema_seleccionado, fuente_css)

    with st.sidebar:
        st.markdown('<div class="titulo-beam">BEAM</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="subtitulo-beam">Chat de dictado e informes radiológicos</div>',
            unsafe_allow_html=True,
        )

        with st.expander("🔑 Conexión (DeepSeek)", expanded=not st.session_state.deepseek_api_key):
            st.session_state.deepseek_api_key = st.text_input(
                "DeepSeek API key", value=st.session_state.deepseek_api_key,
                type="password", placeholder="sk-...",
            )
            modelo = st.selectbox(
                "Modelo",
                list(MODELOS_DEEPSEEK.keys()),
                format_func=lambda m: MODELOS_DEEPSEEK[m],
                index=0,
            )

        with st.expander("🎨 Apariencia"):
            st.session_state.tema_nombre = st.selectbox(
                "Paleta de color", list(TEMAS.keys()),
                index=list(TEMAS.keys()).index(st.session_state.tema_nombre),
            )
            base_accent = TEMAS[st.session_state.tema_nombre]["accent"]
            st.session_state.color_acento_custom = st.color_picker(
                "Color de acento", value=st.session_state.color_acento_custom or base_accent,
            )
            st.session_state.fuente_nombre = st.selectbox(
                "Tipografía", list(FUENTES.keys()),
                index=list(FUENTES.keys()).index(st.session_state.fuente_nombre),
            )

        if st.button("＋ Nueva conversación", use_container_width=True):
            st.session_state.mensajes = []
            _init_estado()
            st.rerun()

        st.divider()

        with st.expander("📄 Tu plantilla de estilo", expanded=not st.session_state.plantilla_texto):
            st.caption(
                "Sube un informe tuyo ya redactado (.docx o .txt) para que BEAM aprenda tu "
                "vocabulario, orden interno y estilo de redacción, y lo use en todos los "
                "informes que genere."
            )
            plantilla_archivo = st.file_uploader(
                "Informe de referencia", type=["docx", "txt"], key="plantilla_uploader",
            )
            if plantilla_archivo is not None:
                try:
                    texto_plantilla = extraer_texto_plantilla(plantilla_archivo)
                    if texto_plantilla.strip():
                        st.session_state.plantilla_texto = texto_plantilla
                        st.success(f"Plantilla cargada ({len(texto_plantilla)} caracteres).")
                    else:
                        st.warning("No se pudo extraer texto de ese archivo.")
                except Exception as e:
                    st.error(f"Error al leer la plantilla: {e}")

            if st.session_state.plantilla_texto:
                st.caption("✅ BEAM está usando tu plantilla como referencia de estilo.")
                st.text_area(
                    "Vista previa (solo lectura)",
                    value=st.session_state.plantilla_texto[:2000],
                    height=120, disabled=True,
                )
                if st.button("Quitar plantilla", use_container_width=True):
                    st.session_state.plantilla_texto = ""
                    st.rerun()

    for mensaje in st.session_state.mensajes:
        with st.chat_message(mensaje["role"]):
            st.markdown(mensaje["content"])

    # Si el último mensaje es un informe completo, ofrece reformular HALLAZGOS o CONCLUSIÓN
    ultimo_msg = st.session_state.mensajes[-1] if st.session_state.mensajes else None
    generar_ahora = False
    if ultimo_msg and ultimo_msg["role"] == "assistant" and es_informe(ultimo_msg["content"]):
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Otras opciones — HALLAZGOS", use_container_width=True):
                st.session_state.mensajes.append({
                    "role": "user",
                    "content": (
                        "Dame 2 o 3 alternativas de redacción para la sección HALLAZGOS del "
                        "informe anterior. Mantén exactamente los mismos hallazgos clínicos "
                        "(no agregues, quites ni cambies ningún hallazgo, positivo o normal), "
                        "solo varía el estilo, el orden y la construcción de las frases. "
                        "Numera cada opción con un encabezado claro (Opción 1, Opción 2, ...)."
                    ),
                })
                st.session_state["_generar_ahora"] = True
                st.rerun()
        with col2:
            if st.button("🔄 Otras opciones — CONCLUSIÓN", use_container_width=True):
                st.session_state.mensajes.append({
                    "role": "user",
                    "content": (
                        "Dame 2 o 3 alternativas de redacción para la sección CONCLUSIÓN del "
                        "informe anterior. Mantén exactamente el mismo contenido clínico y las "
                        "mismas categorías/grados de clasificación si aplica, solo varía el "
                        "estilo, el orden y la construcción de las frases. Numera cada opción "
                        "con un encabezado claro (Opción 1, Opción 2, ...)."
                    ),
                })
                st.session_state["_generar_ahora"] = True
                st.rerun()

    # Ícono de dictado por voz, justo arriba del cuadro de chat
    widget_dictado_voz(st.session_state.color_acento_custom)

    prompt = st.chat_input("Dicta un estudio o pide un ajuste al informe…")

    generar_ahora = generar_ahora or st.session_state.pop("_generar_ahora", False)

    if prompt:
        st.session_state.mensajes.append({"role": "user", "content": prompt})
        generar_ahora = True
        with st.chat_message("user"):
            st.markdown(prompt)

    if generar_ahora:
        if not st.session_state.deepseek_api_key:
            st.error("Falta configurar tu DeepSeek API key en la barra lateral.")
        else:
            with st.chat_message("assistant"):
                try:
                    generador = generar_respuesta(modelo)
                    texto_completo = st.write_stream(generador())
                    texto_final = aplicar_terminologia(texto_completo)
                    if texto_final != texto_completo:
                        st.markdown(texto_final)
                except Exception as e:
                    texto_final = f"Ocurrió un error al generar la respuesta: {e}"
                    st.error(texto_final)
            st.session_state.mensajes.append({"role": "assistant", "content": texto_final})


if __name__ == "__main__":
    main()
