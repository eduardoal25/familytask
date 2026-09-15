from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from sqlmodel import SQLModel, Session, Field, create_engine, select

DATABASE_URL = "postgresql://familytask:familytask@db:5432/familytask"

engine = create_engine(DATABASE_URL, echo=True)

class Task(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    done: bool = False

SQLModel.metadata.create_all(engine)


app = FastAPI(title="FamilyTask")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

import psycopg2

conn = psycopg2.connect("dbname=familytask user=familytask password=familytask host=db")
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    done BOOLEAN DEFAULT FALSE
);
""")
conn.commit()
cur.close()
conn.close()

class Task(BaseModel):
    id: int
    title: str
    done: bool = False
@app.get("/api/tasks", response_model=list[Task])
def get_tasks():
    with Session(engine) as session:
        tasks = session.exec(select(Task)).all()
    return [task.model_dump() for task in tasks]

@app.post("/api/tasks", response_model=Task)
def create_task(task: Task):
    with Session(engine) as session:
        db_task = Task(title=task.title, done=task.done)
        session.add(db_task)
        session.commit()
        session.refresh(db_task)
    return {
  "id": 1,
  "title": "Laver la voiture",
  "done": false
}

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

