import time
from server.cache import Cache

def test_cache_set_and_get():
    cache = Cache(ttl=15)

    cache.set("/hello", b"Hello World", {}, 200)

    result = cache.get("/hello")

    assert result == b"Hello World"

def test_cache_missing_key():

    cache = Cache()

    result = cache.get("/doesnotexist")

    assert result is None

def test_cache_expires(monkeypatch):

    cache = Cache(ttl=10)

    current_time = 1000

    monkeypatch.setattr(time, "time", lambda: current_time)

    cache.set("/hello", b"Hello World", {}, 200)

    monkeypatch.setattr(time, "time", lambda: current_time + 11)

    result  = cache.get("/hello")

    assert result is None

def test_different_query_strings_are_different_keys():

    cache = Cache(ttl=15)

    cache.set("/products?page=1", b"page 1", {}, 200)
    cache.set("/products?page=2", b"page 2", {}, 200)

    assert cache.get("/products?page=1") == b"page 1"
    assert cache.get("/products?page=2") == b"page 2"

def test_cache_has_key():

    cache = Cache()

    cache.set("/hello", b"Hello World", {}, 200)

    assert cache.has("/hello") is True
    assert cache.has("/doesnotexist") is False

def test_different_http_methods_have_different_cache_keys():

    cache = Cache()

    get_key = "GET:/products"
    post_key = "POST:/products"

    cache.set(get_key, b"GET /products", {}, 200)
    cache.set(post_key, b"POST /products", {}, 200)

    assert cache.get(get_key) == b"GET /products"
    assert cache.get(post_key) == b"POST /products"

def test_cache_overwrites_existing_key():

    cache = Cache()

    cache.set("/hello", b"Old Value", {}, 200)
    cache.set("/hello", b"New Value", {}, 200)

    assert cache.get("/hello") == b"New Value"

def test_cache_stores_expiration_time(cache):
    cache = Cache(ttl=15)

    cache.set("/hello", b"Hello World", {}, 200)

    entry = cache.cache["/hello"]

    assert "expires_at" in entry
    assert entry["expires_at"] > time.time()

def test_has_returns_false_after_expiration(monkeypatch):
    cache = Cache(ttl=10)

    current_time = 1000

    monkeypatch.setattr(time, "time", lambda: current_time)

    cache.set("/hello", b"Hello World", {}, 200)

    monkeypatch.setattr(time, "time", lambda: current_time + 11)

    assert cache.has("/hello") is False