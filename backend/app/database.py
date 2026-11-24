import os
import psycopg
from pgvector.psycopg import register_vector

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://devuser:devpassword@db:5432/enterprise_kb"
)


def get_connection():
    conn = psycopg.connect(DATABASE_URL, autocommit=True)
    register_vector(conn)
    return conn


def init_db():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS kb_chunks (
                    id SERIAL PRIMARY KEY,
                    filename TEXT NOT NULL,
                    department TEXT DEFAULT 'general',
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    embedding vector(768),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS kb_chunks_embedding_idx
                ON kb_chunks
                USING hnsw (embedding vector_cosine_ops);
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS query_logs (
                    id SERIAL PRIMARY KEY,
                    query_text TEXT NOT NULL,
                    department_filter TEXT DEFAULT 'all',
                    retrieved_count INTEGER NOT NULL,
                    top_similarity REAL,
                    avg_similarity REAL,
                    retrieval_ms REAL NOT NULL,
                    ttft_ms REAL,
                    total_latency_ms REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)