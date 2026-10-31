"""Isolated Ollama CPU inference sweep for the real ITLR selection prompt.

Runs throwaway containers on private ports; never touches the user's daemon.
"""
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PROMPT = Path('/tmp/opencode/itlr-bench-prompt.txt').read_text()
OUT = Path('/tmp/opencode/itlr-bench')
OUT.mkdir(exist_ok=True)
MODELS = '/usr/share/ollama/.ollama/models'

CONFIGS = [
    ('baseline', {}, {}),
    ('flash', {'OLLAMA_FLASH_ATTENTION': '1'}, {}),
    ('kv_q8', {'OLLAMA_KV_CACHE_TYPE': 'q8_0'}, {}),
    ('flash_kv_q8', {'OLLAMA_FLASH_ATTENTION': '1', 'OLLAMA_KV_CACHE_TYPE': 'q8_0'}, {}),
    ('batch256', {}, {'num_batch': 256}),
    ('thread6', {}, {'num_thread': 6}),
]


def docker(*args, check=True):
    return subprocess.run(['docker', *args], capture_output=True, text=True, check=check)


def post(port, path, payload, timeout=180):
    req = urllib.request.Request(f'http://127.0.0.1:{port}{path}',
                                 data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    started = time.monotonic()
    body = json.load(urllib.request.urlopen(req, timeout=timeout))
    return body, time.monotonic() - started


def wait_ready(port, timeout=90):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            urllib.request.urlopen(f'http://127.0.0.1:{port}/api/tags', timeout=2).read()
            return True
        except Exception:
            time.sleep(0.5)
    return False


results = []
for idx, (name, env, options) in enumerate(CONFIGS):
    port = 19500 + idx
    cname = f'itlr-bench-{name}'
    docker('rm', '-f', cname, check=False)
    args = ['run', '-d', '--name', cname, '--cpus', '8', '-p', f'127.0.0.1:{port}:11434',
            '-v', f'{MODELS}:/root/.ollama/models:ro',
            '-e', 'OLLAMA_HOST=0.0.0.0:11434', '-e', 'OLLAMA_NUM_PARALLEL=1',
            '-e', 'OLLAMA_MAX_LOADED_MODELS=1', '-e', 'OLLAMA_CONTEXT_LENGTH=4096']
    for k, v in env.items():
        args += ['-e', f'{k}={v}']
    args += ['ollama/ollama:0.40.13']
    docker(*args)
    row = {'config': name, 'env': env, 'options': options, 'requests': []}
    try:
        if not wait_ready(port):
            row['error'] = 'server not ready'
            results.append(row)
            continue
        # warm the model with a tiny prompt (not counted)
        post(port, '/api/generate', {'model': 'qwen2.5:3b', 'prompt': 'hi', 'stream': False,
                                     'options': {'num_predict': 2}})
        for attempt in (1, 2):
            body, wall = post(port, '/api/generate', {
                'model': 'qwen2.5:3b', 'prompt': PROMPT, 'stream': False,
                'options': {'num_predict': 20, 'temperature': 0, 'num_ctx': 4096, **options}})
            pe = body.get('prompt_eval_duration', 0) / 1e9
            ed = body.get('eval_duration', 0) / 1e9
            row['requests'].append({
                'attempt': attempt, 'wall_s': round(wall, 3),
                'load_s': round(body.get('load_duration', 0) / 1e9, 3),
                'prompt_tokens': body.get('prompt_eval_count'),
                'prefill_s': round(pe, 3),
                'prefill_tok_s': round(body.get('prompt_eval_count', 0) / pe, 1) if pe else None,
                'eval_tokens': body.get('eval_count'),
                'decode_s': round(ed, 3),
                'decode_tok_s': round(body.get('eval_count', 0) / ed, 1) if ed else None,
                'done_reason': body.get('done_reason'),
            })
    finally:
        docker('rm', '-f', cname, check=False)
    results.append(row)
    print(json.dumps(row, ensure_ascii=False), flush=True)
    (OUT / 'sweep.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
print('SWEEP DONE')
