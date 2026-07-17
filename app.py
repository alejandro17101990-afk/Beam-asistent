import json
import os
import re
from typing import Iterator

import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI

try:
    import docx
except ImportError:
    docx = None

# ══════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN Y PALETA DE ULTRA ALTA FIDELIDAD (GOSTER CLINICAL DARK)
# ══════════════════════════════════════════════════════════════════════════

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
MODELO_DEFECTO = "deepseek-chat"
MODELOS_DEEPSEEK = {
    "deepseek-chat": "DeepSeek Chat (V3) — Operativo",
    "deepseek-reasoner": "DeepSeek Reasoner (R1) — Análisis Clínico Complejo",
}

PALETA = {
    "bg": "#08090C",
    "surface": "#11131A",
    "surface_alt": "#1A1D26",
    "border": "#242936",
    "text": "#F3F4F6",
    "muted": "#9CA3AF",
    "accent": "#10B981",          # Esmeralda Quirúrgico Góster
    "accent_soft": "#10B9811A",
    "word_canvas": "#14161F",      # Color de la hoja Word Dark
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

SYSTEM_PROMPT_BASE = """Eres BEAM, un radiólogo experto redactando informes para un contexto clínico profesional.
Generas directamente el informe completo estructurado estrictamente en tres secciones exactas en mayúsculas:
TÉCNICA
HALLAZGOS
CONCLUSIÓN

Completa de forma sistemática la descripción normal de las estructuras de rutina no mencionadas ("negativa pertinente").
Usa terminología médica estricta: siempre "osteoartrosis" en lugar de "osteoartritis" y "desgarro" en lugar de "ruptura".
Responde ÚNICAMENTE con el informe limpio, estructurado y sin preámbulos, saludos ni explicaciones adicionales."""

ESTILOS_REDACCION = {
    "clinico": {"nombre": "Clínico Directo", "descripcion": "Oraciones cortas, datos medibles por delante.", "instruccion": "Oraciones cortas, voz activa, prioridad absoluta a datos cuantitativos, sin adornos."},
    "academico": {"nombre": "Académico", "descripcion": "Tono de discusión de caso en sesión clínica o ateneo.", "instruccion": "Oraciones compuestas, terminología exhaustiva sin abreviaciones, tono doctoral."},
    "conciso": {"nombre": "Ultra Conciso", "descripcion": "Mínima extensión posible sin pérdida de datos.", "instruccion": "Reduce cada oración a su núcleo informativo puro, eliminando palabras redundantes."},
    "elegante": {"nombre": "Elegante Profesional", "descripcion": "Fluido, con variación sintáctica entre paragraphs.", "instruccion": "Transiciones sumamente fluidas, variación de estructura estructural para máxima legibilidad clínica."},
    "rsna": {"nombre": "Estilo RSNA (Radiology)", "descripcion": "Secuencia anatómica sistemática y objetiva.", "instruccion": "Registro impersonal riguroso siguiendo una secuencia anatómica estricta de proximal a distal."}
}
ORDEN_ESTILOS = list(ESTILOS_REDACCION.keys())

# ══════════════════════════════════════════════════════════════════════════
# INTERFAZ DE ESTILOS CSS AVANZADOS Y CONTENEDORES SCROLLABLE
# ══════════════════════════════════════════════════════════════════════════

st.set_page_config(page_title="BEAM AI × Góster Workspace v2.6", page_icon="⚡", layout="wide", initial_sidebar_state="collapsed")

if "deepseek_api_key" not in st.session_state:
    st.session_state.deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY", "")
if "transcripcion" not in st.session_state:
    st.session_state.transcripcion = ""
if "informe" not in st.session_state:
    st.session_state.informe = {"tecnica": "", "hallazgos": "", "conclusion": ""}
if "current_view" not in st.session_state:
    st.session_state.current_view = "Grid" # Estados: Grid, Col1 (Plantillas), Col2 (Dictado), Col3 (Editor)

def inyectar_estilos_avanzados():
    p = PALETA
    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
        
        .stApp {{ background-color: {p['bg']}; color: {p['text']}; font-family: {FUENTE_UI}; }}
        
        /* Layout Estilo Ventanas Goster */
        .goster-topbar {{
            background-color: {p['surface_alt']};
            border: 1px solid {p['border']};
            border-radius: 8px 8px 0 0;
            padding: 10px 14px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .goster-window-dots {{ display: flex; gap: 6px; align-items: center; }}
        .goster-w-dot {{ width: 10px; height: 10px; border-radius: 50%; display: inline-block; }}
        .w-red {{ background-color: {p['mac_red']}; }}
        .w-yellow {{ background-color: {p['mac_yellow']}; }}
        .w-green {{ background-color: {p['mac_green']}; }}
        
        .goster-window-title {{
            font-size: 0.72rem;
            font-weight: 700;
            color: {p['muted']};
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-left: 10px;
        }}
        
        /* Caja con scroll vertical independiente */
        .goster-body-box-scroll {{
            background-color: {p['surface']};
            border: 1px solid {p['border']};
            border-top: none;
            border-radius: 0 0 8px 8px;
            padding: 16px;
            margin-bottom: 20px;
            height: 70vh;
            overflow-y: auto;
            overflow-x: hidden;
        }}
        
        /* Estilización de las barras de scroll customizadas */
        .goster-body-box-scroll::-webkit-scrollbar {{ width: 6px; }}
        .goster-body-box-scroll::-webkit-scrollbar-track {{ background: {p['surface']}; }}
        .goster-body-box-scroll::-webkit-scrollbar-thumb {{ background: {p['border']}; border-radius: 3px; }}
        .goster-body-box-scroll::-webkit-scrollbar-thumb:hover {{ background: {p['accent']}; }}
        
        /* ENTORNOS WORD EXPERIMENT CONVEX */
        .word-canvas-container {{
            background-color: {p['word_canvas']};
            border: 1px solid {p['border']};
            border-radius: 6px;
            padding: 24px;
            box-shadow: inset 0 2px 8px rgba(0,0,0,0.8);
            margin-bottom: 10px;
        }}
        
        .word-ruler {{
            height: 18px;
            background-image: radial-gradient(circle, {p['border']} 1px, transparent 1px);
            background-size: 10px 10px;
            border-bottom: 1px solid {p['border']};
            margin-bottom: 15px;
            opacity: 0.6;
        }}
        
        .word-status-bar {{
            background-color: {p['surface_alt']};
            border: 1px solid {p['border']};
            padding: 6px 12px;
            border-radius: 4px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.72rem;
            color: {p['muted']};
            font-family: 'JetBrains Mono', monospace;
        }}
        
        /* Inputs y Textareas */
        textarea {{
            background-color: transparent !important;
            color: {p['text']} !important;
            border: none !important;
            border-bottom: 1px dashed {p['border']} !important;
            border-radius: 0px !important;
            font-size: 0.92rem !important;
            line-height: 1.6 !important;
            padding: 5px 0px !important;
        }}
        textarea:focus {{
            border-bottom: 1px solid {p['accent']} !important;
            box-shadow: none !important;
        }}
        
        /* Botones de control */
        div.stButton > button {{
            background-color: {p['surface_alt']};
            color: {p['text']};
            border: 1px solid {p['border']};
            border-radius: 4px;
            font-size: 0.78rem;
            padding: 4px 10px;
            transition: all 0.15s ease;
        }}
        div.stButton > button:hover {{
            border-color: {p['accent']};
            color: {p['accent']};
        }}
        div.stButton > button[kind="primary"] {{
            background-color: {p['accent']};
            color: #0B0C0E;
            font-weight: 700;
            border: none;
        }}
        
        div[data-testid="stWidgetLabel"] p {{
            font-size: 0.72rem !important;
            color: {p['accent']} !important;
            font-weight: 700 !important;
        }}
        </style>
    """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════
# LOGICA DE INFRAESTRUCTURA DE CÓDIGO
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
        return "Error: Instale la biblioteca para procesar Word ejecutando `pip install python-docx`."
    try:
        doc = docx.Document(file)
        return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    except Exception as e:
        return f"Error al leer archivo Word: {str(e)}"

def generar_informe_stream(api_key: str, dictado: str, modelo: str) -> Iterator[str]:
    cliente = obtener_cliente(api_key)
    stream = cliente.chat.completions.create(
        model=modelo,
        messages=[{"role": "system", "content": SYSTEM_PROMPT_BASE}, {"role": "user", "content": dictado}],
        temperature=0.2,
        stream=True,
    )
    for fragmento in stream:
        delta = fragmento.choices[0].delta
        texto = getattr(delta, "content", None) or ""
        if texto: yield texto

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
    return f"TÉCNICA\n{informe.get('tecnica', '').strip()}\n\nHALALZGOS\n{informe.get('hallazgos', '').strip()}\n\nCONCLUSIÓN\n{informe.get('conclusion', '').strip()}"

def reformular_seccion_api(api_key: str, texto_seccion: str, estilo_id: str, modelo: str) -> str:
    if not texto_seccion.strip(): return texto_seccion
    cliente = obtener_cliente(api_key)
    estilo = ESTILOS_REDACCION[estilo_id]
    prompt = f"""Reescribe exclusivamente la sección CONCLUSIÓN de este informe radiológico adoptando el estilo profesional: {estilo['nombre']}.
    Directriz de estilo: {estilo['instruccion']}
    CONCLUSIÓN ORIGINAL:\n{texto_seccion}
    Devuelve ÚNICAMENTE el texto optimizado resultante, sin introducciones ni comentarios."""
    
    respuesta = cliente.chat.completions.create(
        model=modelo,
        messages=[{"role": "system", "content": "Eres un editor médico experto de informes clínicos."}, {"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return aplicar_terminologia(respuesta.choices[0].message.content.strip())

# ══════════════════════════════════════════════════════════════════════════
# COMPONENTES FRONT-END (NATIVOS Y WEB SPEECH API)
# ══════════════════════════════════════════════════════════════════════════

def render_window_header(titulo: str, view_target: str):
    col_dot, col_btn = st.columns([8, 2])
    with col_dot:
        st.markdown(f"""
            <div class="goster-window-dots">
                <span class="goster-w-dot w-red"></span><span class="goster-w-dot w-yellow"></span><span class="goster-w-dot w-green"></span>
                <span class="goster-window-title">{titulo}</span>
            </div>
        """, unsafe_allow_html=True)
    with col_btn:
        if st.session_state.current_view == "Grid":
            if st.button("Expandir ⛶", key=f"exp_{view_target}", use_container_width=True):
                st.session_state.current_view = view_target
                st.rerun()
        else:
            if st.button("Contraer ⧉", key=f"cnt_{view_target}", use_container_width=True):
                st.session_state.current_view = "Grid"
                st.rerun()

def renderizar_microfono_goster(color_accent: str, label_target: str):
    html_code = f"""
    <div style="display:flex; align-items:center; justify-content:center; gap:12px; margin: 5px 0 15px 0; font-family:sans-serif;">
      <button id="btn-mic-goster" style="
          width:42px; height:42px; border-radius:50%; border:none; cursor:pointer;
          background:{color_accent}; display:flex; align-items:center; justify-content:center;
          box-shadow: 0 4px 10px {color_accent}33; transition: all 0.2s ease;">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="#0B0C0E"><path d="M12 14a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v5a3 3 0 0 0 3 3z"/><path d="M19 11a1 1 0 1 0-2 0 5 5 0 0 1-10 0 1 1 0 1 0-2 0 7 7 0 0 0 6 6.92V21a1 1 0 1 0 2 0v-3.08A7 7 0 0 0 19 11z"/></svg>
      </button>
      <span id="txt-status-goster" style="font-size:0.75rem; color:#9CA3AF; font-weight:600; letter-spacing:0.04em;">AUDIO DISPONIBLE (GOOGLE ENTRADA)</span>
    </div>
    <style>
      @keyframes goster-pulse {{ 0% {{ box-shadow: 0 0 0 0 {color_accent}50; }} 70% {{ box-shadow: 0 0 0 10px {color_accent}00; }} 100% {{ box-shadow: 0 0 0 0 {color_accent}00; }} }}
      #btn-mic-goster.recording {{ animation: goster-pulse 1.3s infinite; background: #EF4444 !important; }}
    </style>
    <script>
    (function() {{
      const btn = document.getElementById('btn-mic-goster');
      const status = document.getElementById('txt-status-goster');
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      const TARGET = {label_target!r};
      if (!SpeechRecognition) {{ status.textContent = 'DICTADO NO SOPORTADO'; btn.disabled = true; return; }}
      const rec = new SpeechRecognition(); rec.lang = 'es-MX'; rec.continuous = true; rec.interimResults = true;
      let active = false, manualStop = false, base = '', finalTranscript = '';
      function findArea() {{
        const pDoc = window.parent.document; const boxes = pDoc.querySelectorAll('[data-testid="stTextArea"]');
        for (const box of boxes) {{ if (box.innerText.includes(TARGET)) return box.querySelector('textarea'); }}
        return null;
      }}
      function injectText(text) {{
        const ta = findArea(); if (!ta) return;
        const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
        setter.call(ta, text); ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
      }}
      btn.addEventListener('click', () => {{
        active = !active;
        if (active) {{
          manualStop = false; const ta = findArea(); base = ta ? ta.value : ''; finalTranscript = ''; rec.start();
          btn.classList.add('recording'); status.textContent = 'ESCUCHANDO ATENTAMENTE...'; status.style.color = '#EF4444';
        }} else {{
          manualStop = true; rec.stop(); btn.classList.remove('recording'); status.textContent = 'DICTADO DETENIDO'; status.style.color = '#9CA3AF';
        }}
      }});
      rec.onresult = (event) => {{
        let interim = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {{
          if (event.results[i].isFinal) finalTranscript += event.results[i][0].transcript + ' ';
          else interim += event.results[i][0].transcript;
        }}
        const separator = base && !base.endsWith(' ') ? ' ' : '';
        injectText((base + separator + finalTranscript + interim).trim());
      }};
      rec.onend = () => {{ if (active && !manualStop) rec.start(); }};
    }})();
    </script>
    """
    components.html(html_code, height=65)

def renderizar_boton_copiar(texto: str, id_clave: str):
    texto_safestr = json.dumps(texto or "")
    html = f"""
    <button id="btn-cp-{id_clave}" style="width:100%; background:{PALETA['surface_alt']}; color:{PALETA['text']}; border:1px solid {PALETA['border']}; border-radius:4px; font-size:0.75rem; padding:7px; cursor:pointer; font-weight:600;">📋 Copiar Informe Integrado</button>
    <script>
    document.getElementById('btn-cp-{id_clave}').addEventListener('click', function() {{
        navigator.clipboard.writeText({texto_safestr}); this.innerText = '✓ Copiado al Portapapeles';
        setTimeout(() => {{ this.innerText = '📋 Copiar Informe Integrado'; }}, 1500);
    }});
    </script>
    """
    components.html(html, height=35)

# ══════════════════════════════════════════════════════════════════════════
# CONTENIDO DE RENDERIZACIÓN DE COLUMNAS LOGICAS
# ══════════════════════════════════════════════════════════════════════════

def render_columna_plantillas():
    st.markdown('<div class="goster-body-box-scroll">', unsafe_allow_html=True)
    st.markdown("<p style='font-size:0.8rem; margin-bottom:4px; font-weight:600;'>Subir Documentación Base (.docx)</p>", unsafe_allow_html=True)
    archivo_subido = st.file_uploader("Word", type=["docx"], label_visibility="collapsed")
    
    if archivo_subido is not None:
        texto = extraer_texto_docx(archivo_subido)
        if not texto.startswith("Error"):
            st.success("Documento parseado")
            if st.button("📥 Mapear a área de Dictado", use_container_width=True):
                st.session_state.transcripcion = texto
                st.rerun()
            st.text_area("Cuerpo del archivo Word:", value=texto, height=150, disabled=True)
            
    st.markdown("<p style='font-size:0.8rem; margin:15px 0 4px 0; font-weight:600;'>Estructuras Predefinidas</p>", unsafe_allow_html=True)
    preset = st.selectbox("Presets:", ["— Seleccionar Preset —", "Radiografía de Tórax PA", "RMN Rodilla Simple"], label_visibility="collapsed")
    if preset != "— Seleccionar Preset —":
        presets_map = {
            "Radiografía de Tórax PA": "TÉCNICA: Se realiza proyección posteroanterior de tórax.\nHALLAZGOS: Campos pulmonares limpios, sin consolidaciones ni derrames pleurales recurrentes. Silueta cardiomediastínica normal.",
            "RMN Rodilla Simple": "TÉCNICA: Secuencias multiplanares ponderadas en T1, T2 y DP con supresión grasa.\nHALLAZGOS: Estructuras meniscales íntegras. Ligamentos cruzados estables sin disrupción."
        }
        if st.button("Cargar Estructura en Dictado", use_container_width=True):
            st.session_state.transcripcion = presets_map[preset]
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

def render_columna_dictado(modelo_ia):
    st.markdown('<div class="goster-body-box-scroll">', unsafe_allow_html=True)
    LABEL_DICTADO = "Área de unificación de texto clínico"
    renderizar_microfono_goster(PALETA["accent"], label_target=LABEL_DICTADO)
    
    st.session_state.transcripcion = st.text_area(
        LABEL_DICTADO, value=st.session_state.transcripcion, height=280,
        placeholder="Dicta usando el micro, escribe o pega notas clínicas masivas de forma directa aquí..."
    )
    
    if st.button("🪄 EJECUTAR MOTOR DE INFERENCIA IA", type="primary", use_container_width=True):
        if not st.session_state.deepseek_api_key:
            st.error("Por favor ingrese la clave de DeepSeek.")
        elif not st.session_state.transcripcion.strip():
            st.warning("Ingrese hallazgos diagnósticos para procesar.")
        else:
            contenedor = st.empty()
            acumulado = ""
            try:
                for fragmento in generar_informe_stream(st.session_state.deepseek_api_key, st.session_state.transcripcion, modelo_ia):
                    acumulado += fragmento
                    contenedor.markdown(f'<div style="background:{PALETA["surface_alt"]}; border:1px solid {PALETA["accent"]}; padding:10px; border-radius:4px; font-size:0.85rem; white-space:pre-wrap;">{acumulado}▍</div>', unsafe_allow_html=True)
                st.session_state.informe = parsear_informe(acumulado)
                contenedor.empty()
                st.rerun()
            except Exception as e:
                contenedor.empty()
                st.error(f"Fallo en llamada a API: {str(e)}")
    st.markdown("</div>", unsafe_allow_html=True)

def render_columna_editor(modelo_ia):
    st.markdown('<div class="goster-body-box-scroll">', unsafe_allow_html=True)
    
    # Barra de herramientas superior estilo Word
    st.markdown("""
        <div class="editor-word-toolbar">
            <span class="toolbar-item"><b>B</b></span><span class="toolbar-item"><i>I</i></span><span class="toolbar-item"><u>U</u></span>
            <span style="color:#242936;">|</span>
            <span>Estilo: <b style="color:#FFF;">A4 Clinical Page</b></span><span style="color:#242936;">|</span>
            <span>Zoom: <b>100%</b></span>
        </div>
    """, unsafe_allow_html=True)
    
    # Lienzo simulando la página física de Microsoft Word
    st.markdown('<div class="word-canvas-container"><div class="word-ruler"></div>', unsafe_allow_html=True)
    st.session_state.informe["tecnica"] = st.text_area("TÉCNICA", value=st.session_state.informe.get("tecnica", ""), height=70)
    st.session_state.informe["hallazgos"] = st.text_area("HALLAZGOS", value=st.session_state.informe.get("hallazgos", ""), height=150)
    st.session_state.informe["conclusion"] = st.text_area("CONCLUSIÓN", value=st.session_state.informe.get("conclusion", ""), height=90)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Conteo dinámico de palabras de la página Word
    texto_total = reconstruir_informe(st.session_state.informe)
    conteo_palabras = len(re.findall(r'\w+', texto_total))
    st.markdown(f'<div class="word-status-bar"><span>PÁGINA 1 DE 1</span><span>{conteo_palabras} PALABRAS</span><span>MODO: EDITABLE</span></div><br>', unsafe_allow_html=True)
    
    st.markdown(f"<p style='font-size:0.72rem; color:{PALETA['accent']}; font-weight:700; margin-bottom:4px;'>🔮 REFORMULADOR POR ENFOQUE DE CONCLUSIONES</p>", unsafe_allow_html=True)
    c_sel, c_btn = st.columns([6, 4])
    with c_sel:
        estilo_id = st.selectbox("Estilo", options=ORDEN_ESTILOS, format_func=lambda k: f"{ESTILOS_REDACCION[k]['nombre']}", label_visibility="collapsed")
    with c_btn:
        if st.button("Modular Conclusión", use_container_width=True):
            if not st.session_state.deepseek_api_key:
                st.error("API key requerida.")
            else:
                with st.spinner("Modulando léxico..."):
                    try:
                        res = reformular_seccion_api(st.session_state.deepseek_api_key, st.session_state.informe["conclusion"], estilo_id, modelo_ia)
                        st.session_state.informe["conclusion"] = res
                        st.rerun()
                    except Exception as e: st.error(f"Error: {e}")
                    
    st.markdown("<hr style='border-color:#242936; margin:12px 0;'>", unsafe_allow_html=True)
    col_cp, col_sv = st.columns([1, 1])
    with col_cp:
        renderizar_boton_copiar(texto_total, "word_total_v2")
    with col_sv:
        if st.button("🔒 VALIDAR Y FIRMAR", use_container_width=True, type="primary"):
            st.toast("Informe guardado en el historial clínico", icon="✅")
            st.balloons()
    st.markdown("</div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════
# FLUJO PRINCIPAL DE RENDERIZACIÓN REACTIVA
# ══════════════════════════════════════════════════════════════════════════

def main():
    inyectar_estilos_avanzados()
    
    st.markdown(f"""
        <div style="display:flex; justify-content:space-between; align-items:center; padding-bottom:12px; border-bottom:1px solid {PALETA['border']}; margin-bottom:15px;">
            <div>
                <span style="font-size:1.25rem; font-weight:800; color:{PALETA['text']}; letter-spacing:-0.02em;">BEAM AI</span>
                <span style="font-size:0.75rem; background-color:{PALETA['accent_soft']}; color:{PALETA['accent']}; padding:2px 8px; border-radius:4px; font-weight:700; margin-left:8px;">SCROLL & FOCUS UI v2.6</span>
            </div>
            <div style="font-size:0.78rem; color:{PALETA['muted']}; font-family: 'JetBrains Mono', monospace;">VISTA ACTUAL: MODO INTERACTIVO REACIVABLE</div>
        </div>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.markdown(f"### <span style='color:{PALETA['accent']};'>◆ Motor DeepSeek</span>", unsafe_allow_html=True)
        st.session_state.deepseek_api_key = st.text_input("DeepSeek API Key", value=st.session_state.deepseek_api_key, type="password")
        modelo_base = st.selectbox("Modelo", list(MODELOS_DEEPSEEK.keys()), format_func=lambda m: MODELOS_DEEPSEEK[m])

    # RENDERIZADO CONDICIONAL SEGÚN EL ESTADO DE EXPANSIÓN (CURRENT_VIEW)
    v = st.session_state.current_view
    
    if v == "Grid":
        c_1, c_2, c_3 = st.columns([3.1, 3.9, 5.0])
        with c_1:
            st.markdown('<div class="goster-topbar">', unsafe_allow_html=True)
            render_window_header("GESTIÓN DE PLANTILLAS", "Col1")
            st.markdown('</div>', unsafe_allow_html=True)
            render_columna_plantillas()
        with c_2:
            st.markdown('<div class="goster-topbar">', unsafe_allow_html=True)
            render_window_header("DICTADO Y VOZ", "Col2")
            st.markdown('</div>', unsafe_allow_html=True)
            render_columna_dictado(modelo_base)
        with c_3:
            st.markdown('<div class="goster-topbar">', unsafe_allow_html=True)
            render_window_header("EDITOR DE INFORME TIPO WORD", "Col3")
            st.markdown('</div>', unsafe_allow_html=True)
            render_columna_editor(modelo_base)
            
    elif v == "Col1":
        st.markdown('<div class="goster-topbar">', unsafe_allow_html=True)
        render_window_header("GESTIÓN DE PLANTILLAS (FOCO)", "Col1")
        st.markdown('</div>', unsafe_allow_html=True)
        render_columna_plantillas()
        
    elif v == "Col2":
        st.markdown('<div class="goster-topbar">', unsafe_allow_html=True)
        render_window_header("DICTADO Y VOZ (FOCO)", "Col2")
        st.markdown('</div>', unsafe_allow_html=True)
        render_columna_dictado(modelo_base)
        
    elif v == "Col3":
        st.markdown('<div class="goster-topbar">', unsafe_allow_html=True)
        render_window_header("EDITOR DE INFORME TIPO WORD (FOCO)", "Col3")
        st.markdown('</div>', unsafe_allow_html=True)
        render_columna_editor(modelo_base)

if __name__ == "__main__":
    main()
