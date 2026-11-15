import os
import sys
import uuid
import socket
import pytest

# 1. Deterministic isolated test database configuration
# Generate a unique session-specific test database file to guarantee zero collision across concurrent pytest runs
_SESSION_ID = f"{os.getpid()}_{uuid.uuid4().hex[:8]}"
TEST_DB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".test_dbs"))
os.makedirs(TEST_DB_DIR, exist_ok=True)
TEST_DB_FILE = os.path.abspath(os.path.join(TEST_DB_DIR, f"test_{_SESSION_ID}.db"))
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{TEST_DB_FILE}"

# Safeguard Windows socketpair against indefinite accept() blocking
# In restricted or sandboxed environments where loopback connects are blocked,
# standard library _fallback_socketpair's lsock.accept() would hang indefinitely without a timeout.
_orig_socketpair = getattr(socket, "socketpair", None)
_orig_fallback_socketpair = getattr(socket, "_fallback_socketpair", None)

if sys.platform == "win32" and _orig_fallback_socketpair is not None:
    def _timeout_guarded_socketpair(family=socket.AF_INET, type=socket.SOCK_STREAM, proto=0, *, timeout: float = 2.0):
        host = socket._LOCALHOST if family == socket.AF_INET else socket._LOCALHOST_V6
        lsock = socket.socket(family, type, proto)
        try:
            lsock.bind((host, 0))
            lsock.listen(1)
            lsock.settimeout(timeout)  # Bound accept timeout to prevent indefinite hangs
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
                    f"Windows loopback socketpair timed out after {timeout:.1f}s (SO_ERROR={err}). "
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


def _is_pid_alive(pid: int) -> bool:
    """Check if a process with the given PID is currently active."""
    if pid <= 0:
        return False
    try:
        if sys.platform == "win32":
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if h:
                ctypes.windll.kernel32.CloseHandle(h)
                return True
            return False
        else:
            os.kill(pid, 0)
            return True
    except Exception:
        return False


def _clean_stale_test_dbs(test_db_dir: str):
    """Clean up stale test databases from previously terminated or killed test runs."""
    if not os.path.exists(test_db_dir):
        return
    current_pid = os.getpid()
    for fname in os.listdir(test_db_dir):
        if not fname.startswith("test_"):
            continue
        fpath = os.path.join(test_db_dir, fname)
        # Parse PID from filename: test_{pid}_{uuid}.db...
        parts = fname.split("_")
        if len(parts) >= 2:
            try:
                file_pid = int(parts[1])
                # If PID is not current process and is no longer alive, remove stale artifact
                if file_pid != current_pid and not _is_pid_alive(file_pid):
                    try:
                        os.remove(fpath)
                    except OSError:
                        pass
            except ValueError:
                pass


def _clean_session_test_db(db_file: str):
    """Remove session test database file and any related SQLite journal / WAL / SHM files."""
    try:
        engine.dispose()
    except Exception:
        pass
    for ext in ("", "-wal", "-shm", "-journal"):
        path = f"{db_file}{ext}"
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass


def canonical_database_path(path: str) -> str:
    """Canonicalize a database filesystem path on Windows/POSIX, resolving symlinks
    and directory junctions even if the leaf file does not yet exist.
    """
    abs_p = os.path.abspath(path)
    parent = os.path.dirname(abs_p)
    leaf = os.path.basename(abs_p)
    resolved_parent = os.path.realpath(parent) if os.path.exists(parent) else parent
    return os.path.normcase(os.path.join(resolved_parent, leaf))


def verify_test_database_isolation(target_engine, expected_db_path: str, target_settings=None) -> None:
    """Strictly validates that the SQLAlchemy engine is using the dedicated test SQLite database.
    Rejects development database, PostgreSQL/Supabase, or any non-test configuration.
    Uses canonical, normalized Windows paths for comparison. Never prints credentials or secrets.
    """
    # 1. Verify dialect is sqlite
    if target_engine.dialect.name != "sqlite":
        raise ValueError(
            f"Database isolation violation: expected SQLite dialect, got '{target_engine.dialect.name}'"
        )

    # 2. Verify driver is pysqlite
    if target_engine.driver != "pysqlite":
        raise ValueError(
            f"Database isolation violation: expected pysqlite driver, got '{target_engine.driver}'"
        )

    # 3. Reject external PostgreSQL / Supabase
    url_str = str(target_engine.url).lower()
    if "postgresql" in url_str:
        raise ValueError("Database isolation violation: engine is connected to PostgreSQL/Supabase")

    # 4. Verify resolved database file matches the exact expected test database path
    raw_db = target_engine.url.database
    if not raw_db:
        raise ValueError("Database isolation violation: engine has no database file path")

    norm_resolved = canonical_database_path(raw_db)
    norm_expected = canonical_database_path(expected_db_path)

    # 5. Explicitly reject development database: complexity.db
    dev_db_file = canonical_database_path(os.path.join(os.path.dirname(__file__), "complexity.db"))
    if norm_resolved == dev_db_file or norm_resolved.endswith(os.path.normcase(os.path.sep + "complexity.db")):
        raise ValueError("Database isolation violation: engine is connected to development database complexity.db")

    # 6. Verify resolved database matches expected test database path
    if norm_resolved != norm_expected:
        raise ValueError(
            f"Database isolation violation: engine path does not match expected test database path"
        )

    # 7. Verify settings agree if provided
    if target_settings is not None:
        sett_url = str(target_settings.DATABASE_URL)
        raw_sett_path = sett_url.replace("sqlite+pysqlite:///", "")
        if norm_expected != canonical_database_path(raw_sett_path):
            raise ValueError("Database isolation violation: settings.DATABASE_URL does not match engine path")


@pytest.fixture(autouse=True, scope="session")
def setup_database():
    """Ensure isolated test database schema is created and cleaned up.
    Handles cleanup of pre-existing stale files from previously interrupted runs.
    """
    # 1. Clean stale database files left by previously dead pytest processes
    _clean_stale_test_dbs(TEST_DB_DIR)

    # 2. Strict isolation assertions: prevent accidental production/dev database contamination
    verify_test_database_isolation(engine, TEST_DB_FILE, settings)

    # 3. Create fresh schema in session-unique test database
    Base.metadata.create_all(bind=engine)
    yield

    # 4. Teardown: drop tables, dispose engine, delete session test database files
    try:
        Base.metadata.drop_all(bind=engine)
    except Exception:
        pass
    _clean_session_test_db(TEST_DB_FILE)


def _truncate_all_tables():
    """Helper to cleanly truncate all tables in reverse topological foreign-key order."""
    try:
        with engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(table.delete())
    except Exception:
        pass


@pytest.fixture(autouse=True)
def clean_database_tables():
    """Per-test database table row isolation.
    Ensures each test function starts and ends with completely empty tables.
    """
    _truncate_all_tables()
    yield
    _truncate_all_tables()


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
