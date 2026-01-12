import threading
import requests
import logging


class JishoAPIHandler:
    """
    Handles interaction with the Jisho API to fetch Japanese word information.

    Attributes:
        local_dict_cache (dict): A local cache to store fetched word information for faster retrieval.
        cache_lock (threading.Lock): A lock to ensure thread-safe access to the cache.
    """

    def __init__(self):
        self.local_dict_cache = {}
        self.cache_lock = threading.Lock()

    def fetch_jisho_info(self, word):
        """
        Fetches word information from the Jisho API, utilizing a local cache.

        Args:
            word (str): The Japanese word to look up.

        Returns:
            dict: A dictionary containing the word's readings and meanings,
                  or None if the word is not found or an error occurs.
        """
        with self.cache_lock:
            if word in self.local_dict_cache:
                return self.local_dict_cache[word]
        try:
            response = requests.get(f"https://jisho.org/api/v1/search/words?keyword={word}")
            response.raise_for_status()
            data = response.json()
            if data['data']:
                entry = data['data'][0]
                readings = [reading['reading'] for reading in entry['japanese']]
                meanings = entry['senses'][0]['english_definitions']
                word_info = {'readings': readings, 'meanings': meanings}
                with self.cache_lock:
                    self.local_dict_cache[word] = word_info
                return word_info
            else:
                logging.info(f"-> Word '{word}' not found in Jisho API")
                return None
        except requests.exceptions.RequestException as e:
            logging.error(f"-> Error fetching Jisho data for '{word}': {e}")
            if e.response is not None and e.response.status_code == 404:
                return None
            else:
                return None
