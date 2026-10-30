import json
import sys
from pathlib import Path

sys.path.insert(0, '/home/o/ITLR--RAG')
sys.path.append('/tmp/itlr-audit-tools/lib/python3.14/site-packages')
import coverage
import pytest

cov = coverage.Coverage(source=['itlr'], data_file='/tmp/itlr-engineering/.coverage')
cov.start()
status = pytest.main(['tests/', '-o', 'addopts=', '-q', '-ra'])
cov.stop()
cov.save()
cov.json_report(outfile='/tmp/itlr-engineering/python-coverage.json')
cov.report()
Path('/tmp/itlr-engineering/python-status.json').write_text(json.dumps({'pytest_exit':int(status)}))
raise SystemExit(status)
