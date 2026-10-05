import threading
import time
from collections import OrderedDict


class Cache:
    def __init__(self, ttl=15, max_size=100):
        self.cache = OrderedDict()
        self.ttl = ttl
        self.max_size = max_size
        self.lock = threading.Lock()
        self.cache_hits= 0
        self.cache_misses= 0
    def get(self,key):
        with self.lock:
            if key not in self.cache:
                self.cache_misses += 1
                return None
            entry = self.cache[key]
            response = entry["response"]
            expires_at = entry["expires_at"]

            if time.time() >= expires_at:
                print(f"[CACHE] expired: {key}")
                del self.cache[key]
                self.cache_misses += 1
                return None

            self.cache_hits += 1
            self.cache.move_to_end(key)
            return response

    def set(self, key, value):
        with self.lock:
            expires_at = time.time() + self.ttl

            self.cache[key] = {
                "response": value,
                "expires_at": expires_at
            }

            if len(self.cache) > self.max_size:
                self.cache.popitem(last=False)

            print(
                f"[CACHE] Stored: {key}"
                f"(TTL: {self.ttl}s)"
            )

    def stats(self):
        total = self.cache_hits + self.cache_misses

        hit_rate = (
            self.cache_hits/total * 100
            if total > 0 else 0
        )

        return {
            "hits": self.cache_hits,
            "misses": self.cache_misses,
            "hit_rate": round(hit_rate, 2)
        }

    def has(self, key):
        return self.get(key) is not None