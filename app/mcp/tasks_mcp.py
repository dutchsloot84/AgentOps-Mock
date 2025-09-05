import json
import os
from typing import Dict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

SEED_TASKS = os.getenv("SEED_TASKS", "mocks/data/seed_tasks.json")
app = FastAPI(title="tasks-mcp")

with open(SEED_TASKS, "r", encoding="utf-8") as f:
    TASKS: Dict[str, Dict] = {t["id"]: t for t in json.load(f)}


class AddTask(BaseModel):
    title: str
    due: str


def _new_id() -> str:
    return f"T-{len(TASKS)+1:04d}"


@app.get("/list")
def list_tasks():
    return list(TASKS.values())


@app.post("/add")
def add_task(task: AddTask):
    task_id = _new_id()
    task_obj = {"id": task_id, "title": task.title, "due": task.due, "status": "open"}
    TASKS[task_id] = task_obj
    return task_obj


@app.post("/complete/{task_id}")
def complete_task(task_id: str):
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")
    TASKS[task_id]["status"] = "done"
    return TASKS[task_id]
