from unittest.mock import Mock, patch
import pytest

from scripts.poll_github_artifacts import poll


def test_poll_imports_oldest_first_and_skips_seen(tmp_path):
    state = tmp_path / "state.json"
    client = Mock()
    client.get.return_value.json.return_value = {
        "workflow_runs": [{"id": 3}, {"id": 2}, {"id": 1}]
    }
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    calls = []

    def importer(repo, run_id, api, token):
        calls.append(run_id)
        return {"run_id": run_id}

    with patch("scripts.poll_github_artifacts.httpx.Client", return_value=client):
        result = poll("owner/repo", "http://localhost", "token", state, importer=importer)
        again = poll("owner/repo", "http://localhost", "token", state, importer=importer)
    assert [item["github_run_id"] for item in result] == [1, 2, 3]
    assert again == []
    assert calls == [1, 2, 3]


def test_failed_import_remains_retryable(tmp_path):
    state = tmp_path / "state.json"
    client = Mock()
    client.get.return_value.json.return_value = {"workflow_runs": [{"id": 9}]}
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    with patch("scripts.poll_github_artifacts.httpx.Client", return_value=client):
        with pytest.raises(RuntimeError, match="run 9"):
            poll("owner/repo", "http://localhost", "token", state,
                 importer=lambda *args: (_ for _ in ()).throw(ValueError("missing artifact")))
    assert not state.exists()
