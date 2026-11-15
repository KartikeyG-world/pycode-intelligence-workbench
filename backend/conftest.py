import os
import sys
import socket
import pytest

# 1. Deterministic isolated test database configuration
# Set DATABASE_URL before importing application settings or database modules
TEST_DB_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_complexity.db"))
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{TEST_DB_FILE}"

# Safeguard Windows socketpair against indefinite accept() blocking
# In restricted or sandboxed environments where loopback connects are blocked,
# standard library _fallback_socketpair's lsock.accept() would hang indefinitely without a timeout.
_orig_fallback_socketpair = getattr(socket, "_fallback_socketpair", None)
if _orig_fallback_socketpair is not None:
    def _timeout_guarded_socketpair(family=socket.AF_INET, type=socket.SOCK_STREAM, proto=0):
        host = socket._LOCALHOST if family == socket.AF_INET else socket._LOCALHOST_V6
        lsock = socket.socket(family, type, proto)
        try:
            lsock.bind((host, 0))
            lsock.listen(1)
            lsock.settimeout(2.0)  # Bound accept timeout to prevent indefinite hangs
            addr, port = lsock.getsockname()[:2]
            csock = socket.socket(family, type, proto)
            try:
                csock.setblocking(False)
                try:
                    csock.connect((addr, port))
                except (BlockingIOError, InterruptedError):
                    pass
                csock.setblocking(True)
                ssock, _ = lsock.accept()
                ssock.setblocking(True)
            except Exception:
                csock.close()
                raise
        finally:
            lsock.close()
        return (ssock, csock)

    socket._fallback_socketpair = _timeout_guarded_socketpair
    if getattr(socket, "socketpair", None) is _orig_fallback_socketpair:
        socket.socketpair = _timeout_guarded_socketpair

from app.core.config import settings
# Guarantee settings uses test database URL even if cached
settings.DATABASE_URL = f"sqlite+pysqlite:///{TEST_DB_FILE}"

from app.db.database import Base, engine, SessionLocal
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True, scope="session")
def setup_database():
    """Ensure isolated test database schema is created and cleaned up."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except OSError:
            pass


@pytest.fixture
def db_session():
    """Provide a transactional database session with automatic rollback and cleanup."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client():
    """Provide a TestClient with proper FastAPI lifespan lifecycle management."""
    with TestClient(app) as test_client:
        yield test_client
