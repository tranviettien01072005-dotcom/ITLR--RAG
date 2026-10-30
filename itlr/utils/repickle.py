"""Re-pickle trusted offline copies to update historical Python module paths.

Không chuyển phiên bản sklearn bằng cách đóng dấu lại pickle; mismatch phải rebuild.
Ghi atomic từng file; chạy probe lại sau migration trước khi operator activate.

Vì sao cần: pickle lưu lớp/hàm tùy biến theo đường dẫn module (vd hàm tokenizer
`recommender_utils.tokenize`, lớp `bm25_utils.BM25Index`). Sau khi di chuyển code
sang `itlr.core.*`, các pickle cũ trỏ tới module CŨ -> ModuleNotFoundError khi nạp.

Cách xử lý: tạm ALIAS tên module cũ -> module mới trong sys.modules để nạp được,
rồi DUMP LẠI. Khi dump, pickle ghi theo `__module__` thật của đối tượng (đã là
`itlr.core.*`) -> artifact trỏ đường dẫn MỚI, không cần alias ở lần chạy sau, và
KHÔNG refit/đổi dữ liệu (số hàng giữ nguyên, đồng bộ embeddings/ann).

Chạy MỘT lần sau tái cấu trúc:  python -m itlr.utils.repickle
"""

import pickle
import os
import sys
import tempfile
import warnings
from pathlib import Path
from sklearn.exceptions import InconsistentVersionWarning

from itlr import config
from itlr.core import ann as _ann
from itlr.core import bm25 as _bm25
from itlr.core import embeddings as _embeddings
from itlr.core import rag as _rag
from itlr.core import recommender as _recommender
from itlr.core import rerank as _rerank
from itlr.chatbot import knowledge_base as _kb
from itlr.chatbot import query_understanding as _qu

_ALIASES = {
    "recommender_utils": _recommender,
    "bm25_utils": _bm25,
    "embedding_utils": _embeddings,
    "ann_utils": _ann,
    "rerank_utils": _rerank,
    "rag_utils": _rag,
    "knowledge_base": _kb,
    "query_understanding": _qu,
}

TARGETS = [
    "retrieval_model.pkl",
    "tfidf_vectorizer.pkl",
    "tfidf_matrix.pkl",
    "char_vectorizer.pkl",
    "cf_model.pkl",
    "item_list.pkl",
]


def main() -> int:
    for old, mod in _ALIASES.items():
        sys.modules.setdefault(old, mod)

    failed = False
    for name in TARGETS:
        path = Path(config.artifact(name))
        if not path.is_file():
            print(f"[skip] không thấy {name}")
            continue
        temporary = None
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", InconsistentVersionWarning)
                with open(path, "rb") as f:
                    obj = pickle.load(f)
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f'.{name}.', delete=False) as f:
                temporary = Path(f.name)
                pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)
                f.flush()
                os.fsync(f.fileno())
            temporary.chmod(path.stat().st_mode & 0o777)
            os.replace(temporary, path)
            temporary = None
            print(f"[OK] re-pickled {name}")
        except Exception as e:
            failed = True
            print(f"[ERR] {name}: {e!r}")
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
