import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add package directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "jp_ocr_dict"))

from api import JishoAPIHandler  # noqa: E402
from db_dictionary import SQLiteDictionary  # noqa: E402


def test_jisho_api_empty_query() -> None:
    api = JishoAPIHandler()
    assert api.fetch_jisho_info("") is None
    assert api.lookup_candidates([]) is None
    assert api.scrape_names_info("") == []


def test_extract_ordered_kanji_preserves_reading_order() -> None:
    # Ensure set() scrambling is eliminated and Kanji order strictly matches compound word
    assert JishoAPIHandler.extract_ordered_kanji("日本語能力試験") == [
        "日",
        "本",
        "語",
        "能",
        "力",
        "試",
        "験",
    ]
    # Ensure duplicate kanji are deduplicated while preserving first occurrence
    assert JishoAPIHandler.extract_ordered_kanji("時々") == ["時"]
    assert JishoAPIHandler.extract_ordered_kanji("") == []


def test_sqlite_dictionary_crud(tmp_path: Path) -> None:
    db = SQLiteDictionary(db_path=tmp_path / "test_dict.db")
    assert db.get_word("猫") is None
    assert db.get_kanji("猫") is None
    assert db.get_names("田中") is None

    # Test word persistence
    word_data = {
        "slug": "猫",
        "is_common": True,
        "jlpt": ["N5"],
        "readings": [{"word": "猫", "reading": "ねこ"}],
        "senses": [{"pos": ["Noun"], "meanings": ["cat"], "tags": []}],
    }
    db.save_word("猫", word_data)
    loaded_word = db.get_word("猫")
    assert loaded_word is not None
    assert loaded_word["slug"] == "猫"
    assert loaded_word["readings"][0]["reading"] == "ねこ"

    # Test kanji persistence
    kanji_data = {"kanji": "猫", "stroke_count": 11, "meanings": ["cat"]}
    db.save_kanji("猫", kanji_data)
    loaded_kanji = db.get_kanji("猫")
    assert loaded_kanji is not None
    assert loaded_kanji["stroke_count"] == 11

    # Test names persistence
    names_data = [{"kanji": "田中", "reading": "たなか", "meaning": "surname"}]
    db.save_names("田中", names_data)
    loaded_names = db.get_names("田中")
    assert loaded_names is not None
    assert len(loaded_names) == 1
    assert loaded_names[0]["reading"] == "たなか"

    # Test stats
    stats = db.get_stats()
    assert stats["words"] == 1
    assert stats["kanji"] == 1
    assert stats["names"] == 1


def test_jisho_api_uses_sqlite_first_without_network(tmp_path: Path) -> None:
    db = SQLiteDictionary(db_path=tmp_path / "test_cache.db")
    word_data = {
        "slug": "食べる",
        "is_common": True,
        "jlpt": ["N5"],
        "readings": [{"word": "食べる", "reading": "たべる"}],
        "senses": [{"pos": ["Verb"], "meanings": ["to eat"], "tags": []}],
    }
    db.save_word("食べる", word_data)

    api = JishoAPIHandler(db=db)
    with patch.object(api.session, "get") as mock_get:
        # Should be resolved 100% locally from SQLite with zero network calls
        info = api.fetch_jisho_info("食べる")
        assert info is not None
        assert info["slug"] == "食べる"
        assert mock_get.call_count == 0


def test_jisho_api_parsing(tmp_path: Path) -> None:
    api = JishoAPIHandler(db=SQLiteDictionary(db_path=tmp_path / "test_api_parse.db"))
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [
            {
                "slug": "日本語",
                "is_common": True,
                "jlpt": ["jlpt-n5"],
                "japanese": [{"word": "日本語", "reading": "にほんご"}],
                "senses": [
                    {
                        "parts_of_speech": ["Noun"],
                        "english_definitions": ["Japanese language"],
                        "tags": ["Common word"],
                    }
                ],
            }
        ]
    }

    try:
        with patch.object(api.session, "get", return_value=mock_response):
            info = api.fetch_jisho_info("日本語")
            assert info is not None
            assert info["query"] == "日本語"
            assert info["slug"] == "日本語"
            assert info["is_common"] is True
            assert info["jlpt"] == ["N5"]
            assert len(info["readings"]) == 1
            assert info["readings"][0]["reading"] == "にほんご"
            assert info["senses"][0]["meanings"] == ["Japanese language"]
    finally:
        api.shutdown()


def test_kanji_api_parsing_and_caching(tmp_path: Path) -> None:
    api = JishoAPIHandler(db=SQLiteDictionary(db_path=tmp_path / "test_kanji_parse.db"))
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "kanji": "日",
        "grade": 1,
        "stroke_count": 4,
        "jlpt": 5,
        "meanings": ["day", "sun", "Japan"],
        "on_readings": ["ニチ", "ジツ"],
        "kun_readings": ["ひ", "-び", "-か"],
        "name_readings": ["あ", "あき"],
        "unicode": "65e5",
    }

    try:
        with patch.object(api.session, "get", return_value=mock_response) as mock_get:
            kanji_info = api.fetch_kanji_info("日")
            assert kanji_info is not None
            assert kanji_info["kanji"] == "日"
            assert kanji_info["grade"] == 1
            assert kanji_info["stroke_count"] == 4
            assert kanji_info["jlpt"] == "N5"
            assert kanji_info["unicode"] == "65E5"
            assert "day" in kanji_info["meanings"]

            # Cache check: second call should not trigger another GET request
            cached_info = api.fetch_kanji_info("日")
            assert cached_info == kanji_info
            assert mock_get.call_count == 1
    finally:
        api.shutdown()


def test_fetch_kanji_list_parallel() -> None:
    api = JishoAPIHandler()

    def mock_fetch(char: str):
        return {
            "kanji": char,
            "stroke_count": 4 if char == "日" else 5,
            "meanings": [f"meaning of {char}"],
        }

    with patch.object(api, "fetch_kanji_info", side_effect=mock_fetch):
        results = api.fetch_kanji_list("日本")
        assert len(results) == 2
        assert results[0]["kanji"] == "日"
        assert results[1]["kanji"] == "本"


def test_lookup_candidates_prioritizes_order() -> None:
    api = JishoAPIHandler()

    def mock_fetch(word: str):
        if word == "食べる":
            return {"slug": "食べる", "meanings": ["to eat"]}
        return None

    with patch.object(api, "fetch_jisho_info", side_effect=mock_fetch):
        result = api.lookup_candidates(["食べた", "食べる"])
        assert result is not None
        assert result["slug"] == "食べる"


def test_offline_dictionary_kanji_priority_resolution() -> None:
    """
    Verifies that core Kanji homographs in the SQLite dictionary are resolved
    with their primary, high-frequency readings rather than obscure counter/dialect entries.
    Specifically checks:
    - 日 is read as 'ひ' / 'にち', not 'んち'
    - 人 is read as 'ひと', not 'じん' / 'にん'
    - 年 is read as 'とし' / 'ねん', not 'とせ'
    """
    db = SQLiteDictionary()
    try:
        # If the offline database is populated, verify priority readings
        day_entry = db.get_word("日")
        if day_entry is not None:
            readings = [r.get("reading") for r in day_entry.get("readings", [])]
            assert "ひ" in readings
            assert readings[0] == "ひ"
            assert "んち" not in readings[:2]
            assert day_entry.get("is_common") is True
            meanings = [
                s["meanings"][0].lower() for s in day_entry.get("senses", []) if s.get("meanings")
            ]
            assert any("day" in m or "sun" in m for m in meanings)

        person_entry = db.get_word("人")
        if person_entry is not None:
            readings = [r.get("reading") for r in person_entry.get("readings", [])]
            assert "ひと" in readings
            assert readings[0] == "ひと"

        year_entry = db.get_word("年")
        if year_entry is not None:
            readings = [r.get("reading") for r in year_entry.get("readings", [])]
            assert "とし" in readings
            assert readings[0] == "とし"
            assert "とせ" not in readings[:2]
    finally:
        db.close()


def test_offline_dictionary_pure_kana_and_particle_protection() -> None:
    """
    Verifies that grammatical particles and words usually written in kana (&uk;)
    are never overshadowed by kanji reading aliases.
    Specifically checks:
    - に resolves to the grammatical particle (at, to), slug 'に' (not 荷 or 煮)
    - その resolves to the demonstrative (that), slug 'その' (not 園)
    - ああ resolves to the interjection (ah!, oh!), slug 'ああ' (not 唖々 or 嗚呼)
    - で resolves to the grammatical particle (at, in), slug 'で' (not 出)
    - は resolves to the topic particle, slug 'は' (not 葉)
    - が resolves to the subject particle, slug 'が' (not 絵)
    - 声 has primary reading 'こえ' (not しょう)
    """
    db = SQLiteDictionary()
    try:
        # Particle に
        ni = db.get_word("に")
        assert ni is not None
        assert ni["slug"] == "に"
        ni_meanings = " ".join(
            " ".join(s.get("meanings", [])) for s in ni.get("senses", [])
        ).lower()
        assert "at" in ni_meanings or "in" in ni_meanings or "to" in ni_meanings

        # Demonstrative その
        sono = db.get_word("その")
        assert sono is not None
        assert sono["slug"] == "その"
        sono_meanings = " ".join(
            " ".join(s.get("meanings", [])) for s in sono.get("senses", [])
        ).lower()
        assert "that" in sono_meanings

        # Interjection ああ
        aa = db.get_word("ああ")
        assert aa is not None
        assert aa["slug"] == "ああ"
        assert aa["readings"][0]["reading"] == "ああ"
        aa_meanings = " ".join(
            " ".join(s.get("meanings", [])) for s in aa.get("senses", [])
        ).lower()
        assert "ah!" in aa_meanings or "oh!" in aa_meanings

        # Particle で
        de = db.get_word("で")
        assert de is not None
        assert de["slug"] == "で"
        de_meanings = " ".join(
            " ".join(s.get("meanings", [])) for s in de.get("senses", [])
        ).lower()
        assert "at" in de_meanings or "in" in de_meanings

        # Particle は
        ha = db.get_word("は")
        assert ha is not None
        assert ha["slug"] == "は"

        # Particle が
        ga = db.get_word("が")
        assert ga is not None
        assert ga["slug"] == "が"

        # Kanji 声
        koe = db.get_word("声")
        assert koe is not None
        assert koe["slug"] == "声"
        assert koe["readings"][0]["reading"] == "こえ"
    finally:
        db.close()


def test_jisho_api_shutdown() -> None:
    api = JishoAPIHandler()
    assert not api.executor._shutdown
    api.shutdown()
    assert api.executor._shutdown


def test_lookup_candidates_local_first_avoids_network_on_second_candidate(tmp_path: Path) -> None:
    """
    Verifies two-tier local-first resolution: if candidates[0] is missing locally
    while candidates[1] exists in SQLite, candidates[1] is returned without making
    a remote HTTP request for candidates[0].
    """
    db = SQLiteDictionary(db_path=tmp_path / "test_two_tier.db")
    db.save_word(
        "食べる",
        {
            "query": "食べる",
            "slug": "食べる",
            "is_common": True,
            "jlpt": ["N5"],
            "readings": [{"word": "食べる", "reading": "たべる"}],
            "senses": [{"pos": ["Verb"], "meanings": ["to eat"], "tags": []}],
        },
    )

    api = JishoAPIHandler(db=db)
    try:
        with patch.object(api.session, "get") as mock_get:
            result = api.lookup_candidates(["食べなかった", "食べる"])
            assert result is not None
            assert result["slug"] == "食べる"
            assert mock_get.call_count == 0
    finally:
        api.shutdown()


def test_offline_dictionary_core_homograph_and_kanji_jlpt_accuracy() -> None:
    """
    Verifies that previously broken homographs and JLPT mappings resolve accurately
    in the rebuilt offline JMdict/KANJIDIC2 SQLite database.
    """
    db = SQLiteDictionary()
    try:
        naru = db.get_word("なる")
        if naru is not None:
            meanings = " ".join(
                " ".join(s.get("meanings", [])) for s in naru.get("senses", [])
            ).lower()
            assert "become" in meanings

        mae = db.get_word("前")
        if mae is not None:
            assert mae["slug"] == "前"
            assert mae["readings"][0]["reading"] == "まえ"

        kare = db.get_word("彼")
        if kare is not None:
            assert kare["slug"] == "彼"
            assert kare["readings"][0]["reading"] == "かれ"

        boku = db.get_word("僕")
        if boku is not None:
            assert boku["slug"] == "僕"
            assert boku["readings"][0]["reading"] == "ぼく"

        warui = db.get_word("悪い")
        if warui is not None:
            assert warui["slug"] == "悪い"
            assert warui["readings"][0]["reading"] == "わるい"

        ue = db.get_word("上")
        if ue is not None:
            assert ue["slug"] == "上"
            assert ue["readings"][0]["reading"] == "うえ"

        toki = db.get_word("時")
        if toki is not None:
            assert toki["slug"] == "時"
            assert toki["readings"][0]["reading"] == "とき"

        no_part = db.get_word("の")
        if no_part is not None:
            assert no_part["slug"] == "の"

        miru = db.get_word("見る")
        if miru is not None:
            assert miru["slug"] == "見る"

        kanji_hi = db.get_kanji("日")
        if kanji_hi is not None:
            assert kanji_hi.get("jlpt") == "N5"
    finally:
        db.close()
