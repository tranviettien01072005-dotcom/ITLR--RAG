# ITLR RAG — mục lệnh tiện dụng (GNU make)

VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: venv install build serve test eval-quick eval-full load-models clean

venv:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip wheel setuptools

install:
	$(PIP) install -r requirements.txt

# Tải model HF về cache (lần đầu cần mạng; sau đó bật HF_HUB_OFFLINE=1 được)
load-models:
	$(PY) -c "from huggingface_hub import snapshot_download; \
snapshot_download('intfloat/multilingual-e5-base'); \
snapshot_download('BAAI/bge-reranker-base')"

build:
	$(PY) scripts/build_all.py

serve:
	$(PY) -m uvicorn itlr.api.server:app --host 127.0.0.1 --port 8000

test:
	$(PY) -m pytest -q

eval-quick:
	$(PY) eval/run_all.py --quick

eval-full:
	$(PY) eval/run_all.py

clean:
	rm -rf var/artifacts reports
