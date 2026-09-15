import hashlib

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel, Session, Field, create_engine, select

DATABASE_URL = "postgresql://familytask:familytask@db:5432/familytask"


def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


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


class TaskCreate(SQLModel):
    title: str
    done: bool = False


class MemberCreate(SQLModel):
    email: str
    lien: str
    name: str
    is_admin: bool = False
    family_code: str
    password: str


class MemberRead(SQLModel):
    id: int
    email: str
    lien: str
    name: str
    is_admin: bool
    family_code: str
    token: str | None = None

SQLModel.metadata.create_all(engine)


app = FastAPI(title="FamilyTask")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/api/tasks", response_model=list[Task])
def get_tasks():
    with Session(engine) as session:
        tasks = session.exec(select(Task)).all()
    return [task.model_dump() for task in tasks]

@app.post("/api/tasks", response_model=Task)
def create_tasks(task: TaskCreate):
    with Session(engine) as session:
        db_tasks = Task(title=task.title, done=task.done)
        session.add(db_tasks)
        session.commit()
        session.refresh(db_tasks)
    return db_tasks

@app.patch("/api/tasks/{task_id}", response_model=Task)
def update_task(task_id: int, task: Task):
    with Session(engine) as session:
        db_task = session.get(Task, task_id)
        if not db_task:
            return {"error": "Task not found"}
        db_task.title = task.title
        db_task.done = task.done
        session.add(db_task)
        session.commit()
        session.refresh(db_task)
    return db_task.model_dump()

@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: int):
    with Session(engine) as session:
        db_task = session.get(Task, task_id)
        if not db_task:
            return {"error": "Task not found"}
        session.delete(db_task)
        session.commit()
    return {"message": "Task deleted successfully"}

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/members", response_model=list[MemberRead])
def get_members():
    with Session(engine) as session:
        return session.exec(select(Member)).all()


@app.post("/api/members", response_model=MemberRead, status_code=201)
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
        )
        session.add(db_member)
        session.commit()
        session.refresh(db_member)
        return db_member

