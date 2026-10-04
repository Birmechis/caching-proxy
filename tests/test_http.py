import pytest
from server.my_server import parse_http_request

def test_parse_valid_http_request():
    request = (
        b"GET /products HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"\r\n"
    )

    result = parse_http_request(request)

    assert result["method"] == "GET"
    assert result["path"] == "/products"
    assert result["version"] == "HTTP/1.1"

def test_parse_invalid_http_request():
    request = b"INVALID REQUEST\r\n\r\n"

    with pytest.raises(ValueError):
        parse_http_request(request)

def test_parse_http_headers():
    request = (
        b"GET /products HTTP/1.1\r\n"
        b"Host: locaclhost\r\n"
        b"Content-Type: text/plain\r\n"
        b"Authorization: Bearer xyf321"
        b"\r\n"
    )

    parsed = parse_http_request(request)

    assert parsed["headers"]["Host"] == "locaclhost"
    assert parsed["headers"]["Content-Type"] == "text/plain"
    assert parsed["headers"]["Authorization"] == "Bearer xyf321"

def test_parse_http_body():
    request = (
        b"GET /products HTTP/1.1\r\n"
        b"Host: locaclhost\r\n"
        b"Content-Type: text/plain\r\n"
        b"\r\n"
        b"Hello world"
    )
    parsed = parse_http_request(request)

    assert parsed['body'] == "Hello world"

def test_invalid_http_header_is_rejected():
    request = (
        b"GET /products HTTP/1.1\r\n"
        b"Host locaclhost\r\n"
        b"\r\n"
    )

    with pytest.raises(ValueError):
        parse_http_request(request)