// Mirrors backend Pydantic schemas

export interface BookCreate {
  title: string;
  author?: string;
  language?: "arabic" | "english" | "both";
  madhab?: Madhab;
  category?: Category;
}

export interface BookResponse {
  id: string;
  title: string;
  author: string;
  language: string;
  madhab: string;
  category: string;
  created_at: string;
}

export interface SourceResponse {
  id: string;
  book_id: string;
  filename: string;
  file_type: string;
  status: "pending" | "processing" | "completed" | "failed";
  error_message: string | null;
  created_at: string;
}

export interface UploadResponse {
  source_id: string;
  book_id: string;
  status: string;
  message: string;
}

export interface QueryRequest {
  question: string;
  madhab?: string | null;
  category?: string | null;
  top_k?: number;
}

export interface Citation {
  text_arabic: string | null;
  text_english: string | null;
  source: string;
  chunk_type: "ayah" | "hadith" | "tafsir" | "paragraph";
  metadata: Record<string, unknown> | null;
  auto_translated?: boolean;
}

export interface QueryResponse {
  answer: string;
  citations: Citation[];
}

export interface HealthResponse {
  status: string;
  version: string;
}

// --- Chat ---

export interface ChatSession {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[] | null;
  created_at: string;
}

export interface ChatSessionDetail extends ChatSession {
  messages: ChatMessage[];
}

export interface ChatSendRequest {
  message: string;
  madhab?: string | null;
  category?: string | null;
}

export interface ChatSendResponse {
  message: ChatMessage;
  user_message: ChatMessage;
  session_id: string;
  session_title: string | null;
}

export interface ChatSessionListResponse {
  sessions: ChatSession[];
}

export type Madhab = "hanafi" | "shafii" | "maliki" | "hanbali" | "general";
export type Category = "quran" | "hadith" | "fiqh" | "aqeedah" | "general";

// --- SSE Streaming ---

export interface SSEUserMessageEvent {
  id: string;
  role: "user";
  content: string;
  citations: null;
  created_at: string;
}

export interface SSEContentDeltaEvent {
  token: string;
}

export interface SSECitationsEvent {
  citations: Citation[];
}

export interface SSETitleEvent {
  title: string;
}

export interface SSEDoneEvent {
  message_id: string;
  created_at: string;
}

export interface SSEErrorEvent {
  detail: string;
}

export type SSEEventType =
  | "user_message"
  | "content_delta"
  | "citations"
  | "title"
  | "done"
  | "error";

export interface StreamCallbacks {
  onUserMessage: (data: SSEUserMessageEvent) => void;
  onContentDelta: (data: SSEContentDeltaEvent) => void;
  onCitations: (data: SSECitationsEvent) => void;
  onTitle: (data: SSETitleEvent) => void;
  onDone: (data: SSEDoneEvent) => void;
  onError: (data: SSEErrorEvent) => void;
}

// --- Reader ---

export interface SurahSummary {
  number: number;
  name_arabic: string;
  name_english: string;
  ayah_count: number;
  revelation_type: string;
}

export interface AyahResponse {
  number: number;
  text_arabic: string | null;
  text_english: string | null;
  juz: number | null;
  ruku: number | null;
}

export interface SurahDetailResponse {
  surah: SurahSummary;
  ayahs: AyahResponse[];
}

export interface CollectionSummary {
  slug: string;
  name: string;
  author: string;
  hadith_count: number;
  book_count: number;
}

export interface HadithBookSummary {
  number: number;
  name_arabic: string | null;
  name_english: string | null;
  hadith_count: number;
}

export interface HadithResponseType {
  number: number;
  text_arabic: string | null;
  text_english: string | null;
  chapter: string | null;
}

export interface HadithBookDetailResponse {
  book: HadithBookSummary;
  collection_name: string;
  collection_slug: string;
  hadiths: HadithResponseType[];
}

export interface TafsirSummary {
  slug: string;
  name: string;
  author: string;
  language: string;
  surah_count: number;
}

export interface TafsirEntryResponse {
  ayah_number: number;
  text_arabic: string | null;
  text_english: string | null;
}

export interface TafsirSurahDetailResponse {
  tafsir: TafsirSummary;
  surah_number: number;
  surah_name: string;
  entries: TafsirEntryResponse[];
}

export interface TafsirForAyah {
  tafsir_name: string;
  tafsir_slug: string;
  language: string;
  text: string | null;
}

export interface LibraryStats {
  quran_surah_count: number;
  quran_ayah_count: number;
  hadith_collection_count: number;
  hadith_count: number;
  tafsir_count: number;
  tafsir_entry_count: number;
}
