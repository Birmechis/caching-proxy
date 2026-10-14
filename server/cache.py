
import pickle
import sqlite3
import threading
import time
from contextlib import closing


class Cache:
    def __init__(self, ttl=15, max_size=100, db_path="app_cache.db"):
        self.db_path = str(db_path)
        self.ttl = ttl
        self.max_size = max(1, int(max_size))

        self.lock = threading.Lock()
        self.cache_hits = 0
        self.cache_misses = 0

        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path, timeout=5)

    def _init_db(self):
        with closing(self._connect()) as conn:
            conn.execute("PRAGMA journal_mode=WAL")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS http_cache (
                    cache_key TEXT PRIMARY KEY,
                    value BLOB,
                    headers BLOB NOT NULL,
                    status_code INTEGER NOT NULL,
                    etag TEXT,
                    response BLOB NOT NULL,
                    expires_at REAL NOT NULL,
                    last_accessed REAL NOT NULL
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_http_cache_last_accessed
                ON http_cache(last_accessed)
            """)

            conn.commit()

    @staticmethod
    def _get_header(headers, name):
        for key, value in headers.items():
            if key.lower() == name.lower():
                return value

        return None

    @classmethod
    def _get_cache_control(cls, headers):
        value = cls._get_header(headers, "cache-control")
        return value.lower() if value else ""

    def _ttl_from_headers(self, headers):
        ttl = self.ttl
        cache_control = self._get_cache_control(headers)

        for directive in cache_control.split(","):
            directive = directive.strip()

            if directive.startswith("max-age="):
                try:
                    ttl = max(
                        0,
                        int(
                            directive.split("=", 1)[1]
                            .strip()
                            .strip('"')
                        ),
                    )
                except ValueError:
                    pass

        return ttl

    @staticmethod
    def _serialize_value(value):
        return pickle.dumps(value)

    @staticmethod
    def _response_bytes(value):
        """
        HTTP proxy responses are stored as bytes so they can be
        sent directly to the client.
        """
        if isinstance(value, bytes):
            return value

        if isinstance(value, bytearray):
            return bytes(value)

        if isinstance(value, str):
            return value.encode("utf-8")

        raise TypeError("Cached HTTP responses must be bytes or strings")

    def get_entry(self, key):
        """
        Return cached metadata.

        Fresh entries are cache hits.
        Expired entries with an ETag are retained for revalidation.
        Expired entries without an ETag are deleted.
        """
        now = time.time()

        with self.lock:
            with closing(self._connect()) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT response, headers, status_code,
                           etag, expires_at
                    FROM http_cache
                    WHERE cache_key = ?
                """, (key,))

                row = cursor.fetchone()

                if row is None:
                    self.cache_misses += 1
                    return None

                (
                    response,
                    headers_blob,
                    status_code,
                    etag,
                    expires_at,
                ) = row

                headers = pickle.loads(headers_blob)
                expired = now >= expires_at

                if expired and not etag:
                    cursor.execute("""
                        DELETE FROM http_cache
                        WHERE cache_key = ?
                    """, (key,))

                    conn.commit()
                    self.cache_misses += 1
                    return None

                cursor.execute("""
                    UPDATE http_cache
                    SET last_accessed = ?
                    WHERE cache_key = ?
                """, (now, key))

                conn.commit()

                if expired:
                    self.cache_misses += 1
                    return {
                        "response": response,
                        "headers": headers,
                        "status_code": status_code,
                        "etag": etag,
                        "expires_at": expires_at,
                        "stale": True,
                    }

                self.cache_hits += 1

                return {
                    "response": response,
                    "headers": headers,
                    "status_code": status_code,
                    "etag": etag,
                    "expires_at": expires_at,
                    "stale": False,
                }

    def get(self, key):
        """
        Preserve the simple interface used by existing tests.
        Stale entries are returned as misses; use get_entry()
        when ETag revalidation is required.
        """
        entry = self.get_entry(key)

        if entry is None or entry["stale"]:
            return None

        return entry["response"]

    def set(self, key, value, headers=None, status_code=200):
        headers = dict(headers or {})
        cache_control = self._get_cache_control(headers)

        directives = {
            directive.strip().split("=", 1)[0].strip()
            for directive in cache_control.split(",")
        }

        if directives.intersection({"no-store", "no-cache", "private"}):
            print(f"[CACHE] Skipped due to Cache-Control rules: {key}")
            return "MISS"

        if status_code != 200:
            print(f"[CACHE] Skipped non-200 status code ({status_code}): {key}")
            return "MISS"

        ttl_to_use = self._ttl_from_headers(headers)

        if ttl_to_use == 0:
            print(f"[CACHE] Not storing immediately-expired response: {key}")
            return "MISS"

        etag = self._get_header(headers, "etag")
        now = time.time()

        serialized_value = self._serialize_value(value)
        response = self._response_bytes(value)
        serialized_headers = pickle.dumps(headers)

        with self.lock:
            with closing(self._connect()) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT 1
                    FROM http_cache
                    WHERE cache_key = ?
                """, (key,))

                exists = cursor.fetchone() is not None

                if not exists:
                    cursor.execute("""
                        SELECT COUNT(*)
                        FROM http_cache
                    """)

                    current_size = cursor.fetchone()[0]

                    if current_size >= self.max_size:
                        cursor.execute("""
                            SELECT cache_key
                            FROM http_cache
                            ORDER BY last_accessed ASC
                            LIMIT 1
                        """)

                        oldest_row = cursor.fetchone()

                        if oldest_row:
                            oldest_key = oldest_row[0]

                            cursor.execute("""
                                DELETE FROM http_cache
                                WHERE cache_key = ?
                            """, (oldest_key,))

                            print(
                                f"[CACHE] Evicted oldest entry: {oldest_key}"
                            )

                cursor.execute("""
                    INSERT OR REPLACE INTO http_cache (
                        cache_key,
                        value,
                        headers,
                        status_code,
                        etag,
                        response,
                        expires_at,
                        last_accessed
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    key,
                    serialized_value,
                    serialized_headers,
                    status_code,
                    etag,
                    response,
                    now + ttl_to_use,
                    now,
                ))

                conn.commit()

        print(f"[CACHE] Stored: {key} (TTL: {ttl_to_use}s)")
        return "MISS (CACHED)"

    def refresh(self, key, headers=None):
        """
        Refresh a stale entry after the origin returns
        HTTP 304 Not Modified.
        """
        headers = headers or {}

        with self.lock:
            with closing(self._connect()) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT headers, etag
                    FROM http_cache
                    WHERE cache_key = ?
                """, (key,))

                row = cursor.fetchone()

                if row is None:
                    return False

                stored_headers = pickle.loads(row[0])
                old_etag = row[1]

                # Update only the relevant metadata from the 304 response.
                for name, value in headers.items():
                    if name.lower() in {
                        "etag",
                        "cache-control",
                        "expires",
                    }:
                        existing_name = next(
                            (
                                old_name
                                for old_name in stored_headers
                                if old_name.lower() == name.lower()
                            ),
                            name,
                        )

                        stored_headers[existing_name] = value

                etag = self._get_header(stored_headers, "etag") or old_etag
                ttl = self._ttl_from_headers(stored_headers)
                now = time.time()

                cursor.execute("""
                    UPDATE http_cache
                    SET headers = ?,
                        etag = ?,
                        expires_at = ?,
                        last_accessed = ?
                    WHERE cache_key = ?
                """, (
                    pickle.dumps(stored_headers),
                    etag,
                    now + ttl,
                    now,
                    key,
                ))

                conn.commit()
                return True

    def stats(self):
        with self.lock:
            total = self.cache_hits + self.cache_misses
            hit_rate = (
                self.cache_hits / total * 100
                if total
                else 0
            )

            return {
                "hits": self.cache_hits,
                "misses": self.cache_misses,
                "hit_rate": round(hit_rate, 2),
            }

    def has(self, key):
        return self.get(key) is not None

    def close(self):
        """Compatibility method; connections close after each operation."""
        pass
