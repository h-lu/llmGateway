from gateway.app.db.session import get_engine
from gateway.app.db.base import Base
from gateway.app.db import models  # noqa: F401 - import to register models


def test_db_models_create_tables():
    engine = get_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    tables = Base.metadata.tables.keys()
    assert "students" in tables
    assert "conversations" in tables
    assert "rules" in tables
    assert "quota_logs" in tables
