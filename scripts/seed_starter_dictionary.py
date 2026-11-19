"""
Seeds the local SQLite dictionary with essential core vocabulary,
kanji characters, and name records for instant, zero-latency offline use.
"""

import sys
from pathlib import Path

# Ensure src/jp_ocr_dict is on path
PACKAGE_DIR = Path(__file__).resolve().parent.parent / "src" / "jp_ocr_dict"
if str(PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGE_DIR))

from db_dictionary import SQLiteDictionary  # noqa: E402

# Core high-frequency Japanese vocabulary across JLPT N5-N2 and common manga expressions
CORE_ENTRIES = [
    {
        "keyword": "食べる",
        "slug": "食べる",
        "readings": [{"word": "食べる", "reading": "たべる"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [{"pos": ["Ichidan verb", "transitive"], "meanings": ["to eat"], "tags": []}],
    },
    {
        "keyword": "飲む",
        "slug": "飲む",
        "readings": [{"word": "飲む", "reading": "のむ"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [
            {
                "pos": ["Godan verb", "transitive"],
                "meanings": ["to drink", "to swallow"],
                "tags": [],
            }
        ],
    },
    {
        "keyword": "読む",
        "slug": "読む",
        "readings": [{"word": "読む", "reading": "よむ"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [{"pos": ["Godan verb", "transitive"], "meanings": ["to read"], "tags": []}],
    },
    {
        "keyword": "見る",
        "slug": "見る",
        "readings": [{"word": "見る", "reading": "みる"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [
            {
                "pos": ["Ichidan verb", "transitive"],
                "meanings": ["to see", "to look at", "to watch"],
                "tags": [],
            }
        ],
    },
    {
        "keyword": "行く",
        "slug": "行く",
        "readings": [{"word": "行く", "reading": "いく"}, {"word": "行く", "reading": "ゆく"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [
            {"pos": ["Godan verb", "intransitive"], "meanings": ["to go", "to proceed"], "tags": []}
        ],
    },
    {
        "keyword": "来る",
        "slug": "来る",
        "readings": [{"word": "来る", "reading": "くる"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [
            {"pos": ["Kuru verb", "intransitive"], "meanings": ["to come", "to arrive"], "tags": []}
        ],
    },
    {
        "keyword": "話す",
        "slug": "話す",
        "readings": [{"word": "話す", "reading": "はなす"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [
            {
                "pos": ["Godan verb", "transitive"],
                "meanings": ["to speak", "to talk", "to converse"],
                "tags": [],
            }
        ],
    },
    {
        "keyword": "聞く",
        "slug": "聞く",
        "readings": [{"word": "聞く", "reading": "きく"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [
            {
                "pos": ["Godan verb", "transitive"],
                "meanings": ["to hear", "to listen", "to ask"],
                "tags": [],
            }
        ],
    },
    {
        "keyword": "言う",
        "slug": "言う",
        "readings": [{"word": "言う", "reading": "いう"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [
            {"pos": ["Godan verb", "transitive"], "meanings": ["to say", "to utter"], "tags": []}
        ],
    },
    {
        "keyword": "思う",
        "slug": "思う",
        "readings": [{"word": "思う", "reading": "おもう"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [
            {
                "pos": ["Godan verb", "transitive"],
                "meanings": ["to think", "to feel", "to consider"],
                "tags": [],
            }
        ],
    },
    {
        "keyword": "分かる",
        "slug": "分かる",
        "readings": [{"word": "分かる", "reading": "わかる"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [
            {
                "pos": ["Godan verb", "intransitive"],
                "meanings": ["to understand", "to comprehend", "to be known"],
                "tags": [],
            }
        ],
    },
    {
        "keyword": "知る",
        "slug": "知る",
        "readings": [{"word": "知る", "reading": "しる"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [
            {
                "pos": ["Godan verb", "transitive"],
                "meanings": ["to know", "to be aware of"],
                "tags": [],
            }
        ],
    },
    {
        "keyword": "走る",
        "slug": "走る",
        "readings": [{"word": "走る", "reading": "はしる"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [{"pos": ["Godan verb", "intransitive"], "meanings": ["to run"], "tags": []}],
    },
    {
        "keyword": "本",
        "slug": "本",
        "readings": [{"word": "本", "reading": "ほん"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [{"pos": ["Noun"], "meanings": ["book", "volume", "origin"], "tags": []}],
    },
    {
        "keyword": "日本語",
        "slug": "日本語",
        "readings": [{"word": "日本語", "reading": "にほんご"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [{"pos": ["Noun"], "meanings": ["Japanese language"], "tags": []}],
    },
    {
        "keyword": "日本",
        "slug": "日本",
        "readings": [
            {"word": "日本", "reading": "にほん"},
            {"word": "日本", "reading": "にっぽん"},
        ],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [{"pos": ["Noun"], "meanings": ["Japan"], "tags": []}],
    },
    {
        "keyword": "今日",
        "slug": "今日",
        "readings": [
            {"word": "今日", "reading": "きょう"},
            {"word": "今日", "reading": "こんにち"},
        ],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [{"pos": ["Noun"], "meanings": ["today", "this day"], "tags": []}],
    },
    {
        "keyword": "明日",
        "slug": "明日",
        "readings": [{"word": "明日", "reading": "あした"}, {"word": "明日", "reading": "あす"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [{"pos": ["Noun"], "meanings": ["tomorrow"], "tags": []}],
    },
    {
        "keyword": "昨日",
        "slug": "昨日",
        "readings": [{"word": "昨日", "reading": "きのう"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [{"pos": ["Noun"], "meanings": ["yesterday"], "tags": []}],
    },
    {
        "keyword": "人",
        "slug": "人",
        "readings": [{"word": "人", "reading": "ひと"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [{"pos": ["Noun"], "meanings": ["person", "human", "someone"], "tags": []}],
    },
    {
        "keyword": "猫",
        "slug": "猫",
        "readings": [{"word": "猫", "reading": "ねこ"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [{"pos": ["Noun"], "meanings": ["cat", "feline"], "tags": []}],
    },
    {
        "keyword": "犬",
        "slug": "犬",
        "readings": [{"word": "犬", "reading": "いぬ"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [{"pos": ["Noun"], "meanings": ["dog", "canine"], "tags": []}],
    },
    {
        "keyword": "学校",
        "slug": "学校",
        "readings": [{"word": "学校", "reading": "がっこう"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [{"pos": ["Noun"], "meanings": ["school"], "tags": []}],
    },
    {
        "keyword": "先生",
        "slug": "先生",
        "readings": [{"word": "先生", "reading": "せんせい"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [{"pos": ["Noun"], "meanings": ["teacher", "master", "doctor"], "tags": []}],
    },
    {
        "keyword": "友達",
        "slug": "友達",
        "readings": [{"word": "友達", "reading": "ともだち"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [{"pos": ["Noun"], "meanings": ["friend", "companion"], "tags": []}],
    },
    {
        "keyword": "魔法",
        "slug": "魔法",
        "readings": [{"word": "魔法", "reading": "まほう"}],
        "is_common": True,
        "jlpt": ["N3"],
        "senses": [{"pos": ["Noun"], "meanings": ["magic", "witchcraft", "sorcery"], "tags": []}],
    },
    {
        "keyword": "世界",
        "slug": "世界",
        "readings": [{"word": "世界", "reading": "せかい"}],
        "is_common": True,
        "jlpt": ["N4"],
        "senses": [{"pos": ["Noun"], "meanings": ["the world", "society", "universe"], "tags": []}],
    },
    {
        "keyword": "大丈夫",
        "slug": "大丈夫",
        "readings": [{"word": "大丈夫", "reading": "だいじょうぶ"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [
            {
                "pos": ["Na-adjective", "adverb"],
                "meanings": ["all right", "okay", "safe"],
                "tags": [],
            }
        ],
    },
    {
        "keyword": "凄い",
        "slug": "凄い",
        "readings": [{"word": "凄い", "reading": "すごい"}],
        "is_common": True,
        "jlpt": ["N3"],
        "senses": [
            {
                "pos": ["I-adjective"],
                "meanings": ["terrific", "amazing", "wonderful", "dreadful"],
                "tags": [],
            }
        ],
    },
    {
        "keyword": "本当",
        "slug": "本当",
        "readings": [{"word": "本当", "reading": "ほんとう"}],
        "is_common": True,
        "jlpt": ["N4"],
        "senses": [
            {
                "pos": ["Noun", "Na-adjective"],
                "meanings": ["truth", "reality", "proper"],
                "tags": [],
            }
        ],
    },
    {
        "keyword": "に",
        "slug": "に",
        "readings": [{"word": "に", "reading": "に"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [{"pos": ["particle"], "meanings": ["at", "in", "on", "to"], "tags": []}],
    },
    {
        "keyword": "その",
        "slug": "その",
        "readings": [{"word": "その", "reading": "その"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [
            {"pos": ["pre-noun adjectival (rentaishi)"], "meanings": ["that", "the"], "tags": []}
        ],
    },
    {
        "keyword": "ああ",
        "slug": "ああ",
        "readings": [{"word": "ああ", "reading": "ああ"}],
        "is_common": True,
        "jlpt": [],
        "senses": [{"pos": ["interjection"], "meanings": ["ah!", "oh!", "alas!"], "tags": []}],
    },
    {
        "keyword": "で",
        "slug": "で",
        "readings": [{"word": "で", "reading": "で"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [{"pos": ["particle"], "meanings": ["at", "in", "by"], "tags": []}],
    },
    {
        "keyword": "は",
        "slug": "は",
        "readings": [{"word": "は", "reading": "は"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [{"pos": ["particle"], "meanings": ["indicates sentence topic"], "tags": []}],
    },
    {
        "keyword": "が",
        "slug": "が",
        "readings": [{"word": "が", "reading": "が"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [
            {"pos": ["particle"], "meanings": ["indicates the subject of a sentence"], "tags": []}
        ],
    },
    {
        "keyword": "の",
        "slug": "の",
        "readings": [{"word": "の", "reading": "の"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [{"pos": ["particle"], "meanings": ["indicates possessive"], "tags": []}],
    },
    {
        "keyword": "声",
        "slug": "声",
        "readings": [{"word": "声", "reading": "こえ"}],
        "is_common": True,
        "jlpt": ["N4"],
        "senses": [{"pos": ["Noun"], "meanings": ["voice"], "tags": []}],
    },
    {
        "keyword": "日",
        "slug": "日",
        "readings": [{"word": "日", "reading": "ひ"}, {"word": "日", "reading": "にち"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [{"pos": ["Noun"], "meanings": ["day", "days", "sun"], "tags": []}],
    },
    {
        "keyword": "年",
        "slug": "年",
        "readings": [{"word": "年", "reading": "とし"}, {"word": "年", "reading": "ねん"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [{"pos": ["Noun"], "meanings": ["year"], "tags": []}],
    },
    {
        "keyword": "なる",
        "slug": "なる",
        "readings": [{"word": "成る", "reading": "なる"}],
        "is_common": True,
        "jlpt": ["N4"],
        "senses": [
            {"pos": ["Godan verb"], "meanings": ["to become", "to get", "to grow"], "tags": []}
        ],
    },
    {
        "keyword": "前",
        "slug": "前",
        "readings": [{"word": "前", "reading": "まえ"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [{"pos": ["Noun"], "meanings": ["in front (of)", "before"], "tags": []}],
    },
    {
        "keyword": "彼",
        "slug": "彼",
        "readings": [{"word": "彼", "reading": "かれ"}],
        "is_common": True,
        "jlpt": ["N4"],
        "senses": [{"pos": ["Pronoun"], "meanings": ["he", "him"], "tags": []}],
    },
    {
        "keyword": "僕",
        "slug": "僕",
        "readings": [{"word": "僕", "reading": "ぼく"}],
        "is_common": True,
        "jlpt": ["N4"],
        "senses": [{"pos": ["Pronoun"], "meanings": ["I", "me"], "tags": []}],
    },
    {
        "keyword": "悪い",
        "slug": "悪い",
        "readings": [{"word": "悪い", "reading": "わるい"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [
            {"pos": ["I-adjective"], "meanings": ["bad", "poor", "undesirable"], "tags": []}
        ],
    },
    {
        "keyword": "上",
        "slug": "上",
        "readings": [{"word": "上", "reading": "うえ"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [{"pos": ["Noun"], "meanings": ["above", "over", "up"], "tags": []}],
    },
    {
        "keyword": "時",
        "slug": "時",
        "readings": [{"word": "時", "reading": "とき"}, {"word": "時", "reading": "じ"}],
        "is_common": True,
        "jlpt": ["N5"],
        "senses": [{"pos": ["Noun"], "meanings": ["time", "hour", "moment"], "tags": []}],
    },
]

# Core kanji records
CORE_KANJI = [
    {
        "kanji": "日",
        "grade": 1,
        "stroke_count": 4,
        "jlpt": "N5",
        "meanings": ["day", "sun", "Japan"],
        "on_readings": ["ニチ", "ジツ"],
        "kun_readings": ["ひ", "-び", "-か"],
        "unicode": "65E5",
    },
    {
        "kanji": "本",
        "grade": 1,
        "stroke_count": 5,
        "jlpt": "N5",
        "meanings": [
            "book",
            "present",
            "main",
            "true",
            "real",
            "counter for long cylindrical things",
        ],
        "on_readings": ["ホン"],
        "kun_readings": ["もと"],
        "unicode": "672C",
    },
    {
        "kanji": "語",
        "grade": 2,
        "stroke_count": 14,
        "jlpt": "N5",
        "meanings": ["word", "speech", "language"],
        "on_readings": ["ゴ"],
        "kun_readings": ["かた.る", "かた.らう"],
        "unicode": "8A9E",
    },
    {
        "kanji": "食",
        "grade": 2,
        "stroke_count": 9,
        "jlpt": "N5",
        "meanings": ["eat", "food"],
        "on_readings": ["ショク", "ジキ"],
        "kun_readings": ["く.う", "く.らう", "た.べる"],
        "unicode": "98DF",
    },
    {
        "kanji": "飲",
        "grade": 3,
        "stroke_count": 12,
        "jlpt": "N5",
        "meanings": ["drink", "smoke", "take"],
        "on_readings": ["イン", "オン"],
        "kun_readings": ["の.む"],
        "unicode": "98F2",
    },
    {
        "kanji": "読",
        "grade": 2,
        "stroke_count": 14,
        "jlpt": "N5",
        "meanings": ["read"],
        "on_readings": ["ドク", "トク", "トウ"],
        "kun_readings": ["よ.む"],
        "unicode": "8AAD",
    },
]


def seed(db_path: Path | None = None) -> None:
    db = SQLiteDictionary(db_path=db_path) if db_path is not None else SQLiteDictionary()
    try:
        print("Seeding core Japanese vocabulary into local SQLite database...")
        for entry in CORE_ENTRIES:
            db.save_word(entry["keyword"], entry)
            if entry["keyword"] != entry["slug"]:
                db.save_word(entry["slug"], entry)

        print("Seeding core Kanji characters...")
        for kanji in CORE_KANJI:
            db.save_kanji(kanji["kanji"], kanji)

        stats = db.get_stats()
        print(
            f"Database seeded successfully: {stats['words']} words, {stats['kanji']} kanji in {db.db_path}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    seed()
