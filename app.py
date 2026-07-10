"""
BEAM — Asistente Conversacional de Interpretación Radiológica
Interfaz de chat (estilo ChatGPT / Claude / Gemini) para dictado, redacción
y edición iterativa de informes radiológicos estructurados
(TÉCNICA / HALLAZGOS / CONCLUSIÓN).

Requisitos:
    pip install streamlit openai audio-recorder-streamlit python-docx

Variables de entorno / secrets necesarios:
    OPENAI_API_KEY   -> para Whisper (transcripción) y GPT (generación / chat)

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

MODELOS_DISPONIBLES = ["gpt-4o-mini", "gpt-4.1-mini", "gpt-4o"]

# Reglas terminológicas obligatorias (glosario de sustituciones)
TERMINOLOGIA_CORRECTA = {
    "osteoartritis": "osteoartrosis",
    "ruptura": "desgarro",
    "rasgadura": "desgarro",
}

SYSTEM_PROMPT = """Eres BEAM, un asistente conversacional experto en redacción e interpretación
de informes radiológicos, para radiólogos en un contexto clínico mexicano. Trabajas dentro de
un chat continuo: el radiólogo puede dictar un estudio, pedirte que generes el informe, y luego
pedirte ajustes, ampliaciones, correcciones de estilo, comparaciones con estudios previos,
explicaciones sobre clasificaciones, o cualquier otra consulta relacionada con el caso. Responde
siempre en español.

CUANDO GENERES UN INFORME RADIOLÓGICO, usa exclusivamente estas tres secciones, en mayúsculas
como encabezado, en prosa narrativa continua (nunca listas ni fragmentos telegráficos):

TÉCNICA
HALLAZGOS
CONCLUSIÓN

Reglas terminológicas estrictas (aplican siempre, en informes y en conversación):
- Usa "osteoartrosis", nunca "osteoartritis".
- Usa "desgarro", nunca "ruptura" o "rasgadura" (tendón/menisco).
- Mantén un registro clínico formal, preciso y conciso.
- No inventes hallazgos que no estén mencionados o implícitos en el dictado.
- Si el dictado o el caso involucra sistemas de clasificación (BI-RADS, PI-RADS, TI-RADS,
  LI-RADS, Kellgren-Lawrence, Pfirrmann, Stoller, ICRS, Fleischner, Spetzler-Martin, TOAST, AAST),
  inclúyelos correctamente en la CONCLUSIÓN, con el grado/categoría correspondiente.

CUANDO CONVERSES (ediciones, dudas, comparaciones, explicaciones): responde de forma directa y
clínica, sin preámbulos innecesarios. Si el radiólogo pide un cambio sobre un informe ya
generado, entrega el informe completo actualizado (no solo el fragmento cambiado), salvo que
pida explícitamente solo una explicación.

Si el mensaje del usuario es claramente un dictado (texto libre describiendo un estudio de
imagen), genera directamente el informe estructurado sin pedir confirmación.
"""

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
    if "api_key" not in st.session_state:
        st.session_state.api_key = os.environ.get("OPENAI_API_KEY", "")
    if "transcripcion_pendiente" not in st.session_state:
        st.session_state.transcripcion_pendiente = ""


def aplicar_terminologia(texto: str) -> str:
    """Corrige términos no preferidos según el glosario institucional."""
    for incorrecto, correcto in TERMINOLOGIA_CORRECTA.items():
        texto = texto.replace(incorrecto, correcto)
        texto = texto.replace(incorrecto.capitalize(), correcto.capitalize())
    return texto


def obtener_cliente() -> OpenAI:
    return OpenAI(api_key=st.session_state.api_key)


# ──────────────────────────────────────────────────────────────────────────
# ESTILO — TEMA OSCURO PREMIUM
# ──────────────────────────────────────────────────────────────────────────

def inyectar_estilo():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

        .stApp { background-color: #111112; color: #E8E8E8; }

        section[data-testid="stSidebar"] {
            background-color: #17171A;
            border-right: 1px solid #2A2A2E;
        }

        .titulo-beam {
            font-family: 'Inter', sans-serif;
            font-weight: 700;
            font-size: 1.7rem;
            color: #E8B84B;
            letter-spacing: 0.5px;
        }
        .subtitulo-beam {
            color: #9A9A9E;
            font-size: 0.85rem;
            margin-bottom: 1.2rem;
        }

        [data-testid="stChatMessage"] {
            background-color: #18181B;
            border: 1px solid #2A2A2E;
            border-radius: 12px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.92rem;
            line-height: 1.65;
        }

        div.stButton > button, div.stDownloadButton > button {
            background-color: #E8B84B;
            color: #111112;
            border: none;
            border-radius: 8px;
            font-weight: 600;
        }
        div.stButton > button:hover, div.stDownloadButton > button:hover {
            background-color: #F4C766;
            color: #111112;
        }

        [data-testid="stChatInput"] textarea {
            font-family: 'JetBrains Mono', monospace;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────────
# TRANSCRIPCIÓN (WHISPER)
# ──────────────────────────────────────────────────────────────────────────

def transcribir_audio(audio_bytes: bytes) -> str:
    buffer_audio = io.BytesIO(audio_bytes)
    buffer_audio.name = "dictado.wav"
    cliente = obtener_cliente()
    respuesta = cliente.audio.transcriptions.create(
        model="whisper-1",
        file=buffer_audio,
        language="es",
    )
    return respuesta.text.strip()


# ──────────────────────────────────────────────────────────────────────────
# GENERACIÓN DE RESPUESTA (CHAT, CON STREAMING)
# ──────────────────────────────────────────────────────────────────────────

def generar_respuesta(modelo: str):
    """Llama al modelo con todo el historial y transmite la respuesta en vivo."""
    cliente = obtener_cliente()

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
            delta = fragmento.choices[0].delta.content or ""
            if delta:
                yield delta

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


# ──────────────────────────────────────────────────────────────────────────
# INTERFAZ PRINCIPAL
# ──────────────────────────────────────────────────────────────────────────

def main():
    _init_estado()
    inyectar_estilo()

    with st.sidebar:
        st.markdown('<div class="titulo-beam">BEAM</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="subtitulo-beam">Chat de dictado e informes radiológicos</div>',
            unsafe_allow_html=True,
        )

        if not st.session_state.api_key:
            st.session_state.api_key = st.text_input(
                "OpenAI API key", type="password", placeholder="sk-..."
            )

        modelo = st.selectbox("Modelo", MODELOS_DISPONIBLES, index=0)

        if st.button("＋ Nueva conversación", use_container_width=True):
            st.session_state.mensajes = []
            _init_estado()
            st.rerun()

        st.divider()

        if AUDIO_DISPONIBLE:
            st.caption("🎙️ Dictado por voz")
            audio_bytes = audio_recorder(
                text="",
                recording_color="#E8B84B",
                neutral_color="#2A2A2E",
                icon_size="2x",
                pause_threshold=2.0,
                key="grabadora",
            )
            if audio_bytes:
                with st.spinner("Transcribiendo…"):
                    try:
                        st.session_state.transcripcion_pendiente = transcribir_audio(audio_bytes)
                    except Exception as e:
                        st.error(f"Error al transcribir: {e}")

            if st.session_state.transcripcion_pendiente:
                st.text_area(
                    "Transcripción (editable, envíala desde el chat)",
                    key="transcripcion_pendiente",
                    height=140,
                )
                if st.button("Enviar transcripción al chat", use_container_width=True):
                    texto = st.session_state.transcripcion_pendiente
                    st.session_state.transcripcion_pendiente = ""
                    st.session_state.mensajes.append({"role": "user", "content": texto})
                    st.session_state["_generar_ahora"] = True
                    st.rerun()
        else:
            st.caption("Instala `audio-recorder-streamlit` para dictado por voz.")

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

    # ── Historial del chat ──────────────────────────────────────────────
    for mensaje in st.session_state.mensajes:
        with st.chat_message(mensaje["role"]):
            st.markdown(mensaje["content"])

    # ── Entrada de texto ────────────────────────────────────────────────
    prompt = st.chat_input("Dicta un estudio o pide un ajuste al informe…")

    generar_ahora = st.session_state.pop("_generar_ahora", False)

    if prompt:
        st.session_state.mensajes.append({"role": "user", "content": prompt})
        generar_ahora = True
        with st.chat_message("user"):
            st.markdown(prompt)

    if generar_ahora:
        if not st.session_state.api_key:
            st.error("Falta configurar tu OpenAI API key en la barra lateral.")
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
