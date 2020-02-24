from unittest.mock import patch, Mock

from werkzeug.exceptions import ImATeapot

from tests.test_issue_maker import TestBase


class TestUtils(TestBase):

    github_headers = {
        "Content-Type": "application/json",
        "X-GitHub-Event": "issues",
        "X-Hub-Signature": "sha1=7d38cdd689735b008b3c702edd92eea23791c5f6"}

    github_json = """{
        "action": "opened",
        "issue": {
            "url": "https://api.github.com/repos/octocat/Hello-World/issues/1347",
            "number": 1347,
        },
        "repository" : {
            "id": 1296269,
            "full_name": "octocat/Hello-World",
            "owner": {
                "login": "octocat",
                "id": 1,
            },
        },
        "sender": {
            "login": "octocat",
            "id": 1,
        }
    }"""

    @patch('swaglyrics_backend.utils.is_valid_signature', return_value=True)
    def test_that_request_is_valid(self, signature_mock):
        from swaglyrics_backend.issue_maker import app
        with app.test_client() as c:
            req = c.post(json=self.github_json)
            req.status_code = 200
            req.headers = self.github_headers
            from swaglyrics_backend.utils import validate_request
            self.assertIsNotNone(validate_request(req))

    @patch('swaglyrics_backend.utils.is_valid_signature', return_value=True)
    def test_that_empty_request_is_not_valid(self, signature_mock):
        from swaglyrics_backend.issue_maker import app
        from swaglyrics_backend.utils import validate_request
        with app.test_client() as c:
            req = c.post()
            with self.assertRaises(ImATeapot):
                validate_request(req)

    def test_that_not_valid_signature_aborts_code(self):
        from swaglyrics_backend.issue_maker import app
        from swaglyrics_backend.utils import validate_request
        with app.test_client() as c:
            req = c.post()
            req.headers = self.github_headers
            with self.assertRaises(ImATeapot):
                validate_request(req)
