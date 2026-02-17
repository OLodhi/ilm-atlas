"""Classify user queries to determine search strategy.

Detects metadata lookups (surah/ayah/juz references), counting/listing
queries that need exhaustive keyword search, and semantic queries that
work fine with top-k vector search.
"""

import re
from dataclasses import dataclass, field


@dataclass
class MetadataFilter:
    surah_number: int | None = None
    ayah_number: int | None = None
    juz: int | None = None


@dataclass
class QueryIntent:
    query_type: str  # "counting" | "listing" | "semantic" | "metadata"
    keywords: list[str] = field(default_factory=list)
    max_results: int = 10
    metadata_filter: MetadataFilter | None = None
    structural_context: str | None = None


# Canonical name -> all known variants (English, transliteration, Arabic)
NAMED_ENTITIES: dict[str, list[str]] = {
    # Prophets
    "jesus": ["jesus", "isa", "عيسى", "'isa", "eesa"],
    "moses": ["moses", "musa", "موسى", "moosa"],
    "abraham": ["abraham", "ibrahim", "إبراهيم", "ibraheem"],
    "noah": ["noah", "nuh", "نوح", "nooh"],
    "muhammad": ["muhammad", "mohammad", "محمد", "ahmed", "أحمد"],
    "david": ["david", "dawud", "داود", "dawood"],
    "solomon": ["solomon", "sulaiman", "سليمان", "sulayman"],
    "joseph": ["joseph", "yusuf", "يوسف", "yousuf"],
    "jacob": ["jacob", "yaqub", "يعقوب", "yaqoob"],
    "isaac": ["isaac", "ishaq", "إسحاق", "ishaaq"],
    "ishmael": ["ishmael", "ismail", "إسماعيل", "ismael"],
    "adam": ["adam", "آدم"],
    "lot": ["lot", "lut", "لوط"],
    "jonah": ["jonah", "yunus", "يونس"],
    "job": ["job", "ayyub", "أيوب", "ayub"],
    "aaron": ["aaron", "harun", "هارون", "haroon"],
    "john": ["john", "yahya", "يحيى"],
    "zechariah": ["zechariah", "zakariya", "زكريا", "zakariyya"],
    "elijah": ["elijah", "ilyas", "إلياس"],
    "elisha": ["elisha", "alyasa", "اليسع"],
    "hud": ["hud", "هود"],
    "salih": ["salih", "صالح", "saleh"],
    "shuaib": ["shuaib", "شعيب", "shoaib"],
    "idris": ["idris", "إدريس"],
    "dhulkifl": ["dhulkifl", "ذو الكفل", "zulkifl"],
    "luqman": ["luqman", "لقمان"],
    "mary": ["mary", "maryam", "مريم"],
    # Key figures
    "pharaoh": ["pharaoh", "firaun", "فرعون", "firawn"],
    "iblis": ["iblis", "إبليس", "satan", "shaytan", "شيطان"],
    # Concepts
    "prayer": ["prayer", "salah", "صلاة", "salat", "namaz"],
    "paradise": ["paradise", "jannah", "جنة", "heaven", "garden", "gardens"],
    "hellfire": ["hellfire", "jahannam", "جهنم", "hell", "fire", "naar", "نار"],
    "fasting": ["fasting", "sawm", "صوم", "siyam", "صيام"],
    "charity": ["charity", "zakat", "زكاة", "sadaqah", "صدقة"],
    "pilgrimage": ["pilgrimage", "hajj", "حج"],
    "patience": ["patience", "sabr", "صبر"],
    "repentance": ["repentance", "tawbah", "توبة", "tawba"],
    "mercy": ["mercy", "rahmah", "رحمة", "rahman", "رحمن"],
    "justice": ["justice", "adl", "عدل"],
    "knowledge": ["knowledge", "ilm", "علم"],
    "jihad": ["jihad", "جهاد", "striving"],
    "angels": ["angels", "malaikah", "ملائكة", "angel", "malak"],
    "resurrection": ["resurrection", "qiyamah", "قيامة", "day of judgment"],
}

_COUNTING_PATTERNS = [
    r"\bhow many\b",
    r"\bhow often\b",
    r"\bcount\b",
    r"\bnumber of times\b",
    r"\bnumber of\b",
    r"\bhow frequently\b",
    r"\btotal\s+(?:number|count|times|mentions|occurrences)\b",
]

_LISTING_PATTERNS = [
    r"\blist all\b",
    r"\ball mentions\b",
    r"\bevery verse\b",
    r"\bevery ayah\b",
    r"\bwhich verses\b",
    r"\bwhich ayah\b",
    r"\bwhich surahs?\b",
    r"\ball (?:the )?verses\b",
    r"\ball (?:the )?ayahs?\b",
    r"\bshow (?:me )?all\b",
    r"\beach (?:verse|ayah|mention)\b",
]


# Surah name variants -> surah number (all 114 surahs)
# Keys are lowercase for case-insensitive matching
SURAH_NAMES: dict[str, int] = {
    # 1. Al-Fatiha
    "fatiha": 1, "al-fatiha": 1, "al fatiha": 1, "الفاتحة": 1,
    # 2. Al-Baqara
    "baqara": 2, "baqarah": 2, "al-baqara": 2, "al-baqarah": 2, "al baqara": 2, "البقرة": 2,
    # 3. Aal-E-Imran
    "imran": 3, "aal-e-imran": 3, "al-imran": 3, "ali imran": 3, "آل عمران": 3,
    # 4. An-Nisa
    "nisa": 4, "an-nisa": 4, "al-nisa": 4, "النساء": 4,
    # 5. Al-Ma'ida
    "maida": 5, "maidah": 5, "al-maida": 5, "al-maidah": 5, "المائدة": 5,
    # 6. Al-An'am
    "anam": 6, "al-anam": 6, "الأنعام": 6,
    # 7. Al-A'raf
    "araf": 7, "al-araf": 7, "الأعراف": 7,
    # 8. Al-Anfal
    "anfal": 8, "al-anfal": 8, "الأنفال": 8,
    # 9. At-Tawba
    "tawba": 9, "tawbah": 9, "at-tawba": 9, "at-tawbah": 9, "التوبة": 9,
    # 10. Yunus
    "yunus": 10, "يونس": 10,
    # 11. Hud
    "هود": 11,
    # 12. Yusuf
    "yusuf": 12, "يوسف": 12,
    # 13. Ar-Ra'd
    "rad": 13, "ar-rad": 13, "الرعد": 13,
    # 14. Ibrahim
    "ibrahim": 14, "إبراهيم": 14,
    # 15. Al-Hijr
    "hijr": 15, "al-hijr": 15, "الحجر": 15,
    # 16. An-Nahl
    "nahl": 16, "an-nahl": 16, "النحل": 16,
    # 17. Al-Isra
    "isra": 17, "al-isra": 17, "الإسراء": 17, "bani israel": 17,
    # 18. Al-Kahf
    "kahf": 18, "al-kahf": 18, "الكهف": 18,
    # 19. Maryam
    "maryam": 19, "مريم": 19,
    # 20. Ta-Ha
    "taha": 20, "ta-ha": 20, "طه": 20,
    # 21. Al-Anbiya
    "anbiya": 21, "al-anbiya": 21, "الأنبياء": 21,
    # 22. Al-Hajj
    "hajj": 22, "al-hajj": 22, "الحج": 22,
    # 23. Al-Mu'minun
    "muminun": 23, "al-muminun": 23, "المؤمنون": 23, "muminoon": 23,
    # 24. An-Nur
    "nur": 24, "an-nur": 24, "noor": 24, "النور": 24,
    # 25. Al-Furqan
    "furqan": 25, "al-furqan": 25, "الفرقان": 25,
    # 26. Ash-Shu'ara
    "shuara": 26, "ash-shuara": 26, "الشعراء": 26,
    # 27. An-Naml
    "naml": 27, "an-naml": 27, "النمل": 27,
    # 28. Al-Qasas
    "qasas": 28, "al-qasas": 28, "القصص": 28,
    # 29. Al-Ankabut
    "ankabut": 29, "al-ankabut": 29, "العنكبوت": 29,
    # 30. Ar-Rum
    "rum": 30, "ar-rum": 30, "الروم": 30,
    # 31. Luqman
    "luqman": 31, "لقمان": 31,
    # 32. As-Sajda
    "sajda": 32, "as-sajda": 32, "sajdah": 32, "السجدة": 32,
    # 33. Al-Ahzab
    "ahzab": 33, "al-ahzab": 33, "الأحزاب": 33,
    # 34. Saba
    "saba": 34, "سبأ": 34,
    # 35. Fatir
    "fatir": 35, "فاطر": 35,
    # 36. Ya-Sin
    "yasin": 36, "ya-sin": 36, "يس": 36, "yaseen": 36,
    # 37. As-Saffat
    "saffat": 37, "as-saffat": 37, "الصافات": 37,
    # 38. Sad
    "ص": 38,
    # 39. Az-Zumar
    "zumar": 39, "az-zumar": 39, "الزمر": 39,
    # 40. Ghafir
    "ghafir": 40, "غافر": 40, "al-mumin": 40,
    # 41. Fussilat
    "fussilat": 41, "فصلت": 41, "ha-mim sajdah": 41,
    # 42. Ash-Shura
    "shura": 42, "ash-shura": 42, "الشورى": 42,
    # 43. Az-Zukhruf
    "zukhruf": 43, "az-zukhruf": 43, "الزخرف": 43,
    # 44. Ad-Dukhan
    "dukhan": 44, "ad-dukhan": 44, "الدخان": 44,
    # 45. Al-Jathiya
    "jathiya": 45, "al-jathiya": 45, "الجاثية": 45, "jathiyah": 45,
    # 46. Al-Ahqaf
    "ahqaf": 46, "al-ahqaf": 46, "الأحقاف": 46,
    # 47. Muhammad
    "محمد": 47,
    # 48. Al-Fath
    "fath": 48, "al-fath": 48, "الفتح": 48,
    # 49. Al-Hujurat
    "hujurat": 49, "al-hujurat": 49, "الحجرات": 49,
    # 50. Qaf
    "qaf": 50, "ق": 50,
    # 51. Adh-Dhariyat
    "dhariyat": 51, "adh-dhariyat": 51, "الذاريات": 51,
    # 52. At-Tur
    "tur": 52, "at-tur": 52, "الطور": 52,
    # 53. An-Najm
    "najm": 53, "an-najm": 53, "النجم": 53,
    # 54. Al-Qamar
    "qamar": 54, "al-qamar": 54, "القمر": 54,
    # 55. Ar-Rahman
    "rahman": 55, "ar-rahman": 55, "الرحمن": 55,
    # 56. Al-Waqi'a
    "waqia": 56, "al-waqia": 56, "waqiah": 56, "الواقعة": 56,
    # 57. Al-Hadid
    "hadid": 57, "al-hadid": 57, "الحديد": 57,
    # 58. Al-Mujadila
    "mujadila": 58, "al-mujadila": 58, "المجادلة": 58, "mujadilah": 58,
    # 59. Al-Hashr
    "hashr": 59, "al-hashr": 59, "الحشر": 59,
    # 60. Al-Mumtahina
    "mumtahina": 60, "al-mumtahina": 60, "الممتحنة": 60, "mumtahinah": 60,
    # 61. As-Saff
    "saff": 61, "as-saff": 61, "الصف": 61,
    # 62. Al-Jumu'a
    "jumua": 62, "al-jumua": 62, "jumuah": 62, "الجمعة": 62,
    # 63. Al-Munafiqun
    "munafiqun": 63, "al-munafiqun": 63, "المنافقون": 63, "munafiqoon": 63,
    # 64. At-Taghabun
    "taghabun": 64, "at-taghabun": 64, "التغابن": 64,
    # 65. At-Talaq
    "talaq": 65, "at-talaq": 65, "الطلاق": 65,
    # 66. At-Tahrim
    "tahrim": 66, "at-tahrim": 66, "التحريم": 66,
    # 67. Al-Mulk
    "mulk": 67, "al-mulk": 67, "الملك": 67,
    # 68. Al-Qalam
    "qalam": 68, "al-qalam": 68, "القلم": 68,
    # 69. Al-Haaqqa
    "haaqqa": 69, "al-haaqqa": 69, "الحاقة": 69, "haqqa": 69,
    # 70. Al-Ma'arij
    "maarij": 70, "al-maarij": 70, "المعارج": 70,
    # 71. Nuh
    "nuh": 71, "نوح": 71,
    # 72. Al-Jinn
    "jinn": 72, "al-jinn": 72, "الجن": 72,
    # 73. Al-Muzzammil
    "muzzammil": 73, "al-muzzammil": 73, "المزمل": 73,
    # 74. Al-Muddaththir
    "muddaththir": 74, "al-muddaththir": 74, "المدثر": 74, "muddathir": 74,
    # 75. Al-Qiyama
    "qiyama": 75, "al-qiyama": 75, "القيامة": 75, "qiyamah": 75,
    # 76. Al-Insan
    "insan": 76, "al-insan": 76, "الإنسان": 76, "ad-dahr": 76,
    # 77. Al-Mursalat
    "mursalat": 77, "al-mursalat": 77, "المرسلات": 77,
    # 78. An-Naba
    "naba": 78, "an-naba": 78, "النبأ": 78,
    # 79. An-Nazi'at
    "naziat": 79, "an-naziat": 79, "النازعات": 79,
    # 80. Abasa
    "abasa": 80, "عبس": 80,
    # 81. At-Takwir
    "takwir": 81, "at-takwir": 81, "التكوير": 81,
    # 82. Al-Infitar
    "infitar": 82, "al-infitar": 82, "الانفطار": 82,
    # 83. Al-Mutaffifin
    "mutaffifin": 83, "al-mutaffifin": 83, "المطففين": 83,
    # 84. Al-Inshiqaq
    "inshiqaq": 84, "al-inshiqaq": 84, "الانشقاق": 84,
    # 85. Al-Buruj
    "buruj": 85, "al-buruj": 85, "البروج": 85,
    # 86. At-Tariq
    "tariq": 86, "at-tariq": 86, "الطارق": 86,
    # 87. Al-A'la
    "ala": 87, "al-ala": 87, "الأعلى": 87,
    # 88. Al-Ghashiya
    "ghashiya": 88, "al-ghashiya": 88, "الغاشية": 88, "ghashiyah": 88,
    # 89. Al-Fajr
    "fajr": 89, "al-fajr": 89, "الفجر": 89,
    # 90. Al-Balad
    "balad": 90, "al-balad": 90, "البلد": 90,
    # 91. Ash-Shams
    "shams": 91, "ash-shams": 91, "الشمس": 91,
    # 92. Al-Layl
    "layl": 92, "al-layl": 92, "الليل": 92,
    # 93. Ad-Duha
    "duha": 93, "ad-duha": 93, "الضحى": 93,
    # 94. Ash-Sharh
    "sharh": 94, "ash-sharh": 94, "الشرح": 94, "inshirah": 94, "al-inshirah": 94,
    # 95. At-Tin
    "tin": 95, "at-tin": 95, "التين": 95,
    # 96. Al-Alaq
    "alaq": 96, "al-alaq": 96, "العلق": 96,
    # 97. Al-Qadr
    "qadr": 97, "al-qadr": 97, "القدر": 97,
    # 98. Al-Bayyina
    "bayyina": 98, "al-bayyina": 98, "البينة": 98, "bayyinah": 98,
    # 99. Az-Zalzala
    "zalzala": 99, "az-zalzala": 99, "الزلزلة": 99, "zilzal": 99,
    # 100. Al-Adiyat
    "adiyat": 100, "al-adiyat": 100, "العاديات": 100,
    # 101. Al-Qari'a
    "qaria": 101, "al-qaria": 101, "القارعة": 101, "qariah": 101,
    # 102. At-Takathur
    "takathur": 102, "at-takathur": 102, "التكاثر": 102,
    # 103. Al-Asr
    "asr": 103, "al-asr": 103, "العصر": 103,
    # 104. Al-Humaza
    "humaza": 104, "al-humaza": 104, "الهمزة": 104, "humazah": 104,
    # 105. Al-Fil
    "fil": 105, "al-fil": 105, "الفيل": 105,
    # 106. Quraysh
    "quraysh": 106, "قريش": 106, "quraish": 106,
    # 107. Al-Ma'un
    "maun": 107, "al-maun": 107, "الماعون": 107,
    # 108. Al-Kawthar
    "kawthar": 108, "al-kawthar": 108, "الكوثر": 108, "kausar": 108, "kauthar": 108,
    # 109. Al-Kafirun
    "kafirun": 109, "al-kafirun": 109, "الكافرون": 109, "kafiroon": 109,
    # 110. An-Nasr
    "nasr": 110, "an-nasr": 110, "النصر": 110,
    # 111. Al-Masad
    "masad": 111, "al-masad": 111, "المسد": 111, "lahab": 111, "al-lahab": 111,
    # 112. Al-Ikhlas
    "ikhlas": 112, "al-ikhlas": 112, "الإخلاص": 112,
    # 113. Al-Falaq
    "falaq": 113, "al-falaq": 113, "الفلق": 113,
    # 114. An-Nas
    "nas": 114, "an-nas": 114, "الناس": 114, "naas": 114,
}

# Number of ayahs per surah (used for max_results on whole-surah lookups)
_SURAH_AYAH_COUNTS: dict[int, int] = {
    1: 7, 2: 286, 3: 200, 4: 176, 5: 120, 6: 165, 7: 206, 8: 75, 9: 129,
    10: 109, 11: 123, 12: 111, 13: 43, 14: 52, 15: 99, 16: 128, 17: 111,
    18: 110, 19: 98, 20: 135, 21: 112, 22: 78, 23: 118, 24: 64, 25: 77,
    26: 227, 27: 93, 28: 88, 29: 69, 30: 60, 31: 34, 32: 30, 33: 73,
    34: 54, 35: 45, 36: 83, 37: 182, 38: 88, 39: 75, 40: 85, 41: 54,
    42: 53, 43: 89, 44: 59, 45: 37, 46: 35, 47: 38, 48: 29, 49: 18,
    50: 45, 51: 60, 52: 49, 53: 62, 54: 55, 55: 78, 56: 96, 57: 29,
    58: 22, 59: 24, 60: 13, 61: 14, 62: 11, 63: 11, 64: 18, 65: 12,
    66: 12, 67: 30, 68: 52, 69: 52, 70: 44, 71: 28, 72: 28, 73: 20,
    74: 56, 75: 40, 76: 31, 77: 50, 78: 40, 79: 46, 80: 42, 81: 29,
    82: 19, 83: 36, 84: 25, 85: 22, 86: 17, 87: 19, 88: 26, 89: 30,
    90: 20, 91: 15, 92: 21, 93: 11, 94: 8, 95: 8, 96: 19, 97: 5,
    98: 8, 99: 8, 100: 11, 101: 11, 102: 8, 103: 3, 104: 9, 105: 5,
    106: 4, 107: 7, 108: 3, 109: 6, 110: 3, 111: 5, 112: 4, 113: 5,
    114: 6,
}


def _detect_structural_fact(question: str) -> str | None:
    """Detect questions about the Quran's structure that can be answered from our data.

    Returns a factual context string, or None if not a structural question.
    """
    q_lower = question.lower()

    # "How many surahs" / "number of surahs" / "how many surah's" / "how many surah"
    if re.search(r"\b(?:how many|number of|total)\b.*\bsurah'?s?\b|\b(?:how many|number of|total)\b.*\b(?:suras|chapters)\b", q_lower):
        # Exclude "how many ayahs in surah X" — only match when surahs are the subject
        if not re.search(r"\b(?:ayah|ayat|verse)s?\b.*\b(?:surah|sura|chapter)\b", q_lower):
            return (
                "The Quran contains exactly 114 surahs (chapters). "
                "The first surah is Al-Fatiha and the last is An-Nas."
            )

    # "How many ayahs" (total, not in a specific surah)
    if re.search(r"\b(?:how many|number of|total)\b.*\b(?:ayah|ayat|verse)s?\b", q_lower):
        # Check if it's about a specific surah — if so, let metadata handle it
        if not re.search(r"\b(?:surah|sura|chapter)\s+\w", q_lower):
            return (
                "The Quran contains exactly 6,236 ayahs (verses) "
                "across 114 surahs."
            )

    # "How many juz/para"
    if re.search(r"\b(?:how many|number of|total)\b.*\b(?:juz|para|part)s?\b", q_lower):
        return "The Quran is divided into exactly 30 juz (parts)."

    return None


def _detect_metadata(question: str) -> MetadataFilter | None:
    """Detect structural/metadata lookups in the query.

    Returns a MetadataFilter if the query references a specific surah,
    ayah, or juz by number or name. Returns None for content-based queries.
    """
    q_lower = question.lower()
    mf = MetadataFilter()
    matched = False

    # 1. Specific ayah reference: "2:255", "3:185", etc.
    ayah_ref = re.search(r"\b(\d{1,3}):(\d{1,3})\b", question)
    if ayah_ref:
        mf.surah_number = int(ayah_ref.group(1))
        mf.ayah_number = int(ayah_ref.group(2))
        return mf

    # 2. Juz/para reference: "juz 30", "para 1"
    juz_match = re.search(r"\b(?:juz|para|juzz)\s+(\d{1,2})\b", q_lower)
    if juz_match:
        mf.juz = int(juz_match.group(1))
        return mf

    # 3. Ordinal/positional: "first surah", "last surah", "first ayah"
    if re.search(r"\bfirst\s+surah\b", q_lower):
        mf.surah_number = 1
        return mf
    if re.search(r"\blast\s+surah\b", q_lower):
        mf.surah_number = 114
        return mf
    if re.search(r"\bfirst\s+ayah\b", q_lower):
        mf.surah_number = 1
        mf.ayah_number = 1
        return mf
    if re.search(r"\blast\s+ayah\b", q_lower):
        mf.surah_number = 114
        mf.ayah_number = 6
        return mf

    # 4. Surah by number: "surah 2", "chapter 19", "18th surah", "2nd chapter"
    surah_num = re.search(r"\b(?:surah|sura|chapter)\s+(?:number\s+)?(\d{1,3})\b", q_lower)
    if not surah_num:
        # Ordinal before keyword: "18th surah", "1st chapter"
        surah_num = re.search(r"\b(\d{1,3})(?:st|nd|rd|th)\s+(?:surah|sura|chapter)\b", q_lower)
    if surah_num:
        mf.surah_number = int(surah_num.group(1))
        matched = True

    # 5. Ayah by number within a surah context: "ayah 255", "verse 3", "5th ayah"
    ayah_num = re.search(r"\b(?:ayah|ayat|verse)\s+(\d{1,3})\b", q_lower)
    if not ayah_num:
        ayah_num = re.search(r"\b(\d{1,3})(?:st|nd|rd|th)\s+(?:ayah|ayat|verse)\b", q_lower)
    if ayah_num:
        mf.ayah_number = int(ayah_num.group(1))
        matched = True

    if matched:
        return mf

    # 6. Surah by name: match against SURAH_NAMES keys
    #    Check with "surah/sura/chapter" prefix first for precision,
    #    then fall back to standalone name match for longer names.
    surah_prefix = re.search(r"\b(?:surah|sura|chapter)\s+(.+?)(?:\s*\?|$)", q_lower)
    if surah_prefix:
        name_part = surah_prefix.group(1).strip().rstrip("?").strip()
        # Try matching against SURAH_NAMES
        if name_part in SURAH_NAMES:
            mf.surah_number = SURAH_NAMES[name_part]
            return mf
        # Try without "al-" prefix
        without_al = re.sub(r"^al[- ]", "", name_part)
        if without_al in SURAH_NAMES:
            mf.surah_number = SURAH_NAMES[without_al]
            return mf

    # 7. Standalone surah name match (for queries like "show me Al-Ikhlas")
    #    Use word-boundary matching for Latin names to avoid false positives
    #    (e.g. "tur" inside "masturbation", "rum" as the drink).
    #    Require 5+ chars for Latin standalone to avoid matching common words
    #    like "rum", "tin", "hud", "nuh". Short names still work with
    #    "surah X" prefix (step 6).
    #    Arabic names use substring matching since \b doesn't work for Arabic.
    for name, num in SURAH_NAMES.items():
        if name.isdigit():
            continue
        is_arabic = any(not c.isascii() for c in name if c.isalpha())
        if is_arabic:
            if len(name) >= 2 and name in question:
                mf.surah_number = num
                return mf
        else:
            # Require 5+ chars for standalone Latin names
            if len(name) >= 5 and re.search(r"\b" + re.escape(name) + r"\b", q_lower):
                mf.surah_number = num
                return mf

    return None


def _extract_keywords(question: str) -> list[str]:
    """Extract search keywords from the question using named entity matching."""
    q_lower = question.lower()
    keywords: list[str] = []

    for canonical, variants in NAMED_ENTITIES.items():
        for variant in variants:
            if variant.lower() in q_lower or variant in question:
                # Add all variants for this entity so keyword search catches them all
                keywords.extend(variants)
                break

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for kw in keywords:
        kw_lower = kw.lower()
        if kw_lower not in seen:
            seen.add(kw_lower)
            unique.append(kw)
    return unique


def _matches_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def classify_query(question: str) -> QueryIntent:
    """Classify query intent to determine search strategy."""
    # Check structural facts first (e.g. "how many surahs in the Quran?")
    structural = _detect_structural_fact(question)
    if structural is not None:
        return QueryIntent(
            query_type="metadata",
            structural_context=structural,
            max_results=0,
        )

    # Check metadata patterns (structural lookups by surah/ayah/juz)
    metadata_filter = _detect_metadata(question)
    if metadata_filter is not None:
        # Determine max_results based on what's being looked up
        if metadata_filter.ayah_number is not None:
            max_results = 1
        elif metadata_filter.surah_number is not None:
            max_results = _SURAH_AYAH_COUNTS.get(metadata_filter.surah_number, 300)
        else:
            # Juz-level lookup — can be up to ~560 ayahs
            max_results = 600

        return QueryIntent(
            query_type="metadata",
            metadata_filter=metadata_filter,
            max_results=max_results,
        )

    keywords = _extract_keywords(question)

    if _matches_any(question, _COUNTING_PATTERNS):
        return QueryIntent(
            query_type="counting",
            keywords=keywords,
            max_results=100,
        )

    if _matches_any(question, _LISTING_PATTERNS):
        return QueryIntent(
            query_type="listing",
            keywords=keywords,
            max_results=50,
        )

    return QueryIntent(
        query_type="semantic",
        keywords=[],
        max_results=10,
    )
