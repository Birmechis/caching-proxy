import time
import pytest
from server.cache import Cache

@pytest.fixture
def cache(tmp_path):
    return Cache(db_path=tmp_path / 'test_cache.db')

def test_cache_set_and_get():
    cache = Cache(ttl=15)

    cache.set("/hello", b"Hello World", {})

    result = cache.get("/hello")

    assert result == b"Hello World"

def test_cache_missing_key():

    cache = Cache()

    result = cache.get("/doesnotexist")

    assert result is None

def test_cache_expires(monkeypatch):

    cache = Cache(ttl=15)

    current_time = 1000

    monkeypatch.setattr(time, "time", lambda: current_time)

    cache.set("/hello", b"Hello World", {})

    monkeypatch.setattr(time, "time", lambda: current_time + 16)

    result  = cache.get("/hello")

    assert result is None

def test_different_query_strings_are_different_keys():

    cache = Cache(ttl=15)

    cache.set("/products?page=1", b"page 1", {})
    cache.set("/products?page=2", b"page 2", {})

    assert cache.get("/products?page=1") == b"page 1"
    assert cache.get("/products?page=2") == b"page 2"

def test_cache_has_key():

    cache = Cache()

    cache.set("/hello", b"Hello World", {})

    assert cache.has("/hello") is True
    assert cache.has("/doesnotexist") is False

def test_different_http_methods_have_different_cache_keys():

    cache = Cache()

    get_key = "GET:/products"
    post_key = "POST:/products"

    cache.set(get_key, b"GET /products", {})
    cache.set(post_key, b"POST /products", {})

    assert cache.get(get_key) == b"GET /products"
    assert cache.get(post_key) == b"POST /products"

def test_cache_overwrites_existing_key():

    cache = Cache()

    cache.set("/hello", b"Old Value", {})
    cache.set("/hello", b"New Value", {})

    assert cache.get("/hello") == b"New Value"


def test_cache_stores_expiration_time(tmp_path):
    import sqlite3
    import time
    from server.cache import Cache

    db_path = tmp_path / "test_cache.db"
    cache = Cache(ttl=15, db_path=db_path)

    before = time.time()
    cache.set("/hello", b"Hello World", {})
    after = time.time()

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT expires_at FROM http_cache WHERE cache_key = ?",
            ("/hello",),
        ).fetchone()

    assert row is not None
    assert before + 15 <= row[0] <= after + 15

def test_has_returns_false_after_expiration(monkeypatch):
    cache = Cache(ttl=10)

    current_time = 1000

    monkeypatch.setattr(time, "time", lambda: current_time)

    cache.set("/hello", b"Hello World", {})

    monkeypatch.setattr(time, "time", lambda: current_time + 11)

    assert cache.has("/hello") is False


def test_cache_skips_no_store():
    cache = Cache()

    result = cache.set(
        "/private",
        b"Secret",
        {"Cache-Control": "no-store"},
        200
    )

    assert result == "MISS"
    assert cache.get("/private") is None

def test_cache_skips_no_cache():
    cache = Cache()

    result = cache.set(
        "/products",
        b"Products",
        {"Cache-Control": "no-cache"},
        200
    )

    assert result == "MISS"
    assert cache.get("/products") is None



def test_cache_skips_private_response():
    cache = Cache()

    result = cache.set(
        "/account",
        b"Private data",
        {"Cache-Control": "private"},
        200
    )

    assert result == "MISS"
    assert cache.get("/account") is None


def test_cache_uses_max_age(tmp_path, monkeypatch):
    import sqlite3
    import time
    from server.cache import Cache

    db_path = tmp_path / "max_age_cache.db"
    cache = Cache(ttl=15, db_path=db_path)

    current_time = 1000
    monkeypatch.setattr(time, "time", lambda: current_time)

    cache.set(
        "/Products",
        b"Products",
        {"Cache-Control": "max-age=60"},
        200,
    )

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT expires_at FROM http_cache WHERE cache_key = ?",
            ("/Products",),
        ).fetchone()

    assert row is not None
    assert row[0] == 1060


def test_cache_expires(tmp_path, monkeypatch):
    import time

    cache = Cache(
        ttl=10,
        db_path=tmp_path / "expiration.db"
    )

    current_time = 1000
    monkeypatch.setattr(time, "time", lambda: current_time)

    cache.set("/hello", b"Hello World")

    monkeypatch.setattr(time, "time", lambda: current_time + 11)

    assert cache.get("/hello") is None


def test_cache_survives_reopening_database(tmp_path):
    db_path = tmp_path / "persistent_cache.db"

    first_cache = Cache(
        ttl=60,
        db_path=db_path
    )

    first_cache.set(
        "GET:/products",
        b"HTTP/1.1 200 OK\r\n\r\nHello"
    )

    first_cache.close()

    second_cache = Cache(
        ttl=60,
        db_path=db_path
    )

    result = second_cache.get("GET:/products")

    assert result == b"HTTP/1.1 200 OK\r\n\r\nHello"

    second_cache.close()
