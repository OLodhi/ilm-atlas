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
  StreamCallbacks,
  SSEUserMessageEvent,
  SSEContentDeltaEvent,
  SSECitationsEvent,
  SSETitleEvent,
  SSEDoneEvent,
  SSEErrorEvent,
} from "./types";
import { ApiError } from "./api-errors";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// --- Access token state (in-memory, never persisted) ---

let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

// --- Auth types ---

export interface RegisterData {
  email: string;
  password: string;
  display_name?: string;
}

export interface LoginData {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface UserProfile {
  id: string;
  email: string;
  email_verified: boolean;
  display_name: string | null;
  role: string;
  daily_query_limit: number;
  created_at: string;
}

export interface UsageInfo {
  used: number;
  limit: number;
  date: string;
}

// --- Fetch helpers ---

async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      ...options?.headers,
    },
  });
  if (!res.ok) {
    let detail: string;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body);
    } catch {
      detail = `Request failed (${res.status})`;
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json();
}

// --- Refresh serialization (only one refresh in-flight at a time) ---

let isRefreshing = false;
let refreshPromise: Promise<void> | null = null;

async function ensureValidToken(): Promise<void> {
  if (isRefreshing && refreshPromise) {
    return refreshPromise;
  }
  isRefreshing = true;
  refreshPromise = refreshToken()
    .then(() => {})
    .finally(() => {
      isRefreshing = false;
      refreshPromise = null;
    });
  return refreshPromise;
}

async function authFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const buildHeaders = () => {
    const headers: Record<string, string> = {
      ...((options.headers as Record<string, string>) || {}),
    };
    if (accessToken) {
      headers["Authorization"] = `Bearer ${accessToken}`;
    }
    return headers;
  };

  try {
    return await apiFetch<T>(path, {
      ...options,
      headers: buildHeaders(),
      credentials: "include",
    });
  } catch (err) {
    // Intercept 401 errors — try refreshing the token and retry once
    if (err instanceof ApiError && err.status === 401) {
      try {
        await ensureValidToken();
        return await apiFetch<T>(path, {
          ...options,
          headers: buildHeaders(),
          credentials: "include",
        });
      } catch {
        // Refresh failed — user must re-login
        accessToken = null;
        throw err;
      }
    }
    throw err;
  }
}

// --- Auth API functions ---

export async function register(data: RegisterData): Promise<UserProfile> {
  return apiFetch<UserProfile>("/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function login(data: LoginData): Promise<TokenResponse> {
  const response = await apiFetch<TokenResponse>("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
    credentials: "include",
  });
  setAccessToken(response.access_token);
  return response;
}

export async function refreshToken(): Promise<TokenResponse> {
  const response = await apiFetch<TokenResponse>("/auth/refresh", {
    method: "POST",
    credentials: "include",
  });
  setAccessToken(response.access_token);
  return response;
}

export async function logout(): Promise<void> {
  await authFetch("/auth/logout", { method: "POST" });
  setAccessToken(null);
}

export async function getMe(): Promise<UserProfile> {
  return authFetch<UserProfile>("/auth/me");
}

export async function updateMe(data: {
  display_name?: string;
  current_password?: string;
  new_password?: string;
}): Promise<UserProfile> {
  return authFetch<UserProfile>("/auth/me", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function getUsage(): Promise<UsageInfo> {
  return authFetch<UsageInfo>("/auth/usage");
}

export async function verifyEmail(
  token: string
): Promise<{ message: string }> {
  return apiFetch("/auth/verify-email", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
}

export async function forgotPassword(
  email: string
): Promise<{ message: string }> {
  return apiFetch("/auth/forgot-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
}

export async function resetPassword(
  token: string,
  new_password: string
): Promise<{ message: string }> {
  return apiFetch("/auth/reset-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, new_password }),
  });
}

export async function resendVerification(): Promise<{ message: string }> {
  return authFetch<{ message: string }>("/auth/resend-verification", {
    method: "POST",
  });
}

export async function deleteAccount(): Promise<void> {
  await authFetch("/auth/me", { method: "DELETE" });
  setAccessToken(null);
}

// --- Query ---

export async function postQuery(req: QueryRequest): Promise<QueryResponse> {
  return authFetch<QueryResponse>("/query", {
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

  return authFetch<UploadResponse>("/admin/upload", {
    method: "POST",
    body: formData,
  });
}

export async function fetchSources(): Promise<SourceResponse[]> {
  return authFetch<SourceResponse[]>("/admin/sources");
}

export async function fetchBooks(): Promise<BookResponse[]> {
  return authFetch<BookResponse[]>("/admin/books");
}

export async function checkHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/health");
}

// --- Chat ---

export async function createChatSession(): Promise<ChatSession> {
  return authFetch<ChatSession>("/chat/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
}

export async function listChatSessions(): Promise<ChatSessionListResponse> {
  return authFetch<ChatSessionListResponse>("/chat/sessions");
}

export async function getChatSession(
  sessionId: string
): Promise<ChatSessionDetail> {
  return authFetch<ChatSessionDetail>(`/chat/sessions/${sessionId}`);
}

export async function deleteChatSession(sessionId: string): Promise<void> {
  await authFetch<void>(`/chat/sessions/${sessionId}`, {
    method: "DELETE",
  });
}

export async function renameChatSession(
  sessionId: string,
  title: string
): Promise<ChatSession> {
  return authFetch<ChatSession>(`/chat/sessions/${sessionId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
}

export async function sendChatMessage(
  sessionId: string,
  req: ChatSendRequest
): Promise<ChatSendResponse> {
  return authFetch<ChatSendResponse>(
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

export async function streamChatMessage(
  sessionId: string,
  req: ChatSendRequest,
  callbacks: StreamCallbacks,
  signal?: AbortSignal
): Promise<void> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  const res = await fetch(
    `${API_URL}/chat/sessions/${sessionId}/messages/stream`,
    {
      method: "POST",
      headers,
      credentials: "include",
      body: JSON.stringify({
        message: req.message,
        madhab: req.madhab === "all" ? null : req.madhab,
        category: req.category === "all" ? null : req.category,
      }),
      signal,
    }
  );

  if (!res.ok) {
    let detail: string;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body);
    } catch {
      detail = `Request failed (${res.status})`;
    }
    throw new ApiError(res.status, detail);
  }

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // Split on double-newline (SSE event boundary)
    const parts = buffer.split("\n\n");
    // Last part may be incomplete — keep it in the buffer
    buffer = parts.pop()!;

    for (const part of parts) {
      if (!part.trim()) continue;

      let eventType = "";
      let dataStr = "";

      for (const line of part.split("\n")) {
        if (line.startsWith("event: ")) {
          eventType = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          dataStr = line.slice(6);
        }
      }

      if (!eventType || !dataStr) continue;

      const data = JSON.parse(dataStr);

      switch (eventType) {
        case "user_message":
          callbacks.onUserMessage(data as SSEUserMessageEvent);
          break;
        case "content_delta":
          callbacks.onContentDelta(data as SSEContentDeltaEvent);
          break;
        case "citations":
          callbacks.onCitations(data as SSECitationsEvent);
          break;
        case "title":
          callbacks.onTitle(data as SSETitleEvent);
          break;
        case "done":
          callbacks.onDone(data as SSEDoneEvent);
          break;
        case "error":
          callbacks.onError(data as SSEErrorEvent);
          break;
      }
    }
  }
}
