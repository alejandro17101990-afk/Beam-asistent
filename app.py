import streamlit as st

def main():
    # Configuración de la página
    st.set_page_config(page_title="Beam AI - Asistente Radiológico", layout="wide")
    st.title("Beam AI: Asistente de Redacción de Informes")

    # Menú lateral para la selección de parámetros
    st.sidebar.header("Parámetros del Estudio")
    modalidad = st.sidebar.selectbox("Modalidad", ["Radiografía", "Resonancia Magnética", "Tomografía Computarizada"])
    
    # Dependiendo de tu especialidad, puedes agregar más regiones
    region = st.sidebar.selectbox("Región Anatómica", ["Columna Panorámica", "Rodilla", "Hombro", "Pelvis"])

    st.subheader(f"Plantilla Activa: {modalidad} de {region}")
    st.divider()

    # Interfaz dinámica según la región seleccionada
    if region == "Columna Panorámica":
        generar_plantilla_columna(modalidad, region)
    else:
        st.info("La plantilla para esta región está en desarrollo.")

def generar_plantilla_columna(modalidad, region):
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Mediciones del Eje Vertebral**")
        angulo_cobb = st.number_input("Ángulo de Cobb (grados)", min_value=0, max_value=150, value=0)
        balance_sagital = st.selectbox("Balance Sagital", ["Conservado", "Alterado (Positivo)", "Alterado (Negativo)"])
    
    with col2:
        st.markdown("**Hallazgos Descriptivos**")
        hallazgos = st.text_area("Describa otros hallazgos (osteofitos, espacio discal, etc.)", height=150)

    # Botón para consolidar la información
    if st.button("Generar Reporte Estructurado", type="primary"):
        reporte_final = f"""
**ESTUDIO:** {modalidad} de {region}

**HALLAZGOS:**
- Se realizó evaluación del eje vertebral anatómico.
- Ángulo de Cobb medido: {angulo_cobb}°.
- Balance Sagital: {balance_sagital}.
- Hallazgos adicionales: {hallazgos if hallazgos else "No se observan alteraciones patológicas significativas adicionales."}

**CONCLUSIÓN:**
Alineación del eje vertebral evaluada con los parámetros descritos.
        """
        
        st.success("Reporte generado con éxito. Listo para copiar al RIS/PACS.")
        st.text(reporte_final)

if __name__ == "__main__":
    main()
