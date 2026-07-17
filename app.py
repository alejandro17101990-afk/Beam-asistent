import streamlit as st

# 1. Configuración de la página en modo ancho (wide)
st.set_page_config(
    page_title="BEAM AI",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 2. Inyección de CSS Personalizado para lograr el diseño exacto
st.markdown("""
    <style>
    /* Ocultar elementos por defecto de Streamlit para limpiar la interfaz */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Contenedor principal del encabezado superior */
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
    .brand-logo span {
        margin-right: 8px;
    }
    .report-title-input {
        color: #94a3b8;
        font-size: 1rem;
        font-family: 'Inter', sans-serif;
    }

    /* Estilos para simular las ventanas del sistema operativo (Tarjetas de Módulos) */
    .window-card {
        background-color: #ffffff;
        border-radius: 12px;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.05), 0 2px 6px rgba(0, 0, 0, 0.05);
        border: 1px solid #e2e8f0;
        margin-bottom: 20px;
        display: flex;
        flex-direction: column;
        overflow: hidden;
    }
    
    /* Barra superior de la ventana (Semaforo + Título) */
    .window-header {
        background-color: #ffffff;
        padding: 12px 16px;
        border-bottom: 1px solid #f1f5f9;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .window-controls {
        display: flex;
        gap: 6px;
    }
    .control-dot {
        width: 12px;
        height: 12px;
        border-radius: 50%;
        display: inline-block;
    }
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
    
    .window-right-controls {
        color: #94a3b8;
        font-size: 0.8rem;
        display: flex;
        gap: 10px;
    }

    /* Cuerpo interno de la ventana */
    .window-body {
        padding: 20px;
        min-height: 450px;
        display: flex;
        flex-direction: column;
        background-color: #ffffff;
    }
    
    /* Área de ondas/audio simulada */
    .audio-wave-container {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 20px;
        text-align: center;
        margin-bottom: 20px;
    }
    .wave-dots {
        color: #cbd5e1;
        letter-spacing: 4px;
        font-weight: bold;
        font-size: 1.2rem;
    }

    /* Botón redondo gigante de micrófono */
    .mic-container {
        display: flex;
        justify-content: center;
        margin: 20px 0;
    }
    
    /* Estilos específicos para los pies de página de los módulos */
    .window-footer {
        background-color: #ffffff;
        border-top: 1px solid #f1f5f9;
        padding: 15px 20px;
    }
    
    /* Forzar que los botones de Streamlit se estiren o tengan el color correcto */
    div.stButton > button {
        width: 100%;
        font-weight: bold;
        border-radius: 8px;
    }
    
    /* Ajustes inputs */
    .stTextInput input, .stTextArea textarea {
        border-radius: 8px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# 3. Barra Superior (Navbar)
st.markdown("""
    <div class="custom-header">
        <div class="brand-logo">🔹 BEAM AI</div>
        <div class="report-title-input">Título del informe...</div>
    </div>
    """, unsafe_allow_html=True)

# 4. Grid de 3 Columnas (Una para cada ventana/módulo)
col1, col2, col3 = st.columns(3, gap="large")

# ==========================================
# COLUMNA 1: GESTIÓN DE PLANTILLAS
# ==========================================
with col1:
    # Encabezado estilo ventana
    st.markdown("""
        <div class="window-card">
            <div class="window-header">
                <div class="window-controls">
                    <span class="control-dot dot-red"></span>
                    <span class="control-dot dot-yellow"></span>
                    <span class="control-dot dot-green"></span>
                </div>
                <div class="window-title">GESTIÓN DE PLANTILLAS</div>
                <div class="window-right-controls"><span>—</span> <span>☐</span> <span>✕</span></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Contenido nativo de Streamlit metido en la columna
    search_col, add_col = st.columns([3, 1])
    with search_col:
        st.text_input("Buscar", placeholder="Buscar plantilla...", label_visibility="collapsed", key="search_bar")
    with add_col:
        st.button("＋ Añadir")
        
    # Espacio en blanco simulando el contenedor vacío
    st.markdown('<div style="height: 350px;"></div>', unsafe_allow_html=True)


# ==========================================
# COLUMNA 2: DICTADO Y VOZ
# ==========================================
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
                <div class="window-right-controls"><span>—</span> <span>☐</span> <span>✕</span></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Indicador de nivel de audio
    st.markdown('<p style="color: #64748b; font-size: 0.85rem; margin-bottom: 5px;">🎙️ Audio nivel <span style="float: right; color: #94a3b8;">En espera</span></p>', unsafe_allow_html=True)
    
    # Caja de la onda de audio
    st.markdown("""
        <div class="audio-wave-container">
            <div class="wave-dots">▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪▪</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Botón gigante del micrófono (usamos HTML/CSS para centrarlo estéticamente)
    st.markdown("""
        <div class="mic-container">
            <div style="background-color: #007bff; color: white; width: 65px; height: 65px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 1.6rem; box-shadow: 0 4px 12px rgba(0,123,255,0.3); cursor: pointer;">
                🎙️
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Transcripción del dictado
    st.text_area("Transcripción", placeholder="La transcripción del dictado aparecerá aquí...", label_visibility="collapsed", height=100)
    
    # Botones de Grabar / Pausar
    btn_rec, btn_pause = st.columns(2)
    with btn_rec:
        st.button("🎙️ GRABAR", type="primary")
    with btn_pause:
        st.button("⏸ PAUSAR")
        
    st.markdown('<div style="margin-top: 15px;"></div>', unsafe_allow_html=True)
    st.button("✨ Generar informe", disabled=True)


# ==========================================
# COLUMNA 3: EDITOR DE INFORME E IA
# ==========================================
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
                <div class="window-right-controls"><span>—</span> <span>☐</span> <span>✕</span></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Botón superior derecho dentro del editor
    top_ed_1, top_ed_2 = st.columns([1, 1])
    with top_ed_2:
        st.button("📄 FINALIZAR INFORME", type="primary")
        
    # Espacio del área de texto principal del editor
    st.markdown('<div style="height: 230px;"></div>', unsafe_allow_html=True)
    
    # Fila inferior 1: Reformular conclusión
    st.button("🔄 REFORMULAR CONCLUSIÓN")
    
    # Fila inferior 2: Herramientas IA (Generar resumen + Selector Tono)
    st.markdown('<div style="border-top: 1px solid #f1f5f9; margin: 10px 0;"></div>', unsafe_allow_html=True)
    
    ia_col1, ia_col2, ia_col3 = st.columns([2, 2, 0.5])
    with ia_col1:
        st.button("✨ GENERAR RESUMEN", type="primary")
    with ia_col2:
        st.selectbox("Tono IA", ["Formal", "Informal", "Detallado"], label_visibility="collapsed")
    with ia_col3:
        st.markdown('<p style="text-align: center; font-size: 1.3rem; cursor: pointer; margin-top: 5px;">•••</p>', unsafe_allow_html=True)
