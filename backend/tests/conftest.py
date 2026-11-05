import os
import sys
import tempfile
from pathlib import Path

import pytest

# Bază de date temporară, separată de sql_app.db — testele nu ating datele reale
_TMP = tempfile.mkdtemp(prefix="silmar_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP, 'test.db').as_posix()}"
os.environ["SECRET_KEY"] = "test-secret-key-test-secret-key-1234567890"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "parola-test-123"
os.environ["COOKIE_SECURE"] = "false"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402


@pytest.fixture(scope="session")
def anonim():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        r = c.post("/api/auth/login", json={"username": "admin", "password": "parola-test-123"})
        assert r.status_code == 200, r.text
        yield c


def cnp_valid(prefix12: str) -> str:
    cheie = "279146358279"
    s = sum(int(a) * int(b) for a, b in zip(prefix12, cheie)) % 11
    return prefix12 + str(1 if s == 10 else s)
