from unittest.mock import patch

import pytest
from werkzeug.exceptions import ImATeapot

from tests.base import TestBase


class TestUtils(TestBase):

    github_headers = {
        "Content-Type": "application/json",
        "X-GitHub-Event": "issues",
        "X-Hub-Signature": "sha1=7d38cdd689735b008b3c702edd92eea23791c5f6",
        "User-Agent": "GitHub-Hookshot/044aadd"

    }

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
            assert validate_request(req) is not None

    @patch('swaglyrics_backend.utils.is_valid_signature', return_value=True)
    def test_that_empty_request_is_not_valid(self, signature_mock):
        from swaglyrics_backend.issue_maker import app
        from swaglyrics_backend.utils import validate_request
        with app.test_client() as c:
            req = c.post()
            with pytest.raises(ImATeapot):
                validate_request(req)

    def test_that_not_valid_signature_aborts_code(self):
        from swaglyrics_backend.issue_maker import app
        from swaglyrics_backend.utils import validate_request
        with app.test_client() as c:
            req = c.post()
            req.headers = self.github_headers
            with pytest.raises(ImATeapot):
                validate_request(req)

    @patch('swaglyrics_backend.utils.jwt.encode', return_value=b'a string of bytes')
    def test_get_jwt(self, fake_jwt_encode):
        from swaglyrics_backend.utils import get_jwt
        resp = get_jwt(69, 'use a fake private key')
        assert resp == "a string of bytes"

    @patch('swaglyrics_backend.utils.requests.post')
    def test_get_installation_token(self, fake_post):
        fake_post.return_value.json.return_value = {
            "token": "v1.1f699f1069f60xxx",
            "expires_at": "2016-07-11T22:14:10Z"
        }
        from swaglyrics_backend.utils import get_installation_access_token
        resp = get_installation_access_token("bruh", 420)

        assert resp.json()['token'] == "v1.1f699f1069f60xxx"
        assert resp.json()['expires_at'] == "2016-07-11T22:14:10Z"

    def test_log_decorator_throws_error(self):
        from swaglyrics_backend.utils import log_args

        with pytest.raises(ValueError) as e:
            @log_args(loglevel_name="FAKE_LEVEL")
            def fake_function_to_test_log_decorator():
                return "this should raise a ValueError"
            # fake_function_to_test_log_decorator()

        assert "'FAKE_LEVEL' is not a valid log level name." in str(e.value)

    def test_log_decorator_truncates(self):
        from swaglyrics_backend.utils import log_args

        @log_args(max_chars=5)
        def another_fake_function_to_test_log_decorator(stuff="this will get truncated"):
            return stuff

        resp = another_fake_function_to_test_log_decorator()
        # use caplog here later
        assert resp == "this will get truncated"
