import httpx
import asyncio


async def stream_response():
    """Consume streaming response from Streamable.py server."""
    url = "http://127.0.0.1:8000/stream"

    async with httpx.AsyncClient() as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            async for chunk in response.aiter_text():
                print(chunk, end="")


def stream_response_sync():
    """Synchronous version to consume streaming response."""
    url = "http://127.0.0.1:8000/stream"

    with httpx.Client() as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            for chunk in response.iter_text():
                print(chunk, end="")


if __name__ == "__main__":
    print("=== Async Stream Client ===")
    asyncio.run(stream_response())

    # print("\n=== Sync Stream Client ===")
    # stream_response_sync()
