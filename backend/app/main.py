import io
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pypdf import PdfReader

from .database import init_db, get_connection
from .rag import ingest_document, stream_rag_answer


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="On-Premise Enterprise KB API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    query: str
    department: str | None = "all"


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/documents")
def list_documents():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT filename, department, COUNT(*) as chunks, MAX(created_at) as uploaded_at
                FROM kb_chunks
                GROUP BY filename, department
                ORDER BY uploaded_at DESC
            """)
            rows = cur.fetchall()
    return [
        {
            "filename": r[0],
            "department": r[1],
            "chunks": r[2],
            "uploaded_at": r[3].isoformat() if r[3] else None,
        }
        for r in rows
    ]


@app.post("/ingest")
async def upload_document(
    file: UploadFile = File(...),
    department: str = Form("general"),
):
    raw_bytes = await file.read()
    filename = file.filename or "untitled"

    if filename.lower().endswith(".pdf"):
        reader = PdfReader(io.BytesIO(raw_bytes))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    elif filename.lower().endswith((".txt", ".md")):
        text = raw_bytes.decode("utf-8", errors="ignore")
    else:
        raise HTTPException(
            status_code=400, detail="Only .pdf, .md, and .txt files are supported."
        )

    if not text.strip():
        raise HTTPException(status_code=400, detail="No readable text found in file.")

    chunk_count = await ingest_document(filename, text, department)
    return {
        "filename": filename,
        "department": department,
        "chunks_indexed": chunk_count,
    }


@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    return StreamingResponse(
        stream_rag_answer(req.query, req.department),
        media_type="text/event-stream",
    )

@app.get("/analytics")
def get_analytics():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) AS total_queries,
                    ROUND(AVG(retrieval_ms)::numeric, 2) AS avg_retrieval_ms,
                    ROUND(AVG(ttft_ms)::numeric, 2) AS avg_ttft_ms,
                    ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY total_latency_ms)::numeric, 2) AS p50_latency_ms,
                    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY total_latency_ms)::numeric, 2) AS p95_latency_ms,
                    ROUND(AVG(top_similarity)::numeric, 4) AS avg_top_similarity,
                    ROUND(AVG(avg_similarity)::numeric, 4) AS avg_chunk_similarity
                FROM query_logs
            """)
            summary = cur.fetchone()

            cur.execute("""
                SELECT
                    id,
                    query_text,
                    department_filter,
                    retrieved_count,
                    top_similarity,
                    avg_similarity,
                    retrieval_ms,
                    ttft_ms,
                    total_latency_ms,
                    created_at
                FROM query_logs
                ORDER BY created_at DESC
                LIMIT 10
            """)
            recent_rows = cur.fetchall()

    return {
        "summary": {
            "total_queries": summary[0] if summary else 0,
            "avg_retrieval_ms": float(summary[1]) if summary and summary[1] is not None else 0.0,
            "avg_ttft_ms": float(summary[2]) if summary and summary[2] is not None else 0.0,
            "p50_latency_ms": float(summary[3]) if summary and summary[3] is not None else 0.0,
            "p95_latency_ms": float(summary[4]) if summary and summary[4] is not None else 0.0,
            "avg_top_similarity": float(summary[5]) if summary and summary[5] is not None else 0.0,
            "avg_chunk_similarity": float(summary[6]) if summary and summary[6] is not None else 0.0,
        },
        "recent_queries": [
            {
                "id": r[0],
                "query_text": r[1],
                "department_filter": r[2],
                "retrieved_count": r[3],
                "top_similarity": r[4],
                "avg_similarity": r[5],
                "retrieval_ms": r[6],
                "ttft_ms": r[7],
                "total_latency_ms": r[8],
                "created_at": r[9].isoformat() if r[9] else None,
            }
            for r in recent_rows
        ],
    }