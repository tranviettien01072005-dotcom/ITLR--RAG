"""Isolated cleanup pattern, not application/provider/socket verification.
Awaiting a sync thread's blocking read can still delay this cleanup.
"""
import asyncio,json
from pathlib import Path
from starlette.responses import StreamingResponse
class ClosingStreamingResponse(StreamingResponse):
    def __init__(self, iterator):
        super().__init__(iterator)
        self.source_iterator=iterator
    async def __call__(self,scope,receive,send):
        try:
            await super().__call__(scope,receive,send)
        finally:
            await self.body_iterator.aclose()
            self.source_iterator.close()
async def main():
    closed=[]
    def generate():
        try:
            yield 'first'
            yield 'second'
        finally:
            closed.append(True)
    response=ClosingStreamingResponse(generate())
    sent=asyncio.Event()
    async def send(message):
        if message['type']=='http.response.body':sent.set()
    async def receive():
        await sent.wait()
        return {'type':'http.disconnect'}
    await response({'type':'http','asgi':{'spec_version':'2.0'}},receive,send)
    result={'generator_closed_after_disconnect':bool(closed),'scope':'isolated lifecycle pattern; no actual provider/socket verification; no hard cancellation deadline'}
    assert closed==[True]
    Path('/tmp/itlr-release/cancellation_cleanup_pattern.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result))
asyncio.run(main())
