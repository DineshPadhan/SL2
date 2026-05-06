import os
import sys
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ["DATABASE_URL"] = "sqlite:///./test_skillbridge.db"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["MONITORING_API_KEY"] = "test-monitoring-key"

from src.database import Base, get_db  # noqa: E402
from src.main import app  # noqa: E402


TEST_DATABASE_URL = "sqlite:///./test_skillbridge.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False}, future=True)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def override_get_db() -> Generator:
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
