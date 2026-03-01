from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import time
import json

app = FastAPI()

def event_generator():
    counter = 0
    while True:
        data = {"count": counter}
        yield f"data: {json.dumps(data)}\n\n"
        counter += 1
        time.sleep(1)

@app.get("/stream")
def stream():
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
