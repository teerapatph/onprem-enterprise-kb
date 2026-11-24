"use client";

import { useState, useEffect, useCallback } from "react";
import DocumentSidebar from "@/components/DocumentSidebar";
import ChatPanel from "@/components/ChatPanel";
import { fetchDocuments } from "@/lib/api";
import { DocumentItem } from "@/types/kb";

export default function HomePage() {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [isLoadingDocs, setIsLoadingDocs] = useState(true);

  const loadDocuments = useCallback(async () => {
    try {
      const docs = await fetchDocuments();
      setDocuments(docs);
    } catch (err) {
      console.error("Failed to fetch indexed documents:", err);
    } finally {
      setIsLoadingDocs(false);
    }
  }, []);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  return (
    <div className="flex h-screen overflow-hidden bg-slate-950 text-slate-100">
      <DocumentSidebar
        documents={documents}
        isLoadingDocs={isLoadingDocs}
        onDocumentIndexed={loadDocuments}
      />
      <ChatPanel />
    </div>
  );
}