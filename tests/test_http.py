import pytest
from server.my_server import parse_http_request, parse_http_response

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
        b"Host: localhost\r\n"
        b"Content-Type: text/plain\r\n"
        b"Authorization: Bearer xyf321\r\n"
        b"\r\n"
    )

    parsed = parse_http_request(request)

    assert parsed["headers"]["Host"] == "localhost"
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

def test_parse_http_response_with_etag():
    response = (
        b'HTTP/1.1 200 OK\r\n'
        b'Content-Type: text/plain\r\n'
        b'ETag: "hello-v1"\r\n'
        b'Content-Length: 5\r\n'
        b'\r\n'
        b'Hello'
    )

    result = parse_http_response(response)

    assert result["status_code"] == 200
    assert result["headers"]["ETag"] == '"hello-v1"'
    assert result["body"] == b"Hello"


def test_parse_http_304_response():
    response = (
        b'HTTP/1.1 304 Not Modified\r\n'
        b'ETag: "hello-v1"\r\n'
        b'Connection: close\r\n'
        b'\r\n'
    )

    result = parse_http_response(response)

    assert result["status_code"] == 304
    assert result["headers"]["ETag"] == '"hello-v1"'
    assert result["body"] == b""