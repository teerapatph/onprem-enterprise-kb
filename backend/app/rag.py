import os
import json
import time
import httpx
from typing import AsyncGenerator
from .database import get_connection

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:3b")


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    chunks = []
    start = 0
    text = text.strip()
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return [c for c in chunks if c.strip()]


async def get_embedding(text: str) -> list[float]:
    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.post(
            f"{OLLAMA_BASE_URL}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text},
        )
        res.raise_for_status()
        return res.json()["embedding"]


async def ingest_document(filename: str, text: str, department: str = "general") -> int:
    chunks = chunk_text(text)
    with get_connection() as conn:
        with conn.cursor() as cur:
            for idx, chunk in enumerate(chunks):
                embedding = await get_embedding(chunk)
                cur.execute(
                    """
                    INSERT INTO kb_chunks (filename, department, chunk_index, content, embedding)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (filename, department, idx, chunk, embedding),
                )
    return len(chunks)


async def retrieve_context(
    query: str, department: str | None = None, top_k: int = 4
) -> list[dict]:
    query_embedding = await get_embedding(query)
    with get_connection() as conn:
        with conn.cursor() as cur:
            if department and department != "all":
                cur.execute(
                    """
                    SELECT filename, chunk_index, content, 1 - (embedding <=> %s::vector) AS similarity
                    FROM kb_chunks
                    WHERE department = %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (query_embedding, department, query_embedding, top_k),
                )
            else:
                cur.execute(
                    """
                    SELECT filename, chunk_index, content, 1 - (embedding <=> %s::vector) AS similarity
                    FROM kb_chunks
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (query_embedding, query_embedding, top_k),
                )
            rows = cur.fetchall()

    return [
        {
            "filename": r[0],
            "chunk_index": r[1],
            "content": r[2],
            "similarity": round(float(r[3]), 4),
        }
        for r in rows
    ]


def log_query_metrics(
    query_text: str,
    department_filter: str,
    sources: list[dict],
    retrieval_ms: float,
    ttft_ms: float | None,
    total_latency_ms: float,
) -> None:
    similarities = [s["similarity"] for s in sources]
    top_sim = max(similarities) if similarities else None
    avg_sim = round(sum(similarities) / len(similarities), 4) if similarities else None

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO query_logs (
                    query_text,
                    department_filter,
                    retrieved_count,
                    top_similarity,
                    avg_similarity,
                    retrieval_ms,
                    ttft_ms,
                    total_latency_ms
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    query_text,
                    department_filter,
                    len(sources),
                    top_sim,
                    avg_sim,
                    round(retrieval_ms, 2),
                    round(ttft_ms, 2) if ttft_ms is not None else None,
                    round(total_latency_ms, 2),
                ),
            )


async def stream_rag_answer(
    query: str, department: str | None = None
) -> AsyncGenerator[str, None]:
    request_start = time.perf_counter()
    dept_scope = department or "all"

    sources = await retrieve_context(query, department=dept_scope)
    retrieval_ms = (time.perf_counter() - request_start) * 1000

    yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

    context_block = "\n\n---\n\n".join(
        f"[{s['filename']} | Chunk {s['chunk_index']}]\n{s['content']}"
        for s in sources
    )

    prompt = f"""You are an internal enterprise AI assistant. Answer the user's question strictly using the provided context. If the answer is not in the context, state that you do not have enough information.

Context:
{context_block}

Question: {query}
Answer:"""

    ttft_ms: float | None = None

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{OLLAMA_BASE_URL}/api/generate",
                json={"model": LLM_MODEL, "prompt": prompt, "stream": True},
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    if "response" in data:
                        if ttft_ms is None:
                            ttft_ms = (time.perf_counter() - request_start) * 1000
                        yield f"data: {json.dumps({'type': 'token', 'content': data['response']})}\n\n"
                    if data.get("done"):
                        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    finally:
        total_latency_ms = (time.perf_counter() - request_start) * 1000
        log_query_metrics(
            query_text=query,
            department_filter=dept_scope,
            sources=sources,
            retrieval_ms=retrieval_ms,
            ttft_ms=ttft_ms,
            total_latency_ms=total_latency_ms,
        )