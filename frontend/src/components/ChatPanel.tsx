"use client";

import { useState, useRef, useEffect } from "react";
import { streamChatResponse } from "@/lib/api";
import { ChatMessage, DepartmentFilter, SourceChunk } from "@/types/kb";

const FILTER_OPTIONS: { value: DepartmentFilter; label: string }[] = [
  { value: "all", label: "All Departments" },
  { value: "engineering", label: "Engineering Only" },
  { value: "operations", label: "Operations Only" },
  { value: "hr", label: "HR Only" },
  { value: "general", label: "General Only" },
];

function SourceCard({ source }: { source: SourceChunk }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <button
      type="button"
      onClick={() => setExpanded((prev) => !prev)}
      className="text-left rounded border border-slate-800 bg-slate-900/70 p-2.5 text-xs text-slate-400 transition hover:border-slate-700"
    >
      <div className="flex items-center justify-between font-medium text-slate-300">
        <span className="truncate">
          {source.filename} (Chunk #{source.chunk_index})
        </span>
        <span className="ml-2 shrink-0 text-emerald-400">
          {(source.similarity * 100).toFixed(1)}%
        </span>
      </div>
      <p
        className={`mt-1 text-[11px] text-slate-400 whitespace-pre-wrap ${
          expanded ? "" : "line-clamp-2"
        }`}
      >
        {source.content}
      </p>
      <span className="mt-1 inline-block text-[10px] text-slate-500">
        {expanded ? "Click to collapse" : "Click to read full chunk"}
      </span>
    </button>
  );
}

export default function ChatPanel() {
  const [filterDept, setFilterDept] = useState<DepartmentFilter>("all");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);

  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isStreaming) return;

    const userMsgId = crypto.randomUUID();
    const assistantMsgId = crypto.randomUUID();

    setInput("");
    setIsStreaming(true);

    setMessages((prev) => [
      ...prev,
      { id: userMsgId, role: "user", content: trimmed },
      { id: assistantMsgId, role: "assistant", content: "", sources: [] },
    ]);

    try {
      await streamChatResponse(trimmed, filterDept, {
        onSources: (sources) => {
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantMsgId ? { ...m, sources } : m))
          );
        },
        onToken: (token) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId
                ? { ...m, content: m.content + token }
                : m
            )
          );
        },
      });
    } catch (err) {
      const errorText =
        err instanceof Error
          ? err.message
          : "Unable to reach the local RAG server.";
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsgId ? { ...m, content: `Error: ${errorText}` } : m
        )
      );
    } finally {
      setIsStreaming(false);
    }
  };

  return (
    <main className="flex flex-1 flex-col bg-slate-950">
      {/* Header & Department Scope Selector */}
      <header className="flex items-center justify-between border-b border-slate-800 bg-slate-900/50 px-6 py-3">
        <span className="text-sm font-medium text-slate-200">
          Internal Knowledge Assistant
        </span>
        <div className="flex items-center gap-2 text-xs">
          <label htmlFor="scope-select" className="text-slate-400">
            Search Scope:
          </label>
          <select
            id="scope-select"
            value={filterDept}
            onChange={(e) => setFilterDept(e.target.value as DepartmentFilter)}
            className="rounded border border-slate-700 bg-slate-800 px-2.5 py-1 text-slate-100 focus:border-emerald-500 focus:outline-none"
          >
            {FILTER_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </header>

      {/* Scrollable Chat Feed */}
      <div className="flex-1 space-y-6 overflow-y-auto p-6">
        {messages.length === 0 && (
          <div className="flex h-full items-center justify-center text-center text-sm text-slate-500">
            Upload an internal SOP, spec, or technical note on the left, then
            ask a question below.
          </div>
        )}

        {messages.map((msg, index) => {
          const isLastAssistant =
            msg.role === "assistant" && index === messages.length - 1;

          return (
            <div
              key={msg.id}
              className={`max-w-3xl ${
                msg.role === "user" ? "ml-auto" : "mr-auto"
              }`}
            >
              <div
                className={`rounded-lg px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
                  msg.role === "user"
                    ? "bg-emerald-600 text-white"
                    : "border border-slate-800 bg-slate-900 text-slate-200"
                }`}
              >
                {msg.content ||
                  (isStreaming && isLastAssistant ? "Thinking..." : "")}
              </div>

              {msg.role === "assistant" &&
                msg.sources &&
                msg.sources.length > 0 && (
                  <div className="mt-2.5 grid grid-cols-1 gap-2 sm:grid-cols-2">
                    {msg.sources.map((src, sIdx) => (
                      <SourceCard
                        key={`${msg.id}-src-${sIdx}`}
                        source={src}
                      />
                    ))}
                  </div>
                )}
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>

      {/* Prompt Input Bar */}
      <form
        onSubmit={handleSend}
        className="border-t border-slate-800 bg-slate-900/40 p-4"
      >
        <div className="mx-auto flex max-w-3xl gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question about your indexed documents..."
            className="flex-1 rounded-lg border border-slate-700 bg-slate-900 px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:border-emerald-500 focus:outline-none"
          />
          <button
            type="submit"
            disabled={!input.trim() || isStreaming}
            className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {isStreaming ? "Streaming..." : "Send"}
          </button>
        </div>
      </form>
    </main>
  );
}