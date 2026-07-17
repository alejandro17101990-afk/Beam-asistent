import json
import os
import re
from typing import Iterator

import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI

# Intentar importar python-docx para soporte real de Word
try:
    import docx
except ImportError:
    docx = None

# ══════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN Y PALETA HÍBRIDA (BEAM × GOSTER)
# ══════════════════════════════════════════════════════════════════════════

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
MODELO_DEFECTO = "deepseek-chat"
MODELOS_DEEPSEEK = {
    "deepseek-chat": "DeepSeek Chat (V3) — rápido, uso diario",
    "deepseek-reasoner": "DeepSeek Reasoner (R1) — razonamiento clínico denso",
}

# Paleta "Goster Premium Dark": Fondo grafito profundo + Acentuación Esmeralda Quirúrgico
PALETA = {
    "bg": "#0D0E11",
    "surface": "#16181D",
    "surface_alt": "#1F2229",
    "border": "#2A2E38",
    "text": "#F3F4F6",
    "muted": "#9CA3AF",
    "accent": "#10B981",          # Verde esmeralda Goster
    "accent_soft": "#10B98120",
    "mac_red": "#FF5F56",
    "mac_yellow": "#FFBD2E",
    "mac_green": "#27C93F"
}

FUENTE_UI = "'Inter', -apple-system, BlinkMacSystemFont, sans-serif"

TERMINOLOGIA_CORRECTA = {
    "osteoartritis": "osteoartrosis",
    "ruptura": "desgarro",
    "rasgadura": "desgarro",
}

SYSTEM_PROMPT_BASE = """Eres BEAM, un radiólogo experto redactando informes para un contexto clínico.
Generas directamente el informe completo estructurado en tres secciones exactas en mayúsculas:
TÉCNICA
HALLAZGOS
CONCLUSIÓN

Completa de forma sistemática la descripción normal de las estructuras de rutina no mencionadas ("negativa pertinente").
Usa terminología estricta: "osteoartrosis" en lugar de "osteoartritis" y "desgarro" en lugar de "ruptura".
Responde ÚNICAMENTE con el informe limpio, sin introducciones ni saludos."""

ESTILOS_REDACCION = {
    "clinico": {"nombre": "Clínico directo", "instruccion": "Oraciones cortas, datos medibles por delante, cero adornos."},
    "academico": {"nombre": "Académico", "instruccion": "Estructura conectiva compleja, ideal para ateneos o discusión de casos."},
    "conciso": {"nombre": "Ultra conciso", "instruccion": "Reduce al núcleo informativo. Elimina redundancias sin perder datos."},
    "elegante": {"nombre": "Elegante", "instruccion": "Transiciones fluidas, variación sintáctica profesional."},
    "rsna": {"nombre": "Estilo RSNA", "instruccion": "Secuencia anatómica estricta y sistemática (proximal a distal)."}
}
ORDEN_ESTILOS = list(ESTILOS_REDACCION.keys())

# ══════════════════════════════════════════════════════════════════════════
# FUNCIONES MATRICIALES (LOGICA Y PROCESAMIENTO)
# ══════════════════════════════════════════════════════════════════════════

def obtener_cliente(api_key: str) -> OpenAI:
    return OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)

def aplicar_terminologia(texto: str) -> str:
    for incorrecto, correcto in TERMINOLOGIA_CORRECTA.items():
        texto = texto.replace(incorrecto, correcto)
        texto = texto.replace(incorrecto.capitalize(), correcto.capitalize())
    return texto

def extraer_texto_docx(file) -> str:
    if docx is None:
        return "Error: Instala 'python-docx' (`pip install python-docx`) para procesar archivos Word."
    try:
        doc = docx.Document(file)
        return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    except Exception as e:
        return f"Error procesando el archivo Word: {str(e)}"

def generar_informe_stream(api_key: str, dictado: str, modelo: str) -> Iterator[str]:
    cliente = obtener_cliente(api_key)
    stream = cliente.chat.completions.create(
        model=modelo,
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

def reformular_conclusion_api(api_key: str, conclusion_actual: str, estilo_id: str, modelo: str) -> str:
    if not conclusion_actual.strip():
        return conclusion_actual
    cliente = obtener_cliente(api_key)
    estilo = ESTILOS_REDACCION[estilo_id]
    prompt = f"""Reescribe exclusivamente la sección CONCLUSIÓN de este informe bajo el estilo: {estilo['nombre']}.
    Instrucción: {estilo['instruccion']}
    
    CONCLUSIÓN ORIGINAL:
    {conclusion_actual}
    
    Devuelve SOLO el texto reescrito final, sin comentarios, sin introducciones ni comillas."""
    
    respuesta = cliente.chat.completions.create(
        model=modelo,
        messages=[
            {"role": "system", "content": "Eres un editor experto de informes radiológicos."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )
    return aplicar_terminologia(respuesta.choices[0].message.content.strip())

# ══════════════════════════════════════════════════════════════════════════
# ESTADO DE LA APLICACIÓN
# ══════════════════════════════════════════════════════════════════════════

st.set_page_config(page_title="BEAM × Goster Workspace", page_icon="⚡", layout="wide", initial_sidebar_state="collapsed")

if "deepseek_api_key" not in st.session_state:
    st.session_state.deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY", "")
if "transcripcion" not in st.session_state:
    st.session_state.transcripcion = ""
if "informe" not in st.session_state:
    st.session_state.informe = {"tecnica": "", "hallazgos": "", "conclusion": ""}

# ══════════════════════════════════════════════════════════════════════════
# MAQUETACIÓN ESTILOS CSS PERSONALIZADOS (MODO GOSTER WINDOWS)
# ══════════════════════════════════════════════════════════════════════════

def inyectar_ui_goster():
    p = PALETA
    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        
        .stApp {{ background-color: {p['bg']}; color: {p['text']}; font-family: {FUENTE_UI}; }}
        
        /* Contenedor estilo Ventana macOS de Goster */
        .goster-window {{
            background-color: {p['surface']};
            border: 1px solid {p['border']};
            border-radius: 12px;
            padding: 0px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            overflow: hidden;
        }}
        
        .goster-header {{
            background-color: {p['surface_alt']};
            border-bottom: 1px solid {p['border']};
            padding: 10px 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        
        .goster-dots {{ display: flex; gap: 6px; }}
        .goster-dot {{ width: 10px; height: 10px; border-radius: 50%; }}
        .dot-r {{ background-color: {p['mac_red']}; }}
        .dot-y {{ background-color: {p['mac_yellow']}; }}
        .dot-g {{ background-color: {p['mac_green']}; }}
        
        .goster-title {{
            font-size: 0.75rem;
            font-weight: 600;
            color: {p['muted']};
            text-transform: uppercase;
            letter-spacing: 0.1em;
        }}
        
        .goster-content {{ padding: 16px; }}
        
        /* Simulación Barra de Herramientas Word */
        .word-toolbar {{
            background-color: {p['surface_alt']};
            border: 1px solid {p['border']};
            padding: 6px 12px;
            border-radius: 6px;
            display: flex;
            gap: 14px;
            align-items: center;
            margin-bottom: 12px;
            font-size: 0.8rem;
            color: {p['muted']};
        }}
        .word-tool-btn {{ cursor: pointer; font-weight: bold; padding: 2px 6px; border-radius: 3px; }}
        .word-tool-btn:hover {{ background: {p['border']}; color: {p['text']}; }}
        
        /* Inputs y Textareas */
        textarea, input {{
            background-color: {p['surface_alt']} !important;
            color: {p['text']} !important;
            border: 1px solid {p['border']} !important;
            border-radius: 8px !important;
        }}
        textarea:focus, input:focus {{ border-color: {p['accent']} !important; }}
        
        /* Botones Especiales */
        div.stButton > button {{
            background-color: {p['surface_alt']}; color: {p['text']};
            border: 1px solid {p['border']}; border-radius: 6px;
            font-weight: 500; font-size: 0.85rem; transition: all 0.2s;
        }}
        div.stButton > button:hover {{ border-color: {p['accent']}; color: {p['accent']}; }}
        div.stButton > button[kind="primary"] {{
            background-color: {p['accent']}; color: #000000; border: none; font-weight: 600;
        }}
        div.stButton > button[kind="primary"]:hover {{ opacity: 0.9; color: #000000; }}
        </style>
    """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════
# WIDGET DE DICTADO POR VOZ INTEGRADO (GOOGLE WEB SPEECH API)
# ══════════════════════════════════════════════════════════════════════════

def render_html_mic_goster(color_accent: str, label_target: str):
    html_code = f"""
    <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; gap:12px; margin: 15px 0;">
      <button id="goster-mic" style="
          width:60px; height:60px; border-radius:50%; border:none; cursor:pointer;
          background:{color_accent}; display:flex; align-items:center; justify-content:center;
          box-shadow: 0 4px 15px {color_accent}40; transition: transform 0.2s;">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="#000000">
          <path d="M12 14a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v5a3 3 0 0 0 3 3z"/>
          <path d="M19 11a1 1 0 1 0-2 0 5 5 0 0 1-10 0 1 1 0 1 0-2 0 7 7 0 0 0 6 6.92V21a1 1 0 1 0 2 0v-3.08A7 7 0 0 0 19 11z"/>
        </svg>
      </button>
      <span id="goster-status" style="font-size:0.8rem; color:#9CA3AF; font-family:sans-serif; letter-spacing:0.05em;">PULSA EL BOTÓN PARA DICTAR</span>
    </div>
    
    <style>
      @keyframes mic-pulse {{
        0% {{ box-shadow: 0 0 0 0 {color_accent}60; transform: scale(1); }}
        70% {{ box-shadow: 0 0 0 15px {color_accent}00; transform: scale(1.05); }}
        100% {{ box-shadow: 0 0 0 0 {color_accent}00; transform: scale(1); }}
      }}
      #goster-mic.active {{ animation: mic-pulse 1.4s infinite; background: #EF4444 !important; }}
    </style>
    
    <script>
    (function() {{
      const btn = document.getElementById('goster-mic');
      const status = document.getElementById('goster-status');
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      const TARGET_LABEL = {label_target!r};

      if (!SpeechRecognition) {{
        status.textContent = 'Dictado no soportado en este navegador (Use Chrome/Edge)';
        btn.style.opacity = '0.3'; btn.disabled = true;
        return;
      }}

      const recognition = new SpeechRecognition();
      recognition.lang = 'es-MX';
      recognition.continuous = true;
      recognition.interimResults = true;

      let isRecording = false, manualStop = false, baseTxt = '', finalTranscript = '';

      function getTextArea() {{
        const mainDoc = window.parent.document;
        const areas = mainDoc.querySelectorAll('[data-testid="stTextArea"]');
        for (const zone of areas) {{
          if (zone.innerText.includes(TARGET_LABEL)) return zone.querySelector('textarea');
        }}
        return null;
      }}

      function updateTextareaValue(val) {{
        const el = getTextArea();
        if (!el) return;
        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
        nativeSetter.call(el, val);
        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
      }}

      btn.addEventListener('click', () => {{
        isRecording = !isRecording;
        if (isRecording) {{
          manualStop = false;
          const ta = getTextArea();
          baseTxt = ta ? ta.value : '';
          finalTranscript = '';
          recognition.start();
          btn.classList.add('active');
          status.textContent = 'ESCUCHANDO AUDIO DE FORMA ACTIVA...';
          status.style.color = '#EF4444';
        }} else {{
          manualStop = true;
          recognition.stop();
          btn.classList.remove('active');
          status.textContent = 'DICTADO DETENIDO';
          status.style.color = '#9CA3AF';
        }}
      }});

      recognition.onresult = (e) => {{
        let interim = '';
        for (let i = e.resultIndex; i < e.results.length; i++) {{
          if (e.results[i].isFinal) finalTranscript += e.results[i][0].transcript + ' ';
          else interim += e.results[i][0].transcript;
        }}
        const space = baseTxt && !baseTxt.endsWith(' ') ? ' ' : '';
        updateTextareaValue((baseTxt + space + finalTranscript + interim).trim());
      }};

      recognition.onend = () => {{ if (isRecording && !manualStop) recognition.start(); }};
    }})();
    </script>
    """
    components.html(html_code, height=110)

# ══════════════════════════════════════════════════════════════════════════
# COMPONENTE BOTÓN COPIAR RAPIDO
# ══════════════════════════════════════════════════════════════════════════

def render_btn_copiar(texto: str, element_key: str):
    t_js = json.dumps(texto or "")
    html = f"""
    <button id="cp-{element_key}" style="width:100%; background:{PALETA['surface_alt']}; color:{PALETA['text']}; border:1px solid {PALETA['border']}; border-radius:4px; font-size:0.75rem; padding:6px; cursor:pointer;">📋 Copiar Todo</button>
    <script>
    document.getElementById('cp-{element_key}').addEventListener('click', function() {{
        navigator.clipboard.writeText({t_js});
        this.innerText = '✓ Copiado';
        setTimeout(() => {{ this.innerText = '📋 Copiar Todo'; }}, 1500);
    }});
    </script>
    """
    components.html(html, height=35)

# ══════════════════════════════════════════════════════════════════════════
# CORE DE LA APLICACIÓN: INTERFAZ DE TRES COLUMNAS INDEPENDIENTES
# ══════════════════════════════════════════════════════════════════════════

def main():
    inyectar_ui_goster()
    
    # Encabezado unificado de la suite
    st.markdown(f"""
        <div style="display:flex; justify-content:space-between; align-items:center; padding:10px 0 20px 0; border-bottom:1px solid {PALETA['border']}; margin-bottom:20px;">
            <div style="font-size:1.4rem; font-weight:700; color:{PALETA['text']}; letter-spacing:-0.03em;">BEAM AI <span style="font-weight:300; font-size:0.9rem; color:{PALETA['accent']}; margin-left:10px;">⚡ WORKSPACE MULTICOLUMNA v2.5</span></div>
            <div style="font-size:0.85rem; color:{PALETA['muted']}; font-weight:500;">Estudio Radiológico Activo</div>
        </div>
    """, unsafe_allow_html=True)
    
    # Barra lateral simplificada exclusivamente para credenciales/modelo
    with st.sidebar:
        st.subheader("⚙️ Configuración del Motor")
        st.session_state.deepseek_api_key = st.text_input("DeepSeek API Key", value=st.session_state.deepseek_api_key, type="password")
        modelo_seleccionado = st.selectbox("Modelo Base", list(MODELOS_DEEPSEEK.keys()), format_func=lambda m: MODELOS_DEEPSEEK[m])
        st.markdown("---")
        if st.button("🗑️ Reiniciar Espacio"):
            st.session_state.transcripcion = ""
            st.session_state.informe = {"tecnica": "", "hallazgos": "", "conclusion": ""}
            st.rerun()

    # Creación del Layout de Tres Columnas
    col_plantillas, col_dictado, col_editor = st.columns([2.8, 3.8, 5.4])
    
    # ══════════════════════════════════════════════════════════════════════
    # COLUMNA 1: GESTIÓN DE PLANTILLAS (.DOCX)
    # ══════════════════════════════════════════════════════════════════════
    with col_plantillas:
        st.markdown(f"""
            <div class="goster-window">
                <div class="goster-header">
                    <div class="goster-dots"><div class="goster-dot dot-r"></div><div class="goster-dot dot-y"></div><div class="goster-dot dot-g"></div></div>
                    <div class="goster-title">GESTIÓN DE PLANTILLAS</div>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        archivo_word = st.file_uploader("Cargar plantilla Word (.docx)", type=["docx"], label_visibility="collapsed")
        
        if archivo_word is not None:
            with st.spinner("Leyendo estructura Word..."):
                texto_extraido = extraer_texto_docx(archivo_word)
                if not texto_extraido.startswith("Error"):
                    st.success("Plantilla extraída correctamente")
                    if st.button("📥 Inyectar a área de Dictado"):
                        st.session_state.transcripcion = texto_extraido
                        st.rerun()
                    st.text_area("Vista previa del documento:", value=texto_extraido, height=280, disabled=True)
                else:
                    st.error(texto_extraido)
        else:
            st.info("Sube un archivo .docx para precargar estructuras preestablecidas de informes.")
            
        # Biblioteca Simulada de Plantillas Rápidas
        st.markdown(f"<div style='font-size:0.75rem; color:{PALETA['muted']}; font-weight:bold; margin-top:15px;'>PLANTILLAS RÁPIDAS DE SISTEMA</div>", unsafe_allow_html=True)
        plantilla_rapida = st.selectbox("Seleccionar preset", ["Ninguno", "Rx Tórax PA Normal", "RMN Rodilla Estándar", "TAC Cráneo Simple"])
        if plantilla_rapida != "Ninguno":
            presets = {
                "Rx Tórax PA Normal": "TÉCNICA: Proyección posteroanterior de tórax.\nHALLAZGOS: Parénquima pulmonar limpio, sin consolidaciones ni derrames. Silueta cardiovascular normal.",
                "RMN Rodilla Estándar": "TÉCNICA: Secuencias multiplanares T1, T2 y DP con supresión grasa.\nHALLAZGOS: Estructuras meniscales y ligamentosas sin alteraciones de señal patológica.",
                "TAC Cráneo Simple": "TÉCNICA: Adquisición helicoidal sin medio de contraste.\nHALLAZGOS: Sistema ventricular simétrico. No se observan colecciones ni zonas de isquemia aguda."
            }
            if st.button("Cargar Preset seleccionado"):
                st.session_state.transcripcion = presets[plantilla_rapida]
                st.rerun()

    # ══════════════════════════════════════════════════════════════════════
    # COLUMNA 2: DICTADO POR VOZ Y CAPTURA LIBRE
    # ══════════════════════════════════════════════════════════════════════
    with col_dictado:
        st.markdown(f"""
            <div class="goster-window">
                <div class="goster-header">
                    <div class="goster-dots"><div class="goster-dot dot-r"></div><div class="goster-dot dot-y"></div><div class="goster-dot dot-g"></div></div>
                    <div class="goster-title">DICTADO Y CAPTURA MASIVA</div>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        # Audio Engine Gratuito Web Speech API Integrado
        ETIQUETA_REF = "Área de transcripción y pegado de texto"
        render_html_mic_goster(PALETA["accent"], label_target=ETIQUETA_REF)
        
        # Text area para escribir, pegar o recolectar el dictado de voz
        st.session_state.transcripcion = st.text_area(
            ETIQUETA_REF,
            value=st.session_state.transcripcion,
            height=300,
            placeholder="Los textos dictados o pegados se consolidarán aquí automáticamente..."
        )
        
        btn_generar = st.button("🪄 CORRER MOTOR IA DE INFORME", type="primary", use_container_width=True)
        
        if btn_generar:
            if not st.session_state.deepseek_api_key:
                st.error("⚠️ Configura la API key de DeepSeek en el menú lateral.")
            elif not st.session_state.transcripcion.strip():
                st.warning("⚠️ No hay texto clínico recolectado para procesar.")
            else:
                contenedor_stream = st.empty()
                acumulador_texto = ""
                try:
                    for token in generar_informe_stream(st.session_state.deepseek_api_key, st.session_state.transcripcion, modelo_seleccionado):
                        acumulador_texto += token
                        contenedor_stream.markdown(f"""
                            <div style="background:{PALETA['surface_alt']}; border:1px solid {PALETA['accent']}; border-radius:8px; padding:12px; font-size:0.9rem; white-space:pre-wrap;">
                                {acumulador_texto}▍
                            </div>
                        """, unsafe_allow_html=True)
                    st.session_state.informe = parsear_informe(acumulador_texto)
                    contenedor_stream.empty()
                    st.rerun()
                except Exception as e:
                    contenedor_stream.empty()
                    st.error(f"Fallo en la comunicación clínica: {str(e)}")

    # ══════════════════════════════════════════════════════════════════════
    # COLUMNA 3: EDITOR TIPO OFFICE WORD E INTELECTO DE REFORMULACIÓN
    # ══════════════════════════════════════════════════════════════════════
    with col_editor:
        st.markdown(f"""
            <div class="goster-window">
                <div class="goster-header">
                    <div class="goster-dots"><div class="goster-dot dot-r"></div><div class="goster-dot dot-y"></div><div class="goster-dot dot-g"></div></div>
                    <div class="goster-title">EDITOR DE TEXTO AVANZADO ESTILO WORD</div>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        # Renderizado de barra de herramientas simulando Microsoft Word / Goster UI
        st.markdown("""
            <div class="word-toolbar">
                <span class="word-tool-btn">B</span>
                <span class="word-tool-btn">I</span>
                <span class="word-tool-btn">U</span>
                <span style="color:#2A2E38;">|</span>
                <span>Font: <b style="color:#FFF;">Arial</b></span>
                <span>Size: <b style="color:#FFF;">11pt</b></span>
                <span style="color:#2A2E38;">|</span>
                <span class="word-tool-btn">≡</span>
                <span class="word-tool-btn">📋 Paste</span>
            </div>
        """, unsafe_allow_html=True)
        
        # Bloques editables independientes del documento
        st.session_state.informe["tecnica"] = st.text_area("TÉCNICA:", value=st.session_state.informe.get("tecnica", ""), height=80)
        st.session_state.informe["hallazgos"] = st.text_area("HALLAZGOS:", value=st.session_state.informe.get("hallazgos", ""), height=180)
        st.session_state.informe["conclusion"] = st.text_area("CONCLUSIÓN:", value=st.session_state.informe.get("conclusion", ""), height=100)
        
        st.markdown("---")
        
        # Motor de Reformulación enfocado exclusivamente en la sección CONCLUSIÓN
        st.markdown(f"<div style='font-size:0.8rem; font-weight:bold; color:{PALETA['accent']}; margin-bottom:5px;'>⚙️ MOTOR DE REFORMULACIÓN DIAGNÓSTICA</div>", unsafe_allow_html=True)
        
        c_sel, c_btn = st.columns([6, 4])
        with c_sel:
            estilo_conclusion = st.selectbox(
                "Tono e Identidad IA para la Conclusión",
                options=ORDEN_ESTILOS,
                format_func=lambda k: f"{ESTILOS_REDACCION[k]['nombre']}",
                label_visibility="collapsed"
            )
        with c_btn:
            btn_reformular = st.button("Reformular Conclusión", use_container_width=True)
            
        if btn_reformular:
            if not st.session_state.deepseek_api_key:
                st.error("Clave ausente.")
            else:
                with st.spinner("Modulando terminología clínica..."):
                    try:
                        nueva_concl = reformular_conclusion_api(
                            st.session_state.deepseek_api_key, 
                            st.session_state.informe["conclusion"], 
                            estilo_conclusion, 
                            modelo_seleccionado
                        )
                        st.session_state.informe["conclusion"] = nueva_concl
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al estilizar: {e}")
                        
        # Acciones globales del documento al pie de la ventana de edición
        st.markdown("<br>", unsafe_allow_html=True)
        col_cp, col_fin = st.columns([1, 1])
        with col_cp:
            informe_completo_txt = reconstruir_informe(st.session_state.informe)
            render_btn_copiar(informe_completo_txt, "informe_word_total")
        with col_fin:
            if st.button("🔒 FINALIZAR INFORME", use_container_width=True, type="primary"):
                st.balloons()
                st.success("Estudio Clínico consolidado y listo para integración PACS/RIS.")

if __name__ == "__main__":
    main()
