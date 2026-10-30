"""Real local-only model/API smoke. Requires built artifacts and Ollama qwen2.5:3b."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    for key in ('DEEPSEEK_API_KEY', 'OPENAI_API_KEY'):
        os.environ.pop(key, None)
    os.environ.update(USE_OLLAMA='1', OLLAMA_MODEL='qwen2.5:3b', OLLAMA_BASE_URL='http://127.0.0.1:11434',
                      OLLAMA_TIMEOUT='240', DISABLE_RERANKER='1')
    from itlr.chatbot.llm_client import ollama_chat
    t = time.perf_counter()
    answer = ollama_chat([
        {'role': 'system', 'content': 'Answer only from the supplied source. Cite [item_id:1].'},
        {'role': 'user', 'content': 'Source [item_id:1]: Docker packages applications in containers. What does Docker do?'}
    ], num_predict=80, temperature=0)
    if not answer.strip():
        raise RuntimeError('Ollama returned empty text')
    result = {'provider': 'ollama', 'model': 'qwen2.5:3b', 'mock': False,
              'direct_answer': answer, 'direct_citation_present': '[item_id:1]' in answer,
              'direct_seconds': time.perf_counter()-t, 'api_cost_usd': 0,
              'scope': 'local synthetic catalog smoke; reranker disabled; not DeepSeek'}
    env = os.environ.copy()
    env.update(HF_HOME=str(ROOT/'var/hf'), HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
               OMP_NUM_THREADS='4', MKL_NUM_THREADS='4', ITLR_REQUIRE_ARTIFACT_MANIFEST='1')
    with (ROOT/'var/downloads/local-api.log').open('w') as log:
        proc = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'itlr.api.server:app', '--host',
                                 '127.0.0.1', '--port', '18001', '--workers', '1', '--no-proxy-headers'],
                                cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        def request(path, body=None):
            data = json.dumps(body).encode() if body is not None else None
            req = urllib.request.Request('http://127.0.0.1:18001'+path, data=data,
                                         headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req, timeout=300) as response:
                return json.load(response)
        try:
            for _ in range(60):
                if proc.poll() is not None:
                    raise RuntimeError('API process exited; see local-api.log')
                try:
                    result['health'] = request('/health')
                    break
                except (OSError, ValueError):
                    time.sleep(1)
            else:
                raise RuntimeError('API readiness timed out')
            if result['health']['engine'] != 'ready':
                raise RuntimeError(f"Engine not ready: {result['health']}")
            result['search'] = request('/api/search', {'query':'docker containers','min_pct':70})
            if not result['search']['results']:
                raise RuntimeError('Search returned no results')
            t = time.perf_counter()
            result['chat'] = request('/api/chat', {'message':'Docker là gì? Trích dẫn item_id của tài nguyên nguồn.', 'history':[]})
            result['chat_seconds'] = time.perf_counter()-t
            if not result['chat']['response'].strip():
                raise RuntimeError('Chat returned empty response')
            (ROOT/'reports/local_models_smoke.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
            print(json.dumps({'health':result['health'], 'direct_citation':result['direct_citation_present'],
                              'search_results':len(result['search']['results']), 'chat_seconds':result['chat_seconds']},ensure_ascii=False))
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


if __name__ == '__main__':
    main()
