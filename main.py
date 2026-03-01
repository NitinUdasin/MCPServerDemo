
import logging
import os
import sys
from fastapi import FastAPI, Request
from jsonrpcserver import method, Result, Success, dispatch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

@method
def add(a: int, b: int) -> Result:
    logger.info(f"Received add request with params: a={a}, b={b}")
    result = a + b
    logger.info(f"Add operation result: {result}")
    return Success(result)

@method
def multiply(a: int, b: int) -> Result:
    logger.info(f"Received multiply request with params: a={a}, b={b}")
    result = a * b
    logger.info(f"Multiply operation result: {result}")
    return Success(result)

@app.get("/")
async def root():
    return {"message": "FastAPI is running!"}

from starlette.responses import JSONResponse
# ... (rest of the imports)

@app.post("/")
async def jsonrpc(request: Request):
    request_body_bytes = await request.body()
    request_body_str = request_body_bytes.decode("utf-8")
    logger.info(f"Received JSON-RPC request: {request_body_str}")
    response = dispatch(request_body_str) # Removed await
    logger.info(f"Sending JSON-RPC response: {response}")
    return JSONResponse(content=response)
