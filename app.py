"""
BEAM — Asistente Conversacional de Interpretación Radiológica
Interfaz de chat (estilo ChatGPT / Claude / Gemini) para dictado, redacción
y edición iterativa de informes radiológicos estructurados
(TÉCNICA / HALLAZGOS / CONCLUSIÓN).

Modelo de generación: DeepSeek (deepseek-chat / deepseek-reasoner), vía API
compatible con OpenAI (base_url distinto).

Transcripción por voz: reconocimiento de voz GRATUITO de Google, vía la
librería `SpeechRecognition` (el mismo motor que usa Chrome) — sin API key
ni costo adicional. Al grabar, se transcribe y se envía automáticamente
al chat, sin pasos manuales.

Requisitos:
    pip install streamlit openai audio-recorder-streamlit python-docx SpeechRecognition

Ejecutar:
    streamlit run app.py
"""

import os
import io
import datetime

import streamlit as st
from openai import OpenAI

try:
    from audio_recorder_streamlit import audio_recorder
    AUDIO_DISPONIBLE = True
except ImportError:
    AUDIO_DISPONIBLE = False

try:
    import speech_recognition as sr
    RECONOCIMIENTO_DISPONIBLE = True
except ImportError:
    RECONOCIMIENTO_DISPONIBLE = False

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

SYSTEM_PROMPT = """Eres BEAM, un radiólogo experto de altísimo nivel clínico, que redacta e
interpreta informes radiológicos dentro de un chat continuo, para radiólogos en un contexto
clínico mexicano. El radiólogo puede dictar un estudio, pedirte que generes el informe, y luego
pedirte ajustes, reformulaciones, ampliaciones, comparaciones con estudios previos, o dudas sobre
clasificaciones. Respondes siempre en español, con el criterio y la voz de un radiólogo senior.

FORMATO DEL INFORME
Usa exclusivamente estas tres secciones, en mayúsculas como encabezado, en prosa narrativa
continua (nunca listas ni fragmentos telegráficos):

TÉCNICA
HALLAZGOS
CONCLUSIÓN

NIVEL CLÍNICO Y COMPLETITUD (regla central)
El radiólogo casi siempre dicta solo los hallazgos POSITIVOS (patológicos). Tu trabajo, igual
que el de un radiólogo humano al firmar un estudio, es entregar un informe COMPLETO Y
SISTEMÁTICO de todas las estructuras relevantes evaluadas de rutina en ese tipo de estudio:
- Debes inferir y redactar explícitamente el estado NORMAL de las estructuras no mencionadas,
  siguiendo el protocolo estándar de revisión para esa modalidad y región anatómica (p. ej. en
  una RM de rodilla: si solo te dictan "desgarro de menisco medial", también debes describir
  el estado de ligamentos cruzados y colaterales, el menisco lateral, el cartílago articular,
  los compartimentos, la alineación, los tejidos blandos periarticulares y la presencia o
  ausencia de derrame, aunque no se hayan mencionado).
- NUNCA inventes hallazgos patológicos, mediciones o datos que no fueron dictados o que no son
  clínicamente deducibles del contexto (edad, lateralidad, tipo de estudio).
- SÍ debes generar, con criterio experto, las descripciones normales/negativas pertinentes,
  exactamente como lo haría un radiólogo experimentado al dictar de forma completa.
- Sé exhaustivo, ordenado por regiones o sistemas (no aleatorio), y usa terminología radiológica
  profesional, precisa y de alto nivel, en registro formal mexicano.
- La CONCLUSIÓN debe ser jerárquica: el hallazgo principal primero, seguido de hallazgos
  incidentales relevantes si los hay. Si aplica un sistema de clasificación (BI-RADS, PI-RADS,
  TI-RADS, LI-RADS, Kellgren-Lawrence, Pfirrmann, Stoller, ICRS, Fleischner, Spetzler-Martin,
  TOAST, AAST, etc.), inclúyelo con su categoría/grado exacto.

REGLAS TERMINOLÓGICAS ESTRICTAS (siempre)
- Usa "osteoartrosis", nunca "osteoartritis".
- Usa "desgarro", nunca "ruptura" o "rasgadura" (tendón/menisco).

REFORMULACIÓN Y EDICIÓN
El radiólogo puede pedirte reformular solo los HALLAZGOS, solo la CONCLUSIÓN, o el informe
completo, con una redacción distinta pero preservando el mismo contenido clínico y las mismas
conclusiones diagnósticas (salvo que pida explícitamente cambiar el diagnóstico). Cuando se
pida una reformulación:
- Cambia estructura de frase, sinónimos y orden, no solo palabras sueltas.
- Entrega la sección completa reformulada (o el informe completo si así se pidió), lista para
  usarse, no un fragmento ni una explicación de los cambios.
- Si el radiólogo pide varias opciones/alternativas, numéralas claramente (Opción 1, Opción 2...).

CONVERSACIÓN GENERAL
Para dudas, comparaciones o explicaciones, responde de forma directa y clínica, sin preámbulos
innecesarios. Si el mensaje del usuario es claramente un dictado (texto libre describiendo un
estudio de imagen), genera directamente el informe estructurado y completo, sin pedir
confirmación.
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
                    "Hola, soy **BEAM**. Dicta o pega los hallazgos de un estudio y te "
                    "entrego el informe completo (TÉCNICA / HALLAZGOS / CONCLUSIÓN), "
                    "incluyendo la descripción sistemática del resto de estructuras normales. "
                    "Después puedes pedirme que reformule hallazgos, conclusión, o cualquier "
                    "ajuste, todo en esta misma conversación."
                ),
            }
        ]
    st.session_state.setdefault("deepseek_api_key", os.environ.get("DEEPSEEK_API_KEY", ""))
    st.session_state.setdefault("tema_nombre", "Dorado (original)")
    st.session_state.setdefault("fuente_nombre", "Inter (sans, default)")
    st.session_state.setdefault(
        "color_acento_custom", TEMAS[st.session_state.get("tema_nombre", "Dorado (original)")]["accent"]
    )
    st.session_state.setdefault("_ultimo_audio_procesado", None)


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
        </style>
        """,
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────────
# TRANSCRIPCIÓN (RECONOCIMIENTO DE VOZ GRATUITO DE GOOGLE)
# ──────────────────────────────────────────────────────────────────────────

def transcribir_audio(audio_bytes: bytes) -> str:
    """Transcribe usando el motor gratuito de Google (SpeechRecognition), sin API key."""
    reconocedor = sr.Recognizer()
    with sr.AudioFile(io.BytesIO(audio_bytes)) as fuente:
        datos_audio = reconocedor.record(fuente)
    return reconocedor.recognize_google(datos_audio, language="es-MX").strip()


# ──────────────────────────────────────────────────────────────────────────
# GENERACIÓN DE RESPUESTA (CHAT, CON STREAMING, DEEPSEEK)
# ──────────────────────────────────────────────────────────────────────────

def generar_respuesta(modelo: str):
    cliente = obtener_cliente_deepseek()

    historial_api = [{"role": "system", "content": SYSTEM_PROMPT}] + [
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
# EXPORTAR A WORD
# ──────────────────────────────────────────────────────────────────────────

def exportar_docx(texto: str) -> bytes:
    documento = Document()
    for linea in texto.split("\n"):
        if linea.strip().upper() in ("TÉCNICA", "HALLAZGOS", "CONCLUSIÓN"):
            documento.add_heading(linea.strip(), level=2)
        elif linea.strip():
            documento.add_paragraph(linea.strip())
    buffer = io.BytesIO()
    documento.save(buffer)
    return buffer.getvalue()


def ultimo_mensaje_asistente() -> str:
    for m in reversed(st.session_state.mensajes):
        if m["role"] == "assistant":
            return m["content"]
    return ""


def solicitar_reformulacion(instruccion: str):
    """Agrega una instrucción de reformulación como mensaje de usuario y dispara la generación."""
    st.session_state.mensajes.append({"role": "user", "content": instruccion})
    st.session_state["_generar_ahora"] = True
    st.rerun()


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

        if AUDIO_DISPONIBLE and RECONOCIMIENTO_DISPONIBLE:
            st.caption("🎙️ Dictado por voz · gratuito (Google)")
            audio_bytes = audio_recorder(
                text="",
                recording_color=st.session_state.color_acento_custom,
                neutral_color="#2A2A2E",
                icon_size="2x",
                pause_threshold=2.0,
                key="grabadora",
            )
            # Procesa automáticamente en cuanto hay un audio nuevo: transcribe y
            # lo envía al chat sin pasos manuales, igual que antes.
            if audio_bytes and audio_bytes != st.session_state._ultimo_audio_procesado:
                st.session_state._ultimo_audio_procesado = audio_bytes
                with st.spinner("Transcribiendo (Google, gratis)…"):
                    try:
                        texto = transcribir_audio(audio_bytes)
                        if texto:
                            st.session_state.mensajes.append({"role": "user", "content": texto})
                            st.session_state["_generar_ahora"] = True
                            st.rerun()
                        else:
                            st.warning("No se detectó voz clara en la grabación.")
                    except sr.UnknownValueError:
                        st.warning("No se entendió el audio, intenta de nuevo.")
                    except sr.RequestError as e:
                        st.error(f"Error de conexión con el reconocimiento de Google: {e}")
        elif not AUDIO_DISPONIBLE:
            st.caption("Instala `audio-recorder-streamlit` para dictado por voz.")
        elif not RECONOCIMIENTO_DISPONIBLE:
            st.caption("Instala `SpeechRecognition` para dictado por voz.")

        st.divider()

        ultimo = ultimo_mensaje_asistente()
        if ultimo:
            st.download_button(
                "⬇️ Descargar último informe (.txt)",
                data=ultimo,
                file_name=f"informe_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                use_container_width=True,
            )
            if DOCX_DISPONIBLE:
                st.download_button(
                    "⬇️ Descargar último informe (.docx)",
                    data=exportar_docx(ultimo),
                    file_name=f"informe_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.docx",
                    use_container_width=True,
                )

    for mensaje in st.session_state.mensajes:
        with st.chat_message(mensaje["role"]):
            st.markdown(mensaje["content"])

    # ── Acciones rápidas de reformulación sobre el último informe ──────
    if len(st.session_state.mensajes) > 1 and st.session_state.mensajes[-1]["role"] == "assistant":
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🔁 Reformular hallazgos", use_container_width=True):
                solicitar_reformulacion(
                    "Reformula únicamente la sección de HALLAZGOS del informe anterior, con "
                    "redacción distinta (estructura de frase y sinónimos), preservando "
                    "exactamente el mismo contenido clínico. Entrega el informe completo "
                    "actualizado."
                )
        with col2:
            if st.button("🔁 Reformular conclusión", use_container_width=True):
                solicitar_reformulacion(
                    "Reformula únicamente la sección de CONCLUSIÓN del informe anterior, con "
                    "redacción distinta, preservando el mismo diagnóstico y la misma "
                    "clasificación si aplica. Entrega el informe completo actualizado."
                )
        with col3:
            if st.button("🔁 Dos opciones de conclusión", use_container_width=True):
                solicitar_reformulacion(
                    "Dame dos opciones distintas de redacción para la CONCLUSIÓN del informe "
                    "anterior (Opción 1 y Opción 2), con el mismo contenido diagnóstico pero "
                    "estilo distinto, para que yo elija."
                )

    prompt = st.chat_input("Dicta un estudio o pide un ajuste al informe…")

    generar_ahora = st.session_state.pop("_generar_ahora", False)

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
            st.rerun()


if __name__ == "__main__":
    main()
