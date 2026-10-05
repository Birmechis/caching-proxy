import threading
import time
from collections import OrderedDict


class Cache:
    def __init__(self, ttl=15, max_size=100):
        self.cache = OrderedDict()
        self.storage = {}
        self.ttl = ttl
        self.max_size = max_size
        self.lock = threading.Lock()
    def get(self,key):
        with self.lock:
            if key not in self.storage:
                return None
            entry = self.storage[key]
            response = entry["response"]
            expires_at = entry["expires_at"]

            if time.time() >= expires_at:
                print(f"[CACHE] expired: {key}")
                del self.storage[key]
                return None
            return response

    def set(self, key, value):
        with self.lock:
            expires_at = time.time() + self.ttl

            self.storage[key] = {
                "response": value,
                "expires_at": expires_at
            }

            if len(self.storage) > self.max_size:
                self.cache.popitem(last=False)

            print(
                f"[CACHE] Stored: {key}"
                f"(TTL: {self.ttl}s)"
            )

    def has(self, key):
        return self.get(key) is not None