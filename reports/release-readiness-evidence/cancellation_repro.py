import asyncio,json
from pathlib import Path
from starlette.responses import StreamingResponse
closed=[]
def generate():
    try:
        yield 'first'
        yield 'second'
    finally:
        closed.append(True)
async def main():
    response=StreamingResponse(generate())
    sent=asyncio.Event()
    async def send(message):
        if message['type']=='http.response.body': sent.set()
    async def receive():
        await sent.wait()
        return {'type':'http.disconnect'}
    await response({'type':'http','asgi':{'spec_version':'2.0'}},receive,send)
    result={'generator_closed_after_disconnect':bool(closed),'scope':'isolated ASGI retained-response mock, not real socket/provider cancellation proof'}
    await response.body_iterator.aclose()
    result['generator_closed_after_wrapper_aclose']=bool(closed)
    Path('/tmp/itlr-release/cancellation_repro.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result))
asyncio.run(main())
