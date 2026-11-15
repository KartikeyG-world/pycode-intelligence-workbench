import pytest
from app.db.database import Base, engine

@pytest.fixture(autouse=True, scope="session")
def setup_database():
    """Ensure database schema is created for test runs."""
    Base.metadata.create_all(bind=engine)
    yield
