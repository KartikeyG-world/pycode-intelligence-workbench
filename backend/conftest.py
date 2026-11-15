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
_orig_socketpair = getattr(socket, "socketpair", None)
_orig_fallback_socketpair = getattr(socket, "_fallback_socketpair", None)

if sys.platform == "win32" and _orig_fallback_socketpair is not None:
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
            except (socket.timeout, TimeoutError) as e:
                csock.close()
                err = csock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR) if csock.fileno() != -1 else None
                raise TimeoutError(
                    f"Windows loopback socketpair timed out after 2.0s (SO_ERROR={err}). "
                    "Verify local network / loopback socket permissions."
                ) from e
            except Exception:
                csock.close()
                raise
        finally:
            lsock.close()
        return (ssock, csock)

    socket._fallback_socketpair = _timeout_guarded_socketpair
    if getattr(socket, "socketpair", None) is _orig_fallback_socketpair:
        socket.socketpair = _timeout_guarded_socketpair


def pytest_unconfigure(config):
    """Restore original socket functions on pytest session completion."""
    if sys.platform == "win32":
        if _orig_socketpair is not None:
            socket.socketpair = _orig_socketpair
        if _orig_fallback_socketpair is not None:
            socket._fallback_socketpair = _orig_fallback_socketpair


from app.core.config import settings
# Guarantee settings uses test database URL even if cached
settings.DATABASE_URL = f"sqlite+pysqlite:///{TEST_DB_FILE}"

from app.db.database import Base, engine, SessionLocal
from app.main import app
from fastapi.testclient import TestClient


def _clean_test_db_files():
    """Remove test database file and any related SQLite journal / WAL / SHM files."""
    try:
        engine.dispose()
    except Exception:
        pass
    for ext in ("", "-wal", "-shm", "-journal"):
        path = f"{TEST_DB_FILE}{ext}"
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass


@pytest.fixture(autouse=True, scope="session")
def setup_database():
    """Ensure isolated test database schema is created and cleaned up.
    Handles cleanup of pre-existing stale files from previously interrupted runs.
    """
    # 1. Clean any stale database files left by interrupted runs
    _clean_test_db_files()

    # 2. Strict isolation assertions: prevent accidental production/dev database contamination
    db_url_str = str(engine.url)
    assert "test_complexity.db" in db_url_str, (
        f"Security violation: Tests must run against isolated test_complexity.db, got: {db_url_str}"
    )
    assert not db_url_str.startswith("postgresql"), (
        f"Security violation: Tests must NEVER connect to external Supabase / PostgreSQL: {db_url_str}"
    )
    assert not (db_url_str.endswith("complexity.db") and not db_url_str.endswith("test_complexity.db")), (
        f"Isolation violation: Tests must not connect to the development complexity.db: {db_url_str}"
    )

    # 3. Create fresh schema
    Base.metadata.create_all(bind=engine)
    yield

    # 4. Teardown: drop tables, dispose engine, delete test database files
    try:
        Base.metadata.drop_all(bind=engine)
    except Exception:
        pass
    _clean_test_db_files()


@pytest.fixture(autouse=True)
def clean_database_tables():
    """Per-test database table row isolation.
    Ensures each test function starts and ends with completely empty tables.
    """
    yield
    # Delete all rows after each test to prevent cross-test state leakage
    try:
        with engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(table.delete())
    except Exception:
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
