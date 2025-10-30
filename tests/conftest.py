"""Pytest configuration and fixtures for gryt-ci tests"""
import tempfile
from pathlib import Path
import pytest
from gryt.data import SqliteData


@pytest.fixture
def temp_dir():
    """Provide a temporary directory for test files"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_db(temp_dir):
    """Provide a test database"""
    db_path = temp_dir / "test.db"
    data = SqliteData(db_path=str(db_path))
    yield data
    data.close()


@pytest.fixture
def test_db_path(temp_dir):
    """Provide a test database path (for functions that need Path)"""
    db_path = temp_dir / "test.db"
    # Initialize database
    data = SqliteData(db_path=str(db_path))
    data.close()
    return db_path


@pytest.fixture
def gryt_project(temp_dir):
    """Provide a temporary gryt project directory with .gryt structure"""
    # Create .git folder (for repo root detection)
    git_dir = temp_dir / ".git"
    git_dir.mkdir()

    # Create .gryt structure
    gryt_dir = temp_dir / ".gryt"
    gryt_dir.mkdir()
    (gryt_dir / "generations").mkdir()
    (gryt_dir / "pipelines").mkdir()

    db_path = gryt_dir / "gryt.db"
    data = SqliteData(db_path=str(db_path))
    data.close()

    yield temp_dir
