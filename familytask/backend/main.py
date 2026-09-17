import hashlib
import secrets

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import SQLModel, Session, Field, create_engine, select, text

DATABASE_URL = "postgresql://familytask:familytask@db:5432/familytask"


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