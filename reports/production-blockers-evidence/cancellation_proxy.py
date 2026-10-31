"""Loopback observation proxy; forwards actual Ollama bytes without recording text."""
import asyncio, json, time, hashlib, re
from pathlib import Path
path=Path('/tmp/itlr-blockers/cancellation-proxy.json')
rows=[]
def save():path.write_text(json.dumps({'actual_upstream':'http://127.0.0.1:11434','listen_port':18435,'records':rows},indent=2))
async def handle(reader,writer):
 row={'id':len(rows)+1,'started_monotonic':time.monotonic(),'provider_bytes':0,'client_bytes':0};rows.append(row)
 upstream_writer=None;tasks=[]
 try:
  header=await reader.readuntil(b'\r\n\r\n');lines=header[:-4].split(b'\r\n');method,target,_version=lines[0].decode().split(' ',2)
  headers={line.split(b':',1)[0].lower():line.split(b':',1)[1].strip() for line in lines[1:]}
  body=await reader.readexactly(int(headers.get(b'content-length',b'0')))
  row.update(method=method,path=target,request_bytes=len(body),body_sha256=hashlib.sha256(body).hexdigest())
  if body:
   payload=json.loads(body);row.update(model=payload.get('model'),stream=payload.get('stream'),prompt_chars=sum(len(x.get('content','')) for x in payload.get('messages',[])),num_predict=payload.get('options',{}).get('num_predict'))
  upstream_reader,upstream_writer=await asyncio.open_connection('127.0.0.1',11434)
  forwarded=[lines[0],b'Host: 127.0.0.1:11434',b'Connection: close']+[line for line in lines[1:] if line.split(b':',1)[0].lower() not in (b'host',b'connection')]
  upstream_writer.write(b'\r\n'.join(forwarded)+b'\r\n\r\n'+body);await upstream_writer.drain();row['upstream_request_sent_monotonic']=time.monotonic();save()
  async def downstream_watch():
   try:
    more=await reader.read(1)
    if not more:row['client_closed_monotonic']=time.monotonic();row['client_closed']=True
   except (ConnectionError,OSError):row['client_closed_monotonic']=time.monotonic();row['client_closed']=True
  async def upstream_copy():
   tail=b''
   while True:
    data=await upstream_reader.read(65536)
    if not data:row['provider_eof_monotonic']=time.monotonic();break
    row.setdefault('first_provider_byte_monotonic',time.monotonic());row['provider_bytes']+=len(data)
    tail=(tail+data)[-8192:]
    if re.search(rb'"done"\s*:\s*true',tail):row['provider_done_seen']=True
    writer.write(data);await writer.drain();row['client_bytes']+=len(data)
  tasks=[asyncio.create_task(downstream_watch()),asyncio.create_task(upstream_copy())]
  done,pending=await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
  for task in done:
   exc=task.exception()
   if exc:row['transport_error_type']=type(exc).__name__
  for task in pending:task.cancel()
  await asyncio.gather(*pending,return_exceptions=True)
 except (Exception,asyncio.CancelledError) as exc:row['error_type']=type(exc).__name__
 finally:
  if upstream_writer:
   upstream_writer.close()
   try:await upstream_writer.wait_closed()
   except (ConnectionError,OSError):pass
   row['upstream_socket_closed_monotonic']=time.monotonic()
  writer.close()
  try:await writer.wait_closed()
  except (ConnectionError,OSError):pass
  row['ended_monotonic']=time.monotonic();save()
async def main():
 save()
 async with await asyncio.start_server(handle,'127.0.0.1',18435) as server:await server.serve_forever()
asyncio.run(main())
