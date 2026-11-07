from unittest.mock import Mock, patch
from scripts.rerun_tests import upload_reports


def test_upload_reports(tmp_path):
    reports = []
    for i in range(2):
        path = tmp_path / f"rerun-{i}.xml"
        path.write_text('<testsuite><testcase name="ok"/></testsuite>')
        reports.append({"report": str(path)})
    response = Mock()
    response.json.return_value = {"run_id": 1}
    client = Mock()
    client.post.return_value = response
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    with patch("scripts.rerun_tests.httpx.Client", return_value=client):
        output = upload_reports(reports, "http://localhost:8000", "abc123", "main")
    assert len(output) == 2
    assert client.post.call_count == 2
    for call in client.post.call_args_list:
        assert call.kwargs["data"] == {"commit_sha": "abc123", "branch": "main"}
        assert call.kwargs["files"]["file"][0] == "report.xml"
