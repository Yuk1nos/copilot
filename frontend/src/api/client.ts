import type { DocumentInfo } from "../types";

const BASE = "http://localhost:8000/api";

export async function fetchDocuments(): Promise<DocumentInfo[]> {
  const res = await fetch(`${BASE}/documents`);
  return res.json();
}

export function uploadDocument(file: File): EventSource {
  const formData = new FormData();
  formData.append("file", file);
  // For SSE with POST we need to use fetch + ReadableStream, but for
  // upload (which uses FormData), we fall back to URL-encoded EventSource approach
  // In the actual pages we'll use fetch-based SSE pattern
  return new EventSource(`${BASE}/upload`);
}

export function askQuestion(question: string): EventSource {
  const url = `${BASE}/ask?question=${encodeURIComponent(question)}`;
  return new EventSource(url);
}

export function generateSummary(documentIds?: string[]): EventSource {
  const ids = documentIds?.join(",") || "";
  return new EventSource(`${BASE}/summary?document_ids=${ids}`);
}
