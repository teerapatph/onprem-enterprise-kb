"use client";

import { useState, useRef } from "react";
import { uploadDocument } from "@/lib/api";
import { Department, DocumentItem } from "@/types/kb";

interface DocumentSidebarProps {
  documents: DocumentItem[];
  isLoadingDocs: boolean;
  onDocumentIndexed: () => Promise<void>;
}

const DEPARTMENTS: { value: Department; label: string }[] = [
  { value: "engineering", label: "Engineering" },
  { value: "operations", label: "Operations" },
  { value: "hr", label: "HR" },
  { value: "general", label: "General" },
];

export default function DocumentSidebar({
  documents,
  isLoadingDocs,
  onDocumentIndexed,
}: DocumentSidebarProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [department, setDepartment] = useState<Department>("engineering");
  const [isUploading, setIsUploading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile || isUploading) return;

    setIsUploading(true);
    setErrorMsg(null);
    setStatusMsg(null);

    try {
      const result = await uploadDocument(selectedFile, department);
      setStatusMsg(
        `Indexed "${result.filename}" (${result.chunks_indexed} chunks)`
      );
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      await onDocumentIndexed();
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <aside className="w-80 shrink-0 border-r border-slate-800 bg-slate-900 p-5 flex flex-col">
      <div className="mb-5">
        <h1 className="text-lg font-semibold text-emerald-400">
          On-Premise KB
        </h1>
        <p className="text-xs text-slate-400">
          Local Ollama + pgvector RAG Stack
        </p>
      </div>

      {/* Upload Form */}
      <form
        onSubmit={handleSubmit}
        className="space-y-3 rounded-lg border border-slate-800 bg-slate-950/60 p-3.5"
      >
        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1.5">
            Upload Document (.pdf, .md, .txt)
          </label>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.md,.txt"
            disabled={isUploading}
            onChange={(e) => {
              setSelectedFile(e.target.files?.[0] ?? null);
              setErrorMsg(null);
              setStatusMsg(null);
            }}
            className="block w-full text-xs text-slate-400 file:mr-3 file:rounded file:border-0 file:bg-slate-800 file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-slate-200 hover:file:bg-slate-700 disabled:opacity-50"
          />
        </div>

        <div>
          <label className="block text-xs text-slate-400 mb-1">
            Department Tag
          </label>
          <select
            value={department}
            disabled={isUploading}
            onChange={(e) => setDepartment(e.target.value as Department)}
            className="w-full rounded border border-slate-700 bg-slate-800 px-2.5 py-1.5 text-xs text-slate-100 focus:border-emerald-500 focus:outline-none"
          >
            {DEPARTMENTS.map((dept) => (
              <option key={dept.value} value={dept.value}>
                {dept.label}
              </option>
            ))}
          </select>
        </div>

        <button
          type="submit"
          disabled={!selectedFile || isUploading}
          className="w-full rounded bg-emerald-600 py-1.5 text-xs font-medium text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {isUploading ? "Embedding Chunks..." : "Upload & Index"}
        </button>

        {errorMsg && (
          <p className="rounded border border-red-900/60 bg-red-950/50 px-2.5 py-1.5 text-[11px] text-red-300">
            {errorMsg}
          </p>
        )}

        {statusMsg && (
          <p className="rounded border border-emerald-900/60 bg-emerald-950/50 px-2.5 py-1.5 text-[11px] text-emerald-300">
            {statusMsg}
          </p>
        )}
      </form>

      {/* Indexed Files List */}
      <div className="mt-6 flex-1 overflow-y-auto pr-1">
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
          Indexed Files ({documents.length})
        </h2>

        {isLoadingDocs ? (
          <p className="text-xs text-slate-500">Loading documents...</p>
        ) : documents.length === 0 ? (
          <p className="text-xs text-slate-500">
            No documents indexed yet. Upload a file to begin.
          </p>
        ) : (
          <ul className="space-y-2">
            {documents.map((doc, idx) => (
              <li
                key={`${doc.filename}-${doc.department}-${idx}`}
                className="rounded border border-slate-800 bg-slate-950/40 p-2.5 text-xs"
              >
                <div
                  className="truncate font-medium text-slate-200"
                  title={doc.filename}
                >
                  {doc.filename}
                </div>
                <div className="mt-1.5 flex items-center justify-between text-[11px] text-slate-400">
                  <span className="rounded bg-slate-800 px-1.5 py-0.5 capitalize text-emerald-300">
                    {doc.department}
                  </span>
                  <span>{doc.chunks} chunks</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}