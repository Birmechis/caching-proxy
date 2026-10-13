import threading
import time
from collections import OrderedDict


class Cache:
    def __init__(self, ttl=15, max_size=100):
        self.cache = OrderedDict()
        self.ttl = ttl
        self.max_size = max_size
        self.lock = threading.Lock()
        self.cache_hits = 0
        self.cache_misses = 0

    @staticmethod
    def _get_cache_control(headers):
        for key, value in headers.items():
            if key.lower() == "cache-control":
                return value.lower()
        return ""

    def _ttl_from_headers(self, headers):
        ttl = self.ttl
        cache_control = self._get_cache_control(headers)

        for directive in cache_control.split(","):
            directive = directive.strip()

            if directive.startswith("max-age="):
                try:
                    ttl = max(0, int(directive.split("=", 1)[1].strip().strip('"')))
                except ValueError:
                    pass

        return ttl

    def get_entry(self, key):
        """Return cache metadata, retaining expired ETag entries for revalidation."""
        with self.lock:
            entry = self.cache.get(key)

            if entry is None:
                self.cache_misses += 1
                return None

            expired = time.time() >= entry["expires_at"]

            if expired and not entry.get("etag"):
                del self.cache[key]
                self.cache_misses += 1
                return None

            if expired:
                self.cache_misses += 1
                return {**entry, "stale": True}

            self.cache_hits += 1
            self.cache.move_to_end(key)

            return {**entry, "stale": False}

    def get(self, key):
        """Preserve the original get() interface used by existing tests."""
        entry = self.get_entry(key)

        if entry is None or entry["stale"]:
            return None

        return entry["response"]

    def set(self, key, value, headers=None, status_code=200):
        headers = headers or {}
        cache_control = self._get_cache_control(headers)

        directives = {
            directive.strip().split("=", 1)[0].strip()
            for directive in cache_control.split(",")
        }

        if (
            "no-store" in directives
            or "no-cache" in directives
            or "private" in directives
        ):
            print(f"[CACHE] Skipped due to Cache-Control rules: {key}")
            return "MISS"

        if status_code != 200:
            print(f"[CACHE] Skipped non-200 status code ({status_code}): {key}")
            return "MISS"

        ttl_to_use = self._ttl_from_headers(headers)

        if ttl_to_use == 0:
            print(f"[CACHE] Not storing immediately-expired response: {key}")
            return "MISS"

        etag = next(
            (
                value
                for name, value in headers.items()
                if name.lower() == "etag"
            ),
            None,
        )

        with self.lock:
            if key not in self.cache and len(self.cache) >= self.max_size:
                oldest_key, _ = self.cache.popitem(last=False)
                print(f"[CACHE] Evicted oldest entry: {oldest_key}")

            self.cache[key] = {
                "response": value,
                "headers": dict(headers),
                "status_code": status_code,
                "etag": etag,
                "expires_at": time.time() + ttl_to_use,
            }
            self.cache.move_to_end(key)

        print(f"[CACHE] Stored: {key} (TTL: {ttl_to_use}s)")
        return "MISS (CACHED)"

    def refresh(self, key, headers=None):
        """Refresh a stale entry after the origin returns 304 Not Modified."""
        headers = headers or {}

        with self.lock:
            entry = self.cache.get(key)

            if entry is None:
                return

            # A 304 may provide updated caching metadata.
            for name, value in headers.items():
                if name.lower() in ("etag", "cache-control", "expires"):
                    existing_name = next(
                        (
                            old_name
                            for old_name in entry["headers"]
                            if old_name.lower() == name.lower()
                        ),
                        name,
                    )
                    entry["headers"][existing_name] = value

            entry["etag"] = next(
                (
                    value
                    for name, value in entry["headers"].items()
                    if name.lower() == "etag"
                ),
                entry.get("etag"),
            )

            ttl = self._ttl_from_headers(entry["headers"])
            entry["expires_at"] = time.time() + ttl
            self.cache.move_to_end(key)

    def stats(self):
        with self.lock:
            total = self.cache_hits + self.cache_misses
            hit_rate = self.cache_hits / total * 100 if total else 0

            return {
                "hits": self.cache_hits,
                "misses": self.cache_misses,
                "hit_rate": round(hit_rate, 2),
            }

    def has(self, key):
        return self.get(key) is not None