from io import BytesIO
from zipfile import ZipFile

import pytest
from scripts.import_github_artifact import extract_report


def archive(entries):
    stream = BytesIO()
    with ZipFile(stream, "w") as z:
        for name, data in entries:
            z.writestr(name, data)
    return stream.getvalue()


def test_extract_junit_report():
    xml = b'<testsuite><testcase name="ok"/></testsuite>'
    assert extract_report(archive([("reports/report.xml", xml)])) == xml


def test_missing_report_rejected():
    with pytest.raises(ValueError, match="exactly one"):
        extract_report(archive([("other.xml", "test")]))


def test_duplicate_report_rejected():
    with pytest.raises(ValueError, match="exactly one"):
        extract_report(archive([("a/report.xml", "a"), ("b/report.xml", "b")]))


def test_oversized_report_rejected():
    with pytest.raises(ValueError, match="5 MiB"):
        extract_report(archive([("report.xml", b"x" * (5 * 1024 * 1024 + 1))]))
