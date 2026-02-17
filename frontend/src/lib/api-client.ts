import type {
  QueryRequest,
  QueryResponse,
  UploadResponse,
  SourceResponse,
  BookResponse,
  HealthResponse,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API error ${res.status}: ${body}`);
  }
  return res.json();
}

export async function postQuery(req: QueryRequest): Promise<QueryResponse> {
  return apiFetch<QueryResponse>("/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question: req.question,
      madhab: req.madhab === "all" ? null : req.madhab,
      category: req.category === "all" ? null : req.category,
      top_k: req.top_k ?? 5,
    }),
  });
}

export async function uploadFile(
  file: File,
  metadata: {
    title: string;
    author: string;
    language: string;
    madhab: string;
    category: string;
    chunk_type: string;
  }
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("title", metadata.title);
  formData.append("author", metadata.author);
  formData.append("language", metadata.language);
  formData.append("madhab", metadata.madhab);
  formData.append("category", metadata.category);
  formData.append("chunk_type", metadata.chunk_type);

  return apiFetch<UploadResponse>("/admin/upload", {
    method: "POST",
    body: formData,
  });
}

export async function fetchSources(): Promise<SourceResponse[]> {
  return apiFetch<SourceResponse[]>("/admin/sources");
}

export async function fetchBooks(): Promise<BookResponse[]> {
  return apiFetch<BookResponse[]>("/admin/books");
}

export async function checkHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/health");
}
