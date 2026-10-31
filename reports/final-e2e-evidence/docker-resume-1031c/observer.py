"""Transparent Docker-local Ollama TCP observation; records timings/hashes, never model text."""
import asyncio,hashlib,json,re,signal,time
from pathlib import Path
path=Path('/evidence/provider-sockets.json');rows=[];clients=set()
def save():path.write_text(json.dumps({'real_provider':'http://ollama:11434','records':rows},indent=2))
async def handle(reader,writer):
 client=asyncio.current_task();clients.add(client)
 row={'id':len(rows)+1,'started':time.monotonic(),'provider_bytes':0};rows.append(row)
 upstream=None;tasks=[]
 try:
  header=await reader.readuntil(b'\r\n\r\n');lines=header[:-4].split(b'\r\n');method,target,_=lines[0].decode().split(' ',2)
  headers={line.split(b':',1)[0].lower():line.split(b':',1)[1].strip() for line in lines[1:]}
  body=await reader.readexactly(int(headers.get(b'content-length',b'0')))
  row.update(method=method,path=target,request_sha256=hashlib.sha256(body).hexdigest())
  if body:
   payload=json.loads(body);row.update(model=payload.get('model'),stream=payload.get('stream'),prompt_chars=sum(len(m.get('content','')) for m in payload.get('messages',[])))
  source,upstream=await asyncio.open_connection('ollama',11434)
  forwarded=[lines[0],b'Host: ollama:11434',b'Connection: close']+[line for line in lines[1:] if line.split(b':',1)[0].lower() not in (b'host',b'connection')]
  upstream.write(b'\r\n'.join(forwarded)+b'\r\n\r\n'+body);await upstream.drain();row['sent']=time.monotonic();save()
  async def watch():
   try:
    if not await reader.read(1):row['client_closed']=time.monotonic()
   except (ConnectionError,OSError):row['client_closed']=time.monotonic()
  async def copy():
   tail=b''
   while data:=await source.read(65536):
    row.setdefault('first_provider_byte',time.monotonic());row['provider_bytes']+=len(data)
    tail=(tail+data)[-8192:]
    if re.search(rb'"done"\s*:\s*true',tail):row['provider_done_seen']=True
    writer.write(data);await writer.drain()
  tasks=[asyncio.create_task(watch()),asyncio.create_task(copy())]
  done,pending=await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
  for task in done:
   if task.exception():row['error']=type(task.exception()).__name__
  for task in pending:task.cancel()
  await asyncio.gather(*pending,return_exceptions=True)
 except (Exception,asyncio.CancelledError) as error:row['error']=type(error).__name__
 finally:
  if upstream:
   upstream.close()
   try:await upstream.wait_closed()
   except (ConnectionError,OSError):pass
   row['upstream_socket_closed']=time.monotonic()
  writer.close()
  try:await writer.wait_closed()
  except (ConnectionError,OSError):pass
  row['ended']=time.monotonic();save();clients.discard(client)
async def main():
 save()
 stop=asyncio.Event();asyncio.get_running_loop().add_signal_handler(signal.SIGTERM,stop.set)
 async with await asyncio.start_server(handle,'0.0.0.0',18435) as server:
  await stop.wait()
 for client in list(clients):client.cancel()
 await asyncio.gather(*list(clients),return_exceptions=True)
asyncio.run(main())
