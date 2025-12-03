from namel3ss.secrets.manager import SecretsManager


def test_secret_helpers_for_rag_backends():
    env = {
        "N3_RAG_INDEX_DOCS_BACKEND": "pgvector",
        "N3_RAG_PGVECTOR_DSN": "postgresql://user:pass@localhost/db",
        "N3_RAG_INDEX_DOCS_PG_TABLE": "docs_table",
        "N3_RAG_INDEX_LOCAL_FAISS_INDEX_PATH": "/tmp/faiss",
    }
    secrets = SecretsManager(env=env)
    assert secrets.get_rag_index_backend("docs") == "pgvector"
    assert secrets.get_pgvector_dsn() == "postgresql://user:pass@localhost/db"
    assert secrets.get_pgvector_table("docs") == "docs_table"
    assert secrets.get_faiss_index_path("local") == "/tmp/faiss"
