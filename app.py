"""
AURA — Asistente de Interpretación Radiológica
Suite de dictado médico con transcripción en tiempo real (Whisper) y
generación de informes estructurados (TÉCNICA / HALLAZGOS / CONCLUSIÓN).

Requisitos:
    pip install streamlit openai audio-recorder-streamlit python-docx

Variables de entorno necesarias:
    OPENAI_API_KEY   -> para Whisper (transcripción) y GPT (generación de informe)

Ejecutar:
    streamlit run app.py
"""

import os
import io
import time
import datetime
from dataclasses import dataclass, field

import streamlit as st
from openai import OpenAI
from audio_recorder_streamlit import audio_recorder

# ──────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN GENERAL
# ──────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AURA · Asistente Radiológico",
    page_icon="🩻",
    layout="wide",
    initial_sidebar_state="expanded",
)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Reglas terminológicas obligatorias (glosario de sustituciones)
TERMINOLOGIA_CORRECTA = {
    "osteoartritis": "osteoartrosis",
    "ruptura": "desgarro",
    "rasgadura": "desgarro",
}

PLANTILLA_SISTEMA = """Eres un asistente experto en redacción de informes radiológicos en español,
para radiólogos en un contexto clínico mexicano. A partir de la transcripción de un dictado,
redactas un informe con SOLO estas tres secciones, en mayúsculas como encabezado, y en prosa
narrativa continua (nunca listas ni fragmentos telegráficos):

TÉCNICA
HALLAZGOS
CONCLUSIÓN

Reglas terminológicas estrictas:
- Usa "osteoartrosis", nunca "osteoartritis".
- Usa "desgarro", nunca "ruptura" o "rasgadura".
- Mantén un registro clínico formal, preciso y conciso.
- No inventes hallazgos que no estén mencionados o implícitos en el dictado.
- Si el dictado menciona sistemas de clasificación (BI-RADS, PI-RADS, TI-RADS, LI-RADS,
  Kellgren-Lawrence, Stoller, ICRS, Spetzler-Martin, TOAST, AAST), inclúyelos correctamente
  en la CONCLUSIÓN.
- Devuelve únicamente el informe, sin comentarios ni preámbulos.
"""


@dataclass
class EstadoSesion:
    transcripcion: str = ""
    informe: str = ""
    historial: list = field(default_factory=list)


def _init_estado():
    if "estado" not in st.session_state:
        st.session_state.estado = EstadoSesion()


def aplicar_terminologia(texto: str) -> str:
    """Corrige términos no preferidos según el glosario institucional."""
    for incorrecto, correcto in TERMINOLOGIA_CORRECTA.items():
        texto = texto.replace(incorrecto, correcto)
        texto = texto.replace(incorrecto.capitalize(), correcto.capitalize())
    return texto


# ──────────────────────────────────────────────────────────────────────────
# ESTILO — TEMA OSCURO PREMIUM
# ──────────────────────────────────────────────────────────────────────────

def inyectar_estilo():
    st.markdown(
        """
        <style>
        .stApp {
            background-color: #111112;
            color: #E8E8E8;
        }
        section[data-testid="stSidebar"] {
            background-color: #17171A;
            border-right: 1px solid #2A2A2E;
        }
        .titulo-aura {
            font-family: 'Inter', sans-serif;
            font-weight: 700;
            font-size: 1.6rem;
            color: #E8B84B;
            letter-spacing: 0.5px;
        }
        .subtitulo-aura {
            color: #9A9A9E;
            font-size: 0.9rem;
            margin-bottom: 1.5rem;
        }
        .caja-informe {
            background-color: #18181B;
            border: 1px solid #2A2A2E;
            border-radius: 10px;
            padding: 1.2rem;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.92rem;
            line-height: 1.6;
            white-space: pre-wrap;
        }
        div.stButton > button {
            background-color: #E8B84B;
            color: #111112;
            border: none;
            border-radius: 8px;
            font-weight: 600;
        }
        div.stButton > button:hover {
            background-color: #F4C766;
            color: #111112;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────────
# TRANSCRIPCIÓN (WHISPER)
# ──────────────────────────────────────────────────────────────────────────

def transcribir_audio(audio_bytes: bytes) -> str:
    """Envía el audio grabado a Whisper y devuelve la transcripción en texto."""
    buffer_audio = io.BytesIO(audio_bytes)
    buffer_audio.name = "dictado.wav"
    respuesta = client.audio.transcriptions.create(
        model="whisper-1",
        file=buffer_audio,
        language="es",
    )
    return respuesta.text.strip()


# ──────────────────────────────────────────────────────────────────────────
# GENERACIÓN DE INFORME
# ──────────────────────────────────────────────────────────────────────────

def generar_informe(transcripcion: str, modelo: str = "gpt-4o-mini") -> str:
    respuesta = client.chat.completions.create(
        model=modelo,
        messages=[
            {"role": "system", "content": PLANTILLA_SISTEMA},
            {"role": "user", "content": f"Dictado del radiólogo:\n\n{transcripcion}"},
        ],
        temperature=0.2,
        stream=True,
    )

    contenedor = st.empty()
    texto_acumulado = ""
    for fragmento in respuesta:
        delta = fragmento.choices[0].delta.content or ""
        texto_acumulado += delta
        contenedor.markdown(
            f'<div class="caja-informe">{texto_acumulado}</div>',
            unsafe_allow_html=True,
        )

    return aplicar_terminologia(texto_acumulado)


# ──────────────────────────────────────────────────────────────────────────
# INTERFAZ PRINCIPAL
# ──────────────────────────────────────────────────────────────────────────

def main():
    _init_estado()
    inyectar_estilo()
    estado = st.session_state.estado

    with st.sidebar:
        st.markdown('<div class="titulo-aura">AURA</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="subtitulo-aura">Dictado médico · Transcripción en tiempo real</div>',
            unsafe_allow_html=True,
        )
        modelo = st.selectbox(
            "Modelo de generación",
            ["gpt-4o-mini", "gpt-4.1-mini"],
            index=0,
        )
        st.divider()
        st.caption(f"Sesión: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}")

        if estado.historial:
            st.subheader("Historial de la sesión")
            for i, item in enumerate(reversed(estado.historial)):
                with st.expander(f"Informe {len(estado.historial) - i}"):
                    st.text(item["informe"][:200] + "…")

    col_dictado, col_informe = st.columns([1, 1.4], gap="large")

    # ── Columna de dictado ──────────────────────────────────────────────
    with col_dictado:
        st.subheader("🎙️ Dictado")
        st.caption("Presiona el micrófono, dicta el estudio y detén la grabación al terminar.")

        audio_bytes = audio_recorder(
            text="",
            recording_color="#E8B84B",
            neutral_color="#2A2A2E",
            icon_size="3x",
            pause_threshold=2.0,
        )

        if audio_bytes:
            with st.spinner("Transcribiendo dictado…"):
                try:
                    texto = transcribir_audio(audio_bytes)
                    estado.transcripcion = texto
                except Exception as e:
                    st.error(f"Error al transcribir: {e}")

        estado.transcripcion = st.text_area(
            "Transcripción (editable)",
            value=estado.transcripcion,
            height=320,
            placeholder="La transcripción del dictado aparecerá aquí…",
        )

        generar = st.button("Generar informe ➜", use_container_width=True)

    # ── Columna de informe ──────────────────────────────────────────────
    with col_informe:
        st.subheader("📄 Informe radiológico")

        if generar:
            if not estado.transcripcion.strip():
                st.warning("Primero registra o escribe una transcripción.")
            else:
                with st.spinner("Redactando informe…"):
                    informe = generar_informe(estado.transcripcion, modelo=modelo)
                    estado.informe = informe
                    estado.historial.append(
                        {
                            "fecha": datetime.datetime.now().isoformat(),
                            "transcripcion": estado.transcripcion,
                            "informe": informe,
                        }
                    )
        elif estado.informe:
            st.markdown(
                f'<div class="caja-informe">{estado.informe}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.info("El informe generado aparecerá aquí, listo para revisión y edición.")

        if estado.informe:
            st.download_button(
                "⬇️ Descargar informe (.txt)",
                data=estado.informe,
                file_name=f"informe_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                use_container_width=True,
            )


if __name__ == "__main__":
    main()
