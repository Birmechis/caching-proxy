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

    def set(self, key, value, headers, status_code, etag=None):

        headers_lower = {k.lower(): v for k, v in headers.items()}
        cache_control = headers_lower.get("cache-control", "").lower()

        if 'no-store' in cache_control or 'no-cache' in cache_control or 'private' in cache_control:
            print(f"[CACHE] Skipped due to Cache-Control rules: {key}")
            return "MISS"

        if status_code != 200:
            print(f"[CACHE] Skipped non-200 status code ({status_code}): {key}")
            return "MISS"

        ttl_to_use = self.ttl
        for directive in cache_control.split(","):
            directive = directive.strip()
            if directive.startswith("max-age"):
                try:
                    ttl = int(directive.split("=")[1])
                    ttl_to_use = ttl
                except (ValueError, IndexError):
                    pass

        with self.lock:
            if key in self.cache:
                del self.cache[key]

            elif len(self.cache) >= self.max_size:
                oldest_key,_ = self.cache.popitem(last=False)
                print(f"[CACHE] Evicted oldest entry due to capacity limit: {oldest_key}")

            expires_at = time.time() + ttl_to_use
            self.cache[key] = {
                "response": value,
                "expires_at": expires_at,
                "etag": etag
            }

            print(f"[CACHE] Stored: {key} (TTL: {ttl_to_use}s)")
            return "MISS (CACHED)"

    def get_etag(self, key):
        with self.lock:
            if key not in self.cache:
                return None

            entry = self.cache[key]

            if time.time() >= entry["expires_at"]:
                del self.cache[key]
                return None

            return entry["etag"]

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