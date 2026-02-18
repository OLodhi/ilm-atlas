import type {
  QueryRequest,
  QueryResponse,
  UploadResponse,
  SourceResponse,
  BookResponse,
  HealthResponse,
  ChatSession,
  ChatSessionDetail,
  ChatSessionListResponse,
  ChatSendRequest,
  ChatSendResponse,
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
  if (res.status === 204) {
    return undefined as T;
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

// --- Chat ---

export async function createChatSession(): Promise<ChatSession> {
  return apiFetch<ChatSession>("/chat/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
}

export async function listChatSessions(): Promise<ChatSessionListResponse> {
  return apiFetch<ChatSessionListResponse>("/chat/sessions");
}

export async function getChatSession(
  sessionId: string
): Promise<ChatSessionDetail> {
  return apiFetch<ChatSessionDetail>(`/chat/sessions/${sessionId}`);
}

export async function deleteChatSession(sessionId: string): Promise<void> {
  await apiFetch<void>(`/chat/sessions/${sessionId}`, {
    method: "DELETE",
  });
}

export async function renameChatSession(
  sessionId: string,
  title: string
): Promise<ChatSession> {
  return apiFetch<ChatSession>(`/chat/sessions/${sessionId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
}

export async function sendChatMessage(
  sessionId: string,
  req: ChatSendRequest
): Promise<ChatSendResponse> {
  return apiFetch<ChatSendResponse>(
    `/chat/sessions/${sessionId}/messages`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: req.message,
        madhab: req.madhab === "all" ? null : req.madhab,
        category: req.category === "all" ? null : req.category,
      }),
    }
  );
}
