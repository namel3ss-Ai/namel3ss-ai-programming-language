import pytest

from namel3ss.rag.vectorstores.pgvector import PGVectorStore, psycopg
from namel3ss.errors import Namel3ssError


def test_pgvector_requires_dsn():
    with pytest.raises(Namel3ssError):
        PGVectorStore(dsn="")


@pytest.mark.skipif(psycopg is None, reason="psycopg not installed")
def test_pgvector_table_creation(monkeypatch):
    # Skip actual DB interaction; ensure constructor does not raise when psycopg is mocked.
    called = {}

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, *args, **kwargs):
            called["execute"] = True

        def commit(self):
            called["commit"] = True

    monkeypatch.setattr("namel3ss.rag.vectorstores.pgvector.psycopg.connect", lambda dsn: FakeConn())
    store = PGVectorStore(dsn="postgresql://user:pass@localhost/db", table="rag_items_test")
    assert store.table == "rag_items_test"
    assert called
