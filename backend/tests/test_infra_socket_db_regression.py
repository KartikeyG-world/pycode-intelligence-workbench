import os
import sys
import socket
import time
import inspect
from unittest import mock
import pytest
from sqlalchemy import create_engine
from app.db.database import engine, Base, SessionLocal
from app.models.models import CodeSubmission, AnalysisResult
from conftest import (
    TEST_DB_FILE,
    TEST_DB_DIR,
    verify_test_database_isolation,
    canonical_database_path,
    _clean_session_test_db,
    _clean_stale_test_dbs,
    _timeout_guarded_socketpair,
)


def test_socketpair_active_and_functional():
    """Verify that socket.socketpair() succeeds, connects, and can transfer bidirectional data."""
    s1, s2 = socket.socketpair()
    try:
        s1.sendall(b"PING")
        received = s2.recv(1024)
        assert received == b"PING"
        s2.sendall(b"PONG")
        received_back = s1.recv(1024)
        assert received_back == b"PONG"
    finally:
        s1.close()
        s2.close()


def test_timeout_guarded_socketpair_bounded_failure():
    """Verify that _timeout_guarded_socketpair executes its accept timeout and cleans up.
    Simulates the exact failure condition (WSAEWOULDBLOCK where connection never reaches lsock).
    Verifies that it raises TimeoutError in bounded time and default timeout is 2.0s.
    """
    if sys.platform != "win32":
        pytest.skip("Windows-specific timeout guard regression test")

    # 1. Verify default timeout parameter is exactly 2.0s
    sig = inspect.signature(_timeout_guarded_socketpair)
    assert sig.parameters["timeout"].default == 2.0, "Default listener timeout must be 2.0s"

    # 2. Exercise the actual _timeout_guarded_socketpair failure path with a shortened 0.3s timeout
    start_time = time.monotonic()
    with mock.patch.object(socket.socket, "connect", side_effect=BlockingIOError):
        with pytest.raises(TimeoutError, match="Windows loopback socketpair timed out after 0.3s") as exc_info:
            _timeout_guarded_socketpair(timeout=0.3)
    duration = time.monotonic() - start_time

    # Must complete boundedly in approximately 0.3s (allowing scheduling variance)
    assert 0.25 <= duration <= 0.60, f"Expected ~0.3s timeout duration, took {duration:.3f}s"
    assert "SO_ERROR" in str(exc_info.value)


def test_database_isolation_runtime_invariants():
    """Verify that tests execute exclusively against the dedicated isolated test SQLite database."""
    # Must pass without raising any ValueError
    verify_test_database_isolation(engine, TEST_DB_FILE)


def test_database_isolation_canonical_path_resolution(tmp_path):
    """Verify canonical_database_path handles symlinks, parent directories, and case normalization."""
    raw_path = str(tmp_path / "SubDir" / "test.db")
    canon = canonical_database_path(raw_path)

    # Must normalize drive and casing
    assert canon == os.path.normcase(os.path.abspath(raw_path))

    # Leaf non-existence must not cause resolution failure
    assert not os.path.exists(canon)
    assert canonical_database_path(canon) == canon


def test_database_isolation_negative_rejection(tmp_path):
    """Verify that verify_test_database_isolation rejects invalid, development, or external DB configurations."""
    # Case 1: Rejects development database complexity.db
    dev_db = os.path.abspath(os.path.join(os.path.dirname(TEST_DB_FILE), "..", "complexity.db"))
    dev_engine = create_engine(f"sqlite+pysqlite:///{dev_db}")
    with pytest.raises(ValueError, match="development database"):
        verify_test_database_isolation(dev_engine, TEST_DB_FILE)

    # Case 2: Rejects external PostgreSQL configuration
    pg_engine = create_engine("sqlite+pysqlite:///:memory:")  # Create sqlite engine but mock URL check
    pg_engine.url = pg_engine.url.set(drivername="postgresql+psycopg")
    with pytest.raises(ValueError, match="PostgreSQL/Supabase|expected SQLite dialect"):
        verify_test_database_isolation(pg_engine, TEST_DB_FILE)

    # Case 3: Rejects mismatched database path
    other_db = str(tmp_path / "other_database.db")
    other_engine = create_engine(f"sqlite+pysqlite:///{other_db}")
    with pytest.raises(ValueError, match="does not match expected"):
        verify_test_database_isolation(other_engine, TEST_DB_FILE)


def test_database_per_test_row_isolation_part_1():
    """Part 1 of cross-test isolation verification: insert a test record."""
    session = SessionLocal()
    try:
        sub = CodeSubmission(
            id="test-isolation-sub-1",
            title="Isolation Test 1",
            code="def foo(): pass",
        )
        session.add(sub)
        session.commit()
        count = session.query(CodeSubmission).filter_by(id="test-isolation-sub-1").count()
        assert count == 1
    finally:
        session.close()


def test_database_per_test_row_isolation_part_2():
    """Part 2 of cross-test isolation verification: verify table is empty, proving part 1 was cleaned up."""
    session = SessionLocal()
    try:
        # Table must be completely clean; part 1 record must have been deleted by clean_database_tables
        count = session.query(CodeSubmission).filter_by(id="test-isolation-sub-1").count()
        assert count == 0, "Cross-test database contamination detected: row from Part 1 leaked into Part 2!"
    finally:
        session.close()


def test_stale_database_cleanup_handles_interrupted_runs(tmp_path):
    """Verify that stale test database cleanup removes files from dead PIDs."""
    test_dir = str(tmp_path / "stale_dir")
    os.makedirs(test_dir, exist_ok=True)

    # Create a fake test DB with a dead PID (e.g. 999999)
    dead_pid_file = os.path.join(test_dir, "test_999999_deadbeef.db")
    with open(dead_pid_file, "w") as f:
        f.write("stale_db")
    with open(f"{dead_pid_file}-wal", "w") as f:
        f.write("stale_wal")

    assert os.path.exists(dead_pid_file)
    assert os.path.exists(f"{dead_pid_file}-wal")

    # Clean stale files in test directory
    _clean_stale_test_dbs(test_dir)

    # Files associated with dead PID 999999 must have been removed
    assert not os.path.exists(dead_pid_file)
    assert not os.path.exists(f"{dead_pid_file}-wal")
