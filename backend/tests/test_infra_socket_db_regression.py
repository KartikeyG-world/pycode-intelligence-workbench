import os
import sys
import socket
import pytest
from sqlalchemy import create_engine
from app.db.database import engine, Base, SessionLocal
from app.models.models import CodeSubmission, AnalysisResult
from conftest import (
    TEST_DB_FILE,
    TEST_DB_DIR,
    verify_test_database_isolation,
    _clean_session_test_db,
    _clean_stale_test_dbs,
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
    """Verify that if an accept connection does not arrive, it fails cleanly with TimeoutError in <= 2.5s."""
    if sys.platform != "win32":
        pytest.skip("Windows-specific timeout guard regression test")

    lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    lsock.bind(("127.0.0.1", 0))
    lsock.listen(1)
    lsock.settimeout(0.5)  # 0.5s test timeout
    try:
        # Deliberately do not connect: accept() must raise socket.timeout / TimeoutError boundedly
        with pytest.raises((socket.timeout, TimeoutError)):
            lsock.accept()
    finally:
        lsock.close()


def test_database_isolation_runtime_invariants():
    """Verify that tests execute exclusively against the dedicated isolated test SQLite database."""
    # Must pass without raising any ValueError
    verify_test_database_isolation(engine, TEST_DB_FILE)


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
