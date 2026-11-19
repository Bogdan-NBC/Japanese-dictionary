import contextlib
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from urllib.parse import quote

import lxml.html
import requests
from db_dictionary import SQLiteDictionary

logger = logging.getLogger(__name__)

KANJI_REGEX = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")


class JishoAPIHandler:
    """
    Hybrid Local-First Dictionary Engine.
    Queries a high-performance local SQLite database (< 0.01 ms) first.
    On a cache miss, transparently falls back to Jisho.org / Kanjiapi.dev
    and persists the result into SQLite for permanent offline access.
    """

    def __init__(self, db: SQLiteDictionary | None = None) -> None:
        self.db = db if db is not None else SQLiteDictionary()
        self.word_cache: dict[str, dict[str, Any]] = {}
        self.kanji_cache: dict[str, dict[str, Any]] = {}
        self.names_cache: dict[str, list[dict[str, str]]] = {}
        self.cache_lock = threading.Lock()

        # Persistent HTTP connection pooling for fast fallback requests
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                )
            }
        )
        self.executor = ThreadPoolExecutor(max_workers=6)

    def shutdown(self) -> None:
        """Immediately terminates background worker pools and closes persistent HTTP/DB connections."""
        with contextlib.suppress(Exception):
            self.executor.shutdown(wait=False, cancel_futures=True)
        with contextlib.suppress(Exception):
            self.session.close()
        with contextlib.suppress(Exception):
            self.db.close()

    @staticmethod
    def extract_ordered_kanji(text: str) -> list[str]:
        """Extracts unique Kanji characters while preserving their exact order in the word."""
        return list(dict.fromkeys(KANJI_REGEX.findall(text or "")))

    def lookup_candidates(self, candidates: list[str]) -> dict[str, Any] | None:
        """
        Tries a prioritized list of word candidates (e.g., [base_form, surface_form])
        using local-first two-tier resolution so local SQLite entries are resolved
        before any candidate incurs remote network fallback latency.
        """
        clean_candidates: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            clean = candidate.strip()
            if clean and clean not in seen:
                seen.add(clean)
                clean_candidates.append(clean)

        if not clean_candidates:
            return None

        local_candidates: list[str] = []
        remote_candidates: list[str] = []
        for clean in clean_candidates:
            with self.cache_lock:
                in_mem = clean in self.word_cache
            if in_mem:
                local_candidates.append(clean)
                continue
            local_word = self.db.get_word(clean)
            if local_word is not None:
                with self.cache_lock:
                    self.word_cache[clean] = local_word
                local_candidates.append(clean)
            else:
                remote_candidates.append(clean)

        for clean in local_candidates + remote_candidates:
            info = self.fetch_jisho_info(clean)
            if info:
                return info
        return None

    def fetch_jisho_info(self, word: str) -> dict[str, Any] | None:
        """
        Fetches detailed word information.
        1. Checks in-memory hot cache.
        2. Checks local indexed SQLite database (< 0.01 ms).
        3. Falls back to Jisho API over HTTPS and caches result to SQLite.
        """
        if not word:
            return None

        # 1. In-memory hot cache
        with self.cache_lock:
            if word in self.word_cache:
                return self.word_cache[word]

        # 2. Local SQLite persistent database
        local_word = self.db.get_word(word)
        if local_word:
            with self.cache_lock:
                self.word_cache[word] = local_word
            return local_word

        # 3. Remote network fallback (Jisho API)
        try:
            url = f"https://jisho.org/api/v1/search/words?keyword={quote(word)}"
            response = self.session.get(url, timeout=4)
            response.raise_for_status()
            data = response.json()

            if data.get("data"):
                entries = data["data"]
                # Prioritize an exact match that is marked common
                entry = entries[0]
                for e in entries:
                    is_exact = any(
                        j.get("word") == word or j.get("reading") == word
                        for j in e.get("japanese", [])
                    )
                    if is_exact and e.get("is_common"):
                        entry = e
                        break

                readings = [
                    {
                        "word": item.get("word", ""),
                        "reading": item.get("reading", ""),
                    }
                    for item in entry.get("japanese", [])
                ]

                jlpt_tags = [tag.replace("jlpt-n", "N").upper() for tag in entry.get("jlpt", [])]

                senses = [
                    {
                        "pos": sense.get("parts_of_speech", []),
                        "meanings": sense.get("english_definitions", []),
                        "tags": sense.get("tags", []),
                    }
                    for sense in entry.get("senses", [])
                ]

                word_info: dict[str, Any] = {
                    "query": word,
                    "slug": entry.get("slug", word),
                    "readings": readings,
                    "is_common": entry.get("is_common", False),
                    "jlpt": jlpt_tags,
                    "senses": senses,
                }

                # Persist to local SQLite and update in-memory cache
                self.db.save_word(word, word_info)
                with self.cache_lock:
                    self.word_cache[word] = word_info
                return word_info

            logger.info("Word '%s' not found in Jisho API", word)
            return None
        except Exception as e:
            logger.error("Error fetching Jisho data for '%s': %s", word, e)
            return None

    def fetch_kanji_info(self, kanji_char: str) -> dict[str, Any] | None:
        """
        Fetches detailed information for a single Kanji character.
        1. Checks in-memory hot cache.
        2. Checks local indexed SQLite database (< 0.01 ms).
        3. Falls back to Kanjiapi.dev over HTTPS and caches result to SQLite.
        """
        if not kanji_char:
            return None

        # 1. In-memory hot cache
        with self.cache_lock:
            if kanji_char in self.kanji_cache:
                return self.kanji_cache[kanji_char]

        # 2. Local SQLite persistent database
        local_kanji = self.db.get_kanji(kanji_char)
        if local_kanji:
            with self.cache_lock:
                self.kanji_cache[kanji_char] = local_kanji
            return local_kanji

        # 3. Remote network fallback (Kanjiapi.dev)
        try:
            url = f"https://kanjiapi.dev/v1/kanji/{quote(kanji_char)}"
            response = self.session.get(url, timeout=4)
            if response.status_code == 200:
                data = response.json()
                kanji_info = {
                    "kanji": data.get("kanji"),
                    "grade": data.get("grade"),
                    "stroke_count": data.get("stroke_count"),
                    "jlpt": f"N{data.get('jlpt')}" if data.get("jlpt") else None,
                    "meanings": data.get("meanings", []),
                    "on_readings": data.get("on_readings", []),
                    "kun_readings": data.get("kun_readings", []),
                    "name_readings": data.get("name_readings", []),
                    "unicode": data.get("unicode", "").upper(),
                }
                # Persist to local SQLite and update in-memory cache
                self.db.save_kanji(kanji_char, kanji_info)
                with self.cache_lock:
                    self.kanji_cache[kanji_char] = kanji_info
                return kanji_info
            return None
        except Exception as e:
            logger.error("Error fetching Kanji API for '%s': %s", kanji_char, e)
            return None

    def fetch_kanji_list(self, text: str) -> list[dict[str, Any]]:
        """
        Extracts all unique Kanji from `text` in reading order and fetches their
        details concurrently using a thread pool.
        """
        kanji_chars = self.extract_ordered_kanji(text)
        if not kanji_chars:
            return []

        futures = [self.executor.submit(self.fetch_kanji_info, ch) for ch in kanji_chars]
        results: list[dict[str, Any]] = []
        for future in futures:
            info = future.result()
            if info:
                results.append(info)
        return results

    def scrape_names_info(self, word: str) -> list[dict[str, str]]:
        """
        Fetches name definitions for a given keyword.
        1. Checks in-memory hot cache.
        2. Checks local indexed SQLite database.
        3. Falls back to scraping Jisho #names and caches result to SQLite.
        """
        if not word:
            return []

        # 1. In-memory hot cache
        with self.cache_lock:
            if word in self.names_cache:
                return self.names_cache[word]

        # 2. Local SQLite persistent database
        local_names = self.db.get_names(word)
        if local_names is not None:
            with self.cache_lock:
                self.names_cache[word] = local_names
            return local_names

        # 3. Remote network fallback (Jisho #names)
        try:
            url = f"https://jisho.org/search/{quote(word)}%23names"
            response = self.session.get(url, timeout=4)
            if response.status_code != 200:
                return []

            doc = lxml.html.fromstring(response.text)
            names_block = doc.xpath('//div[@class="names_block"]')
            if not names_block:
                self.db.save_names(word, [])
                with self.cache_lock:
                    self.names_cache[word] = []
                return []

            concepts = names_block[0].xpath('.//div[contains(@class, "concept_light")]')
            names_list: list[dict[str, str]] = []

            for concept in concepts:
                readings_elem = concept.xpath('.//div[contains(@class, "concept_light-readings")]')
                if not readings_elem:
                    continue
                readings_text = readings_elem[0].text_content().strip()
                lines = [line.strip() for line in readings_text.split("\n") if line.strip()]
                if not lines:
                    continue
                reading = lines[0]
                kanji = ""
                if len(lines) > 1:
                    kanji_part = lines[1]
                    if kanji_part.startswith("【") and kanji_part.endswith("】"):
                        kanji = kanji_part[1:-1]

                tags_elem = concept.xpath('.//div[@class="meaning-tags"]')
                tags = tags_elem[0].text_content().strip() if tags_elem else ""

                meaning_elem = concept.xpath('.//span[@class="meaning-meaning"]')
                meaning = meaning_elem[0].text_content().strip() if meaning_elem else ""

                if not tags and not meaning:
                    continue

                names_list.append(
                    {
                        "kanji": kanji or word,
                        "reading": reading,
                        "tags": tags,
                        "meaning": meaning,
                    }
                )

            # Persist to local SQLite and update in-memory cache
            self.db.save_names(word, names_list)
            with self.cache_lock:
                self.names_cache[word] = names_list
            return names_list

        except Exception as e:
            logger.error("Error scraping Jisho names for '%s': %s", word, e)
            return []
