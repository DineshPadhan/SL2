from pathlib import Path
import sys

from fastapi import FastAPI

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.config import settings
from src.database import Base, engine
from src.task1_core_api import router as core_router
from src.task2_auth import router as auth_router
from src.task3_validation import register_exception_handlers

Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.app_name)
register_exception_handlers(app)
app.include_router(auth_router)
app.include_router(core_router)


@app.get("/")
def root():
    return {"app": settings.app_name, "status": "ok"}
