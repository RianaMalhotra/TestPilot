from fastapi.testclient import TestClient
from app.main import app, Base, engine


def test_junit_import_and_regression():
    with TestClient(app) as client:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        def upload(sha, failure):
            xml = (
                '<testsuite tests="2">'
                '<testcase classname="tests.test_math" name="test_add" time="0.025">'
                + ('<failure message="expected 2">assert 1 == 2</failure>' if failure else '')
                + '</testcase><testcase name="test_skip"><skipped/></testcase></testsuite>'
            )
            return client.post(
                "/runs/junit",
                data={"commit_sha": sha},
                files={"file": ("report.xml", xml, "application/xml")},
            )
        first = upload("good", False)
        assert first.status_code == 201, first.text
        assert first.json()["tests_recorded"] == 1
        second = upload("bad", True)
        assert second.status_code == 201, second.text
        assert client.get("/analytics/tests").json()[0]["failure_rate"] == 0.5
        assert len(client.get("/analytics/regressions").json()) == 1


def test_junit_rejects_invalid_and_unsafe_xml():
    with TestClient(app) as client:
        for xml in ("not xml", '<!DOCTYPE foo [<!ENTITY x "abc">]><testsuite/>'):
            response = client.post(
                "/runs/junit", data={"commit_sha": "bad"},
                files={"file": ("report.xml", xml, "application/xml")},
            )
            assert response.status_code == 422
