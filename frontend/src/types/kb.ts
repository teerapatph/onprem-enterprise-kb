export type Department = "general" | "engineering" | "operations" | "hr";

export type DepartmentFilter = "all" | Department;

export interface DocumentItem {
    filename: string;
    department: Department;
    chunks: number;
    uploaded_at: string | null;
}

export interface IngestResponse {
    filename: string;
    department: Department;
    chunks_indexed: number;
}

export interface SourceChunk {
    filename: string;
    chunk_index: number;
    content: string;
    similarity: number;
}

export interface ChatMessage {
    id: string;
    role: "user" | "assistant";
    content: string;
    sources?: SourceChunk[];
}

export type StreamEvent =
    | { type: "sources"; sources: SourceChunk[] }
    | { type: "token"; content: string }
    | { type: "done" };