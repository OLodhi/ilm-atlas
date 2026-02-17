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
  chunk_type: "ayah" | "hadith" | "paragraph";
  metadata: Record<string, unknown> | null;
}

export interface QueryResponse {
  answer: string;
  citations: Citation[];
}

export interface HealthResponse {
  status: string;
  version: string;
}

export type Madhab = "hanafi" | "shafii" | "maliki" | "hanbali" | "general";
export type Category = "quran" | "hadith" | "fiqh" | "aqeedah" | "general";
