import json
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import init_db, get_connection

TEST_ENG_FILE = "pytest_eng_spec.txt"
TEST_HR_FILE = "pytest_hr_policy.txt"
TEST_QUERY_MARKER = "[PYTEST_INTEGRATION]"


def cleanup_test_records():
    """Remove only rows created by this test suite."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM kb_chunks WHERE filename IN (%s, %s);",
                (TEST_ENG_FILE, TEST_HR_FILE),
            )
            cur.execute(
                "DELETE FROM query_logs WHERE query_text LIKE %s;",
                (f"{TEST_QUERY_MARKER}%",),
            )


@pytest.fixture(scope="module", autouse=True)
def setup_and_teardown_db():
    init_db()
    cleanup_test_records()
    yield
    cleanup_test_records()


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def parse_sse_stream(raw_text: str) -> tuple[list[dict], str, bool]:
    """Parse SSE lines into (sources, full_answer_text, received_done)."""
    sources: list[dict] = []
    tokens: list[str] = []
    done = False

    for block in raw_text.strip().split("\n\n"):
        if not block.startswith("data: "):
            continue
        payload = json.loads(block[6:])
        event_type = payload.get("type")

        if event_type == "sources":
            sources = payload.get("sources", [])
        elif event_type == "token":
            tokens.append(payload.get("content", ""))
        elif event_type == "done":
            done = True

    return sources, "".join(tokens), done


def test_health_endpoint(client: TestClient):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_ingest_and_list_documents(client: TestClient):
    eng_content = (
        b"Internal GPU server runs on VLAN 10.99.0.0/24 using port 11434 "
        b"with NVMe model storage at /mnt/nvme-models."
    )
    hr_content = (
        b"Probation period is 90 days. Engineers receive 15 days of annual leave "
        b"and must submit leave requests 14 days in advance."
    )

    res_eng = client.post(
        "/ingest",
        files={"file": (TEST_ENG_FILE, eng_content, "text/plain")},
        data={"department": "engineering"},
    )
    assert res_eng.status_code == 200
    assert res_eng.json()["chunks_indexed"] >= 1

    res_hr = client.post(
        "/ingest",
        files={"file": (TEST_HR_FILE, hr_content, "text/plain")},
        data={"department": "hr"},
    )
    assert res_hr.status_code == 200
    assert res_hr.json()["chunks_indexed"] >= 1

    # Verify both appear in /documents
    docs_res = client.get("/documents")
    assert docs_res.status_code == 200
    filenames = {d["filename"]: d["department"] for d in docs_res.json()}
    assert filenames.get(TEST_ENG_FILE) == "engineering"
    assert filenames.get(TEST_HR_FILE) == "hr"


def test_ingest_rejects_unsupported_extension(client: TestClient):
    res = client.post(
        "/ingest",
        files={"file": ("malware.exe", b"binary", "application/octet-stream")},
        data={"department": "general"},
    )
    assert res.status_code == 400


def test_chat_department_filtering(client: TestClient):
    # 1. Query engineering scope -> top source must come from engineering file, never HR
    res_eng = client.post(
        "/chat",
        json={
            "query": f"{TEST_QUERY_MARKER} Which VLAN and port does the GPU server use?",
            "department": "engineering",
        },
    )
    assert res_eng.status_code == 200
    sources_eng, answer_eng, done_eng = parse_sse_stream(res_eng.text)

    assert done_eng is True
    assert len(sources_eng) > 0
    assert all(s["filename"] != TEST_HR_FILE for s in sources_eng)
    assert any(s["filename"] == TEST_ENG_FILE for s in sources_eng)
    assert "10.99.0.0/24" in answer_eng or "11434" in answer_eng

    # 2. Query HR scope -> no engineering chunks should be retrieved
    res_hr = client.post(
        "/chat",
        json={
            "query": f"{TEST_QUERY_MARKER} How many days of annual leave do engineers get?",
            "department": "hr",
        },
    )
    assert res_hr.status_code == 200
    sources_hr, answer_hr, done_hr = parse_sse_stream(res_hr.text)

    assert done_hr is True
    assert all(s["filename"] != TEST_ENG_FILE for s in sources_hr)
    assert any(s["filename"] == TEST_HR_FILE for s in sources_hr)
    assert "15" in answer_hr


def test_analytics_records_telemetry(client: TestClient):
    res = client.get("/analytics")
    assert res.status_code == 200
    data = res.json()

    assert "summary" in data
    assert "recent_queries" in data
    assert data["summary"]["total_queries"] >= 2
    assert data["summary"]["avg_retrieval_ms"] > 0
    assert data["summary"]["p50_latency_ms"] > 0

    logged_queries = [
        q for q in data["recent_queries"] if q["query_text"].startswith(TEST_QUERY_MARKER)
    ]
    assert len(logged_queries) >= 2
    assert logged_queries[0]["ttft_ms"] is not None
    assert logged_queries[0]["top_similarity"] > 0