import time
from server.cache import Cache

def test_cache_set_and_get():
    cache = Cache(ttl=15)

    cache.set("/hello", b"Hello World")

    result = cache.get("/hello")

    assert result == b"Hello World"

def test_cache_missing_key():

    cache = Cache()

    result = cache.get("/doesnotexist")

    assert result == None

def test_cache_expires():

    cache = Cache(ttl=1)

    cache.set("/hello", b"Hello World")

    time.sleep(1.1)

    result  = cache.get("/hello")

    assert result == None

def test_different_query_strings_are_different_keys():

    cache = Cache(ttl=15)

    cache.set("/products?page=1", b"page 1")
    cache.set("/products?page=2", b"page 2")

    assert cache.get("/products?page=1") == b"page 1"
    assert cache.get("/products?page=2") == b"page 2"