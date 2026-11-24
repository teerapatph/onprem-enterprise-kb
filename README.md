# On-Premise Enterprise Knowledge Assistant

A self-hosted, privacy-focused Retrieval-Augmented Generation (RAG) web application designed for enterprise environments. All document ingestion, vector indexing, and LLM inference run entirely locally on-premise without external cloud API dependencies.

---

## Architecture & Tech Stack

- **Inference Engine:** [Ollama](https://ollama.com/) (`qwen2.5:3b` for generation, `nomic-embed-text` for 768-dimensional embeddings)
- **Database & Vector Store:** PostgreSQL 16 with `pgvector` (HNSW cosine similarity indexing + SQL telemetry logging)
- **Backend API:** Python 3.11, FastAPI, `psycopg3`, Server-Sent Events (SSE) token streaming
- **Frontend UI:** Next.js (App Router), TypeScript, Tailwind CSS
- **Infrastructure & Testing:** Docker Compose, `pytest`

---

## Repository Structure

```text
onprem-ai-warmup/
├── docker-compose.yml          # PostgreSQL (pgvector), Ollama, and FastAPI services
├── .gitignore                  # Exclusion rules for node_modules, cache, and env files
├── README.md                   # Project documentation
├── backend/
│   ├── Dockerfile              # Container definition for FastAPI backend
│   ├── requirements.txt        # Python package dependencies
│   ├── pytest.ini              # Pytest configuration and warning filters
│   ├── app/
│   │   ├── main.py             # FastAPI routes (/health, /documents, /ingest, /chat, /analytics)
│   │   ├── database.py         # PostgreSQL connection pool & schema initialization
│   │   └── rag.py              # Text chunking, embeddings, vector search & SSE streaming
│   └── tests/
│       ├── __init__.py
│       └── test_api.py         # End-to-end integration test suite
└── frontend/
    └── src/
        ├── app/                # Next.js App Router layout & dashboard page
        ├── components/         # DocumentSidebar & ChatPanel UI components
        ├── lib/                # Typed API client & SSE stream parser
        └── types/              # Shared TypeScript interfaces
```

---

## Quick Start Guide

### 1. Start Infrastructure & Fetch Local AI Models
Launch the PostgreSQL database and Ollama containers in the background, then download the generation and embedding models:

```powershell
# Navigate to project root
cd D:\working\onprem-ai-warmup

# Launch database and inference engine
docker compose up -d db ollama

# Pull local embedding and generation models into Ollama
docker exec -it warmup-ollama ollama pull nomic-embed-text
docker exec -it warmup-ollama ollama pull qwen2.5:3b
```

### 2. Launch the FastAPI Backend Container
Build and start the Python backend container:

```powershell
docker compose up -d --build backend
```

Verify that the backend is healthy by visiting `http://localhost:8000/health` or exploring the interactive OpenAPI documentation at `http://localhost:8000/docs`.

### 3. Launch the Next.js Frontend
Start the Next.js development server locally for instant hot-reloading:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000` in your browser.

---

## API Reference Table

| Method | Endpoint | Request Payload / Params | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | None | Service health check returning `{"status": "ok"}` |
| `GET` | `/documents` | None | Returns list of indexed files with chunk counts & department tags |
| `POST` | `/ingest` | `multipart/form-data` (`file`, `department`) | Splits document, generates vectors, and indexes in PostgreSQL |
| `POST` | `/chat` | `JSON` (`query`, `department`) | Streams RAG response tokens and source citations via SSE |
| `GET` | `/analytics` | None | Retrieves telemetry metrics (`p50`/`p95` latency, TTFT, similarity) |

---

## Testing & Quality Assurance

Run the automated `pytest` integration suite inside the backend container to test document parsing, department scope isolation, SSE streaming, and analytics telemetry:

```powershell
# Copy test suite into the running container
docker cp ./backend/tests warmup-backend:/app/tests

# Run pytest with verbose execution output
docker exec -it warmup-backend pytest -v
```

---

## License & Operational Security

This software is built strictly for internal enterprise execution. No outbound network connections are established during vector embedding, document retrieval, or prompt generation.