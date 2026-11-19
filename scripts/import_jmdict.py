"""
Complete Offline Japanese Dictionary Importer.
Downloads and indexes:
1. JMdict_e.gz (~185,000+ Japanese vocabulary words) from EDRDG via HTTPS.
2. kanjidic2.xml.gz (~13,100+ Kanji characters with strokes, grades, readings) via HTTPS.

All data is indexed into the local SQLite database (`data/dictionary.db`),
giving the application full offline, sub-millisecond dictionary lookups.
"""

import gzip
import json
import logging
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

# Ensure src/jp_ocr_dict is on path
PACKAGE_DIR = Path(__file__).resolve().parent.parent / "src" / "jp_ocr_dict"
if str(PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGE_DIR))

from db_dictionary import DB_PATH, SQLiteDictionary  # noqa: E402

logger = logging.getLogger(__name__)

# Official EDRDG Mirrors
JMDICT_URLS = [
    "https://ftp.edrdg.org/pub/Nihongo/JMdict_e.gz",
    "https://www.edrdg.org/pub/Nihongo/JMdict_e.gz",
]
KANJIDIC_URLS = [
    "https://www.edrdg.org/kanjidic/kanjidic2.xml.gz",
    "https://ftp.edrdg.org/pub/Nihongo/kanjidic2.xml.gz",
]

# High-frequency core Kanji readings (ensures N5/N4 core readings precede dialect/obscure homographs)
CORE_KANJI_PREFERRED = {
    "日": "ひ",
    "声": "こえ",
    "下": "した",
    "年": "とし",
    "人": "ひと",
    "上": "うえ",
    "目": "め",
    "手": "て",
    "月": "つき",
    "気": "き",
    "水": "みず",
    "火": "ひ",
}

# Everyday colloquial words and interjections that should default to kana display
ALWAYS_KANA_HEADWORDS = {
    "ああ",
    "あー",
    "あぁ",
    "ああっ",
    "ええ",
    "うん",
    "うーん",
    "ありがとう",
    "さようなら",
    "おはよう",
    "こんにちは",
    "こんばんは",
}

# Exact JLPT tags for core vocabulary (used alongside kanji-based estimation)
CORE_WORD_JLPT: dict[str, list[str]] = {
    "食べる": ["N5"],
    "飲む": ["N5"],
    "読む": ["N5"],
    "見る": ["N5"],
    "行く": ["N5"],
    "来る": ["N5"],
    "話す": ["N5"],
    "聞く": ["N5"],
    "言う": ["N5"],
    "思う": ["N5"],
    "分かる": ["N5"],
    "わかる": ["N5"],
    "知る": ["N5"],
    "走る": ["N5"],
    "本": ["N5"],
    "日本語": ["N5"],
    "日本": ["N5"],
    "今日": ["N5"],
    "明日": ["N5"],
    "昨日": ["N5"],
    "人": ["N5"],
    "猫": ["N5"],
    "犬": ["N5"],
    "学校": ["N5"],
    "先生": ["N5"],
    "友達": ["N5"],
    "大丈夫": ["N5"],
    "世界": ["N4"],
    "本当": ["N4"],
    "魔法": ["N3"],
    "凄い": ["N3"],
}

BOUND_POS = frozenset(
    {
        "suffix",
        "counter",
        "prefix",
        "noun, used as a suffix",
        "noun, used as a prefix",
    }
)

JLPT_RANK = {"N5": 5, "N4": 4, "N3": 3, "N2": 2, "N1": 1}
RANK_TO_JLPT = {5: "N5", 4: "N4", 3: "N3", 2: "N2", 1: "N1"}


def download_file_with_fallback(urls: list[str], dest_path: Path) -> None:
    """Downloads a file with automatic fallback across mirrors and live progress tracking."""
    import requests
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Japanese-OCR-Dict-Importer/2.0"
    }

    last_error = None
    for url in urls:
        print(f"\nConnecting to {url}...")
        try:
            start_time = time.time()
            response = requests.get(url, headers=headers, stream=True, timeout=45, verify=False)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            chunk_size = 512 * 1024
            downloaded = 0

            with open(dest_path, "wb") as out_file:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        out_file.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            mb = downloaded / (1024 * 1024)
                            total_mb = total_size / (1024 * 1024)
                            print(
                                f"  Downloading: {mb:.1f} MB / {total_mb:.1f} MB ({percent:.1f}%)",
                                end="\r",
                            )
                        else:
                            mb = downloaded / (1024 * 1024)
                            print(f"  Downloading: {mb:.1f} MB...", end="\r")

            elapsed = time.time() - start_time
            print(f"\n  Download complete in {elapsed:.1f}s ({dest_path.name})")
            return
        except Exception as e:
            print(f"  Mirror failed ({e}), trying next mirror...")
            last_error = e

    raise RuntimeError(f"All download mirrors failed. Last error: {last_error}")


def _map_kanjidic_jlpt(raw_jlpt: str | None, grade: int | None) -> str | None:
    """Maps pre-2010 KANJIDIC2 4-level JLPT codes (1..4) to modern N1..N5."""
    if raw_jlpt == "4":
        return "N5"
    if raw_jlpt == "3":
        return "N4"
    if raw_jlpt == "2":
        return "N3" if grade in (1, 2, 3, 4) else "N2"
    if raw_jlpt == "1":
        return "N1"
    return None


def import_kanjidic(gz_path: Path, db: SQLiteDictionary) -> dict[str, str]:
    """Parses kanjidic2.xml.gz, populates SQLite `kanji`, and returns char->JLPT map."""
    print(f"\n[1/2] Parsing and indexing Kanji from {gz_path.name}...")
    start_time = time.time()

    db.close()
    conn = db._get_connection()
    conn.execute("PRAGMA synchronous=OFF;")

    batch: list[tuple[str, str]] = []
    batch_size = 2000
    count = 0
    kanji_jlpt_map: dict[str, str] = {}

    with gzip.open(gz_path, "rb") as f:
        context = ET.iterparse(f, events=("end",))
        for _event, elem in context:
            if elem.tag == "character":
                literal = elem.findtext("literal")
                if literal:
                    stroke_text = elem.findtext(".//stroke_count")
                    stroke_count = (
                        int(stroke_text) if stroke_text and stroke_text.isdigit() else None
                    )

                    grade_text = elem.findtext(".//grade")
                    grade = int(grade_text) if grade_text and grade_text.isdigit() else None

                    jlpt_text = elem.findtext(".//jlpt")
                    jlpt = _map_kanjidic_jlpt(jlpt_text, grade)
                    if jlpt:
                        kanji_jlpt_map[literal] = jlpt

                    unicode_val = elem.findtext(".//cp_value[@cp_type='ucs']") or ""

                    on_readings = [
                        r.text for r in elem.findall(".//reading[@r_type='ja_on']") if r.text
                    ]
                    kun_readings = [
                        r.text for r in elem.findall(".//reading[@r_type='ja_kun']") if r.text
                    ]
                    nanori = [n.text for n in elem.findall(".//nanori") if n.text]

                    # English meanings have no attribute in KANJIDIC2
                    meanings = [
                        m.text for m in elem.findall(".//meaning") if not m.attrib and m.text
                    ]

                    kanji_info = {
                        "kanji": literal,
                        "grade": grade,
                        "stroke_count": stroke_count,
                        "jlpt": jlpt,
                        "meanings": meanings[:8],
                        "on_readings": on_readings,
                        "kun_readings": kun_readings,
                        "name_readings": nanori,
                        "unicode": unicode_val.upper(),
                    }

                    batch.append((literal, json.dumps(kanji_info, ensure_ascii=False)))
                    count += 1

                    if len(batch) >= batch_size:
                        conn.executemany(
                            "INSERT OR REPLACE INTO kanji (character, data_json) VALUES (?, ?);",
                            batch,
                        )
                        conn.commit()
                        batch.clear()
                        print(f"  Indexed {count:,} Kanji characters...", end="\r")

                elem.clear()

    if batch:
        conn.executemany(
            "INSERT OR REPLACE INTO kanji (character, data_json) VALUES (?, ?);",
            batch,
        )
        conn.commit()

    conn.close()
    elapsed = time.time() - start_time
    print(f"\n  Indexed {count:,} Kanji in {elapsed:.1f}s.")
    return kanji_jlpt_map


def score_pri_tags(pri_tags: set[str]) -> int:
    """Computes priority points for a specific headword or reading's JMdict priority tags."""
    score = 0
    if any("ichi1" in p for p in pri_tags):
        score += 150
    if any("news1" in p for p in pri_tags):
        score += 100
    if any("spec1" in p or "gai1" in p for p in pri_tags):
        score += 70
    if any("ichi2" in p or "news2" in p or "spec2" in p or "gai2" in p for p in pri_tags):
        score += 35

    for p in pri_tags:
        if p.startswith("nf"):
            try:
                rank = int(p[2:])
                score += max(0, 50 - rank)
            except ValueError:
                pass
    return score


def _estimate_word_jlpt(
    key: str,
    primary_word: str,
    is_common: bool,
    is_particle: bool,
    pri_tags: set[str],
    kanji_jlpt_map: dict[str, str],
) -> list[str]:
    """Derives an approximate JLPT badge for common vocabulary words."""
    if key in CORE_WORD_JLPT:
        return CORE_WORD_JLPT[key]
    if primary_word in CORE_WORD_JLPT:
        return CORE_WORD_JLPT[primary_word]
    if not is_common:
        return []

    has_ichi1 = any("ichi1" in p for p in pri_tags)
    has_news1 = any("news1" in p for p in pri_tags)
    nf_ranks = []
    for p in pri_tags:
        if p.startswith("nf") and p[2:].isdigit():
            nf_ranks.append(int(p[2:]))
    min_nf = min(nf_ranks) if nf_ranks else 99

    kanji_chars = [
        ch for ch in primary_word if "\u4e00" <= ch <= "\u9fff" or "\u3400" <= ch <= "\u4dbf"
    ]
    if kanji_chars:
        if any(ch not in kanji_jlpt_map for ch in kanji_chars):
            return ["N1"] if has_ichi1 or has_news1 else []
        hardest = min(JLPT_RANK[kanji_jlpt_map[ch]] for ch in kanji_chars)
        if hardest >= 4 and min_nf > 24 and not has_ichi1:
            hardest = max(1, hardest - 1)
        elif hardest == 5 and (min_nf > 18 and not has_ichi1):
            hardest = 4
        return [RANK_TO_JLPT[hardest]]

    if is_particle and has_ichi1:
        return ["N5"]
    if has_ichi1 and min_nf <= 12:
        return ["N5"]
    if has_ichi1:
        return ["N4"]
    if has_news1:
        return ["N3"]
    return []


def _merge_entry(
    words_dict: dict[str, dict[str, Any]],
    key: str,
    candidate: dict[str, Any],
    is_rare_form: bool,
) -> None:
    """
    Order-independent homograph merger:
    - Authentic written headwords (or pure-kana/uk/particle entries) always displace aliases.
    - Higher-scoring entries become primary and retain non-duplicate secondary readings/senses.
    - Non-rare lower-scoring homographs contribute secondary readings/senses without hijacking primary metadata.
    """
    existing = words_dict.get(key)
    pref = CORE_KANJI_PREFERRED.get(key)

    if existing is None:
        if pref:
            candidate["readings"].sort(key=lambda x: 0 if x["reading"] == pref else 1)
        words_dict[key] = candidate
        return

    cand_written = candidate.get("is_written_headword", False)
    exist_written = existing.get("is_written_headword", False)

    if cand_written and not exist_written:
        if pref:
            candidate["readings"].sort(key=lambda x: 0 if x["reading"] == pref else 1)
        words_dict[key] = candidate
        return

    if not cand_written and exist_written:
        return

    if candidate["score"] > existing["score"]:
        merged_readings = list(candidate["readings"])
        seen_r = {r["reading"] for r in merged_readings}
        for old_r in existing["readings"]:
            if old_r["reading"] not in seen_r:
                seen_r.add(old_r["reading"])
                merged_readings.append(old_r)
        if pref:
            merged_readings.sort(key=lambda x: 0 if x["reading"] == pref else 1)
        candidate["readings"] = merged_readings[:6]

        merged_senses = list(candidate["senses"][:4])
        seen_s = {tuple(s["meanings"]) for s in merged_senses}
        for old_s in existing["senses"]:
            sig = tuple(old_s["meanings"])
            if sig not in seen_s:
                seen_s.add(sig)
                merged_senses.append(old_s)
        candidate["senses"] = merged_senses[:6]
        candidate["is_common"] = candidate["is_common"] or existing["is_common"]
        if not candidate["jlpt"] and existing.get("jlpt"):
            candidate["jlpt"] = existing["jlpt"]
        words_dict[key] = candidate
    elif not is_rare_form and cand_written:
        seen_r = {r["reading"] for r in existing["readings"]}
        for new_r in candidate["readings"]:
            if new_r["reading"] not in seen_r:
                seen_r.add(new_r["reading"])
                existing["readings"].append(new_r)
        if pref:
            existing["readings"].sort(key=lambda x: 0 if x["reading"] == pref else 1)
        existing["readings"] = existing["readings"][:6]

        seen_s = {tuple(s["meanings"]) for s in existing["senses"]}
        for new_s in candidate["senses"]:
            sig = tuple(new_s["meanings"])
            if sig not in seen_s:
                seen_s.add(sig)
                existing["senses"].append(new_s)
        existing["senses"] = existing["senses"][:6]
        existing["is_common"] = existing["is_common"] or candidate["is_common"]


def import_jmdict(
    gz_path: Path, db: SQLiteDictionary, kanji_jlpt_map: dict[str, str] | None = None
) -> None:
    """Parses JMdict_e.gz and populates the SQLite `words` table with priority merging."""
    print(f"\n[2/2] Parsing and indexing Vocabulary from {gz_path.name} (~185,000+ entries)...")
    start_time = time.time()
    kanji_jlpt_map = kanji_jlpt_map or {}

    words_dict: dict[str, dict[str, Any]] = {}
    count = 0

    with gzip.open(gz_path, "rb") as f:
        context = ET.iterparse(f, events=("end",))
        for _event, elem in context:
            if elem.tag != "entry":
                continue

            count += 1
            ent_seq_str = elem.findtext("ent_seq") or ""
            ent_seq = int(ent_seq_str) if ent_seq_str.isdigit() else 9999999

            k_eles: list[dict[str, Any]] = []
            for k_el in elem.findall("./k_ele"):
                keb = k_el.findtext("keb")
                if not keb:
                    continue
                ke_pri = [p.text for p in k_el.findall("ke_pri") if p.text]
                ke_inf = [i.text.lower() for i in k_el.findall("ke_inf") if i.text]
                is_so = any("search-only" in inf for inf in ke_inf)
                is_rare = any(
                    x in inf
                    for inf in ke_inf
                    for x in ("rarely used", "out-dated", "obsolete", "irregular")
                )
                k_eles.append({"keb": keb, "ke_pri": ke_pri, "is_so": is_so, "is_rare": is_rare})

            r_eles: list[dict[str, Any]] = []
            for r_el in elem.findall("./r_ele"):
                reb = r_el.findtext("reb")
                if not reb:
                    continue
                re_pri = [p.text for p in r_el.findall("re_pri") if p.text]
                re_inf = [i.text.lower() for i in r_el.findall("re_inf") if i.text]
                is_so = any("search-only" in inf for inf in re_inf)
                is_rare = any(
                    x in inf
                    for inf in re_inf
                    for x in ("rarely used", "out-dated", "obsolete", "irregular")
                )
                r_eles.append({"reb": reb, "re_pri": re_pri, "is_so": is_so, "is_rare": is_rare})

            valid_kebs = [k for k in k_eles if not k["is_so"]]
            valid_rebs = [r for r in r_eles if not r["is_so"]] or r_eles

            # Parse senses with JMdict POS inheritance from preceding sense
            senses: list[dict[str, Any]] = []
            sense_miscs: list[list[str]] = []
            prev_pos: list[str] = []
            for s in elem.findall("./sense"):
                pos_list = [p.text for p in s.findall("pos") if p.text]
                if pos_list:
                    prev_pos = pos_list
                else:
                    pos_list = list(prev_pos)
                misc_list = [m.text for m in s.findall("misc") if m.text]
                glosses = [g.text for g in s.findall("gloss") if g.text]
                if glosses:
                    senses.append(
                        {
                            "pos": pos_list[:3],
                            "meanings": glosses[:6],
                            "tags": [],
                        }
                    )
                    sense_miscs.append(misc_list)

            if valid_rebs and senses:
                primary_reading = valid_rebs[0]["reb"]
                is_pure_kana = len(valid_kebs) == 0

                first_pos = [p.lower() for p in senses[0]["pos"]]
                first_misc = [m.lower() for m in sense_miscs[0]]

                is_particle = any(p == "particle" for p in first_pos)
                is_uk = any("kana alone" in m or m == "uk" for m in first_misc) or (
                    primary_reading in ALWAYS_KANA_HEADWORDS
                )
                is_bound = bool(first_pos) and all(p in BOUND_POS for p in first_pos)
                is_rare_sense = any(
                    x in m
                    for m in first_misc
                    for x in ("rare", "archaic", "archaism", "obsolete", "out-dated")
                )
                has_content = any(
                    any(
                        x in p
                        for x in (
                            "noun",
                            "verb",
                            "adjective",
                            "adverb",
                            "interjection",
                            "pronoun",
                            "rentaishi",
                            "adjectival",
                            "numeric",
                            "expression",
                        )
                    )
                    for p in first_pos
                )

                base_mod = 0
                if ent_seq < 2000000:
                    base_mod += 50 + max(0, (1600000 - ent_seq) // 15000)
                base_mod += min(len(senses) * 15, 120)
                if is_rare_sense:
                    base_mod -= 150
                if is_bound and not is_particle:
                    base_mod -= 120
                elif has_content:
                    base_mod += 40

                all_pri_tags = {p for k in valid_kebs for p in k["ke_pri"]} | {
                    p for r in valid_rebs for p in r["re_pri"]
                }
                is_common = bool(all_pri_tags)
                reb_strings = [r["reb"] for r in valid_rebs]
                primary_word = (
                    primary_reading
                    if (is_particle or is_uk or is_pure_kana or not valid_kebs)
                    else valid_kebs[0]["keb"]
                )

                # 1. Index authentic Kanji headwords
                for k_idx, k_info in enumerate(valid_kebs):
                    k = k_info["keb"]
                    pri_set = set(k_info["ke_pri"])
                    pri_score = score_pri_tags(pri_set)
                    if k_idx == 0 and not pri_set:
                        pri_score = score_pri_tags(set(valid_rebs[0]["re_pri"])) // 2

                    score = pri_score + base_mod + (60 if k_idx == 0 else -35 * k_idx)
                    if k_info["is_rare"]:
                        score -= 250
                    if is_uk:
                        score -= 90

                    kanji_slug = (
                        k if (k_idx == 0 or not k_info["is_rare"]) else valid_kebs[0]["keb"]
                    )
                    readings = [{"word": k, "reading": r} for r in reb_strings]
                    jlpt = _estimate_word_jlpt(
                        k,
                        kanji_slug,
                        is_common,
                        is_particle,
                        pri_set or all_pri_tags,
                        kanji_jlpt_map,
                    )

                    candidate = {
                        "query": k,
                        "slug": kanji_slug,
                        "score": score,
                        "is_common": is_common,
                        "is_written_headword": True,
                        "is_pure_kana": is_pure_kana,
                        "is_uk": is_uk,
                        "jlpt": jlpt,
                        "readings": readings,
                        "senses": senses[:5],
                    }
                    _merge_entry(words_dict, k, candidate, is_rare_form=k_info["is_rare"])

                # 2. Index Kana readings (authentic headwords when particle/uk/pure_kana, else alias)
                is_authentic_kana = is_particle or is_uk or is_pure_kana or not valid_kebs
                for r_idx, r_info in enumerate(valid_rebs):
                    r = r_info["reb"]
                    pri_set = set(r_info["re_pri"])
                    score = score_pri_tags(pri_set) + base_mod + (40 if r_idx == 0 else -25 * r_idx)
                    if r_info["is_rare"]:
                        score -= 200
                    if is_particle:
                        score += 350
                    elif is_uk or is_pure_kana:
                        score += 180

                    kana_slug = primary_word
                    if is_authentic_kana:
                        readings = [{"word": primary_word, "reading": rb} for rb in reb_strings]
                        # Ensure the queried kana reading comes first
                        readings.sort(key=lambda x: 0 if x["reading"] == r else 1)
                    else:
                        readings = [{"word": primary_word, "reading": r}]

                    jlpt = _estimate_word_jlpt(
                        r,
                        kana_slug,
                        is_common,
                        is_particle,
                        pri_set or all_pri_tags,
                        kanji_jlpt_map,
                    )

                    candidate = {
                        "query": r,
                        "slug": kana_slug,
                        "score": score,
                        "is_common": is_common,
                        "is_written_headword": is_authentic_kana and (r_idx == 0 or is_pure_kana),
                        "is_pure_kana": is_pure_kana,
                        "is_uk": is_uk,
                        "jlpt": jlpt,
                        "readings": readings,
                        "senses": senses[:5],
                    }
                    _merge_entry(words_dict, r, candidate, is_rare_form=r_info["is_rare"])

            elem.clear()

    print(f"  Aggregated {count:,} raw entries into {len(words_dict):,} prioritized keywords.")
    db.close()
    conn = db._get_connection()
    conn.execute("PRAGMA synchronous=OFF;")
    conn.execute("DELETE FROM words;")
    conn.commit()

    batch: list[tuple[str, str, str]] = []
    batch_size = 10000
    for k, v in words_dict.items():
        slug = v.get("slug", k)
        payload = json.dumps(v, ensure_ascii=False)
        batch.append((k, slug, payload))
        if len(batch) >= batch_size:
            conn.executemany(
                "INSERT INTO words (keyword, slug, data_json) VALUES (?, ?, ?);", batch
            )
            conn.commit()
            batch.clear()

    if batch:
        conn.executemany("INSERT INTO words (keyword, slug, data_json) VALUES (?, ?, ?);", batch)
        conn.commit()

    conn.close()
    elapsed = time.time() - start_time
    print(f"\n  Indexed {count:,} words in {elapsed:.1f}s.")


def main() -> None:
    print("=" * 65)
    print(" Japanese Pop-up Dictionary - Offline JMdict and Kanji Importer")
    print("=" * 65)

    db = SQLiteDictionary()
    data_cache = Path(__file__).resolve().parent / "cache"
    data_cache.mkdir(parents=True, exist_ok=True)

    jmdict_gz = data_cache / "JMdict_e.gz"
    kanjidic_gz = data_cache / "kanjidic2.xml.gz"

    # Step 1: Download files if not already cached
    if not jmdict_gz.exists():
        download_file_with_fallback(JMDICT_URLS, jmdict_gz)
    else:
        print(f"Using existing cached file: {jmdict_gz}")

    if not kanjidic_gz.exists():
        download_file_with_fallback(KANJIDIC_URLS, kanjidic_gz)
    else:
        print(f"Using existing cached file: {kanjidic_gz}")

    # Step 2: Index into SQLite
    kanji_jlpt_map = import_kanjidic(kanjidic_gz, db)
    import_jmdict(jmdict_gz, db, kanji_jlpt_map=kanji_jlpt_map)

    # Step 3: Print final stats
    stats = db.get_stats()
    db.close()
    print("\n" + "=" * 65)
    print(" Offline Dictionary Build Complete")
    print(f"   Database File: {DB_PATH}")
    print(f"   Total Indexed Words: {stats['words']:,}")
    print(f"   Total Indexed Kanji: {stats['kanji']:,}")
    print("=" * 65)
    print("Local database is ready for offline lookups.")


if __name__ == "__main__":
    main()
