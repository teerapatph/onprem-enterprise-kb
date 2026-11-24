import {
    Department,
    DepartmentFilter,
    DocumentItem,
    IngestResponse,
    SourceChunk,
    StreamEvent,
} from "@/types/kb";

const API_BASE_URL =
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function fetchDocuments(): Promise<DocumentItem[]> {
    const response = await fetch(`${API_BASE_URL}/documents`, {
        cache: "no-store",
    });

    if (!response.ok) {
        throw new Error(`Failed to load documents (${response.status})`);
    }

    return response.json();
}

export async function uploadDocument(
    file: File,
    department: Department
): Promise<IngestResponse> {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("department", department);

    const response = await fetch(`${API_BASE_URL}/ingest`, {
        method: "POST",
        body: formData,
    });

    if (!response.ok) {
        let detail = "Document ingestion failed";
        try {
            const errorData = await response.json();
            if (errorData?.detail) detail = errorData.detail;
        } catch {
            // Fallback to default message if response is not JSON
        }
        throw new Error(detail);
    }

    return response.json();
}

export interface StreamChatCallbacks {
    onSources: (sources: SourceChunk[]) => void;
    onToken: (token: string) => void;
    onDone?: () => void;
}

export async function streamChatResponse(
    query: string,
    department: DepartmentFilter,
    callbacks: StreamChatCallbacks
): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, department }),
    });

    if (!response.ok || !response.body) {
        throw new Error(`Chat request failed (${response.status})`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() ?? "";

        for (const rawEvent of events) {
            if (!rawEvent.startsWith("data: ")) continue;
            const parsed: StreamEvent = JSON.parse(rawEvent.slice(6));

            if (parsed.type === "sources") {
                callbacks.onSources(parsed.sources);
            } else if (parsed.type === "token") {
                callbacks.onToken(parsed.content);
            } else if (parsed.type === "done") {
                callbacks.onDone?.();
            }
        }
    }
}