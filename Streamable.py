from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import time

app = FastAPI()

def generate_stream():
    for i in range(10):
        yield f"Chunk {i}\n"
        time.sleep(1)

@app.get("/stream")
def stream():
    return StreamingResponse(generate_stream(), media_type="text/plain")
