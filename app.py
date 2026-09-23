import os
import json
import uuid
import shutil
import random
import string
from datetime import datetime
from typing import Optional

import streamlit as st
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
import sqlite3

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA DE STREAMLIT
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="TERRAE | Estudio de Arquitectura",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------------------------------------------------------------------
# INICIALIZACIÓN Y MIGRACIONES DE BASE DE DATOS
# -----------------------------------------------------------------------------
DATABASE_URL = "sqlite:///./terrae_app.db"
UPLOAD_DIR = "./uploaded_media"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def apply_migrations():
    conn = sqlite3.connect("./terrae_app.db")
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE question_blocks ADD COLUMN is_active BOOLEAN DEFAULT 1;")
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute("ALTER TABLE projects ADD COLUMN is_client_blocked BOOLEAN DEFAULT 0;")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE projects ADD COLUMN project_code VARCHAR(50);")
    except sqlite3.OperationalError:
        pass
        
    conn.commit()
    conn.close()

apply_migrations()

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    role = Column(String(20), default="architect")

class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)
    architect_id = Column(Integer, ForeignKey("users.id"))
    project_code = Column(String(50), nullable=True)
    access_code = Column(String(20), unique=True, index=True, nullable=False)
    alias = Column(String(100), nullable=False)
    direccion = Column(String(255), nullable=True)
    is_client_blocked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    responses = relationship("Response", back_populates="project", cascade="all, delete-orphan")
    block_accesses = relationship("ProjectBlockAccess", back_populates="project", cascade="all, delete-orphan")

class QuestionBlock(Base):
    __tablename__ = "question_blocks"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(150), nullable=False)
    subtitle = Column(String(255), nullable=True)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    
    questions = relationship("Question", back_populates="block", cascade="all, delete-orphan")

class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True, index=True)
    block_id = Column(Integer, ForeignKey("question_blocks.id"))
    question_text = Column(Text, nullable=False)
    question_type = Column(String(30), default="text")
    sort_order = Column(Integer, default=0)
    
    block = relationship("QuestionBlock", back_populates="questions")

class ProjectBlockAccess(Base):
    __tablename__ = "project_block_access"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    block_id = Column(Integer, ForeignKey("question_blocks.id"))
    is_enabled = Column(Boolean, default=False)
    
    project = relationship("Project", back_populates="block_accesses")

class Response(Base):
    __tablename__ = "responses"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    question_id = Column(Integer, ForeignKey("questions.id"))
    answer_text = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    project = relationship("Project", back_populates="responses")
    media = relationship("ResponseMedia", back_populates="response", cascade="all, delete-orphan")

class ResponseMedia(Base):
    __tablename__ = "response_media"
    id = Column(Integer, primary_key=True, index=True)
    response_id = Column(Integer, ForeignKey("responses.id"))
    file_path = Column(String(255), nullable=False)
    filename = Column(String(255), nullable=False)
    
    response = relationship("Response", back_populates="media")

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        return db
    finally:
        db.close()

def init_db_data():
    db = SessionLocal()
    if db.query(User).count() == 0:
        admin = User(name="Super Admin", email="admin@terrae.com", password="admin", role="superadmin")
        architect = User(name="Arquitecta Nerea", email="arquitecta@terrae.com", password="terrae", role="architect")
        db.add_all([admin, architect])
        db.commit()

    if db.query(QuestionBlock).count() == 0:
        b1 = QuestionBlock(title="01. NOS CONOCEMOS", subtitle="antes de empezar a dibujar", sort_order=1)
        b2 = QuestionBlock(title="02. MIRAMOS Y DESCUBRIMOS", subtitle="antes de tomar decisiones de diseño", sort_order=2)
        b3 = QuestionBlock(title="03. EMPEZAMOS A HABITAR", subtitle="ya tenemos una primera propuesta de distribución", sort_order=3)
        b4 = QuestionBlock(title="04. DEFINIMOS", subtitle="ahora que sabemos cómo queremos vivir el espacio", sort_order=4)
        b5 = QuestionBlock(title="05. CONCRETAMOS", subtitle="pasamos de la idea al detalle", sort_order=5)
        b6 = QuestionBlock(title="06. CERRAMOS", subtitle="revisamos todo lo que hemos construido juntos", sort_order=6)
        
        db.add_all([b1, b2, b3, b4, b5, b6])
        db.commit()

        preguntas_bloque_1 = [
            ("¿Cómo vivís actualmente?", "text"),
            ("¿Qué funciona bien en vuestra vivienda?", "text"),
            ("¿Qué cosas no funcionan o echáis en falta?", "text"),
            ("¿Quién va a utilizar el espacio?", "text"),
            ("¿Cómo es vuestro día a día?", "text"),
            ("¿Qué actividades queréis que tengan lugar en la vivienda?", "text"),
            ("¿Hay necesidades actuales que debamos tener en cuenta?", "text"),
            ("¿Hay necesidades futuras que queráis prever?", "text"),
            ("¿Qué elementos queréis conservar?", "text"),
            ("¿Qué es imprescindible para vosotros?", "text"),
            ("¿Qué os gustaría conseguir con este proyecto?", "text"),
            ("¿Cómo queréis sentiros en el espacio?", "text"),
            ("¿Qué presupuesto queréis destinar al proyecto y a la obra?", "text"),
            ("Hemos identificado necesidades", "checkbox_arquitecto"),
            ("Hemos identificado prioridades", "checkbox_arquitecto"),
            ("Hemos hablado de presupuesto", "checkbox_arquitecto"),
            ("Hemos definido qué es importante para vosotros", "checkbox_arquitecto")
        ]
        for idx, (p_text, p_type) in enumerate(preguntas_bloque_1, start=1):
            db.add(Question(block_id=b1.id, question_text=p_text, question_type=p_type, sort_order=idx))

        preguntas_bloque_2 = [
            ("Espacios completos", "inspiration_category"), ("Salón", "inspiration_category"),
            ("Cocina", "inspiration_category"), ("Dormitorio", "inspiration_category"),
            ("Baño", "inspiration_category"), ("Exterior", "inspiration_category"),
            ("Iluminación", "inspiration_category"), ("Materiales", "inspiration_category"),
            ("Texturas", "inspiration_category"), ("Colores", "inspiration_category"),
            ("Carpintería", "inspiration_category"), ("Vegetación", "inspiration_category"),
            ("Otros", "inspiration_category")
        ]
        for idx, (p_text, p_type) in enumerate(preguntas_bloque_2, start=1):
            db.add(Question(block_id=b2.id, question_text=p_text, question_type=p_type, sort_order=idx))

        preguntas_bloque_3 = [
            ("RECORRIDO GENERAL", "habitar_section"), ("COCINA", "habitar_section"),
            ("SALÓN", "habitar_section"), ("DORMITORIO", "habitar_section"),
            ("BAÑOS", "habitar_section"), ("EN GENERAL", "habitar_section"),
            ("La distribución responde a nuestra forma de vivir", "checkbox_arquitecto"),
            ("Hemos detectado necesidades que no habían aparecido inicialmente", "checkbox_arquitecto"),
            ("Hemos revisado los espacios desde la experiencia, no solo desde el plano", "checkbox_arquitecto"),
            ("La distribución puede avanzar", "checkbox_arquitecto")
        ]
        for idx, (p_text, p_type) in enumerate(preguntas_bloque_3, start=1):
            db.add(Question(block_id=b3.id, question_text=p_text, question_type=p_type, sort_order=idx))

        preguntas_bloque_4 = [
            ("Pavimentos", "image"), ("Revestimientos", "image"), ("Paredes", "image"),
            ("Techos", "image"), ("Materiales naturales", "image"), ("Texturas", "image"),
            ("Colores", "image"), ("Color de puertas", "image"), ("Color de armarios", "image"),
            ("Color de cocina", "image"), ("Tiradores", "image"), ("Tipo de frente", "image"),
            ("Luz general", "image"), ("Luz ambiental", "image"), ("Luz de trabajo", "image"),
            ("Luz decorativa", "image"), ("Lámparas que queremos incorporar", "image"),
            ("Iluminación exterior", "image"), ("Plantas existentes que queremos conservar", "image"),
            ("Nuevas plantas", "image"), ("Ubicación de plantas", "image"), ("Necesidades de luz / riego", "image"),
            ("Tenemos una línea material definida", "checkbox_arquitecto"),
            ("Las decisiones responden a la distribución", "checkbox_arquitecto"),
            ("Hemos comprobado que materiales, colores y presupuesto son compatibles", "checkbox_arquitecto")
        ]
        for idx, (p_text, p_type) in enumerate(preguntas_bloque_4, start=1):
            db.add(Question(block_id=b4.id, question_text=p_text, question_type=p_type, sort_order=idx))

        db.commit()
    db.close()

init_db_data()

def generate_secure_code():
    chars = string.ascii_uppercase + string.digits
    db = SessionLocal()
    while True:
        code = f"TR-{''.join(random.choices(chars, k=6))}"
        if not db.query(Project).filter(Project.access_code == code).first():
            db.close()
            return code

# -----------------------------------------------------------------------------
# GESTIÓN DE ESTADO EN STREAMLIT
# -----------------------------------------------------------------------------
if "user" not in st.session_state:
    st.session_state.user = None
if "current_project" not in st.session_state:
    st.session_state.current_project = None

# -----------------------------------------------------------------------------
# INTERFAZ PRINCIPAL
# -----------------------------------------------------------------------------
st.title("🏠 TERRAE | Cuaderno de Diseño")

# --- VISTA: LOGIN ---
if not st.session_state.user and not st.session_state.current_project:
    tab_client, tab_staff = st.tabs(["Soy Cliente", "Arquitecta / Admin"])
    
    with tab_client:
        st.subheader("Acceso Cliente")
        client_code_input = st.text_input("Código Único de Proyecto", placeholder="EJ: TR-7K9X2M").strip().upper()
        if st.button("Acceder a mi proyecto"):
            db = SessionLocal()
            project = db.query(Project).filter(Project.access_code == client_code_input).first()
            db.close()
            if project and not project.is_client_blocked:
                st.session_state.current_project = {
                    "project_id": project.id,
                    "alias": project.alias,
                    "access_code": project.access_code,
                    "direccion": project.direccion
                }
                st.success("¡Acceso concedido!")
                st.rerun()
            else:
                st.error("Código no válido o proyecto bloqueado.")

    with tab_staff:
        st.subheader("Acceso Staff")
        email_input = st.text_input("Correo electrónico")
        password_input = st.text_input("Contraseña", type="password")
        if st.button("Iniciar Sesión Staff"):
            db = SessionLocal()
            user = db.query(User).filter(User.email == email_input, User.password == password_input).first()
            db.close()
            if user:
                st.session_state.user = {"id": user.id, "name": user.name, "role": user.role}
                st.success(f"¡Bienvenida, {user.name}!")
                st.rerun()
            else:
                st.error("Credenciales incorrectas.")

# --- VISTA: PANEL DE ARQUITECTA ---
elif st.session_state.user:
    st.sidebar.write(f"👤 **{st.session_state.user['name']}**")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.user = None
        st.rerun()

    architect_tab = st.sidebar.radio("Navegación", ["Gestión de Proyectos", "Crear Proyecto", "Gestión de Cuestionario"])
    db = SessionLocal()

    if architect_tab == "Gestión de Proyectos":
        st.header("📋 Proyectos Registrados")
        search_query = st.text_input("Buscar proyecto (código, alias, dirección)...").lower()
        
        projects = db.query(Project).all()
        for p in projects:
            if search_query and search_query not in f"{p.project_code} {p.access_code} {p.alias} {p.direccion}".lower():
                continue
            
            with st.expander(f"📁 [{p.project_code or 'S/C'}] {p.alias} (Código: {p.access_code})"):
                st.write(f"📍 **Dirección:** {p.direccion or 'Sin dirección'}")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("🔒 Bloquear/Desbloquear", key=f"block_client_{p.id}"):
                        p.is_client_blocked = not p.is_client_blocked
                        db.commit()
                        st.rerun()
                with col2:
                    if st.button("🗑️ Borrar Proyecto", key=f"del_proj_{p.id}"):
                        db.delete(p)
                        db.commit()
                        st.rerun()
                with col3:
                    if st.button("👁️ Ver Respuestas", key=f"view_proj_{p.id}"):
                        st.session_state.current_project = {
                            "project_id": p.id,
                            "alias": p.alias,
                            "access_code": p.access_code,
                            "direccion": p.direccion
                        }
                        st.rerun()

                st.write("**Fases Habilitadas:**")
                blocks = db.query(QuestionBlock).all()
                for b in blocks:
                    access = db.query(ProjectBlockAccess).filter(
                        ProjectBlockAccess.project_id == p.id,
                        ProjectBlockAccess.block_id == b.id
                    ).first()
                    is_enabled = access.is_enabled if access else False
                    
                    new_state = st.checkbox(b.title, value=is_enabled, key=f"chk_block_{p.id}_{b.id}")
                    if new_state != is_enabled:
                        if not access:
                            db.add(ProjectBlockAccess(project_id=p.id, block_id=b.id, is_enabled=new_state))
                        else:
                            access.is_enabled = new_state
                        db.commit()

    elif architect_tab == "Crear Proyecto":
        st.header("➕ Crear Nuevo Proyecto")
        with st.form("create_project_form"):
            p_code = st.text_input("Código de Proyecto (Siglas internas, ej: PRY-2701)")
            p_alias = st.text_input("Nombre / Alias del Proyecto (ej: Casa de Juan)")
            p_direccion = st.text_input("Dirección")
            submitted = st.form_submit_button("Generar Proyecto")
            
            if submitted and p_alias:
                access_code = generate_secure_code()
                new_p = Project(
                    project_code=p_code.strip(),
                    access_code=access_code,
                    alias=p_alias,
                    direccion=p_direccion,
                    architect_id=st.session_state.user["id"]
                )
                db.add(new_p)
                db.commit()
                db.refresh(new_p)
                
                # Habilitar primeros bloques por defecto
                for b_id in [1, 2, 3, 4]:
                    db.add(ProjectBlockAccess(project_id=new_p.id, block_id=b_id, is_enabled=True))
                db.commit()
                st.success(f"¡Proyecto creado con éxito! Código de acceso: **{access_code}**")

    elif architect_tab == "Gestión de Cuestionario":
        st.header("⚙️ Editor del Cuestionario Maestro")
        with st.form("new_block_form"):
            b_title = st.text_input("Título del nuevo Bloque")
            b_sub = st.text_input("Subtítulo")
            if st.form_submit_button("Crear Bloque") and b_title:
                max_order = db.query(QuestionBlock).count()
                db.add(QuestionBlock(title=b_title, subtitle=b_sub, sort_order=max_order + 1))
                db.commit()
                st.success("Bloque creado.")
                st.rerun()

        blocks = db.query(QuestionBlock).all()
        for b in blocks:
            with st.expander(f"{b.title} ({'Activo' if b.is_active else 'Oculto'})"):
                if st.button("Cambiar visibilidad bloque", key=f"toggle_b_{b.id}"):
                    b.is_active = not b.is_active
                    db.commit()
                    st.rerun()
                
                for q in b.questions:
                    st.write(f"- [{q.question_type}] {q.question_text}")

                with st.form(f"add_q_{b.id}"):
                    q_text = st.text_input("Nueva pregunta", key=f"txt_q_{b.id}")
                    q_type = st.selectbox("Tipo", ["text", "image", "checkbox_arquitecto", "inspiration_category", "habitar_section"], key=f"sel_q_{b.id}")
                    if st.form_submit_button("Añadir Pregunta") and q_text:
                        db.add(Question(block_id=b.id, question_text=q_text, question_type=q_type))
                        db.commit()
                        st.success("Pregunta añadida.")
                        st.rerun()

    db.close()

# --- VISTA: CUESTIONARIO (CLIENTE O ARQUITECTA REVISANDO) ---
elif st.session_state.current_project:
    proj_info = st.session_state.current_project
    is_architect = st.session_state.user is not None

    if st.button("⬅️ Volver al Panel"):
        st.session_state.current_project = None
        st.rerun()

    st.subheader(f"Proyecto: {proj_info['alias']}")
    if proj_info['direccion']:
        st.write(f"📍 {proj_info['direccion']}")

    db = SessionLocal()
    blocks = db.query(QuestionBlock).filter(QuestionBlock.is_active == True).all()

    for b in blocks:
        # Comprobar si está habilitado para el proyecto
        access = db.query(ProjectBlockAccess).filter(
            ProjectBlockAccess.project_id == proj_info['project_id'],
            ProjectBlockAccess.block_id == b.id,
            ProjectBlockAccess.is_enabled == True
        ).first()

        if not access and not is_architect:
            continue

        with st.expander(f"📌 {b.title} - {b.subtitle or ''}"):
            for q in b.questions:
                resp = db.query(Response).filter(
                    Response.project_id == proj_info['project_id'],
                    Response.question_id == q.id
                ).first()
                current_answer = resp.answer_text if resp else ""

                if q.question_type == "checkbox_arquitecto":
                    checked_val = current_answer == "1"
                    if is_architect:
                        new_chk = st.checkbox(f"{q.question_text} (Control Arquitecta)", value=checked_val, key=f"q_{q.id}")
                        if new_chk != checked_val:
                            if not resp:
                                resp = Response(project_id=proj_info['project_id'], question_id=q.id, answer_text="1" if new_chk else "0")
                                db.add(resp)
                            else:
                                resp.answer_text = "1" if new_chk else "0"
                            db.commit()
                    else:
                        st.write(f"✅ {q.question_text}: **{'Sí' if checked_val else 'Pendiente'}**")
                
                elif q.question_type == "image":
                    st.write(f"🖼️ **{q.question_text}**")
                    uploaded_file = st.file_uploader(f"Subir imagen para {q.question_text}", type=["jpg", "png", "jpeg"], key=f"file_{q.id}")
                    if uploaded_file and resp:
                        file_ext = os.path.splitext(uploaded_file.name)[1]
                        unique_name = f"{uuid.uuid4().hex}{file_ext}"
                        file_path = os.path.join(UPLOAD_DIR, unique_name)
                        with open(file_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        db.add(ResponseMedia(response_id=resp.id, file_path=file_path, filename=unique_name))
                        db.commit()
                    
                    new_text = st.text_area(f"Notas sobre {q.question_text}", value=current_answer, key=f"txt_{q.id}")
                    if st.button("Guardar notas", key=f"btn_{q.id}"):
                        if not resp:
                            resp = Response(project_id=proj_info['project_id'], question_id=q.id, answer_text=new_text)
                            db.add(resp)
                        else:
                            resp.answer_text = new_text
                        db.commit()
                        st.success("Guardado.")

                else:
                    new_text = st.text_area(q.question_text, value=current_answer, key=f"txt_{q.id}")
                    if st.button("Guardar", key=f"btn_std_{q.id}"):
                        if not resp:
                            resp = Response(project_id=proj_info['project_id'], question_id=q.id, answer_text=new_text)
                            db.add(resp)
                        else:
                            resp.answer_text = new_text
                        db.commit()
                        st.success("Guardado.")

    db.close()