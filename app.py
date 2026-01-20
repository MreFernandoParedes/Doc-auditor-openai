import streamlit as st
import database
import processor
import os
import json
from dotenv import load_dotenv
from streamlit_agraph import agraph, Node, Edge, Config






load_dotenv()
st.set_page_config(layout="wide", page_title="Doc Auditor (OpenAI)")
# Custom CSS to reduce whitespace and title size
st.markdown("""
<style>
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 0rem !important;
    }
    h1 {
        font-size: 1.8rem !important;
        margin-top: 0rem !important;
        margin-bottom: 1rem !important;
    }
    .sticky-header {
        position: fixed;
        top: 2.7rem;
        left: 20.2rem;
        z-index: 80;
        background-color: rgba(255, 255, 255, 0.8);
        width: fit-content;
        padding: 5px 15px;
        border-radius: 8px;
        font-size: 1.8rem;
        font-weight: 600;
        backdrop-filter: blur(4px);
        margin-bottom: 1rem;
    }
    iframe {
        border: 1px solid #ddd;
        border-radius: 5px;
        padding: 10px;
        background-color: #fafafa;
    }
    /* Sidebar specific adjustments */
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: 0rem;
        padding-top: 0rem;
    }
    [data-testid="stSidebar"] .block-container {
        padding-top: 0rem !important;
    }
    [data-testid="stSidebar"] h1 {
        margin-top: -2.6rem !important;
    }
</style>
""", unsafe_allow_html=True)
def main():
    st.sidebar.header("Doc Auditor (OpenAI)")
    # Initialize DB (idempotent)
    database.init_db()
    # --- SIDEBAR CONFIG ---
    if os.environ.get("OPENAI_API_KEY"):
        st.sidebar.info("OPENAI_API_KEY cargada desde .env.")
    else:
        st.sidebar.warning("Falta OPENAI_API_KEY en .env; el an\u00E1lisis con IA no funcionar\u00E1.")
    # --- SIDEBAR ACTIONS ---
    if st.sidebar.button("Escanear Documentos"):
        with st.spinner("Procesando documentos..."):
            processor.scan_directory()
        st.success("Escaneo completado!")
        st.rerun()
    # --- VIEW STATE MANAGEMENT ---
    # Ensure view_mode is in session state to allow programmatic switching
    if "view_mode" not in st.session_state:
        st.session_state["view_mode"] = "\u00C1rbol de Dependencias"
    view_mode = st.sidebar.radio(
        "Vista", 
        ["\u00C1rbol de Dependencias", "Lectura Inteligente / Auditor\u00EDa"],
        key="view_mode_widget", # Use a separate widget key to avoid direct conflict, or just sync manually
        index=0 if st.session_state.get("view_mode") == "\u00C1rbol de Dependencias" else 1,
        on_change=lambda: st.session_state.update({"view_mode": st.session_state.view_mode_widget})
    )
    # --- GRAPH VIEW ---
    if st.session_state["view_mode"] == "\u00C1rbol de Dependencias":
        st.markdown('<div class="sticky-header">\u00C1rbol de Dependencias</div>', unsafe_allow_html=True)
        show_ghosts = st.sidebar.checkbox("Mostrar documentos no disponibles", value=True)
        docs, dependencies = database.get_dependencies_graph()
        if not docs:
            st.warning("No hay documentos en la base de datos. Por favor pon archivos .txt en la carpeta 'documentos' y dale a 'Escanear'.")
            return
        nodes = []
        edges = []
        added_node_ids = set()
        # Add Nodes
        for doc_id, filename in docs:
            nodes.append(Node(id=filename, label=filename, size=25, shape="dot"))
            added_node_ids.add(filename)
        # Add Edges
        for child_id, parent_id, ref_name in dependencies:
            child_name = next((d[1] for d in docs if d[0] == child_id), "Unknown")
            if parent_id:
                parent_name = next((d[1] for d in docs if d[0] == parent_id), "Unknown")
                edges.append(Edge(source=child_name, target=parent_name, label="depende de"))
            elif show_ghosts:
                # Create a ghost node for the unresolved reference
                # Check duplication first
                if ref_name not in added_node_ids:
                    nodes.append(Node(id=ref_name, label=ref_name + " (?)", color="gray"))
                    added_node_ids.add(ref_name)
                edges.append(Edge(source=child_name, target=ref_name, label=" "))
        # Physics / Animation Toggle
        # If checked: Stabilization False (Show animation)
        # If unchecked: Stabilization True (Show static / pre-calculated)
        use_physics = st.sidebar.checkbox("Mostrar animaci\u00F3n de nodos", value=True)
        physics_config = {
            "enabled": True,
            "solver": "barnesHut",
            "stabilization": {
                "enabled": False,
                "iterations": 200,
                "fit": True
            },
            "timestep": 0.4,
            "minVelocity": 0.08,
            "maxVelocity": 40,
            "barnesHut": {
                "gravitationalConstant": -4000, # Much stronger repulsion
                "centralGravity": 0.1,
                "springLength": 280, # Slightly shorter springs for snap-back
                "springConstant": 0.03, # A bit stiffer = more rebound
                "damping": 0.05, # Low damping = visible oscillation
                "avoidOverlap": 1
            }
        }
        config = Config(
            width=1200, 
            height=800, 
            directed=True, 
            nodeHighlightBehavior=True, 
            highlightColor="#F7A7A6", 
            collapsible=False, 
            fit=True,
            physics=use_physics
        )
        if use_physics:
            config.physics = physics_config
        # Render Graph
        return_value = agraph(nodes=nodes, edges=edges, config=config)
        # Interaction (Simulated double click via selection)
        if return_value:
            st.info(f"Seleccionaste: {return_value}")
            if st.button("Auditar este documento"):
                st.session_state['selected_doc'] = return_value
                st.session_state['view_mode'] = "Lectura Inteligente / Auditor\u00EDa"
                st.rerun()
    # --- AUDIT VIEW ---
    elif st.session_state["view_mode"] == "Lectura Inteligente / Auditor\u00EDa":
        st.title("Lectura Inteligente y Auditor\u00EDa")
        all_docs = database.get_all_docs()
        doc_options = {d[1]: d[0] for d in all_docs}
        # Pre-select if clicked in graph
        default_index = 0
        if 'selected_doc' in st.session_state and st.session_state['selected_doc'] in doc_options:
             default_index = list(doc_options.keys()).index(st.session_state['selected_doc'])
        selected_filename = st.selectbox("Seleccionar Documento para Auditar", list(doc_options.keys()), index=default_index)
        if selected_filename:
            doc_id = doc_options[selected_filename]
            doc_data = database.get_doc_by_id(doc_id) # id, filename, content, analysis_json
            child_content = doc_data[2]
            analysis_json = doc_data[3]
            col1, col2 = st.columns([1, 1])
            with col1:
                st.subheader("Contenido y An\u00E1lisis")
                # Check Cache
                struct = None
                if analysis_json:
                    try:
                        struct = json.loads(analysis_json)
                        st.caption("An\u00E1lisis cargado desde base de datos (sin costo)")
                    except json.JSONDecodeError:
                        pass
                if not struct:
                    with st.spinner("Generando an\u00E1lisis con IA..."):
                        struct = processor.analyze_document_structure(child_content)
                        # Save to DB
                        database.update_doc_analysis(doc_id, json.dumps(struct))
                        st.caption("Nuevo an\u00E1lisis generado y guardado.")
                st.markdown("### Resumen General")
                st.info(struct["general_summary"] or "No se pudo generar un resumen.")
                st.markdown("### Secciones Detectadas")
                for i, section in enumerate(struct["sections"]):
                    with st.expander(f"{section['title']} ({len(section['content'])} chars)"):
                        st.markdown("**Resumen de la secci\u00F3n:**")
                        st.markdown(f"_{section['summary']}_")
                        st.markdown("**Contenido:**")
                        st.text_area("Texto", section['content'], height=200, key=f"{section['title']}_{doc_id}_{i}")
            with col2:
                st.subheader("Reporte de Auditor\u00EDa")
                # Get Parents
                parents = database.get_parent_docs(doc_id)
                if not parents:
                    st.info("Este documento no parece depender de otros (o no se encontraron referencias).")
                for p_id, p_filename in parents:
                    st.write(f"---")
                    st.subheader(f"Rector: {p_filename}")
                    # Check connection
                    st.success("Documento Rector encontrado en sistema.")
                    # Get Rules from Parent
                    rules = database.get_rules_for_doc(p_id)
                    if not rules:
                        st.warning("No se extrajeron reglas claras de este documento rector.")
                    for rule_text, rule_type in rules:
                        # AUDIT CHECK
                        status = processor.check_compliance(child_content, rule_text)
                        icon = "?"
                        color = "gray"
                        msg = "Desconocido"
                        if status == "MATCH":
                            icon = "OK"
                            color = "green"
                            msg = "Cumple"
                        elif status == "PARTIAL":
                            icon = "WARN"
                            color = "orange"
                            msg = "Parcial / Ambiguo"
                        else:
                            icon = "FAIL"
                            color = "red"
                            msg = "No encontrado / Incumplimiento"
                        st.markdown(f"**[{rule_type}]** {rule_text}")
                        st.markdown(f":{color}[{icon} **{msg}**]")
if __name__ == "__main__":
    main()
