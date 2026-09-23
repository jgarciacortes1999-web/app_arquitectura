import os
import json
import uuid
import shutil
import random
import string
from typing import List, Optional
from datetime import datetime

import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Form, File, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
import sqlite3

# -----------------------------------------------------------------------------
# INICIALIZACIÓN Y MIGRACIONES DE BASE DE DATOS
# -----------------------------------------------------------------------------
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

# -----------------------------------------------------------------------------
# BASE DE DATOS Y CONFIGURACIÓN
# -----------------------------------------------------------------------------
DATABASE_URL = "sqlite:///./terrae_app.db"
UPLOAD_DIR = "./uploaded_media"
STATIC_DIR = "./static"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

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
        yield db
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
            q = Question(block_id=b1.id, question_text=p_text, question_type=p_type, sort_order=idx)
            db.add(q)

        preguntas_bloque_2 = [
            ("Espacios completos", "inspiration_category"),
            ("Salón", "inspiration_category"),
            ("Cocina", "inspiration_category"),
            ("Dormitorio", "inspiration_category"),
            ("Baño", "inspiration_category"),
            ("Exterior", "inspiration_category"),
            ("Iluminación", "inspiration_category"),
            ("Materiales", "inspiration_category"),
            ("Texturas", "inspiration_category"),
            ("Colores", "inspiration_category"),
            ("Carpintería", "inspiration_category"),
            ("Vegetación", "inspiration_category"),
            ("Otros", "inspiration_category")
        ]

        for idx, (p_text, p_type) in enumerate(preguntas_bloque_2, start=1):
            q = Question(block_id=b2.id, question_text=p_text, question_type=p_type, sort_order=idx)
            db.add(q)

        preguntas_bloque_3 = [
            ("RECORRIDO GENERAL", "habitar_section"),
            ("COCINA", "habitar_section"),
            ("SALÓN", "habitar_section"),
            ("DORMITORIO", "habitar_section"),
            ("BAÑOS", "habitar_section"),
            ("EN GENERAL", "habitar_section"),
            ("La distribución responde a nuestra forma de vivir", "checkbox_arquitecto"),
            ("Hemos detectado necesidades que no habían aparecido inicialmente", "checkbox_arquitecto"),
            ("Hemos revisado los espacios desde la experiencia, no solo desde el plano", "checkbox_arquitecto"),
            ("La distribución puede avanzar", "checkbox_arquitecto")
        ]

        for idx, (p_text, p_type) in enumerate(preguntas_bloque_3, start=1):
            q = Question(block_id=b3.id, question_text=p_text, question_type=p_type, sort_order=idx)
            db.add(q)

        # BLOQUE 4
        preguntas_bloque_4 = [
            ("Pavimentos", "image"),
            ("Revestimientos", "image"),
            ("Paredes", "image"),
            ("Techos", "image"),
            ("Materiales naturales", "image"),
            ("Texturas", "image"),
            ("Colores", "image"),
            ("Color de puertas", "image"),
            ("Color de armarios", "image"),
            ("Color de cocina", "image"),
            ("Tiradores", "image"),
            ("Tipo de frente", "image"),
            ("Luz general", "image"),
            ("Luz ambiental", "image"),
            ("Luz de trabajo", "image"),
            ("Luz decorativa", "image"),
            ("Lámparas que queremos incorporar", "image"),
            ("Iluminación exterior", "image"),
            ("Plantas existentes que queremos conservar", "image"),
            ("Nuevas plantas", "image"),
            ("Ubicación de plantas", "image"),
            ("Necesidades de luz / riego", "image"),
            ("Tenemos una línea material definida", "checkbox_arquitecto"),
            ("Las decisiones responden a la distribución", "checkbox_arquitecto"),
            ("Hemos comprobado que materiales, colores y presupuesto son compatibles", "checkbox_arquitecto")
        ]

        for idx, (p_text, p_type) in enumerate(preguntas_bloque_4, start=1):
            q = Question(block_id=b4.id, question_text=p_text, question_type=p_type, sort_order=idx)
            db.add(q)

        db.commit()

    db.close()

init_db_data()

app = FastAPI(title="TERRAE - Cuaderno de Diseño")
app.mount("/media", StaticFiles(directory=UPLOAD_DIR), name="media")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

def generate_secure_code():
    chars = string.ascii_uppercase + string.digits
    while True:
        part = ''.join(random.choices(chars, k=6))
        code = f"TR-{part}"
        db = SessionLocal()
        exists = db.query(Project).filter(Project.access_code == code).first()
        db.close()
        if not exists:
            return code

@app.post("/api/login")
def login(email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email, User.password == password).first()
    if not user:
        raise HTTPException(status_code=400, detail="Credenciales incorrectas")
    return {"status": "ok", "user": {"id": user.id, "name": user.name, "role": user.role}}

@app.post("/api/client-access")
def client_access(code: str = Form(...), db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.access_code == code.strip().upper()).first()
    if not project or project.is_client_blocked:
        raise HTTPException(status_code=404, detail="Código no válido")
    return {"status": "ok", "project_id": project.id, "alias": project.alias, "access_code": project.access_code}

@app.get("/api/projects")
def list_projects(db: Session = Depends(get_db)):
    projects = db.query(Project).all()
    result = []
    for p in projects:
        accesses = db.query(ProjectBlockAccess).filter(ProjectBlockAccess.project_id == p.id, ProjectBlockAccess.is_enabled == True).all()
        enabled_blocks = [a.block_id for a in accesses]
        result.append({
            "id": p.id,
            "project_code": p.project_code or "",
            "access_code": p.access_code,
            "alias": p.alias,
            "direccion": p.direccion or "",
            "is_client_blocked": p.is_client_blocked,
            "created_at": p.created_at.strftime("%Y-%m-%d %H:%M"),
            "enabled_blocks": enabled_blocks
        })
    return result

@app.post("/api/projects/create")
def create_project(
    project_code: str = Form(...),
    alias: str = Form(...),
    direccion: str = Form(...),
    db: Session = Depends(get_db)
):
    access_code = generate_secure_code()
    
    project = Project(
        project_code=project_code.strip(),
        access_code=access_code,
        alias=alias,
        direccion=direccion,
        architect_id=2
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    
    access1 = ProjectBlockAccess(project_id=project.id, block_id=1, is_enabled=True)
    access2 = ProjectBlockAccess(project_id=project.id, block_id=2, is_enabled=True)
    access3 = ProjectBlockAccess(project_id=project.id, block_id=3, is_enabled=True)
    access4 = ProjectBlockAccess(project_id=project.id, block_id=4, is_enabled=True)
    db.add_all([access1, access2, access3, access4])
    db.commit()
    return {"status": "ok", "project": {"id": project.id, "project_code": project.project_code, "access_code": project.access_code, "alias": project.alias}}

@app.post("/api/projects/toggle-client-block")
def toggle_client_block(project_id: int = Form(...), db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    project.is_client_blocked = not project.is_client_blocked
    db.commit()
    return {"status": "ok", "is_client_blocked": project.is_client_blocked}

@app.post("/api/projects/delete")
def delete_project_permanent(project_id: int = Form(...), db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    
    responses = db.query(Response).filter(Response.project_id == project_id).all()
    for resp in responses:
        media_items = db.query(ResponseMedia).filter(ResponseMedia.response_id == resp.id).all()
        for m in media_items:
            try:
                if os.path.exists(m.file_path):
                    os.remove(m.file_path)
            except Exception:
                pass

    db.delete(project)
    db.commit()
    return {"status": "ok"}

@app.post("/api/projects/toggle-block")
def toggle_block(project_id: int = Form(...), block_id: int = Form(...), enabled: bool = Form(...), db: Session = Depends(get_db)):
    access = db.query(ProjectBlockAccess).filter(
        ProjectBlockAccess.project_id == project_id,
        ProjectBlockAccess.block_id == block_id
    ).first()
    if not access:
        access = ProjectBlockAccess(project_id=project_id, block_id=block_id, is_enabled=enabled)
        db.add(access)
    else:
        access.is_enabled = enabled
    db.commit()
    return {"status": "ok"}

@app.get("/api/blocks")
def get_blocks(project_id: Optional[int] = None, include_hidden: bool = False, db: Session = Depends(get_db)):
    query = db.query(QuestionBlock)
    if not include_hidden:
        query = query.filter(QuestionBlock.is_active == True)
    blocks = query.order_by(QuestionBlock.sort_order).all()
    
    enabled_block_ids = []
    if project_id:
        accesses = db.query(ProjectBlockAccess).filter(
            ProjectBlockAccess.project_id == project_id,
            ProjectBlockAccess.is_enabled == True
        ).all()
        enabled_block_ids = [a.block_id for a in accesses]

    result = []
    for b in blocks:
        questions = db.query(Question).filter(Question.block_id == b.id).order_by(Question.sort_order).all()
        q_list = []
        for q in questions:
            resp_data = None
            media_list = []
            if project_id:
                resp = db.query(Response).filter(Response.project_id == project_id, Response.question_id == q.id).first()
                if resp:
                    resp_data = resp.answer_text
                    m_items = db.query(ResponseMedia).filter(ResponseMedia.response_id == resp.id).all()
                    media_list = [{"id": m.id, "url": f"/media/{m.filename}", "name": m.filename} for m in m_items]
            
            q_list.append({
                "id": q.id,
                "text": q.question_text,
                "question_text": q.question_text,
                "type": q.question_type,
                "question_type": q.question_type,
                "response": resp_data,
                "media": media_list
            })
            
        result.append({
            "id": b.id,
            "title": b.title,
            "subtitle": b.subtitle,
            "is_active": b.is_active,
            "is_enabled": b.id in enabled_block_ids if project_id else True,
            "questions": q_list
        })
    return result

@app.post("/api/admin/blocks/create")
def create_block(title: str = Form(...), subtitle: Optional[str] = Form(None), db: Session = Depends(get_db)):
    max_order = db.query(QuestionBlock).count()
    new_block = QuestionBlock(title=title, subtitle=subtitle, sort_order=max_order + 1, is_active=True)
    db.add(new_block)
    db.commit()
    return {"status": "ok"}

@app.post("/api/admin/blocks/toggle-active")
def toggle_block_active(block_id: int = Form(...), db: Session = Depends(get_db)):
    block = db.query(QuestionBlock).filter(QuestionBlock.id == block_id).first()
    if block:
        block.is_active = not block.is_active
        db.commit()
    return {"status": "ok"}

@app.post("/api/admin/blocks/delete")
def delete_block(block_id: int = Form(...), db: Session = Depends(get_db)):
    block = db.query(QuestionBlock).filter(QuestionBlock.id == block_id).first()
    if block:
        db.delete(block)
        db.commit()
    return {"status": "ok"}

@app.post("/api/admin/questions/create")
def create_question(block_id: int = Form(...), question_text: str = Form(...), question_type: str = Form("text"), db: Session = Depends(get_db)):
    max_order = db.query(Question).filter(Question.block_id == block_id).count()
    new_q = Question(block_id=block_id, question_text=question_text, question_type=question_type, sort_order=max_order + 1)
    db.add(new_q)
    db.commit()
    return {"status": "ok"}

@app.post("/api/admin/questions/delete")
def delete_question(question_id: int = Form(...), db: Session = Depends(get_db)):
    q = db.query(Question).filter(Question.id == question_id).first()
    if q:
        db.delete(q)
        db.commit()
    return {"status": "ok"}

@app.post("/api/responses/save")
async def save_response(
    project_id: int = Form(...),
    question_id: int = Form(...),
    answer_text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    resp = db.query(Response).filter(Response.project_id == project_id, Response.question_id == question_id).first()
    if not resp:
        resp = Response(project_id=project_id, question_id=question_id, answer_text=answer_text)
        db.add(resp)
        db.commit()
        db.refresh(resp)
    else:
        if answer_text is not None:
            resp.answer_text = answer_text
            resp.updated_at = datetime.utcnow()
        db.commit()

    if file:
        file_ext = os.path.splitext(file.filename)[1]
        unique_name = f"{uuid.uuid4().hex}{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, unique_name)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        media = ResponseMedia(response_id=resp.id, file_path=file_path, filename=unique_name)
        db.add(media)
        db.commit()

    return {"status": "ok"}

@app.post("/api/media/delete")
def delete_media(media_id: int = Form(...), db: Session = Depends(get_db)):
    media = db.query(ResponseMedia).filter(ResponseMedia.id == media_id).first()
    if media:
        try:
            if os.path.exists(media.file_path):
                os.remove(media.file_path)
        except Exception:
            pass
        db.delete(media)
        db.commit()
    return {"status": "ok"}

# -----------------------------------------------------------------------------
# INTERFAZ FRONTEND HTML/JS INTEGRADA (100% RESPONSIVA)
# -----------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    return """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TERRAE | Estudio de Arquitectura</title>

    <!-- Favicon -->
    <link rel="icon" type="image/jpeg" href="/static/logo_icon.jpg?v=1">
    <link rel="shortcut icon" type="image/jpeg" href="/static/logo_icon.jpg?v=1">
    <link rel="apple-touch-icon" href="/static/logo_icon.jpg?v=1">

    <!-- Tipografías Oficiales TERRAE: DM Sans & Fraunces -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,100..1000;1,9..40,100..1000&family=Fraunces:ital,opsz,wght@0,9..144,100..900;1,9..144,100..900&display=swap" rel="stylesheet">

    <!-- Tailwind CSS con Paleta Oficial TERRAE Modificada -->
    <script src="https://cdn.tailwindcss.com"></script>
    
    <!-- SweetAlert2 CSS & JS -->
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>

    <script>
      tailwind.config = {
        theme: {
          extend: {
            colors: {
              terrae: {
                oliva: '#67610B',
                tierra: '#5E2D19',
                terracota: '#BB4214',
                origen: '#C1B591',
                natural: 'rgba(103, 97, 11, 0.12)',
                DEFAULT: '#67610B',
                dark: '#524d09',
                bg: 'rgba(103, 97, 11, 0.10)',
                text: '#2B2823'
              }
            },
            fontFamily: {
              serif: ['Fraunces', 'serif'],
              sans: ['DM Sans', 'sans-serif']
            }
          }
        }
      }
    </script>
    <style>
        h1, h2, h3, h4, .font-heading {
            font-family: 'Fraunces', serif;
        }
        body, input, textarea, select, button {
            font-family: 'DM Sans', sans-serif;
        }
        .swal2-popup {
            font-family: 'DM Sans', sans-serif !important;
            border-radius: 0.75rem !important;
            border: 1px solid #C1B591 !important;
            max-width: 90vw !important;
        }
        .swal2-styled.swal2-confirm {
            background-color: #5E2D19 !important;
            box-shadow: none !important;
        }
        .swal2-styled.swal2-confirm:hover {
            background-color: #4c2414 !important;
        }
    </style>
</head>
<body class="bg-terrae-bg text-terrae-text min-h-screen flex flex-col font-sans antialiased overflow-x-hidden">

    <!-- HEADER FIJO RESPONSIVO -->
    <header class="sticky top-0 z-50 bg-white/95 backdrop-blur-sm border-b-2 border-terrae-origen px-4 sm:px-8 py-3 sm:py-4 flex justify-between items-center shadow-sm">
        <div class="flex items-center gap-2 sm:gap-3 min-w-0">
            <img src="/static/logo_icon.jpg" alt="Logo Icono TERRAE" class="h-8 sm:h-10 object-contain shrink-0" onerror="this.style.display='none'">
            <img src="/static/logo_full.jpg" alt="TERRAE Estudio de Arquitectura" class="h-6 sm:h-8 object-contain hidden sm:block shrink-0" onerror="this.style.display='none'">
            <div class="sm:hidden min-w-0">
                <h1 class="text-lg font-normal tracking-widest text-terrae-tierra truncate">TERRAE</h1>
            </div>
        </div>
        <div id="userHeaderArea" class="hidden items-center gap-2 sm:gap-3 shrink-0">
            <span id="userBadge" class="text-[11px] sm:text-xs font-semibold text-terrae-tierra bg-terrae-natural px-2.5 sm:px-3 py-1 sm:py-1.5 rounded-full border border-terrae-oliva/30 truncate max-w-[120px] sm:max-w-none"></span>
            <button onclick="logout()" class="text-[11px] sm:text-xs font-semibold uppercase tracking-wider text-terrae-tierra hover:opacity-75 transition px-2 sm:px-3 py-1 sm:py-1.5 rounded border border-transparent cursor-pointer shrink-0">
                Salir
            </button>
        </div>
    </header>

    <!-- MAIN CONTAINER -->
    <main class="flex-1 max-w-5xl w-full mx-auto p-3 sm:p-6 min-w-0">

        <!-- LOGIN VIEW -->
        <div id="loginView" class="max-w-md mx-auto my-6 sm:my-12 bg-white p-5 sm:p-8 rounded-lg shadow-sm border border-terrae-origen">
            <h2 class="text-xl sm:text-2xl font-normal text-center mb-6 tracking-wide text-terrae-tierra">Acceso al Cuaderno</h2>

            <div class="flex border-b border-terrae-origen mb-6">
                <button id="tabClientBtn" onclick="switchTab('client')" class="flex-1 py-2 text-center font-bold text-xs sm:text-sm transition border-b-2 border-terrae-oliva text-terrae-oliva cursor-pointer">
                    Soy Cliente
                </button>
                <button id="tabStaffBtn" onclick="switchTab('staff')" class="flex-1 py-2 text-center font-medium text-xs sm:text-sm transition border-b-2 border-transparent text-gray-400 hover:text-terrae-text cursor-pointer">
                    Arquitecta / Admin
                </button>
            </div>

            <div id="clientTabContent" class="space-y-4">
                <form onsubmit="handleClientLogin(event)" class="space-y-4">
                    <div>
                        <label class="block text-xs uppercase font-semibold text-gray-600 mb-1">Código Único de Proyecto</label>
                        <input type="text" id="clientCode" placeholder="EJ: TR-7K9X2M" required class="w-full px-4 py-3 border border-terrae-origen rounded focus:outline-none focus:border-terrae-oliva text-center font-bold uppercase text-base sm:text-lg bg-white text-terrae-text placeholder-gray-300">
                    </div>
                    <button type="submit" class="w-full bg-terrae-tierra text-white py-3 rounded text-xs uppercase tracking-wider transition font-bold cursor-pointer shadow">ACCEDER A MI PROYECTO</button>
                </form>
            </div>

            <div id="staffTabContent" class="hidden space-y-4">
                <form onsubmit="handleStaffLogin(event)" class="space-y-3">
                    <div>
                        <label class="block text-xs uppercase font-semibold text-gray-600 mb-1">Correo Electrónico</label>
                        <input type="email" id="staffEmail" placeholder="Email" required class="w-full px-3 py-2 border border-terrae-origen rounded text-sm focus:outline-none focus:border-terrae-oliva">
                    </div>
                    <div>
                        <label class="block text-xs uppercase font-semibold text-gray-600 mb-1">Contraseña</label>
                        <input type="password" id="staffPassword" placeholder="Contraseña" required class="w-full px-3 py-2 border border-terrae-origen rounded text-sm focus:outline-none focus:border-terrae-oliva">
                    </div>
                    <button type="submit" class="w-full bg-terrae-tierra text-white py-3 rounded text-xs uppercase tracking-wider hover:opacity-90 transition font-bold cursor-pointer shadow">Iniciar Sesión Staff</button>
                </form>
            </div>
        </div>

        <!-- ARCHITECT DASHBOARD -->
        <div id="architectView" class="hidden space-y-4 sm:space-y-6">
            <div class="flex overflow-x-auto border-b border-terrae-origen gap-2 sm:gap-4 bg-white p-2 rounded-t-lg shadow-sm whitespace-nowrap">
                <button id="navProjectsBtn" onclick="switchArchitectTab('projects')" class="px-3 sm:px-4 py-2 font-bold text-xs sm:text-sm border-b-2 border-terrae-oliva text-terrae-oliva cursor-pointer shrink-0">
                    Gestión de Proyectos
                </button>
                <button id="navCreateBtn" onclick="switchArchitectTab('create')" class="px-3 sm:px-4 py-2 font-medium text-xs sm:text-sm border-b-2 border-transparent text-gray-400 hover:text-terrae-text cursor-pointer shrink-0">
                    Creación de Proyecto
                </button>
                <button id="navBuilderBtn" onclick="switchArchitectTab('builder')" class="px-3 sm:px-4 py-2 font-medium text-xs sm:text-sm border-b-2 border-transparent text-gray-400 hover:text-terrae-text cursor-pointer shrink-0">
                    Gestión de Cuestionario
                </button>
            </div>

            <!-- SECCIÓN 1: GESTIÓN DE PROYECTOS -->
            <div id="architectProjectsSection" class="space-y-4 sm:space-y-6">
                <div class="bg-white p-4 sm:p-6 rounded-lg shadow-sm border border-terrae-origen">
                    <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6 pb-4 border-b border-terrae-origen/40">
                        <h3 class="text-base sm:text-lg font-normal text-terrae-tierra m-0">Proyectos Registrados</h3>
                        
                        <div class="relative w-full sm:w-72">
                            <span class="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none text-terrae-oliva">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                            </span>
                            <input type="text" id="projectSearchInput" oninput="filterProjectsList()" placeholder="Buscar por código, alias..." class="w-full pl-9 pr-8 py-2 bg-white border border-terrae-origen rounded-lg text-xs text-terrae-text placeholder-terrae-oliva/60 focus:outline-none focus:border-terrae-origen shadow-inner">
                            <button id="clearSearchBtn" onclick="clearProjectSearch()" class="absolute inset-y-0 right-0 hidden items-center pr-2.5 text-gray-400 hover:text-terrae-tierra text-xs">✕</button>
                        </div>
                    </div>

                    <div id="projectsList" class="space-y-4"></div>
                </div>
            </div>

            <!-- SECCIÓN 2: CREACIÓN DE PROYECTO -->
            <div id="architectCreateSection" class="hidden space-y-4 sm:space-y-6">
                <div class="bg-white p-4 sm:p-6 rounded-lg border border-terrae-origen shadow-sm space-y-4">
                    <h3 class="text-base sm:text-lg font-normal text-terrae-tierra mb-2">Crear Nuevo Proyecto</h3>
                    <form onsubmit="handleCreateProject(event)" class="space-y-4">
                        <div>
                            <label class="block text-xs uppercase font-semibold text-gray-600 mb-1">Código de Proyecto (Tus siglas internas)</label>
                            <input type="text" id="newProjectCode" placeholder="Ej: PRY-2701" class="w-full px-4 py-2 border border-terrae-origen rounded focus:outline-none focus:border-terrae-oliva bg-white text-terrae-text font-bold">
                        </div>
                        <div>
                            <label class="block text-xs uppercase font-semibold text-gray-600 mb-1">Nombre / Alias del Proyecto</label>
                            <input type="text" id="newAlias" placeholder="Ej: Casa de Juan y Elena" class="w-full px-4 py-2 border border-terrae-origen rounded focus:outline-none focus:border-terrae-oliva bg-white text-terrae-text">
                        </div>
                        <div>
                            <label class="block text-xs uppercase font-semibold text-gray-600 mb-1">Dirección</label>
                            <input type="text" id="newDireccion" placeholder="Ej: Calle Aljarafe 14, Sevilla" class="w-full px-4 py-2 border border-terrae-origen rounded focus:outline-none focus:border-terrae-oliva bg-white text-terrae-text">
                        </div>
                        <div class="bg-terrae-natural/40 p-3 rounded border border-terrae-origen text-xs text-terrae-tierra">
                            💡 El sistema generará automáticamente un <b>Código de Acceso Seguro</b> asociado a este proyecto.
                        </div>
                        <div class="flex justify-end pt-2">
                            <button type="submit" class="w-full sm:w-auto bg-terrae-tierra text-white px-6 py-2.5 rounded transition font-bold text-xs uppercase tracking-wider cursor-pointer shadow">GENERAR PROYECTO</button>
                        </div>
                    </form>
                </div>
            </div>

            <!-- SECCIÓN 3: GESTIÓN DE CUESTIONARIO -->
            <div id="architectBuilderSection" class="hidden space-y-4 sm:space-y-6">
                <div class="bg-white p-4 sm:p-6 rounded-lg shadow-sm border border-terrae-origen">
                    <h2 class="text-lg sm:text-xl font-normal text-terrae-tierra mb-1">Editor del Cuestionario Maestro</h2>
                    <p class="text-xs text-gray-500 mb-4">Añade, elimina u oculta bloques y preguntas globales.</p>
                    
                    <form onsubmit="handleCreateBlock(event)" class="flex flex-col sm:flex-row gap-3 sm:items-end bg-terrae-natural/30 p-4 rounded border border-terrae-origen">
                        <div class="flex-1 w-full">
                            <label class="block text-xs font-semibold text-gray-600 mb-1">Título del Bloque / Fase</label>
                            <input type="text" id="newBlockTitle" placeholder="Ej: 07. MATERIALES" required class="w-full px-3 py-2 sm:py-1.5 border border-terrae-origen rounded text-sm bg-white">
                        </div>
                        <div class="flex-1 w-full">
                            <label class="block text-xs font-semibold text-gray-600 mb-1">Subtítulo (Opcional)</label>
                            <input type="text" id="newBlockSubtitle" placeholder="Ej: Selección de texturas" class="w-full px-3 py-2 sm:py-1.5 border border-terrae-origen rounded text-sm bg-white">
                        </div>
                        <button type="submit" class="w-full sm:w-auto bg-terrae-oliva hover:bg-terrae-dark text-white px-4 py-2 sm:py-1.5 rounded text-sm transition cursor-pointer font-medium shrink-0">+ Crear Bloque</button>
                    </form>
                </div>

                <div id="builderBlocksContainer" class="space-y-6"></div>
            </div>
        </div>

        <!-- QUESTIONNAIRE VIEW -->
        <div id="questionnaireView" class="hidden space-y-4 sm:space-y-6">
            <!-- BARRA SUPERIOR REDISEÑADA Y ADAPTADA A MÓVIL (FLEX-COL EN SM-) -->
            <div id="architectTopBar" class="bg-white p-4 sm:p-5 rounded-xl shadow-sm border border-terrae-origen flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div class="flex flex-col sm:flex-row sm:items-center gap-3 min-w-0 w-full">
                    <div class="inline-flex items-center gap-2 bg-white text-terrae-tierra border border-terrae-origen px-3 py-1.5 rounded-full text-xs font-bold tracking-wide shadow-2xs self-start shrink-0">
                        <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                        <span id="projectCodeBadge"></span>
                    </div>
                    <div class="min-w-0 w-full">
                        <h2 id="projectAliasHeader" class="text-base sm:text-base font-bold text-terrae-tierra font-heading m-0 truncate"></h2>
                        <p id="projectDireccionHeader" class="text-xs text-gray-500 mt-1 truncate"></p>
                    </div>
                </div>
                
                <div class="flex items-center w-full sm:w-auto shrink-0 pt-2 sm:pt-0 border-t sm:border-t-0 border-terrae-origen/20">
                    <button id="btnBackToPanel" onclick="goBackFromQuestionnaire()" class="w-full sm:w-auto bg-white border border-terrae-origen text-terrae-tierra hover:bg-terrae-natural/20 px-4 py-2.5 sm:py-2 rounded-lg text-xs font-semibold uppercase tracking-wider transition cursor-pointer shadow-2xs text-center">
                        Volver al Panel
                    </button>
                </div>
            </div>

            <div id="blocksContainer" class="space-y-4 sm:space-y-6"></div>
        </div>

    </main>

    <script>
        let currentProject = null;
        let allProjectsCache = [];
        let allBlocksCache = [];

        const habitarQuestionsMap = {
            "RECORRIDO GENERAL": [
                "¿Qué vemos al entrar?",
                "¿Dónde dejamos las cosas al llegar?",
                "¿Cómo nos desplazamos por la vivienda?",
                "¿Dónde ocurre cada actividad?",
                "¿Hay recorridos que resulten incómodos?",
                "¿Hay espacios que podrían tener otro uso?"
            ],
            "COCINA": [
                "¿Quién cocina habitualmente?",
                "¿Se cocina solo o acompañado?",
                "¿Se desayuna aquí?",
                "¿Se come aquí?",
                "¿Qué necesitamos tener a mano?",
                "¿Qué pequeños electrodomésticos utilizamos?",
                "¿Dónde los guardaríamos?",
                "¿Qué necesitamos enchufar?"
            ],
            "SALÓN": [
                "¿Dónde nos sentamos?",
                "¿Vemos la televisión?",
                "¿Leemos?",
                "¿Trabajamos?",
                "¿Recibimos visitas?",
                "¿Necesitamos diferentes ambientes?"
            ],
            "DORMITORIO": [
                "¿Cómo empieza y termina nuestro día?",
                "¿Necesitamos televisión?",
                "¿Leemos en la cama?",
                "¿Qué necesitamos guardar?",
                "¿Necesitamos enchufes junto a la cama?",
                "¿Hay iluminación específica que necesitemos?"
            ],
            "BAÑOS": [
                "¿Quién utiliza cada baño?",
                "¿Necesitamos almacenamiento?",
                "¿Ducha o bañera?",
                "¿Necesitamos espacio para dos personas?",
                "¿Hay alguna necesidad especial?"
            ],
            "EN GENERAL": [
                "¿Dónde cargaríamos el móvil?",
                "¿Dónde enchufamos el aspirador?",
                "¿Dónde ponemos el ordenador?",
                "¿Dónde dejamos las llaves?",
                "¿Dónde guardamos aquello que utilizamos diariamente?"
            ]
        };

        const Toast = Swal.mixin({
            toast: true,
            position: 'bottom-end',
            showConfirmButton: false,
            timer: 2500,
            timerProgressBar: true,
            didOpen: (toast) => {
                toast.addEventListener('mouseenter', Swal.stopTimer);
                toast.addEventListener('mouseleave', Swal.resumeTimer);
            }
        });

        function switchTab(tab) {
            const clientTab = document.getElementById('clientTabContent');
            const staffTab = document.getElementById('staffTabContent');
            const clientBtn = document.getElementById('tabClientBtn');
            const staffBtn = document.getElementById('tabStaffBtn');

            if (tab === 'client') {
                clientTab.classList.remove('hidden');
                staffTab.classList.add('hidden');
                
                clientBtn.className = 'flex-1 py-2 text-center font-bold text-xs sm:text-sm transition border-b-2 border-terrae-oliva text-terrae-oliva cursor-pointer';
                staffBtn.className = 'flex-1 py-2 text-center font-medium text-xs sm:text-sm transition border-b-2 border-transparent text-gray-400 hover:text-terrae-text cursor-pointer';
            } else {
                clientTab.classList.add('hidden');
                staffTab.classList.remove('hidden');

                staffBtn.className = 'flex-1 py-2 text-center font-bold text-xs sm:text-sm transition border-b-2 border-terrae-oliva text-terrae-oliva cursor-pointer';
                clientBtn.className = 'flex-1 py-2 text-center font-medium text-xs sm:text-sm transition border-b-2 border-transparent text-gray-400 hover:text-terrae-text cursor-pointer';
            }
        }

        function switchArchitectTab(tab) {
            const projectsSec = document.getElementById('architectProjectsSection');
            const createSec = document.getElementById('architectCreateSection');
            const builderSec = document.getElementById('architectBuilderSection');
            
            const projectsBtn = document.getElementById('navProjectsBtn');
            const createBtn = document.getElementById('navCreateBtn');
            const builderBtn = document.getElementById('navBuilderBtn');

            projectsSec.classList.add('hidden');
            createSec.classList.add('hidden');
            builderSec.classList.add('hidden');

            projectsBtn.className = 'px-3 sm:px-4 py-2 font-medium text-xs sm:text-sm border-b-2 border-transparent text-gray-400 hover:text-terrae-text cursor-pointer shrink-0';
            createBtn.className = 'px-3 sm:px-4 py-2 font-medium text-xs sm:text-sm border-b-2 border-transparent text-gray-400 hover:text-terrae-text cursor-pointer shrink-0';
            builderBtn.className = 'px-3 sm:px-4 py-2 font-medium text-xs sm:text-sm border-b-2 border-transparent text-gray-400 hover:text-terrae-text cursor-pointer shrink-0';

            if (tab === 'projects') {
                projectsSec.classList.remove('hidden');
                projectsBtn.className = 'px-3 sm:px-4 py-2 font-bold text-xs sm:text-sm border-b-2 border-terrae-oliva text-terrae-oliva cursor-pointer shrink-0';
                loadProjects();
            } else if (tab === 'create') {
                createSec.classList.remove('hidden');
                createBtn.className = 'px-3 sm:px-4 py-2 font-bold text-xs sm:text-sm border-b-2 border-terrae-oliva text-terrae-oliva cursor-pointer shrink-0';
            } else if (tab === 'builder') {
                builderSec.classList.remove('hidden');
                builderBtn.className = 'px-3 sm:px-4 py-2 font-bold text-xs sm:text-sm border-b-2 border-terrae-oliva text-terrae-oliva cursor-pointer shrink-0';
                loadBuilderBlocks();
            }
        }

        async function handleClientLogin(e) {
            e.preventDefault();
            const code = document.getElementById('clientCode').value;
            const formData = new FormData();
            formData.append('code', code);

            try {
                const res = await fetch('/api/client-access', { method: 'POST', body: formData });
                const data = await res.json();
                if (res.ok) {
                    currentProject = data;
                    Toast.fire({ icon: 'success', title: '¡Bienvenido a tu cuaderno!' });
                    showQuestionnaire(data.project_id, data.alias, data.access_code);
                } else {
                    Swal.fire({
                        icon: 'error',
                        title: 'Acceso no disponible',
                        text: data.detail || 'El código introducido no es válido o el acceso ha sido bloqueado.',
                        confirmButtonText: 'Entendido'
                    });
                }
            } catch (err) {
                Swal.fire({ icon: 'error', title: 'Error de conexión', text: 'No se pudo conectar con el servidor.' });
            }
        }

        async function handleStaffLogin(e) {
            e.preventDefault();
            const formData = new FormData();
            formData.append('email', document.getElementById('staffEmail').value);
            formData.append('password', document.getElementById('staffPassword').value);

            try {
                const res = await fetch('/api/login', { method: 'POST', body: formData });
                const data = await res.json();
                if (res.ok) {
                    currentProject = null;
                    document.getElementById('userBadge').innerText = data.user.name;
                    
                    const headerArea = document.getElementById('userHeaderArea');
                    if (headerArea) {
                        headerArea.classList.remove('hidden');
                        headerArea.classList.add('flex');
                    }

                    Toast.fire({ icon: 'success', title: `Hola, ${data.user.name}` });
                    showArchitectDashboard();
                } else {
                    Swal.fire({ icon: 'error', title: 'Error de acceso', text: data.detail });
                }
            } catch (err) {
                Swal.fire({ icon: 'error', title: 'Error de conexión', text: 'No se pudo conectar con el servidor.' });
            }
        }

        function showArchitectDashboard() {
            document.getElementById('loginView').classList.add('hidden');
            document.getElementById('questionnaireView').classList.add('hidden');
            document.getElementById('architectView').classList.remove('hidden');
            switchArchitectTab('projects');
        }

        async function loadProjects() {
            const res = await fetch('/api/projects');
            allProjectsCache = await res.json();
            const blocksRes = await fetch('/api/blocks');
            allBlocksCache = await blocksRes.json();

            renderProjects(allProjectsCache);
        }

        function renderProjects(projectsToRender) {
            const container = document.getElementById('projectsList');
            container.innerHTML = '';

            if (!projectsToRender || projectsToRender.length === 0) {
                container.innerHTML = '<p class="text-xs text-gray-500 italic text-center py-4">No se encontraron proyectos registrados con ese criterio.</p>';
                return;
            }

            projectsToRender.forEach(p => {
                const item = document.createElement('div');
                item.className = 'border border-terrae-origen p-3 sm:p-4 rounded-xl bg-white shadow-xs space-y-3';
                
                let blockCheckboxes = allBlocksCache.map(b => {
                    const isChecked = p.enabled_blocks.includes(b.id) ? 'checked' : '';
                    return `
                        <label class="inline-flex items-center text-[11px] sm:text-xs bg-white px-2 py-1 rounded-md border border-terrae-origen/60 cursor-pointer">
                            <input type="checkbox" ${isChecked} onchange="toggleBlock(${p.id}, ${b.id}, this.checked)" class="mr-1.5 accent-[#67610B]">
                            ${b.title}
                        </label>
                    `;
                }).join(' ');

                const blockClientText = p.is_client_blocked ? '🔓 Desbloquear' : '🔒 Bloquear';
                const blockClientClass = p.is_client_blocked 
                    ? 'text-[11px] bg-amber-50 text-amber-800 border border-amber-300 px-2.5 py-1.5 rounded-lg hover:bg-amber-100 cursor-pointer font-medium'
                    : 'text-[11px] bg-white text-gray-700 border border-terrae-origen px-2.5 py-1.5 rounded-lg hover:bg-terrae-natural/50 cursor-pointer font-medium';

                item.innerHTML = `
                    <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-3">
                        <div class="space-y-1 min-w-0 w-full md:w-auto">
                            <div class="flex items-center gap-2 flex-wrap">
                                <span class="font-bold text-[11px] sm:text-xs bg-terrae-oliva text-white px-2.5 py-1 rounded-md">${p.project_code || 'S/C'}</span>
                                <span class="font-bold text-[11px] sm:text-xs bg-white px-2.5 py-1 rounded-full border border-terrae-origen text-terrae-tierra inline-flex items-center gap-1.5">
                                    <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                                    ${p.access_code}
                                    <button onclick="shareProjectCode('${p.access_code}', '${p.alias}')" title="Copiar código" class="text-xs hover:opacity-75 cursor-pointer ml-1">📋</button>
                                </span>
                                <span class="font-bold font-heading text-terrae-tierra text-sm sm:text-base truncate max-w-full">${p.alias}</span>
                                ${p.is_client_blocked ? '<span class="text-[10px] bg-red-100 text-red-700 px-2 py-0.5 rounded font-bold">Bloqueado</span>' : ''}
                            </div>
                            <p class="text-xs text-gray-500 pl-0.5 truncate">📍 ${p.direccion || 'Sin dirección'}</p>
                        </div>
                        <div class="flex items-center gap-2 flex-wrap w-full md:w-auto justify-start md:justify-end pt-2 md:pt-0 border-t md:border-t-0 border-terrae-origen/20">
                            <button onclick="toggleClientBlock(${p.id}, ${p.is_client_blocked})" class="${blockClientClass}">${blockClientText}</button>
                            <button onclick="deleteProject(${p.id}, '${p.alias}')" class="text-[11px] bg-red-50 text-red-600 border border-red-200 px-2.5 py-1.5 rounded-lg hover:bg-red-100 cursor-pointer font-medium">🗑️ Borrar</button>
                            <button onclick="showQuestionnaire(${p.id}, '${p.alias}', '${p.access_code}', '${p.direccion || ''}')" class="text-xs bg-terrae-tierra text-white px-3.5 py-1.5 rounded-lg hover:opacity-95 cursor-pointer font-medium shadow-2xs">Ver Respuestas</button>
                        </div>
                    </div>
                    <div class="pt-2 border-t border-terrae-origen/20">
                        <p class="text-[11px] sm:text-xs font-semibold text-gray-500 mb-1.5">Fases Habilitadas para el cliente:</p>
                        <div class="flex flex-wrap gap-1.5">${blockCheckboxes}</div>
                    </div>
                `;
                container.appendChild(item);
            });
        }

        function filterProjectsList() {
            const query = document.getElementById('projectSearchInput').value.toLowerCase().trim();
            const clearBtn = document.getElementById('clearSearchBtn');

            if (query.length > 0) {
                clearBtn.classList.remove('hidden');
                clearBtn.classList.add('flex');
            } else {
                clearBtn.classList.add('hidden');
                clearBtn.classList.remove('flex');
            }

            const filtered = allProjectsCache.filter(p => {
                const codeMatch = (p.project_code || '').toLowerCase().includes(query);
                const accessMatch = (p.access_code || '').toLowerCase().includes(query);
                const aliasMatch = (p.alias || '').toLowerCase().includes(query);
                const dirMatch = (p.direccion || '').toLowerCase().includes(query);

                return codeMatch || accessMatch || aliasMatch || dirMatch;
            });

            renderProjects(filtered);
        }

        function clearProjectSearch() {
            document.getElementById('projectSearchInput').value = '';
            document.getElementById('clearSearchBtn').classList.add('hidden');
            renderProjects(allProjectsCache);
        }

        function shareProjectCode(code, alias) {
            navigator.clipboard.writeText(code).then(() => {
                Toast.fire({
                    icon: 'success',
                    title: '¡Código copiado!',
                    text: `Se ha copiado al portapapeles: ${code}`
                });
            }).catch(() => {
                Swal.fire({ icon: 'info', title: 'Código de acceso', text: `El código es: ${code}` });
            });
        }

        async function handleCreateProject(e) {
            e.preventDefault();
            const projectCode = document.getElementById('newProjectCode').value;
            const alias = document.getElementById('newAlias').value;
            const direccion = document.getElementById('newDireccion').value;

            const formData = new FormData();
            formData.append('project_code', projectCode);
            formData.append('alias', alias);
            formData.append('direccion', direccion);

            const res = await fetch('/api/projects/create', { method: 'POST', body: formData });
            const data = await res.json();
            if (res.ok) {
                document.getElementById('newProjectCode').value = '';
                document.getElementById('newAlias').value = '';
                document.getElementById('newDireccion').value = '';
                Toast.fire({ icon: 'success', title: '¡Proyecto creado con éxito!' });
                switchArchitectTab('projects');
            } else {
                Swal.fire({ icon: 'error', title: 'Error', text: data.detail || 'No se pudo crear el proyecto.' });
            }
        }

        async function toggleClientBlock(projectId, currentlyBlocked) {
            const actionText = currentlyBlocked ? 'desbloquear el acceso al cliente' : 'bloquear el acceso al cliente con su código';
            
            const result = await Swal.fire({
                title: '¿Estás segura?',
                text: `Vas a ${actionText}. El arquitecto mantendrá acceso total en todo momento.`,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonText: 'Sí, confirmar',
                cancelButtonText: 'Cancelar'
            });

            if (!result.isConfirmed) return;

            const formData = new FormData();
            formData.append('project_id', projectId);
            const res = await fetch('/api/projects/toggle-client-block', { method: 'POST', body: formData });
            if (res.ok) {
                Toast.fire({ icon: 'success', title: 'Estado actualizado correctamente' });
                loadProjects();
            } else {
                Swal.fire({ icon: 'error', title: 'Error', text: 'No se pudo actualizar el estado del cliente.' });
            }
        }

        async function deleteProject(projectId, alias) {
            const result = await Swal.fire({
                title: '¿Borrar proyecto permanentemente?',
                text: `Estás a punto de eliminar "${alias}" y toda su información de forma definitiva. ¡Esta acción no se puede deshacer!`,
                icon: 'error',
                showCancelButton: true,
                confirmButtonColor: '#d33',
                cancelButtonColor: '#67610B',
                confirmButtonText: 'Sí, borrar para siempre',
                cancelButtonText: 'Cancelar'
            });

            if (!result.isConfirmed) return;

            const formData = new FormData();
            formData.append('project_id', projectId);
            const res = await fetch('/api/projects/delete', { method: 'POST', body: formData });
            if (res.ok) {
                Swal.fire({ icon: 'success', title: 'Proyecto eliminado', text: 'Se ha eliminado de todas las bases de datos.' });
                loadProjects();
            } else {
                Swal.fire({ icon: 'error', title: 'Error', text: 'No se pudo eliminar el proyecto.' });
            }
        }

        async function toggleBlock(projectId, blockId, enabled) {
            const formData = new FormData();
            formData.append('project_id', projectId);
            formData.append('block_id', blockId);
            formData.append('enabled', enabled);
            await fetch('/api/projects/toggle-block', { method: 'POST', body: formData });
            Toast.fire({ icon: 'success', title: 'Fases actualizadas' });
        }

        async function loadBuilderBlocks() {
            const res = await fetch('/api/blocks?include_hidden=true');
            const blocks = await res.json();
            const container = document.getElementById('builderBlocksContainer');
            container.innerHTML = '';

            blocks.forEach(b => {
                const card = document.createElement('div');
                card.className = `p-4 sm:p-5 rounded-lg border bg-white shadow-sm space-y-4 ${b.is_active ? 'border-terrae-origen' : 'border-red-200 bg-red-50/20'}`;

                let questionsList = b.questions.map(q => `
                    <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 bg-white p-2.5 rounded border border-terrae-origen/60 text-xs">
                        <div class="flex items-center gap-2 min-w-0">
                            <span class="px-1.5 py-0.5 rounded bg-gray-100 text-gray-700 font-mono text-[10px] uppercase shrink-0">${q.type}</span>
                            <span class="truncate">${q.text}</span>
                        </div>
                        <button onclick="deleteQuestion(${q.id})" class="text-red-500 hover:text-red-700 font-bold px-2 py-0.5 rounded hover:bg-red-50 self-end sm:self-auto">✕</button>
                    </div>
                `).join('');

                card.innerHTML = `
                    <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 border-b border-terrae-origen pb-3">
                        <div class="min-w-0">
                            <div class="flex items-center gap-2 flex-wrap">
                                <h3 class="text-sm sm:text-base font-normal text-terrae-tierra truncate">${b.title}</h3>
                                ${!b.is_active ? '<span class="text-[10px] bg-red-100 text-red-700 px-2 py-0.5 rounded font-bold uppercase">Oculto</span>' : ''}
                            </div>
                            <p class="text-xs text-gray-500 truncate">${b.subtitle || 'Sin subtítulo'}</p>
                        </div>
                        <div class="flex gap-2 flex-wrap w-full sm:w-auto justify-end">
                            <button onclick="toggleBlockActive(${b.id})" class="text-xs px-2.5 py-1 rounded border ${b.is_active ? 'border-amber-300 bg-amber-50 text-amber-800' : 'border-emerald-300 bg-emerald-50 text-emerald-800'} cursor-pointer">
                                ${b.is_active ? '👁️ Ocultar' : '👁️ Mostrar'}
                            </button>
                            <button onclick="deleteBlock(${b.id})" class="text-xs bg-red-50 text-red-600 hover:bg-red-100 border border-red-200 px-2.5 py-1 rounded cursor-pointer">
                                🗑️ Eliminar
                            </button>
                        </div>
                    </div>

                    <div class="space-y-2">
                        <p class="text-xs font-semibold text-gray-500 uppercase tracking-wider">Preguntas / Ítems en este bloque:</p>
                        ${questionsList || '<p class="text-xs text-gray-400 italic">No hay preguntas registradas en esta fase.</p>'}
                    </div>

                    <form onsubmit="handleAddQuestion(event, ${b.id})" class="flex flex-col sm:flex-row gap-2 pt-2">
                        <input type="text" placeholder="Escribe un nuevo ítem o pregunta..." required class="new-q-text flex-1 px-3 py-2 sm:py-1.5 text-xs border border-terrae-origen rounded focus:outline-none focus:border-terrae-oliva bg-white">
                        <select class="new-q-type px-2 py-2 sm:py-1.5 text-xs border border-terrae-origen rounded bg-white">
                            <option value="text">Texto</option>
                            <option value="image">Subida de Imagen</option>
                            <option value="checkbox_arquitecto">Check Arquitecto</option>
                            <option value="inspiration_category">Inspiración (Bloque 2)</option>
                            <option value="habitar_section">Habitar (Bloque 3)</option>
                        </select>
                        <button type="submit" class="bg-terrae-oliva text-white px-3 py-2 sm:py-1.5 rounded text-xs hover:bg-terrae-dark transition cursor-pointer font-medium">+ Añadir</button>
                    </form>
                `;
                container.appendChild(card);
            });
        }

        async function handleCreateBlock(e) {
            e.preventDefault();
            const title = document.getElementById('newBlockTitle').value;
            const subtitle = document.getElementById('newBlockSubtitle').value;

            const formData = new FormData();
            formData.append('title', title);
            if (subtitle) formData.append('subtitle', subtitle);

            const res = await fetch('/api/admin/blocks/create', { method: 'POST', body: formData });
            if (res.ok) {
                document.getElementById('newBlockTitle').value = '';
                document.getElementById('newBlockSubtitle').value = '';
                Toast.fire({ icon: 'success', title: 'Bloque creado con éxito' });
                loadBuilderBlocks();
            }
        }

        async function toggleBlockActive(blockId) {
            const formData = new FormData();
            formData.append('block_id', blockId);
            await fetch('/api/admin/blocks/toggle-active', { method: 'POST', body: formData });
            Toast.fire({ icon: 'success', title: 'Estado del bloque actualizado' });
            loadBuilderBlocks();
        }

        async function deleteBlock(blockId) {
            const result = await Swal.fire({
                title: '¿Eliminar bloque?',
                text: 'Se eliminará el bloque y todas sus preguntas asociadas.',
                icon: 'warning',
                showCancelButton: true,
                confirmButtonText: 'Sí, eliminar',
                cancelButtonText: 'Cancelar'
            });

            if (!result.isConfirmed) return;

            const formData = new FormData();
            formData.append('block_id', blockId);
            await fetch('/api/admin/blocks/delete', { method: 'POST', body: formData });
            Toast.fire({ icon: 'success', title: 'Bloque eliminado' });
            loadBuilderBlocks();
        }

        async function handleAddQuestion(e, blockId) {
            e.preventDefault();
            const form = e.target;
            const qText = form.querySelector('.new-q-text').value;
            const qType = form.querySelector('.new-q-type').value;

            const formData = new FormData();
            formData.append('block_id', blockId);
            formData.append('question_text', qText);
            formData.append('question_type', qType);

            const res = await fetch('/api/admin/questions/create', { method: 'POST', body: formData });
            if (res.ok) {
                Toast.fire({ icon: 'success', title: 'Ítem añadido' });
                loadBuilderBlocks();
            }
        }

        async function deleteQuestion(questionId) {
            const result = await Swal.fire({
                title: '¿Borrar pregunta?',
                text: 'Esta acción no se puede deshacer.',
                icon: 'warning',
                showCancelButton: true,
                confirmButtonText: 'Sí, borrar',
                cancelButtonText: 'Cancelar'
            });

            if (!result.isConfirmed) return;

            const formData = new FormData();
            formData.append('question_id', questionId);
            await fetch('/api/admin/questions/delete', { method: 'POST', body: formData });
            Toast.fire({ icon: 'success', title: 'Pregunta eliminada' });
            loadBuilderBlocks();
        }

        function renderInspirationCards(blockId, projectId, categories) {
            const container = document.getElementById(`inspirationFormsContainer-${blockId}`);
            if (!container) return;
            container.innerHTML = '';

            categories.forEach(cat => {
                const chk = document.getElementById(`cat-chk-${blockId}-${cat.id}`);
                if (chk && chk.checked) {
                    let mediaHTML = (cat.media || []).map(m => `
                        <div class="relative inline-block group">
                            <img src="${m.url}" class="h-16 w-16 sm:h-20 sm:w-20 object-cover rounded border border-terrae-origen">
                            <button onclick="deleteMediaItem(${m.id}, ${projectId})" class="absolute -top-1.5 -right-1.5 bg-red-600 text-white rounded-full w-5 h-5 text-[10px] flex items-center justify-center opacity-80 hover:opacity-100 shadow cursor-pointer">✕</button>
                        </div>
                    `).join('');

                    const formCard = document.createElement('div');
                    formCard.className = 'bg-white p-4 sm:p-5 rounded-lg border border-terrae-origen shadow-sm space-y-4 transition-all duration-200';
                    formCard.innerHTML = `
                        <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-terrae-origen/30 pb-3">
                            <div>
                                <span class="text-[10px] bg-terrae-oliva text-white px-2.5 py-0.5 rounded font-bold uppercase tracking-wider">Ámbito: ${cat.text}</span>
                                <h5 class="font-heading text-sm sm:text-base text-terrae-tierra font-normal mt-1">AÑADE AQUELLO QUE TE INSPIRE</h5>
                                <p class="text-[11px] text-gray-500 uppercase tracking-wide">Fotografía · Pinterest · Instagram · foto propia...</p>
                            </div>
                            <label class="w-full sm:w-auto text-center bg-terrae-tierra hover:bg-terrae-tierra/90 text-white px-4 py-2 rounded text-xs font-bold uppercase tracking-wider cursor-pointer shadow flex items-center justify-center gap-2 transition">
                                <span>＋ SUBIR IMAGEN</span>
                                <input type="file" onchange="uploadInspirationImage(${projectId}, ${cat.id}, this)" class="hidden">
                            </label>
                        </div>

                        <div class="space-y-3 pt-2">
                            <div>
                                <label class="block text-xs font-semibold text-gray-700 mb-1">¿Quieres contarnos algo sobre esta referencia (${cat.text})?</label>
                                <textarea data-question-id="${cat.id}" data-project-id="${projectId}" class="insp-textarea-${blockId} w-full p-2.5 border border-terrae-origen rounded text-xs focus:outline-none focus:border-terrae-oliva bg-white" rows="2" placeholder="Escribe aquí...">${cat.response || ''}</textarea>
                            </div>

                            <div class="flex gap-2 flex-wrap mt-2">${mediaHTML}</div>

                            <div class="text-[11px] text-terrae-oliva font-semibold pt-1">
                                Categoría seleccionada activa en este proyecto.
                            </div>
                        </div>
                    `;
                    container.appendChild(formCard);
                }
            });
        }

        function handleInspirationCategoryChange(blockId, projectId, categories) {
            renderInspirationCards(blockId, projectId, categories);
        }

        async function showQuestionnaire(projectId, alias, code, direccion = '') {
            document.getElementById('loginView').classList.add('hidden');
            document.getElementById('architectView').classList.add('hidden');
            document.getElementById('questionnaireView').classList.remove('hidden');

            const isArchitect = !currentProject;

            const topBar = document.getElementById('architectTopBar');
            if (topBar) {
                if (isArchitect) {
                    topBar.classList.remove('hidden');
                    topBar.classList.add('flex');
                } else {
                    topBar.classList.remove('flex');
                    topBar.classList.add('hidden');
                }
            }

            const headerArea = document.getElementById('userHeaderArea');
            if (headerArea) {
                if (currentProject) {
                    document.getElementById('userBadge').innerText = `Cliente: ${code}`;
                }
                headerArea.classList.remove('hidden');
                headerArea.classList.add('flex');
            }

            if (isArchitect) {
                document.getElementById('projectCodeBadge').innerText = `ACCESO: ${code}`;
                document.getElementById('projectAliasHeader').innerText = alias;
                document.getElementById('projectDireccionHeader').innerText = direccion ? `📍 ${direccion}` : '';
            }

            try {
                const res = await fetch(`/api/blocks?project_id=${projectId}`);
                if (!res.ok) return;

                const blocks = await res.json();
                const container = document.getElementById('blocksContainer');
                container.innerHTML = '';

                if (!blocks || blocks.length === 0) {
                    container.innerHTML = '<p class="text-sm text-gray-500 italic p-4 bg-white rounded border border-terrae-origen">No hay bloques ni preguntas registradas.</p>';
                    return;
                }

                blocks.forEach(b => {
                    const shouldShowQuestions = b.is_enabled;

                    const blockDiv = document.createElement('div');
                    blockDiv.id = `block-card-${b.id}`;
                    blockDiv.className = `bg-white p-4 sm:p-6 rounded-lg shadow-sm border ${b.is_enabled ? 'border-terrae-origen' : 'border-gray-200 bg-gray-50/50'}`;

                    let qHTML = '';
                    let architectChecksHTML = '';
                    let inspirationCategories = [];

                    if (b.id === 2 && b.questions) {
                        inspirationCategories = b.questions.filter(q => (q.type || q.question_type) === 'inspiration_category');
                    }

                    if (shouldShowQuestions && b.questions && b.questions.length > 0) {
                        let textQuestionsHTML = '';

                        // Renderizador especial agrupado para Bloque 4
                        if (b.id === 4) {
                            const materialidadItems = ["Pavimentos", "Revestimientos", "Paredes", "Techos", "Materiales naturales", "Texturas", "Colores"];
                            const carpinteriasItems = ["Color de puertas", "Color de armarios", "Color de cocina", "Tiradores", "Tipo de frente"];
                            const iluminacionItems = ["Luz general", "Luz ambiental", "Luz de trabajo", "Luz decorativa", "Lámparas que queremos incorporar", "Iluminación exterior"];
                            const vegetacionItems = ["Plantas existentes que queremos conservar", "Nuevas plantas", "Ubicación de plantas", "Necesidades de luz / riego"];

                            const renderGroup = (groupTitle, itemNames) => {
                                let groupHtml = `
                                    <div class="my-5 p-4 sm:p-5  rounded-xl border border-terrae-origen/60 space-y-4">
                                        <h4 class="font-heading text-sm sm:text-base font-bold text-terrae-tierra uppercase tracking-wider border-b border-terrae-origen/30 pb-2">${groupTitle}</h4>
                                        <div class="space-y-4">
                                `;
                                
                                itemNames.forEach(name => {
                                    const qObj = b.questions.find(q => (q.text || q.question_text) === name);
                                    if (qObj) {
                                        const qResponse = qObj.response || '';
                                        const qType = qObj.type || qObj.question_type || 'text';
                                        let mediaHTML = (qObj.media || []).map(m => `
                                            <div class="relative inline-block group">
                                                <img src="${m.url}" class="h-16 w-16 sm:h-20 sm:w-20 object-cover rounded border border-terrae-origen">
                                                <button onclick="deleteMediaItem(${m.id}, ${projectId})" class="absolute -top-1.5 -right-1.5 bg-red-600 text-white rounded-full w-5 h-5 text-[10px] flex items-center justify-center opacity-80 hover:opacity-100 shadow cursor-pointer">✕</button>
                                            </div>
                                        `).join('');

                                        let fileInputHTML = '';
                                        if (qType === 'image') {
                                            fileInputHTML = `
                                                <div class="flex items-center gap-2">
                                                    <input type="file" onchange="uploadFile(${projectId}, ${qObj.id}, this)" class="text-xs block w-full text-gray-500 file:mr-2 file:py-1 file:px-2 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-terrae-natural/40 file:text-terrae-tierra hover:file:bg-terrae-natural/60 cursor-pointer">
                                                </div>
                                            `;
                                        }

                                        groupHtml += `
                                            <div class="space-y-2 bg-white p-3.5 rounded-lg border border-terrae-origen/60 shadow-2xs">
                                                <label class="block text-xs sm:text-sm font-medium text-terrae-text">
                                                    <span>${name}</span>
                                                </label>
                                                ${fileInputHTML}
                                                <textarea 
                                                    data-question-id="${qObj.id}" 
                                                    data-project-id="${projectId}" 
                                                    class="w-full p-2.5 border border-terrae-origen rounded text-xs focus:outline-none focus:border-terrae-oliva bg-white" 
                                                    rows="2" 
                                                    placeholder="Añadir notas o detalles sobre ${name.toLowerCase()}...">${qResponse}</textarea>
                                                <div class="flex gap-2 flex-wrap mt-1">${mediaHTML}</div>
                                            </div>
                                        `;
                                    }
                                });

                                groupHtml += `</div></div>`;
                                return groupHtml;
                            };

                            textQuestionsHTML += renderGroup("MATERIALIDAD", materialidadItems);
                            textQuestionsHTML += renderGroup("CARPINTERÍAS", carpinteriasItems);
                            textQuestionsHTML += renderGroup("ILUMINACIÓN", iluminacionItems);
                            textQuestionsHTML += renderGroup("VEGETACIÓN", vegetacionItems);

                            b.questions.forEach(q => {
                                const qText = q.text || q.question_text || '';
                                const qType = q.type || q.question_type || 'text';
                                const qResponse = q.response || '';

                                if (qType === 'checkbox_arquitecto') {
                                    const isChecked = qResponse === '1' ? 'checked' : '';
                                    if (isArchitect) {
                                        architectChecksHTML += `
                                            <div class="flex items-center space-x-3 p-3 bg-white rounded-xl border border-terrae-origen my-2">
                                                <input type="checkbox" data-question-id="${q.id}" data-project-id="${projectId}" class="architect-chk w-5 h-5 text-terrae-terracota rounded border-stone-300 focus:ring-terrae-terracota cursor-pointer shrink-0" ${isChecked}>
                                                <span class="text-xs sm:text-sm font-bold text-terrae-tierra">${qText} <span class="text-[11px] text-terrae-terracota font-normal">(Control Arquitecta)</span></span>
                                            </div>
                                        `;
                                    } else {
                                        const clientCheckedText = qResponse === '1' ? '✓ Sí' : 'Pendiente';
                                        architectChecksHTML += `
                                            <div class="flex items-center justify-between p-3 bg-white rounded-xl border border-terrae-origen my-2 gap-2">
                                                <span class="text-xs sm:text-sm font-medium text-stone-700 flex items-center gap-2"><span class="text-terrae-terracota font-bold">✓</span>${qText}</span>
                                                <span class="text-xs font-bold px-2.5 py-1 rounded shrink-0 ${qResponse === '1' ? 'bg-emerald-100 text-emerald-800' : 'bg-gray-200 text-gray-600'}">${clientCheckedText}</span>
                                            </div>
                                        `;
                                    }
                                }
                            });

                        } else {
                            b.questions.forEach(q => {
                                const qText = q.text || q.question_text || '';
                                const qType = q.type || q.question_type || 'text';
                                const qResponse = q.response || '';

                                if (qType === 'inspiration_category') {
                                    return;
                                }

                                let mediaHTML = (q.media || []).map(m => `
                                    <div class="relative inline-block group">
                                        <img src="${m.url}" class="h-16 w-16 sm:h-20 sm:w-20 object-cover rounded border border-terrae-origen">
                                        <button onclick="deleteMediaItem(${m.id}, ${projectId})" class="absolute -top-1.5 -right-1.5 bg-red-600 text-white rounded-full w-5 h-5 text-[10px] flex items-center justify-center opacity-80 hover:opacity-100 shadow cursor-pointer">✕</button>
                                    </div>
                                `).join('');

                                let fileInputHTML = '';
                                if (qType === 'image') {
                                    fileInputHTML = `<input type="file" onchange="uploadFile(${projectId}, ${q.id}, this)" class="text-xs mb-2 block w-full text-gray-500 file:mr-2 file:py-1 file:px-2 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-terrae-natural/40 file:text-terrae-tierra hover:file:bg-terrae-natural/60 cursor-pointer">`;
                                }

                                if (qType === 'habitar_section') {
                                    let reflectionBullets = (habitarQuestionsMap[qText] || []).map(qItem => `
                                        <li class="flex items-start gap-2 text-xs text-stone-700">
                                            <span class="text-terrae-oliva font-bold">□</span>
                                            <span>${qItem}</span>
                                        </li>
                                    `).join('');

                                    textQuestionsHTML += `
                                        <div class="space-y-3  p-4 sm:p-5 rounded-xl border border-terrae-origen/60 my-4 sm:my-6 shadow-sm">
                                            <h4 class="font-heading text-sm sm:text-base font-normal text-terrae-tierra uppercase tracking-wider border-b border-terrae-origen/30 pb-2">${qText}</h4>
                                            
                                            <div class="space-y-1.5 py-1">
                                                <p class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Preguntas para reflexionar:</p>
                                                <ul class="space-y-1.5 pl-1">
                                                    ${reflectionBullets}
                                                </ul>
                                            </div>

                                            <div class="space-y-2 pt-3">
                                                <label class="block text-xs font-semibold text-terrae-text">Tus anotaciones o recorrido general en este apartado:</label>
                                                ${fileInputHTML}
                                                <textarea 
                                                    data-question-id="${q.id}" 
                                                    data-project-id="${projectId}" 
                                                    class="w-full p-2.5 border border-terrae-origen rounded text-sm focus:outline-none focus:border-terrae-oliva bg-white" 
                                                    rows="3" 
                                                    placeholder="Escribe de forma opcional a modo genérico...">${qResponse}</textarea>
                                                <div class="flex gap-2 flex-wrap mt-2">${mediaHTML}</div>
                                            </div>
                                        </div>
                                    `;
                                } else if (qType === 'checkbox_arquitecto') {
                                    const isChecked = qResponse === '1' ? 'checked' : '';
                                    if (isArchitect) {
                                        architectChecksHTML += `
                                            <div class="flex items-center space-x-3 p-3 bg-white rounded-xl border border-terrae-origen my-2">
                                                <input type="checkbox" data-question-id="${q.id}" data-project-id="${projectId}" class="architect-chk w-5 h-5 text-terrae-terracota rounded border-stone-300 focus:ring-terrae-terracota cursor-pointer shrink-0" ${isChecked}>
                                                <span class="text-xs sm:text-sm font-bold text-terrae-tierra">${qText} <span class="text-[11px] text-terrae-terracota font-normal">(Control Arquitecta)</span></span>
                                            </div>
                                        `;
                                    } else {
                                        const clientCheckedText = qResponse === '1' ? '✓ Sí' : 'Pendiente';
                                        architectChecksHTML += `
                                            <div class="flex items-center justify-between p-3 bg-white rounded-xl border border-terrae-origen my-2 gap-2">
                                                <span class="text-xs sm:text-sm font-medium text-stone-700">${qText}</span>
                                                <span class="text-xs font-bold px-2.5 py-1 rounded shrink-0 ${qResponse === '1' ? 'bg-emerald-100 text-emerald-800' : 'bg-gray-200 text-gray-600'}">${clientCheckedText}</span>
                                            </div>
                                        `;
                                    }
                                } else {
                                    textQuestionsHTML += `
                                        <div class="space-y-2 border-b border-terrae-origen/40 pb-4 last:border-b-0">
                                            <label class="block text-xs sm:text-sm font-medium text-terrae-text">${qText}</label>
                                            ${fileInputHTML}
                                            <textarea 
                                                data-question-id="${q.id}" 
                                                data-project-id="${projectId}" 
                                                class="w-full p-2.5 border border-terrae-origen rounded text-sm focus:outline-none focus:border-terrae-oliva bg-white" 
                                                rows="3" 
                                                placeholder="Escribe tu respuesta...">${qResponse}</textarea>
                                            <div class="flex gap-2 flex-wrap mt-2">${mediaHTML}</div>
                                        </div>
                                    `;
                                }
                            });
                        }

                        qHTML = textQuestionsHTML;

                        if (b.id === 2 && inspirationCategories.length > 0) {
                            let checkboxesGridHTML = '';
                            
                            inspirationCategories.forEach(cat => {
                                const hasData = (cat.response && cat.response.trim() !== '') || (cat.media && cat.media.length > 0);
                                const isCheckedAttr = hasData ? 'checked' : '';

                                checkboxesGridHTML += `
                                    <label class="inline-flex items-center text-xs bg-white px-2.5 sm:px-3 py-2 rounded-lg border border-terrae-origen/70 cursor-pointer hover:bg-terrae-natural/20 transition">
                                        <input type="checkbox" id="cat-chk-${b.id}-${cat.id}" value="${cat.text}" ${isCheckedAttr} onchange="handleInspirationCategoryChange(${b.id}, ${projectId}, ${JSON.stringify(inspirationCategories).replace(/"/g, '&quot;')})" class="cat-checkbox-${b.id} mr-2 accent-[#67610B] w-4 h-4 shrink-0">
                                        <span class="font-medium text-terrae-text truncate">${cat.text}</span>
                                    </label>
                                `;
                            });

                            qHTML += `
                                <div class="my-4 sm:my-6 p-4 sm:p-5 bg-white rounded-xl border border-terrae-origen space-y-4 shadow-xs">
                                    <div>
                                        <h4 class="text-xs sm:text-sm font-bold uppercase tracking-wider text-terrae-tierra">Selecciona los ámbitos de inspiración</h4>
                                        <p class="text-xs text-gray-500">Elige sobre qué aspectos quieres aportar referencias o imágenes:</p>
                                    </div>
                                    <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                                        ${checkboxesGridHTML}
                                    </div>
                                    <div id="inspirationFormsContainer-${b.id}" class="space-y-4 mt-4"></div>
                                </div>
                            `;
                        }

                        if (architectChecksHTML !== '') {
                            qHTML += `
                                <div class="mt-6 pt-4 border-t border-terrae-origen/30">
                                    <div class="mb-3">
                                        <h3 class="text-base sm:text-lg font-normal text-terrae-tierra uppercase">AL TERMINAR ESTA ETAPA</h3>
                                    </div>
                                    <div class="space-y-2">
                                        ${architectChecksHTML}
                                    </div>
                                </div>
                            `;
                        }

                        qHTML += `
                            <div class="pt-4 flex justify-end">
                                <button onclick="saveBlockAnswers(${b.id}, ${projectId})" class="w-full sm:w-auto bg-terrae-tierra hover:bg-terrae-tierra/90 text-white px-5 py-2.5 rounded text-xs font-bold uppercase tracking-wider transition cursor-pointer shadow flex items-center justify-center gap-1.5">
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7" />
                                    </svg>
                                    Guardar esta fase
                                </button>
                            </div>
                        `;
                    } else if (!b.is_enabled) {
                        qHTML = isArchitect 
                            ? `<p class="text-xs text-gray-400 italic bg-white p-3 rounded border border-dashed border-terrae-origen">
                                🔒 Esta fase está desactivada para el cliente. Puedes habilitarla desde el Panel de Gestión.
                               </p>`
                            : `<p class="text-xs text-gray-400 italic bg-white p-3 rounded border border-dashed border-terrae-origen">
                                🔒 Esta fase se habilitará próximamente.
                               </p>`;
                    } else {
                        qHTML = `<p class="text-xs text-gray-400 italic">No hay preguntas en esta fase.</p>`;
                    }

                    const statusBadge = b.is_enabled 
                        ? `<span class="text-[10px] bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded font-medium">Habilitada</span>`
                        : `<span class="text-[10px] bg-gray-200 text-gray-600 px-2 py-0.5 rounded font-medium">Bloqueada</span>`;

                    blockDiv.innerHTML = `
                        <div class="mb-4 flex justify-between items-start gap-2">
                            <div class="min-w-0">
                                <h3 class="text-base sm:text-lg font-normal text-terrae-tierra truncate">${b.title}</h3>
                                <p class="text-xs text-gray-500 truncate">${b.subtitle || ''}</p>
                            </div>
                            ${isArchitect ? statusBadge : ''}
                        </div>
                        <div class="space-y-4">${qHTML}</div>
                    `;
                    container.appendChild(blockDiv);

                    if (b.id === 2 && inspirationCategories.length > 0) {
                        renderInspirationCards(b.id, projectId, inspirationCategories);
                    }
                });
            } catch (error) {
                console.error('Error:', error);
            }
        }

        async function uploadFile(projectId, questionId, input) {
            if (!input.files[0]) return;
            const formData = new FormData();
            formData.append('project_id', projectId);
            formData.append('question_id', questionId);
            formData.append('file', input.files[0]);
            await fetch('/api/responses/save', { method: 'POST', body: formData });
            Toast.fire({ icon: 'success', title: 'Imagen subida correctamente' });
            reloadCurrentQuestionnaire(projectId);
        }

        async function uploadInspirationImage(projectId, questionId, input) {
            if (!input.files[0]) return;
            const formData = new FormData();
            formData.append('project_id', projectId);
            formData.append('question_id', questionId);
            formData.append('file', input.files[0]);
            await fetch('/api/responses/save', { method: 'POST', body: formData });
            Toast.fire({ icon: 'success', title: 'Referencia de inspiración subida' });
            reloadCurrentQuestionnaire(projectId);
        }

        async function deleteMediaItem(mediaId, projectId) {
            const formData = new FormData();
            formData.append('media_id', mediaId);
            await fetch('/api/media/delete', { method: 'POST', body: formData });
            Toast.fire({ icon: 'success', title: 'Imagen eliminada' });
            reloadCurrentQuestionnaire(projectId);
        }

        function reloadCurrentQuestionnaire(projectId) {
            const aliasEl = document.getElementById('projectAliasHeader');
            const codeEl = document.getElementById('projectCodeBadge');
            const dirEl = document.getElementById('projectDireccionHeader');
            const codeVal = codeEl ? codeEl.innerText.replace('ACCESO: ', '') : '';
            showQuestionnaire(projectId, aliasEl ? aliasEl.innerText : '', codeVal, dirEl ? dirEl.innerText.replace('📍 ', '') : '');
        }

        function goBackFromQuestionnaire() {
            if (!currentProject) {
                document.getElementById('questionnaireView').classList.add('hidden');
                document.getElementById('architectView').classList.remove('hidden');
                loadProjects();
            } else {
                logout();
            }
        }

        async function saveBlockAnswers(blockId, projectId) {
            const blockCard = document.getElementById(`block-card-${blockId}`);
            if (!blockCard) return;

            const textareas = blockCard.querySelectorAll('textarea');
            const checkboxes = blockCard.querySelectorAll('.architect-chk');
            let savePromises = [];

            textareas.forEach(textarea => {
                const questionId = textarea.getAttribute('data-question-id');
                const val = textarea.value;

                if (questionId && projectId && val.trim() !== '') {
                    const formData = new FormData();
                    formData.append('project_id', projectId);
                    formData.append('question_id', questionId);
                    formData.append('answer_text', val);
                    
                    savePromises.push(fetch('/api/responses/save', { method: 'POST', body: formData }));
                }
            });

            checkboxes.forEach(chk => {
                const questionId = chk.getAttribute('data-question-id');
                const val = chk.checked ? '1' : '0';

                if (questionId && projectId) {
                    const formData = new FormData();
                    formData.append('project_id', projectId);
                    formData.append('question_id', questionId);
                    formData.append('answer_text', val);
                    
                    savePromises.push(fetch('/api/responses/save', { method: 'POST', body: formData }));
                }
            });

            try {
                if (savePromises.length > 0) {
                    await Promise.all(savePromises);
                }
                Toast.fire({ icon: 'success', title: '¡Respuestas guardadas con éxito!' });
                reloadCurrentQuestionnaire(projectId);
            } catch (err) {
                Swal.fire({ icon: 'error', title: 'Error', text: 'No se pudieron guardar las respuestas.' });
            }
        }

        function logout() {
            currentProject = null;
            const headerArea = document.getElementById('userHeaderArea');
            if (headerArea) {
                headerArea.classList.add('hidden');
                headerArea.classList.remove('flex');
            }
            document.getElementById('questionnaireView').classList.add('hidden');
            document.getElementById('architectView').classList.add('hidden');
            document.getElementById('loginView').classList.remove('hidden');
            Toast.fire({ icon: 'info', title: 'Sesión cerrada' });
        }
    </script>
</body>
</html>
    """

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)