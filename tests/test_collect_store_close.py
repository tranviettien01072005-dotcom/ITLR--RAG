"""Close must release SQLite even when final commit fails, without hiding data loss."""
from unittest.mock import Mock

import pytest

from itlr.collect.store import CollectStore


def test_close_releases_connection_and_propagates_commit_failure():
    store = CollectStore.__new__(CollectStore)
    store._conn = Mock()
    store._conn.commit.side_effect = RuntimeError('fixture commit failure')
    with pytest.raises(RuntimeError, match='fixture commit failure'):
        store.close()
    store._conn.close.assert_called_once()
