import hashlib
import json
import os
import secrets

import httpx
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import SQLModel, Session, Field, create_engine, select, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://familytask:familytask@db:5432/familytask")


def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


def new_session_token(previous_token: str | None = None) -> str:
    token = secrets.token_urlsafe(32)
    while token == previous_token:
        token = secrets.token_urlsafe(32)
    return token


engine = create_engine(DATABASE_URL, echo=True)

class Member(SQLModel, table=True):
    __tablename__ = "Members"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    lien: str
    name: str 
    is_admin: bool = False
    family_code: str = Field(index=True)
    password_hash: str
    token: str | None = None

class Task(SQLModel, table=True):
    __tablename__ = "tasks"

    id: int | None = Field(default=None, primary_key=True)
    title: str 
    done: bool = False
    member_id: int | None = Field(default=None, index=True)


class TaskCreate(SQLModel):
    title: str
    done: bool = False
    member_id: int | None = None
    assign_to_all: bool = False


class MemberCreate(SQLModel):
    email: str
    lien: str
    name: str
    is_admin: bool = False
    family_code: str
    password: str


class MemberAdminCreate(SQLModel):
    email: str
    lien: str
    name: str
    is_admin: bool = False
    password: str


class Lien(SQLModel, table=True):
    __tablename__ = "liens"

    id: int | None = Field(default=None, primary_key=True)
    family_code: str = Field(index=True)
    label: str


class LienCreate(SQLModel):
    label: str


class MemberRead(SQLModel):
    id: int
    email: str
    lien: str
    name: str
    is_admin: bool
    family_code: str


class AuthResponse(MemberRead):
    token: str


def ensure_task_member_column() -> None:
    with Session(engine) as session:
        if str(engine.url).startswith("sqlite"):
            result = session.exec(text("PRAGMA table_info(tasks)"))
            columns = [row[1] for row in result.all()]
            if "member_id" not in columns:
                session.exec(text("ALTER TABLE tasks ADD COLUMN member_id INTEGER"))
            session.commit()
            return

        session.exec(text('ALTER TABLE tasks ADD COLUMN IF NOT EXISTS member_id INTEGER'))
        session.commit()


def ensure_lien_table() -> None:
    with Session(engine) as session:
        session.exec(text('CREATE TABLE IF NOT EXISTS liens (id SERIAL PRIMARY KEY, family_code TEXT NOT NULL, label TEXT NOT NULL)'))
        session.commit()


SQLModel.metadata.create_all(engine)
ensure_task_member_column()
ensure_lien_table()


app = FastAPI(title="FamilyTask")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
bearer_scheme = HTTPBearer(auto_error=False)


def current_member(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Member:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    token = credentials.credentials

    with Session(engine) as session:
        member = session.exec(select(Member).where(Member.token == token)).first()
        if not member:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return member


@app.get("/api/tasks", response_model=list[Task])
def get_tasks(current: Member = Depends(current_member)):
    with Session(engine) as session:
        tasks = session.exec(
            select(Task).where(Task.member_id == current.id)
        ).all()
    return [task.model_dump() for task in tasks]


@app.get("/api/tasks/famille", response_model=list[Task])
def get_family_tasks(current: Member = Depends(current_member)):
    if not current.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    with Session(engine) as session:
        family_members = session.exec(
            select(Member.id).where(Member.family_code == current.family_code)
        ).all()
        if not family_members:
            return []
        tasks = session.exec(
            select(Task).where(Task.member_id.in_(family_members))
        ).all()
    return [task.model_dump() for task in tasks]


@app.post("/api/tasks", response_model=list[Task])
def create_tasks(task: TaskCreate, current: Member = Depends(current_member)):
    with Session(engine) as session:
        if not current.is_admin and task.assign_to_all:
            raise HTTPException(status_code=403, detail="Only admins can assign a task to all members")

        if task.assign_to_all:
            family_members = session.exec(
                select(Member.id).where(Member.family_code == current.family_code)
            ).all()
            if not family_members:
                raise HTTPException(status_code=404, detail="No members found in the family")

            created_tasks = []
            for member_id in family_members:
                db_task = Task(
                    title=task.title,
                    done=task.done,
                    member_id=member_id,
                )
                session.add(db_task)
                session.commit()
                session.refresh(db_task)
                created_tasks.append(db_task)
            return created_tasks

        assigned_member_id = current.id

        if task.member_id is not None:
            if not current.is_admin:
                raise HTTPException(status_code=403, detail="Only admins can assign tasks to another member")

            target_member = session.get(Member, task.member_id)
            if not target_member or target_member.family_code != current.family_code:
                raise HTTPException(status_code=404, detail="Member not found in the same family")
            assigned_member_id = target_member.id

        db_task = Task(
            title=task.title,
            done=task.done,
            member_id=assigned_member_id,
        )
        session.add(db_task)
        session.commit()
        session.refresh(db_task)
        return [db_task]


@app.patch("/api/tasks/{task_id}", response_model=Task)
def update_task(task_id: int, task: Task, current: Member = Depends(current_member)):
    with Session(engine) as session:
        db_task = session.get(Task, task_id)
        if not db_task:
            raise HTTPException(status_code=404, detail="Task not found")

        if db_task.member_id != current.id and not current.is_admin:
            raise HTTPException(status_code=403, detail="You can only update your own tasks")

        if current.is_admin and db_task.member_id is not None:
            owner = session.get(Member, db_task.member_id)
            if owner is None or owner.family_code != current.family_code:
                raise HTTPException(status_code=404, detail="Task not found in the family")

        db_task.title = task.title
        db_task.done = task.done
        session.add(db_task)
        session.commit()
        session.refresh(db_task)
    return db_task.model_dump()


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: int, current: Member = Depends(current_member)):
    with Session(engine) as session:
        db_task = session.get(Task, task_id)
        if not db_task:
            raise HTTPException(status_code=404, detail="Task not found")

        if db_task.member_id != current.id and not current.is_admin:
            raise HTTPException(status_code=403, detail="You can only delete your own tasks")

        if current.is_admin and db_task.member_id is not None:
            owner = session.get(Member, db_task.member_id)
            if owner is None or owner.family_code != current.family_code:
                raise HTTPException(status_code=404, detail="Task not found in the family")

        session.delete(db_task)
        session.commit()
    return {"message": "Task deleted successfully"}

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/liens", response_model=list[Lien])
def get_liens(current: Member = Depends(current_member)):
    with Session(engine) as session:
        return session.exec(
            select(Lien).where(Lien.family_code == current.family_code)
        ).all()


@app.post("/api/liens", response_model=Lien)
def create_lien(lien: LienCreate, current: Member = Depends(current_member)):
    if not current.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    with Session(engine) as session:
        existing = session.exec(
            select(Lien).where((Lien.family_code == current.family_code) & (Lien.label == lien.label))
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="This relationship label already exists")

        db_lien = Lien(family_code=current.family_code, label=lien.label)
        session.add(db_lien)
        session.commit()
        session.refresh(db_lien)
        return db_lien


@app.get("/api/members", response_model=list[MemberRead])
def get_members(current: Member = Depends(current_member)):
    with Session(engine) as session:
        return session.exec(
            select(Member).where(Member.family_code == current.family_code)
        ).all()


@app.post("/api/members", response_model=AuthResponse, status_code=201)
def create_member_admin(member: MemberAdminCreate, current: Member = Depends(current_member)):
    if not current.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    with Session(engine) as session:
        existing_member = session.exec(
            select(Member).where(Member.email == member.email)
        ).first()
        if existing_member:
            raise HTTPException(status_code=409, detail="Email already exists")

        db_member = Member(
            email=member.email,
            lien=member.lien,
            name=member.name,
            is_admin=member.is_admin,
            family_code=current.family_code,
            password_hash=hash_password(member.password),
            token=new_session_token(),
        )
        session.add(db_member)
        session.commit()
        session.refresh(db_member)
        return db_member


@app.post("/api/members/signup", response_model=AuthResponse, status_code=201)
def create_member(member: MemberCreate):
    with Session(engine) as session:
        existing_member = session.exec(
            select(Member).where(Member.email == member.email)
        ).first()
        if existing_member:
            raise HTTPException(status_code=409, detail="Email already exists")

        db_member = Member(
            email=member.email,
            lien=member.lien,
            name=member.name,
            is_admin=member.is_admin,
            family_code=member.family_code,
            password_hash=hash_password(member.password),
            token=new_session_token(),
        )
        session.add(db_member)
        session.commit()
        session.refresh(db_member)
        return db_member        

@app.post("/api/members/login", response_model=AuthResponse)
def login_member(email: str, password: str):
    with Session(engine) as session:
        db_member = session.exec(
            select(Member).where(Member.email == email)
        ).first()
        if not db_member or db_member.password_hash != hash_password(password):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        db_member.token = new_session_token(db_member.token)
        session.add(db_member)
        session.commit()
        session.refresh(db_member)
        return db_member

@app.get("/api/members/me", response_model=MemberRead)
def get_current_member(current: Member = Depends(current_member)):
    return current


@app.post("/api/logout")
def logout(current: Member = Depends(current_member)):
    with Session(engine) as session:
        member = session.get(Member, current.id)
        member.token = None
        session.add(member)
        session.commit()
    return {"ok": True, "message": "Successfully logged out"}


@app.get("/api/members/{member_id}", response_model=MemberRead)
def get_member(member_id: int, current: Member = Depends(current_member)):
    with Session(engine) as session:
        db_member = session.get(Member, member_id)
        if not db_member or db_member.family_code != current.family_code:
            raise HTTPException(status_code=404, detail="Member not found")
        return db_member


@app.delete("/api/members/{member_id}")
def delete_member(member_id: int, current: Member = Depends(current_member)):
    if not current.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    if current.id == member_id:
        raise HTTPException(status_code=403, detail="You cannot delete your own account")

    with Session(engine) as session:
        db_member = session.get(Member, member_id)
        if not db_member:
            raise HTTPException(status_code=404, detail="Member not found")
        if db_member.family_code != current.family_code:
            raise HTTPException(status_code=404, detail="Member not found")

        session.exec(text('DELETE FROM tasks WHERE member_id = :member_id'), {"member_id": member_id})
        session.delete(db_member)
        session.commit()

    return {"ok": True, "message": "Member deleted successfully"}

AI_URL = (os.getenv("AI_URL") or "https://models.github.ai/inference").rstrip("/")
if AI_URL.endswith("/chat/completions"):
    AI_URL = AI_URL.removesuffix("/chat/completions")
AI_MODEL = os.getenv("AI_MODEL", "openai/gpt-4o-mini")
AI_TOKEN = os.getenv("AI_TOKEN", "")
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "ajouter_tache",
            "description": "Ajoute une tâche à la liste d'un membre de la famille.",
            "parameters": {
                "type": "object",
                "properties": {
                    "titre": {"type": "string", "description": "Le titre de la tâche."},
                    "personne": {"type": "string", "description": "Le prénom ou le lien de la personne concernée."},
                },
                "required": ["titre", "personne"],
            },
        },
    }
]


def normalize_member_hint(value: str | None) -> str:
    return (value or "").strip().lower().strip("'\"")


def is_self_reference(current: Member, member_hint: str | None) -> bool:
    hint = normalize_member_hint(member_hint)
    if not hint:
        return True

    self_tokens = {
        "moi",
        "moi-meme",
        "moi-même",
        "moi meme",
        "moi-meme",
        "myself",
        "me",
        "je",
        current.name.lower().strip() if current.name else "",
        current.lien.lower().strip() if current.lien else "",
        (current.lien.lower().strip() if current.lien else "").rstrip("s"),
    }
    return hint in self_tokens or hint.rstrip("s") in self_tokens


def resolve_member_for_task(current: Member, member_hint: str | None, session: Session) -> Member:
    candidates = resolve_member_candidates(current, member_hint, session)
    if not candidates:
        return current
    return candidates[0]


def resolve_member_candidates(current: Member, member_hint: str | None, session: Session) -> list[Member]:
    hint = (member_hint or "").strip()
    if not hint:
        return []

    normalized = hint.lower()
    members = session.exec(select(Member).where(Member.family_code == current.family_code)).all()
    matches: list[Member] = []

    for member in members:
        if member.name and member.name.lower() == normalized:
            matches.append(member)
        if member.lien and member.lien.lower() == normalized:
            matches.append(member)
        if member.lien and member.lien.lower().rstrip("s") == normalized.rstrip("s"):
            matches.append(member)

    unique: list[Member] = []
    seen: set[int] = set()
    for member in matches:
        if member.id is not None and member.id in seen:
            continue
        if member.id is not None:
            seen.add(member.id)
        unique.append(member)
    return unique


def detect_ambiguous_member_in_message(message: str, current: Member, session: Session) -> str | None:
    if not message:
        return None

    members = session.exec(select(Member).where(Member.family_code == current.family_code)).all()
    lowered = message.lower()

    for member in members:
        if member.name and member.name.lower() in lowered:
            matches = [m for m in members if m.name and m.name.lower() == member.name.lower()]
            if len(matches) > 1:
                names = ", ".join(f"{m.name} ({m.lien})" if m.lien else m.name for m in matches)
                return f"Il y a plusieurs personnes appelées {member.name} ({names}). Pour qui ?"

        if not member.lien:
            continue
        link = member.lien.lower().strip()
        base = link.rstrip("s")
        if link in lowered or base in lowered or (base + "s") in lowered:
            matches = [m for m in members if m.lien and m.lien.lower() == link]
            if len(matches) > 1:
                names = ", ".join(f"{m.name} ({m.lien})" if m.lien else m.name for m in matches)
                return f"Il y a plusieurs {link}s ({names}). Pour qui ?"
    return None


@app.post("/api/assistant")
async def assistant(message: str, current: Member = Depends(current_member)):
    if not AI_TOKEN:
        raise HTTPException(status_code=500, detail="AI_TOKEN is not configured")

    with Session(engine) as session:
        ambiguous = detect_ambiguous_member_in_message(message, current, session)
        if ambiguous:
            return {"reply": ambiguous}

    payload = {
        "model": AI_MODEL,
        "messages": [{"role": "user", "content": message}],
        "tools": TOOLS,
        "tool_choice": "auto",
        "temperature": 0.7,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{AI_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {AI_TOKEN}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"GitHub Models request failed: {exc}") from exc

    response_msg = (data.get("choices") or [{}])[0].get("message", {}) or {}
    tool_calls = response_msg.get("tool_calls") or []
    if tool_calls:
        with Session(engine) as session:
            for call in tool_calls:
                function = call.get("function", {}) or {}
                name = function.get("name")
                raw_args = function.get("arguments", {})
                if isinstance(raw_args, str):
                    try:
                        arguments = json.loads(raw_args)
                    except json.JSONDecodeError:
                        arguments = {}
                else:
                    arguments = raw_args or {}

                if name == "ajouter_tache":
                    titre = arguments.get("titre") or "Nouvelle tâche"
                    personne = arguments.get("personne") or current.name

                    if not current.is_admin and not is_self_reference(current, personne):
                        return {"reply": "Tu ne peux attribuer une tâche qu’à toi. Demande à l’assistant de créer une tâche pour toi."}

                    candidates = resolve_member_candidates(current, personne, session)
                    if len(candidates) == 0:
                        return {"reply": f"Je ne trouve personne correspondant à « {personne} » dans la famille."}

                    if len(candidates) > 1:
                        noms = ", ".join(f"{m.name} ({m.lien})" if m.lien else m.name for m in candidates)
                        if all(m.lien for m in candidates):
                            label = candidates[0].lien
                            return {"reply": f"Il y a plusieurs {label}s ({noms}). Pour qui ?"}
                        return {"reply": f"Il y a plusieurs personnes possibles ({noms}). Pour qui ?"}

                    target = candidates[0]
                    if not current.is_admin and target.id != current.id:
                        return {"reply": "Tu ne peux attribuer une tâche qu’à toi. Demande à l’assistant de créer une tâche pour toi."}

                    db_task = Task(title=titre, done=False, member_id=target.id)
                    session.add(db_task)
                    session.commit()
                    session.refresh(db_task)
                    return {"reply": f"Tâche ajoutée pour {target.name} : {db_task.title}"}

    reply = response_msg.get("content")
    if reply is None:
        raise HTTPException(status_code=502, detail="GitHub Models response is missing content")
    return {"reply": reply}
