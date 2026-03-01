from app.services.reader import slugify


def test_slugify_basic():
    assert slugify("Sahih Bukhari") == "sahih-bukhari"


def test_slugify_apostrophe():
    assert slugify("Jami' Al-Tirmidhi") == "jami-al-tirmidhi"


def test_slugify_parentheses():
    assert slugify("Tafsir Ibn Kathir (Abridged)") == "tafsir-ibn-kathir-abridged"


def test_slugify_quran_special_chars():
    assert slugify("Ma'arif al-Qur'an") == "maarif-al-quran"
