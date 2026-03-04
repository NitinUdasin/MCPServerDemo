# JSON RPC Server with FastAPI and Python

This project implements a simple JSON-RPC server using FastAPI, Uvicorn, and jsonrpcserver in Python. It exposes `add` and `multiply` methods.

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd json-rpc-server
    ```

2.  **Create a virtual environment and install dependencies using `uv`:**
    ```bash
    uv venv
    .\.venv\Scripts\activate # On Windows
    # source .venv/bin/activate # On Linux/macOS
    uv pip install fastapi uvicorn jsonrpcserver
    ```

## Running the Server

To start the development server with auto-reloading:

```bash
.\.venv\Scripts\activate # On Windows
# source .venv/bin/activate # On Linux/macOS
uv run python -m uvicorn main:app --reload
```

The server will run at `http://127.0.0.1:8000/`.

## API Endpoints

### GET /

A simple test endpoint to confirm the server is running.

**Request:**

```bash
# Using curl (Linux/macOS/Git Bash)
curl http://127.0.0.1:8000/

# Using Invoke-RestMethod (PowerShell)
Invoke-RestMethod -Uri "http://127.0.0.1:8000/" -Method Get
```

**Response:**

```json
{
  "message": "FastAPI is running!"
}
```

### POST / (JSON-RPC 2.0)

This is the main JSON-RPC endpoint for `add` and `multiply` methods.

#### Add Method

**Request:**

```bash
# Using curl
curl -X POST -H "Content-Type: application/json" -d '{"jsonrpc": "2.0", "method": "add", "params": [2, 3], "id": 1}' http://127.0.0.1:8000/

# Using Invoke-RestMethod (PowerShell)
Invoke-RestMethod -Uri "http://127.0.0.1:8000/"   -Method Post -Headers @{ "Content-Type" = "application/json" }   -Body '{"jsonrpc":"2.0","method":"add","params":[2,3],"id":1}'
```

**Response (Example):**

```json
{"jsonrpc": "2.0", "result": 5, "id": 1}
```

#### Multiply Method

**Request:**

```bash
# Using curl
curl -X POST -H "Content-Type: application/json" -d '{"jsonrpc": "2.0", "method": "multiply", "params": [4, 5], "id": 1}' http://127.0.0.1:8000/

# Using Invoke-RestMethod (PowerShell)
Invoke-RestMethod -Uri "http://127.0.0.1:8000/"  -Method Post -Headers @{ "Content-Type" = "application/json" }  -Body '{"jsonrpc":"2.0","method":"multiply","params":[4,5],"id":1}'
```

**Response (Example):**

```json
{"jsonrpc": "2.0", "result": 20, "id": 1}
```

#### Multipl Methods in a sigal call 
```bash
curl -X POST -H "Content-Type: application/json" -d '[{"jsonrpc": "2.0", "method": "add", "params": [2, 3], "id": 1},{"jsonrpc": "2.0", "method": "multiply", "params": [2, 30], "id": 2}]' http://127.0.0.1:8000/


Invoke-RestMethod -Uri "http://127.0.0.1:8000/" -Method Post -Headers @{ "Content-Type" = "application/json" }  -Body '[{"jsonrpc":"2.0","method":"add","params":[2,3],"id":1},{"jsonrpc":"2.0","method":"multiply","params":[2,30],"id":2}]'
```

## Install fastmcp
```bash
uv add fastmcp
```

## Run MCP inspector 
```bash 
uv run fastmcp dev inspector TestMPCserver.py 
```

## Run MCP server 
```bash 
uv run fastmcp run TestMPCserver.py
```


## Connect to cluade-desktop 
```bash
uv run fastmcp install claude-desktop TestMPCserver.py
```

##  Run MCP server 
```bash
uv run fastmcp run DataprovidersMCPServer.py
```

## Connect to cluade-desktop 
```bash
uv run fastmcp install claude-desktop DataprovidersMCPServer.py
```

```bash
uv add langchain langchain-openai langchain-mcp-adapters python-dotenv streamlit logging pandas fastmcp python-dotenv jsonrpcserver uvicorn streamlit langchain-ollama fastapi
```

```bashe
 uvicorn serversendevent:app
```


```bashe
 uvicorn Streamable:app
```

## Streaming HTTP Demo

This project includes a streaming HTTP endpoint demonstration using FastAPI's `StreamingResponse`.

### Start the Stream Server

```bash
uv run uvicorn Streamable:app --reload
```

The server will run at `http://127.0.0.1:8000/stream` and sends 10 chunks with 1-second intervals.

### Run the Stream Client

```bash
python StreamableClient.py
```

The client demonstrates both async and synchronous methods to consume the streaming response.

### Test with curl

```bash
# Using curl (Linux/macOS/Git Bash)
curl http://127.0.0.1:8000/stream

# Using Invoke-RestMethod (PowerShell)
Invoke-RestMethod -Uri "http://127.0.0.1:8000/stream" -Method Get
```

## VS Code Debugging

A `launch.json` file is provided in the `.vscode` directory to enable debugging with VS Code. You can set breakpoints in `main.py` and run the "Python: FastAPI" configuration.
