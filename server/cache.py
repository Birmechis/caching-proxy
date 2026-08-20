import time

class Cache:
    def __init__(self, ttl=15):
        self.storage = {}
        self.ttl = ttl
    def get(self,key):
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
        expires_at = time.time() + self.ttl

        self.storage[key] = {
            "response": value,
            "expires_at": expires_at
        }

        print(
            f"[CACHE] Stored: {key}"
            f"(TTL: {self.ttl}s)"
        )
    def has(self, key):
        return self.get(key) is not None