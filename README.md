# Caching Proxy Server

A Python-based HTTP caching proxy server that sits between clients and an origin server, caching GET requests to reduce load on the origin server and improve response times.

## Architecture Overview

```
Client <-> Proxy Server (with Cache) <-> Origin Server
```

The proxy server intercepts HTTP requests from clients, checks its cache, and either serves cached responses or forwards requests to the origin server.

## How It Works

### 1. Proxy Server Accepts Connections

The proxy server (`proxy_server.py`) listens for incoming client connections using Python's `socket` library:

```python
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((self.host, self.port))
server.listen(5)  # Queue up to 5 connections
```

**Process:**
1. Creates a TCP socket on the specified host and port (e.g., `127.0.0.1:8080`)
2. Sets `SO_REUSEADDR` option to allow immediate socket reuse after restart
3. Enters an infinite loop calling `server.accept()` to wait for client connections
4. When a client connects, spawns a handler (`handle_client()`) to process the request
5. Accepts the next connection (single-threaded sequential processing)

### 2. Request Forwarding

When the proxy receives a request, it follows this flow:

**Step 1: Parse the Request**
```python
parsed_request = parse_http_request(request)
method = parsed_request["method"]  # GET, POST, etc.
path = parsed_request["path"]      # /api/data, /index.html, etc.
```

The `parse_http_request()` function extracts:
- HTTP method (GET, POST, PUT, DELETE, etc.)
- Request path
- HTTP version
- Headers
- Body

**Step 2: Check Cache (for GET requests only)**
- Only GET requests are cacheable
- POST, PUT, DELETE requests bypass cache entirely

**Step 3: Forward to Origin (if needed)**
```python
origin_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
origin_socket.connect((origin_host, origin_port))
origin_socket.sendall(request)  # Send original request unchanged
```

The proxy:
1. Parses the origin URL to extract hostname and port
2. Opens a new TCP connection to the origin server
3. Sends the original client request as-is
4. Calls `shutdown(socket.SHUT_WR)` to signal request completion
5. Receives the response in 4096-byte chunks
6. Closes the origin connection
7. Returns the complete response

### 3. Caching Mechanism

The cache (`cache.py`) is a simple in-memory time-to-live (TTL) based cache:

**Storage Structure:**
```python
self.storage = {
    "/api/data": {
        "response": b"HTTP/1.1 200 OK\r\n...",
        "expires_at": 1678901234.56  # Unix timestamp
    }
}
```

**Cache Operations:**

- **`set(key, value)`**: Stores a response with an expiration timestamp (current time + TTL)
- **`get(key)`**: Retrieves a response if it exists and hasn't expired
- **`has(key)`**: Checks if a valid (non-expired) entry exists

**Default TTL:** 15 seconds (configurable)

### 4. Cache Hit Flow

When a cached response is found and still valid:

```
Client Request → Proxy receives request
                    ↓
                Check cache
                    ↓
              Cache HIT! ✓
                    ↓
         Serve cached response
                    ↓
              Close connection
```

**What happens:**
1. Client sends GET request to proxy
2. Proxy parses request and extracts the path (cache key)
3. `cache.get(path)` finds a valid entry
4. Proxy logs: `[CACHE] HIT: /path`
5. Cached response is sent directly to client
6. Connection closes immediately
7. **Origin server is never contacted** (saves network round-trip and origin processing)

**Benefits:**
- Near-instant response time
- Reduced origin server load
- Lower bandwidth usage

### 5. Cache Miss Flow

When no cached response exists or it has expired:

```
Client Request → Proxy receives request
                    ↓
                Check cache
                    ↓
              Cache MISS! ✗
                    ↓
         Forward to origin server
                    ↓
         Receive origin response
                    ↓
         Store in cache (if GET)
                    ↓
         Send response to client
                    ↓
              Close connection
```

**What happens:**
1. Client sends GET request to proxy
2. `cache.get(path)` returns `None` (not found or expired)
3. Proxy logs: `[CACHE] MISS: /path`
4. Proxy forwards request to origin server
5. Origin processes request and sends response
6. Proxy stores response: `cache.set(path, response)`
7. Proxy logs: `[CACHE] storing: /path` and `[CACHE] Stored: /path (TTL: 15s)`
8. Response is sent to client
9. Subsequent requests within 15 seconds will be cache hits

**Cache Expiration:**
If `time.time() >= expires_at`:
- Entry is deleted from storage
- Logs: `[CACHE] expired: /path`
- Next request becomes a cache miss

### 6. Origin Server

The origin server (`origin_server.py`) is a simple HTTP server for testing:

**Functionality:**
1. Listens on `127.0.0.1:9000`
2. Accepts incoming connections
3. Receives and logs the full HTTP request
4. Generates a simple response:
   - Status: `200 OK`
   - Content-Type: `text/plain`
   - Body: `"Hello from the origin server!"`
5. Sends response and closes connection

**Response Format:**
```http
HTTP/1.1 200 OK
Content-Type: text/plain
Content-Length: 30
Connection: close

Hello from the origin server!
```

The origin server simulates a real backend service that the proxy protects from excessive requests.

## Testing

### Test Setup

**Terminal 1: Start Origin Server**
```bash
python server/origin_server.py
```
Expected output:
```
Origin server listening on 127.0.0.1:9000
```

**Terminal 2: Start Proxy Server**
```bash
python run.py
```
Input when prompted:
```
--port: 8080
--url: http://127.0.0.1:9000
```
Expected output:
```
Proxy server listening on 127.0.0.1:8080
Origin server: http://127.0.0.1:9000
```

### Test Scenarios

#### Test 1: Cache Miss (First Request)

**Command:**
```bash
curl http://127.0.0.1:8080/test
```

**Proxy Output:**
```
Connection from ('127.0.0.1', 54321)
GET /test
[CACHE] MISS: /test
[PROXY] Forwarding request to origin
[PROXY] connecting to 127.0.0.1:9000
[PROXY] Connected to origin
[PROXY] request sent to origin
[PROXY] request sending side closed
[PROXY] waiting data from origin
[PROXY] received 85 bytes from origin
[PROXY] origin closed connection
[PROXY] received 85 bytes from origin
[CACHE] storing: /test
[CACHE] Stored: /test (TTL: 15s)
```

**Origin Output:**
```
Client ('127.0.0.1', 54322) connected
[ORIGIN] Received request:
GET /test HTTP/1.1
...

[ORIGIN] Sending response:
HTTP/1.1 200 OK
...

[ORIGIN] Connection closed
```

**Result:** Response time ~50-100ms (includes origin processing)

#### Test 2: Cache Hit (Immediate Second Request)

**Command:**
```bash
curl http://127.0.0.1:8080/test
```

**Proxy Output:**
```
Connection from ('127.0.0.1', 54323)
GET /test
[CACHE] HIT: /test
```

**Origin Output:**
```
(No new output - origin not contacted)
```

**Result:** Response time ~5-10ms (served from memory)

#### Test 3: Cache Expiration

**Wait 15+ seconds, then run:**
```bash
curl http://127.0.0.1:8080/test
```

**Proxy Output:**
```
Connection from ('127.0.0.1', 54324)
GET /test
[CACHE] expired: /test
[CACHE] MISS: /test
[PROXY] Forwarding request to origin
...
```

**Result:** Cache entry expired, request forwarded to origin again

#### Test 4: Non-GET Request (No Caching)

**Command:**
```bash
curl -X POST http://127.0.0.1:8080/api/data -d "test=data"
```

**Proxy Output:**
```
Connection from ('127.0.0.1', 54325)
POST /api/data
[PROXY] Forwarding request to origin
...
```

**Result:** POST request bypasses cache entirely (no caching for non-GET methods)

#### Test 5: Different Paths

**Commands:**
```bash
curl http://127.0.0.1:8080/path1
curl http://127.0.0.1:8080/path2
curl http://127.0.0.1:8080/path1  # Cache hit
```

**Result:** Each unique path has its own cache entry with independent expiration

## Key Features

✅ **In-memory caching** with configurable TTL (default 15 seconds)  
✅ **GET request caching** only (safe idempotent operations)  
✅ **Automatic expiration** of stale cache entries  
✅ **Transparent proxying** - forwards non-cacheable requests unchanged  
✅ **Detailed logging** for debugging and monitoring  
✅ **Socket-level implementation** using Python's `socket` library  

## Configuration

Edit `run.py` or pass parameters when prompted:

- **Proxy Port**: Port where proxy listens for client connections (e.g., 8080)
- **Origin URL**: Complete URL of the backend server (e.g., `http://127.0.0.1:9000`)
- **Cache TTL**: Modify `Cache(ttl=15)` in `proxy_server.py` (time in seconds)

## Limitations

- **Single-threaded**: Handles one request at a time
- **In-memory only**: Cache is lost on restart
- **No cache size limit**: Could grow unbounded with many unique paths
- **No HTTP/1.1 persistent connections**: Closes connection after each request
- **Basic HTTP parsing**: May not handle all edge cases correctly
- **No HTTPS support**: Plain HTTP only

## Dependencies

See `requirements.txt` for full list. Core implementation uses only standard library:
- `socket` - Network communication
- `time` - TTL calculation
- `urllib.parse` - URL parsing

## Project Structure

```
caching server/
├── run.py                    # Entry point
├── requirements.txt          # Dependencies
└── server/
    ├── proxy_server.py       # Main proxy logic
    ├── cache.py              # Cache implementation
    ├── origin_server.py      # Test origin server
    └── my_server.py          # HTTP parsing utilities
```

## Future Enhancements

- Multi-threading for concurrent request handling
- Persistent cache (Redis, file-based)
- Cache eviction policies (LRU, LFU)
- HTTP header-based caching (Cache-Control, ETag)
- HTTPS support
- Configurable cache key generation
- Cache statistics and monitoring
