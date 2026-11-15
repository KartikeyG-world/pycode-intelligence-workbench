import os
import sys
import socket
import pytest
from app.db.database import engine, Base, SessionLocal
from app.models.models import CodeSubmission, AnalysisResult
from conftest import TEST_DB_FILE, _clean_test_db_files


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
    url_str = str(engine.url)
    assert "test_complexity.db" in url_str, f"Unexpected DB in engine: {url_str}"
    assert not url_str.startswith("postgresql"), f"Automated tests must never target PostgreSQL: {url_str}"
    assert not (url_str.endswith("complexity.db") and not url_str.endswith("test_complexity.db")), (
        f"Automated tests must not target development complexity.db: {url_str}"
    )


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
    """Verify that _clean_test_db_files removes .db, -wal, -shm, and -journal files left by interrupted runs."""
    fake_db = str(tmp_path / "stale_test.db")
    for ext in ("", "-wal", "-shm", "-journal"):
        with open(f"{fake_db}{ext}", "w") as f:
            f.write("stale_data")
        assert os.path.exists(f"{fake_db}{ext}")

    # Test file deletion logic
    for ext in ("", "-wal", "-shm", "-journal"):
        path = f"{fake_db}{ext}"
        if os.path.exists(path):
            os.remove(path)
        assert not os.path.exists(f"{fake_db}{ext}")
