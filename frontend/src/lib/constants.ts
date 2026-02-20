export const MADHAB_OPTIONS = [
  { value: "all", label: "All Madhabs" },
  { value: "hanafi", label: "Hanafi" },
  { value: "shafii", label: "Shafi'i" },
  { value: "maliki", label: "Maliki" },
  { value: "hanbali", label: "Hanbali" },
  { value: "general", label: "General" },
] as const;

export const CATEGORY_OPTIONS = [
  { value: "all", label: "All Categories" },
  { value: "quran", label: "Quran" },
  { value: "hadith", label: "Hadith" },
  { value: "fiqh", label: "Fiqh" },
  { value: "aqeedah", label: "Aqeedah" },
  { value: "general", label: "General" },
] as const;

export const LANGUAGE_OPTIONS = [
  { value: "arabic", label: "Arabic" },
  { value: "english", label: "English" },
  { value: "both", label: "Both" },
] as const;

export const CHUNK_TYPE_OPTIONS = [
  { value: "paragraph", label: "Paragraph" },
  { value: "hadith", label: "Hadith" },
  { value: "ayah", label: "Ayah" },
] as const;

export const CHUNK_TYPE_COLORS: Record<string, string> = {
  ayah: "border-l-emerald-600",
  hadith: "border-l-amber-600",
  tafsir: "border-l-violet-600",
  paragraph: "border-l-slate-400",
};

export const CHUNK_TYPE_BADGE_VARIANTS: Record<string, string> = {
  ayah: "bg-emerald-50 text-emerald-800 border-emerald-200",
  hadith: "bg-amber-50 text-amber-800 border-amber-200",
  tafsir: "bg-violet-50 text-violet-800 border-violet-200",
  paragraph: "bg-slate-50 text-slate-700 border-slate-200",
};

export const STREAMING_MSG_ID = "__streaming__";
