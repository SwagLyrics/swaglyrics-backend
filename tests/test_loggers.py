from unittest.mock import patch

from requests import Response

from tests.base import TestBase


class TestIssueMaker(TestBase):
    github_payload_json = {  # trimmed a bit
        "ref": "refs/heads/master",
        "before": "89463fa7125a614f13c313c6a231c5d2f932571d",
        "after": "50ff2b454dbeca33fbb902564cc02a6b8c5098f5",
        "compare": "https://github.com/SwagLyrics/swaglyrics-backend/compare/89463fa7125a...50ff2b454dbe",
        "commits": [
            {
                "id": "50ff2b454dbeca33fbb902564cc02a6b8c5098f5",
                "tree_id": "880a194dd74b841e657f5428c8c9d5c7971b2072",
                "distinct": True,
                "message": "fix test\n\nSigned-off-by: Aadi Bajpai <redacted>",
                "timestamp": "2020-06-04T03:59:02+05:30",
                "url": "https://github.com/SwagLyrics/swaglyrics-backend/commit/50ff2b454dbeca33fbb902564cc02a6b8c50"
                       "98f5",
                "author": {
                    "name": "Aadi Bajpai",
                    "email": "[redacted]",
                    "username": "aadibajpai"
                },
                "added": [

                ],
                "removed": [

                ],
                "modified": [
                    "tests/test_issue_maker.py"
                ]
            }
        ],
        "head_commit": {
            "id": "50ff2b454dbeca33fbb902564cc02a6b8c5098f5",
            "tree_id": "880a194dd74b841e657f5428c8c9d5c7971b2072",
            "distinct": True,
            "message": "fix test\n\nSigned-off-by: Aadi Bajpai <redacted>",
            "timestamp": "2020-06-04T03:59:02+05:30",
            "url": "https://github.com/SwagLyrics/swaglyrics-backend/commit/50ff2b454dbeca33fbb902564cc02a6b8c5098f5",
            "author": {
                "name": "Aadi Bajpai",
                "email": "[redacted]",
                "username": "aadibajpai"
            },
            "committer": {
                "name": "Aadi Bajpai",
                "email": "[redacted]",
                "username": "aadibajpai"
            },
            "added": [

            ],
            "removed": [

            ],
            "modified": [
                "tests/test_issue_maker.py"
            ]
        }
    }

    @patch('swaglyrics_backend.issue_maker.requests.post')
    def test_discord_deploy_logger_works(self, fake_post):
        # also tests embed creation
        fake_post.return_value.status_code = 200
        from swaglyrics_backend.issue_maker import discord_deploy_logger
        with self.assertLogs() as logs:
            discord_deploy_logger(self.github_payload_json)
        embed = fake_post.call_args.kwargs['json']['embeds'][0]

        assert "sent discord message" in logs.output[0]
        assert embed['author']['name'] == "Aadi Bajpai"
        assert embed['author']['url'] == "https://github.com/aadibajpai"
        assert embed['title'] == "fix test"

    @patch('swaglyrics_backend.issue_maker.requests.post')
    def test_discord_deploy_logger_handles_error(self, fake_post):
        # also tests embed creation
        fake_post.return_value.status_code = 500
        from swaglyrics_backend.issue_maker import discord_deploy_logger
        with self.assertLogs() as logs:
            discord_deploy_logger(self.github_payload_json)

        assert "discord message send failed: 500" in logs.output[0]

    @patch('swaglyrics_backend.issue_maker.requests.post')
    def test_discord_genius_logger_works_when_stripper_found(self, fake_post):
        fake_post.return_value.status_code = 200
        from swaglyrics_backend.issue_maker import discord_genius_logger
        with self.assertLogs() as logs:
            discord_genius_logger('Hello', 'Adele', 'Adele-hello')
        assert "sent discord genius message" in logs.output[0]

    @patch('swaglyrics_backend.issue_maker.requests.post')
    def test_discord_genius_logger_handles_error(self, fake_post):
        fake_post.return_value.status_code = 500
        from swaglyrics_backend.issue_maker import discord_genius_logger
        with self.assertLogs() as logs:
            discord_genius_logger('bruh', 'heck', None)
        assert "discord genius message send failed: 500" in logs.output[0]

    @patch('swaglyrics_backend.issue_maker.requests.post')
    def test_discord_instrumental_logger_works(self, fake_post):
        # figure out a way to also test embed creation
        response = Response()
        response.status_code = 200
        fake_post.return_value = response
        from swaglyrics_backend.issue_maker import discord_instrumental_logger
        with self.assertLogs() as logs:
            discord_instrumental_logger('changes', 'XXXTENTACION', False, 0.69, 0.42)
        assert "sent discord instrumental message" in logs.output[0]

    @patch('swaglyrics_backend.issue_maker.requests.post')
    def test_discord_instrumental_logger_handles_error(self, fake_post):
        fake_post.return_value.status_code = 529
        from swaglyrics_backend.issue_maker import discord_instrumental_logger
        with self.assertLogs() as logs:
            discord_instrumental_logger('Up There', 'Frontliner & Geck-o', True, 0.31, 0.12)
        assert "discord instrumental message send failed: 529" in logs.output[0]
