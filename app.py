import streamlit as st
import requests
import io
import datetime

try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False

# ============================================================
# CONFIGURACIÓN DE PÁGINA
# ============================================================
st.set_page_config(
    page_title="BEAM AI",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================
# CONFIGURACIÓN DEEPSEEK
# ============================================================
def get_api_key():
    try:
        return st.secrets["DEEPSEEK_API_KEY"]
    except Exception:
        import os
        return os.environ.get("DEEPSEEK_API_KEY", "")

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

def call_deepseek(system_prompt: str, user_prompt: str, temperature: float = 0.4) -> str:
    api_key = get_api_key()
    if not api_key:
        return "⚠️ No se encontró DEEPSEEK_API_KEY en st.secrets ni en variables de entorno."
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": 2000,
    }
    try:
        resp = requests.post(DEEPSEEK_URL, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"⚠️ Error al contactar DeepSeek: {e}"

# ============================================================
# ESTADO DE SESIÓN
# ============================================================
defaults = {
    "titulo_informe": "",
    "templates": [
        {"nombre": "Rodilla - Resonancia", "contenido": "TÉCNICA: Estudio de resonancia magnética de rodilla...\n\nHALLAZGOS:\n\nCONCLUSIÓN:"},
        {"nombre": "Columna lumbar - TC", "contenido": "TÉCNICA: Estudio tomográfico de columna lumbar...\n\nHALLAZGOS:\n\nCONCLUSIÓN:"},
    ],
    "transcripcion": "",
    "informe": "",
    "tono_ia": "Formal",
    "grabando": False,
    "busqueda_plantilla": "",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ============================================================
# CSS (idéntico al mockup original + ajustes de funcionalidad)
# ============================================================
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    .custom-header {
        background-color: #ffffff;
        padding: 15px 25px;
        display: flex;
        align-items: center;
        border-bottom: 1px solid #e2e8f0;
        margin-bottom: 25px;
        border-radius: 8px;
    }
    .brand-logo {
        color: #007bff;
        font-weight: 800;
        font-size: 1.2rem;
        font-family: 'Inter', sans-serif;
        display: flex;
        align-items: center;
        margin-right: 20px;
    }
    .brand-logo span { margin-right: 8px; }

    .window-card {
        background-color: #ffffff;
        border-radius: 12px 12px 0 0;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.05), 0 2px 6px rgba(0, 0, 0, 0.05);
        border: 1px solid #e2e8f0;
        border-bottom: none;
        margin-bottom: 0px;
        overflow: hidden;
    }
    .window-header {
        background-color: #ffffff;
        padding: 12px 16px;
        border-bottom: 1px solid #f1f5f9;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .window-controls { display: flex; gap: 6px; }
    .control-dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; }
    .dot-red { background-color: #ff5f56; }
    .dot-yellow { background-color: #ffbd2e; }
    .dot-green { background-color: #27c93f; }
    .window-title {
        font-size: 0.85rem;
        font-weight: 700;
        color: #1e293b;
        letter-spacing: 0.5px;
        font-family: 'Inter', sans-serif;
        margin-right: auto;
        margin-left: 15px;
    }

    .body-panel {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-top: none;
        border-radius: 0 0 12px 12px;
        padding: 18px;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.05);
        margin-bottom: 25px;
    }

    .audio-wave-container {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 15px;
        text-align: center;
        margin-bottom: 12px;
    }

    div.stButton > button {
        width: 100%;
        font-weight: bold;
        border-radius: 8px;
    }
    .stTextInput input, .stTextArea textarea {
        border-radius: 8px !important;
    }
    .plantilla-item {
        padding: 8px 10px;
        border-radius: 8px;
        border: 1px solid #f1f5f9;
        margin-bottom: 6px;
        font-size: 0.85rem;
        color: #334155;
        cursor: pointer;
    }
    .plantilla-item:hover { background-color: #f8fafc; }
    </style>
    """, unsafe_allow_html=True)

# ============================================================
# ENCABEZADO
# ============================================================
h1, h2 = st.columns([1, 4])
with h1:
    st.markdown('<div class="brand-logo">🔹 BEAM AI</div>', unsafe_allow_html=True)
with h2:
    st.session_state.titulo_informe = st.text_input(
        "Título",
        value=st.session_state.titulo_informe,
        placeholder="Título del informe...",
        label_visibility="collapsed",
    )
st.markdown('<hr style="margin-top:-10px;">', unsafe_allow_html=True)

col1, col2, col3 = st.columns(3, gap="large")

# ============================================================
# COLUMNA 1 — GESTIÓN DE PLANTILLAS
# ============================================================
with col1:
    st.markdown("""
        <div class="window-card">
            <div class="window-header">
                <div class="window-controls">
                    <span class="control-dot dot-red"></span>
                    <span class="control-dot dot-yellow"></span>
                    <span class="control-dot dot-green"></span>
                </div>
                <div class="window-title">GESTIÓN DE PLANTILLAS</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="body-panel">', unsafe_allow_html=True)

        search_col, add_col = st.columns([3, 1])
        with search_col:
            st.session_state.busqueda_plantilla = st.text_input(
                "Buscar", placeholder="Buscar plantilla...",
                label_visibility="collapsed", key="search_bar",
                value=st.session_state.busqueda_plantilla,
            )
        with add_col:
            abrir_nueva = st.button("＋ Añadir", key="btn_add_plantilla")

        if abrir_nueva:
            st.session_state["mostrar_form_plantilla"] = True

        if st.session_state.get("mostrar_form_plantilla"):
            nuevo_nombre = st.text_input("Nombre de la plantilla", key="nueva_plantilla_nombre")
            nuevo_contenido = st.text_area("Contenido base", key="nueva_plantilla_contenido", height=120)
            gc, cc = st.columns(2)
            with gc:
                if st.button("Guardar", key="guardar_plantilla"):
                    if nuevo_nombre.strip():
                        st.session_state.templates.append(
                            {"nombre": nuevo_nombre.strip(), "contenido": nuevo_contenido}
                        )
                        st.session_state["mostrar_form_plantilla"] = False
                        st.rerun()
            with cc:
                if st.button("Cancelar", key="cancelar_plantilla"):
                    st.session_state["mostrar_form_plantilla"] = False
                    st.rerun()

        st.markdown('<div style="height:6px;"></div>', unsafe_allow_html=True)

        filtro = st.session_state.busqueda_plantilla.lower().strip()
        plantillas_filtradas = [
            t for t in st.session_state.templates
            if filtro in t["nombre"].lower()
        ] if filtro else st.session_state.templates

        if not plantillas_filtradas:
            st.caption("No hay plantillas que coincidan.")
        else:
            for i, t in enumerate(plantillas_filtradas):
                pc1, pc2 = st.columns([4, 1])
                with pc1:
                    st.markdown(f'<div class="plantilla-item">📄 {t["nombre"]}</div>', unsafe_allow_html=True)
                with pc2:
                    if st.button("Usar", key=f"usar_plantilla_{i}"):
                        st.session_state.informe = t["contenido"]
                        st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# COLUMNA 2 — DICTADO Y VOZ (+ ENTRADA MANUAL)
# ============================================================
with col2:
    st.markdown("""
        <div class="window-card">
            <div class="window-header">
                <div class="window-controls">
                    <span class="control-dot dot-red"></span>
                    <span class="control-dot dot-yellow"></span>
                    <span class="control-dot dot-green"></span>
                </div>
                <div class="window-title">DICTADO Y VOZ</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="body-panel">', unsafe_allow_html=True)

        tab_dictado, tab_manual = st.tabs(["🎙️ Dictado", "⌨️ Escribir manualmente"])

        # ---- TAB DICTADO ----
        with tab_dictado:
            st.markdown(
                '<p style="color:#64748b;font-size:0.85rem;margin-bottom:5px;">🎙️ Audio nivel '
                '<span style="float:right;color:#94a3b8;">'
                + ("Grabando..." if st.session_state.grabando else "En espera")
                + '</span></p>',
                unsafe_allow_html=True,
            )
            st.markdown('<div class="audio-wave-container">', unsafe_allow_html=True)

            if not SR_AVAILABLE:
                st.warning("Falta el paquete SpeechRecognition. Agrega `SpeechRecognition` a requirements.txt.")
            else:
                audio_value = st.audio_input("Grabar dictado", label_visibility="collapsed")
                if audio_value is not None:
                    if st.button("📝 Transcribir audio", key="btn_transcribir"):
                        with st.spinner("Transcribiendo con Google Speech Recognition..."):
                            try:
                                recognizer = sr.Recognizer()
                                audio_bytes = audio_value.read()
                                with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
                                    audio_data = recognizer.record(source)
                                texto = recognizer.recognize_google(audio_data, language="es-MX")
                                st.session_state.transcripcion = (
                                    st.session_state.transcripcion + " " + texto
                                ).strip()
                                st.rerun()
                            except sr.UnknownValueError:
                                st.error("No se pudo entender el audio. Intenta de nuevo.")
                            except sr.RequestError as e:
                                st.error(f"Error de conexión con el servicio de reconocimiento: {e}")

            st.markdown('</div>', unsafe_allow_html=True)

        # ---- TAB MANUAL ----
        with tab_manual:
            st.caption("Si no puedes dictar, describe aquí el estudio directamente.")
            texto_manual = st.text_area(
                "Entrada manual",
                placeholder="Escribe aquí la descripción del estudio, hallazgos relevantes, datos clínicos...",
                label_visibility="collapsed",
                height=150,
                key="texto_manual_input",
            )
            if st.button("➕ Añadir a la transcripción", key="btn_add_manual"):
                if texto_manual.strip():
                    st.session_state.transcripcion = (
                        st.session_state.transcripcion + " " + texto_manual
                    ).strip()
                    st.rerun()

        # ---- TRANSCRIPCIÓN EDITABLE (compartida por ambos métodos) ----
        st.markdown('<p style="font-size:0.8rem;color:#64748b;margin-top:10px;">Transcripción (editable)</p>', unsafe_allow_html=True)
        st.session_state.transcripcion = st.text_area(
            "Transcripción",
            value=st.session_state.transcripcion,
            placeholder="La transcripción del dictado aparecerá aquí. También puedes editarla libremente...",
            label_visibility="collapsed",
            height=100,
            key="transcripcion_editable",
        )

        bc1, bc2 = st.columns(2)
        with bc1:
            if st.button("🗑️ Limpiar", key="btn_limpiar_transcripcion"):
                st.session_state.transcripcion = ""
                st.rerun()
        with bc2:
            st.button("⏸ PAUSAR", key="btn_pausar")

        st.markdown('<div style="margin-top:10px;"></div>', unsafe_allow_html=True)

        generar_disabled = not st.session_state.transcripcion.strip()
        if st.button("✨ Generar informe", key="btn_generar_informe", disabled=generar_disabled, type="primary"):
            with st.spinner("Generando informe con IA..."):
                system_prompt = (
                    "Eres un radiólogo experto que redacta informes radiológicos en español formal "
                    "de México. Usa la terminología correcta: 'osteoartrosis' (nunca 'osteoartritis'), "
                    "'desgarro' (nunca 'ruptura' para tendones o meniscos). Redacta en prosa narrativa, "
                    "nunca en listas ni viñetas. Estructura siempre el informe en tres secciones con "
                    "encabezados en mayúsculas: TÉCNICA, HALLAZGOS y CONCLUSIÓN."
                )
                user_prompt = (
                    f"Título del estudio: {st.session_state.titulo_informe or 'No especificado'}\n\n"
                    f"Dictado / notas del radiólogo:\n{st.session_state.transcripcion}\n\n"
                    "Redacta el informe radiológico estructurado."
                )
                st.session_state.informe = call_deepseek(system_prompt, user_prompt)
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# COLUMNA 3 — EDITOR DE INFORME E IA
# ============================================================
with col3:
    st.markdown("""
        <div class="window-card">
            <div class="window-header">
                <div class="window-controls">
                    <span class="control-dot dot-red"></span>
                    <span class="control-dot dot-yellow"></span>
                    <span class="control-dot dot-green"></span>
                </div>
                <div class="window-title">EDITOR DE INFORME E IA</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="body-panel">', unsafe_allow_html=True)

        top_ed_1, top_ed_2 = st.columns([1, 1])
        with top_ed_2:
            finalizar = st.button("📄 FINALIZAR INFORME", key="btn_finalizar", type="primary")

        st.session_state.informe = st.text_area(
            "Editor de informe",
            value=st.session_state.informe,
            placeholder="El informe generado aparecerá aquí. Puedes editarlo libremente...",
            label_visibility="collapsed",
            height=280,
            key="editor_informe",
        )

        if st.button("🔄 REFORMULAR CONCLUSIÓN", key="btn_reformular"):
            if st.session_state.informe.strip():
                with st.spinner("Reformulando conclusión..."):
                    system_prompt = (
                        "Eres un radiólogo experto en redacción médica en español formal de México. "
                        "Se te dará un informe radiológico completo. Reformula ÚNICAMENTE la sección "
                        "CONCLUSIÓN con una redacción distinta pero clínicamente equivalente, en prosa, "
                        "sin viñetas. Devuelve el informe completo con la CONCLUSIÓN reformulada, "
                        "conservando TÉCNICA y HALLAZGOS sin cambios."
                    )
                    st.session_state.informe = call_deepseek(system_prompt, st.session_state.informe)
                    st.rerun()
            else:
                st.warning("Primero genera o escribe un informe.")

        st.markdown('<hr style="border-top:1px solid #f1f5f9;margin:10px 0;">', unsafe_allow_html=True)

        ia_col1, ia_col2, ia_col3 = st.columns([2, 2, 0.6])
        with ia_col1:
            generar_resumen = st.button("✨ GENERAR RESUMEN", key="btn_resumen", type="primary")
        with ia_col2:
            st.session_state.tono_ia = st.selectbox(
                "Tono IA", ["Formal", "Informal", "Detallado"],
                label_visibility="collapsed",
                index=["Formal", "Informal", "Detallado"].index(st.session_state.tono_ia),
            )
        with ia_col3:
            st.markdown('<p style="text-align:center;font-size:1.3rem;margin-top:5px;">•••</p>', unsafe_allow_html=True)

        if generar_resumen:
            if st.session_state.informe.strip():
                with st.spinner("Generando resumen..."):
                    tono_map = {
                        "Formal": "un tono clínico formal",
                        "Informal": "un tono cercano y sencillo, apto para explicar al paciente",
                        "Detallado": "un tono detallado y técnico, ampliando los hallazgos relevantes",
                    }
                    system_prompt = (
                        f"Eres un radiólogo redactando en español de México con {tono_map[st.session_state.tono_ia]}. "
                        "Resume el informe radiológico en un párrafo breve y claro, en prosa, sin viñetas."
                    )
                    resumen = call_deepseek(system_prompt, st.session_state.informe)
                    st.info(resumen)
            else:
                st.warning("Primero genera o escribe un informe.")

        if finalizar:
            if st.session_state.informe.strip():
                fecha = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
                nombre_archivo = f"informe_{fecha}.txt"
                st.download_button(
                    "⬇️ Descargar informe (.txt)",
                    data=st.session_state.informe,
                    file_name=nombre_archivo,
                    mime="text/plain",
                    key="btn_descargar",
                )
            else:
                st.warning("El informe está vacío.")

        st.markdown('</div>', unsafe_allow_html=True)
