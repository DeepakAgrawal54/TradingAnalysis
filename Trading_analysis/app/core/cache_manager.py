# app/core/cache.py
import pickle
from datetime import datetime, timedelta
import threading
import os
from typing import Any, Optional

class CacheManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, filename: str = 'cache.pkl'):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.filename = filename
                cls._instance.cache = {}
                cls._instance.lock = threading.Lock()
                cls._instance._load_cache()
            return cls._instance

    def _load_cache(self) -> None:
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'rb') as f:
                    self.cache = pickle.load(f)
                # Clean expired entries on load
                self._clean_expired()
            except Exception as e:
                print(f"Error loading cache: {str(e)}")
                self.cache = {}

    def _save_cache(self) -> None:
            with open(self.filename, 'wb') as f:
                pickle.dump(self.cache, f)



    def _clean_expired(self) -> None:
        now = datetime.now()
        expired_keys = [
            key for key, value in self.cache.items() 
            if now >= value['expiry']
        ]
        for key in expired_keys:
            del self.cache[key]

    def get(self, key: str) -> Optional[Any]:
        self._clean_expired()
        entry = self.cache.get(key)
        if entry and datetime.now() < entry['expiry']:
            return entry['data']
        return None

    def set(self, key: str, data: Any, ttl: int) -> None:
        with self.lock:
            self.cache[key] = {
                'data': data,
                'expiry': datetime.now() + timedelta(seconds=ttl)
            }
            self._save_cache()

    def delete(self, key: str) -> None:
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                self._save_cache()

    def clear(self) -> None:
        with self.lock:
            self.cache = {}
            self._save_cache()

    def get_all_keys(self) -> list[str]:
        self._clean_expired()
        return list(self.cache.keys())