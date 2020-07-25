import time
from unittest.mock import patch

from requests import Response

from tests.base import TestBase, get_spotify_json, generate_fake_unsupported


class TestIssueMaker(TestBase):
    sample_spotify_json = ({
        "access_token": "NgCXRKNgCXRKNgCXRKNgCXRKNgCXRKNgCXRKMzYjw",
        "token_type": "Bearer",
        "scope": "user-read-private user-read-email",
        "expires_in": 3600,
        "refresh_token": "NgAagA...Um_SHo"
    })

    unknown_song_json = {
        "tracks": {
            "href": "https://api.spotify.com/v1/search?query=asddasdsaasd&type=track&offset=0&limit=20",
            "items": [],
            "limit": 20,
            "next": "null",
            "offset": 0,
            "previous": "null",
            "total": 0
        }
    }

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

    def test_that_del_line_deletes_line(self):
        from swaglyrics_backend.issue_maker import del_line
        song = "Supersonics"
        artist = "Caravan Palace"
        generate_fake_unsupported()
        del_line(song, artist)
        with open('unsupported.txt', 'r') as f:
            lines = f.readlines()
            assert not (song + " by " + artist in lines)

    @patch('requests.Response.json', return_value=sample_spotify_json)
    @patch('requests.post', return_value=Response())
    def test_update_spotify_token(self, requests_mock, json_mock):
        from swaglyrics_backend.issue_maker import get_spotify_token
        from swaglyrics_backend import issue_maker
        get_spotify_token()
        assert issue_maker.spotify_token != ''
        assert issue_maker.spotify_token_expiry != 0

    @patch('swaglyrics_backend.issue_maker.time.time', return_value=1133742069)
    def test_not_update_spotify_token_if_not_expired(self, fake_time):
        from swaglyrics_backend.issue_maker import get_spotify_token
        from swaglyrics_backend import issue_maker
        issue_maker.spotify_token = 'this is a real token'
        issue_maker.spotify_token_expiry = 1133742069 + 500  # so it shouldn't update
        token = get_spotify_token()
        assert token == issue_maker.spotify_token
        assert issue_maker.spotify_token_expiry == 1133742569  # check expiry not updated

    @patch('swaglyrics_backend.issue_maker.get_installation_access_token')
    @patch('swaglyrics_backend.issue_maker.get_jwt')
    def test_update_github_token(self, fake_jwt, fake_token):
        fake_token.return_value.json.return_value = {
            "token": "v1.1f699f1069f60xxx",
            "expires_at": "2020-07-26T22:14:10Z"
        }
        from swaglyrics_backend.issue_maker import get_github_token
        from swaglyrics_backend import issue_maker
        token = get_github_token()
        assert issue_maker.gh_token == token
        assert issue_maker.gh_token_expiry != 0

    @patch('swaglyrics_backend.issue_maker.time.time', return_value=1133742069)
    def test_not_update_github_token_if_not_expired(self, fake_time):
        from swaglyrics_backend.issue_maker import get_github_token
        from swaglyrics_backend import issue_maker
        issue_maker.gh_token = 'this is also a real token'
        issue_maker.gh_token_expiry = 1133742069 + 500  # so it shouldn't update
        token = get_github_token()
        assert token == issue_maker.gh_token
        assert issue_maker.gh_token_expiry == 1133742569  # check expiry not updated

    @patch('swaglyrics_backend.issue_maker.discord_instrumental_logger')
    @patch('requests.Response.json', return_value=get_spotify_json('spotify_instrumental.json'))  # Für Elise
    @patch('requests.get', return_value=Response())
    def test_check_song_instrumental_returns_true(self, fake_post, fake_json, fake_discord):
        from swaglyrics_backend.issue_maker import check_song_instrumental
        # we reuse the Miracle by Caravan Palace json for other tests but the return value will be Für Elise
        track = get_spotify_json('correct_spotify_data.json')['tracks']['items'][0]
        instrumental = check_song_instrumental(track, {"Authorization": ""})
        assert instrumental is True

    @patch('swaglyrics_backend.issue_maker.discord_instrumental_logger')
    @patch('requests.Response.json', return_value=get_spotify_json('spotify_not_instrumental.json'))  # Miracle
    @patch('requests.get', return_value=Response())
    def test_check_song_instrumental_returns_false(self, fake_post, fake_json, fake_discord):
        from swaglyrics_backend.issue_maker import check_song_instrumental
        track = get_spotify_json('correct_spotify_data.json')['tracks']['items'][0]  # Miracle by Caravan Palace
        instrumental = check_song_instrumental(track, {"Authorization": ""})
        assert instrumental is False

    @patch('swaglyrics_backend.issue_maker.get_spotify_token', return_value={"access_token": ""})
    @patch('requests.Response.json', return_value={'error': 'yes'})
    @patch('requests.get', return_value=Response())
    def test_check_song_returns_false_on_bad_response(self, requests_mock, response_mock, spotify_mock):
        from swaglyrics_backend.issue_maker import check_song
        from swaglyrics_backend import issue_maker
        issue_maker.t_expiry = time.time() + 3600
        assert not check_song("Miracle", "Caravan Palace")

    @patch('swaglyrics_backend.issue_maker.get_spotify_token', return_value={"access_token": ""})
    @patch('requests.Response.json', return_value={'error', 'yes'})
    @patch('requests.get', return_value=Response())
    @patch('swaglyrics_backend.issue_maker.check_song_instrumental', return_value=False)
    def test_that_check_song_returns_true(self, check_instrumental, mock_get, mock_response, spotify_token):
        from swaglyrics_backend.issue_maker import check_song
        mock_response.return_value = get_spotify_json('correct_spotify_data.json')
        assert check_song("Miracle", "Caravan Palace")

    @patch('swaglyrics_backend.issue_maker.get_spotify_token', return_value={"access_token": ""})
    @patch('requests.get')
    @patch('swaglyrics_backend.issue_maker.check_song_instrumental', return_value=True)
    def test_that_check_song_returns_false_when_instrumental(self, check_instrumental, mock_get, spotify_token):
        from swaglyrics_backend.issue_maker import check_song
        mock_get.return_value.json.return_value = get_spotify_json('correct_spotify_data.json')

        with self.assertLogs() as logs:
            resp = check_song("Miracle", "Caravan Palace")

        assert not resp
        assert "Miracle by Caravan Palace seems to be instrumental" in logs.output[2]

    @patch('swaglyrics_backend.issue_maker.get_spotify_token', return_value={"access_token": ""})
    @patch('requests.get')
    def test_that_check_song_returns_false_when_mismatch(self, mock_get, spotify_token):
        from swaglyrics_backend.issue_maker import check_song
        wrong_json = get_spotify_json('correct_spotify_data.json')
        wrong_json['tracks']['items'][0]['name'] = "Not Miracle"  # so it mismatches
        mock_get.return_value.json.return_value = wrong_json

        assert not check_song("Miracle", "Caravan Palace")

    @patch('swaglyrics_backend.issue_maker.get_spotify_token', return_value={"access_token": ""})
    @patch('requests.Response.json', return_value=unknown_song_json)
    @patch('requests.get', return_value=Response())
    def test_that_check_song_returns_false_on_non_legit_song(self, mock_get, mock_response, spotify_token):
        from swaglyrics_backend.issue_maker import check_song
        assert not check_song("Miracle", "Caravan Palace")

    @patch('requests.Response.json', return_value=None)
    @patch('requests.get', return_value=Response())
    def test_that_genius_stripper_returns_none(self, mock_get, mock_response):
        from swaglyrics_backend.issue_maker import genius_stripper
        assert genius_stripper("Miracle", "Caravan Palace") is None

    @patch('requests.get')
    def test_that_genius_stripper_returns_none_on_error(self, mock_get):
        from swaglyrics_backend.issue_maker import genius_stripper
        fake_json = get_spotify_json('sample_genius_data.json')
        fake_json['meta']['status'] = 500
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = fake_json
        assert genius_stripper("Miracle", "Caravan Palace") is None

    @patch('requests.Response.json', return_value=get_spotify_json('sample_genius_data.json'))
    @patch('requests.get')
    def test_that_genius_stripper_returns_stripper(self, mock_get, fake_response):
        from swaglyrics_backend.issue_maker import genius_stripper
        response = Response()
        response.status_code = 200
        mock_get.return_value = response
        assert genius_stripper("Miracle", "Caravan Palace") == "Caravan-palace-miracle"

    @patch('requests.get')
    def test_that_genius_stripper_returns_none_when_stripper_not_found(self, mock_get):
        from swaglyrics_backend.issue_maker import genius_stripper
        fake_json = get_spotify_json('sample_genius_data.json')  # json is for Miracle by Caravan Palace
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = fake_json
        assert genius_stripper("Fake Song Name lol", "Fake Artist") is None

    @patch('requests.get')
    def test_that_genius_stripper_checks_for_stripper_format(self, mock_get):
        from swaglyrics_backend.issue_maker import genius_stripper
        fake_json = get_spotify_json('sample_genius_data.json')
        fake_json['response']['hits'][0]['result']['path'] = "/Caravan-palace-miracle-annotated"  # no lyrics at end
        # adjust titles so none match
        fake_json['response']['hits'][1]['result']["full_title"] = "fake title"
        fake_json['response']['hits'][4]['result']["full_title"] = "fake title"
        fake_json['response']['hits'][5]['result']["full_title"] = "fake title"

        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = fake_json
        with self.assertLogs() as logs:
            stripper = genius_stripper("Miracle", "Caravan Palace")

        assert stripper is None
        assert "Path did not end in lyrics: /Caravan-palace-miracle-annotated" in logs.output[7]

    @patch('swaglyrics_backend.issue_maker.requests.get')
    def test_that_check_stripper_checks_stripper(self, fake_get):
        from swaglyrics_backend.issue_maker import check_stripper
        fake_get.return_value.status_code = 200
        assert check_stripper("Hello", "Adele") is True

    def test_that_title_mismatches(self):
        from swaglyrics_backend.issue_maker import is_title_mismatched
        assert is_title_mismatched(["Bohemian", "Rhapsody", "by", "Queen"], "Miracle by Caravan Palace", 2)

    def test_that_title_not_mismatches(self):
        from swaglyrics_backend.issue_maker import is_title_mismatched
        assert not is_title_mismatched(["Bohemian", "Rhapsody", "by", "Queen"], "bohemian rhapsody by queen", 2)

    def test_that_title_not_mismatches_with_one_error(self):
        from swaglyrics_backend.issue_maker import is_title_mismatched
        assert not is_title_mismatched(["BoHemIaN", "RhaPsoDy", "2011", "bY", "queen"], "bohemian RHAPSODY By QUEEN", 2)

    @patch('swaglyrics_backend.issue_maker.get_github_token', return_value='fake token')
    @patch('swaglyrics_backend.issue_maker.requests.post')
    def test_create_issue(self, fake_post, fake_token):
        fake_post.return_value.json.return_value = {
            "html_url": "https://github.com/SwagLyrics/SwagLyrics-For-Spotify/issues/1337"
        }
        fake_post.return_value.status_code = 200
        from swaglyrics_backend.issue_maker import create_issue
        resp = create_issue('Hello', 'Adele', '1.2.0', 'Adele-Hello')

        assert resp['status_code'] == 200
        assert resp['link'] == "https://github.com/SwagLyrics/SwagLyrics-For-Spotify/issues/1337"
        assert fake_post.call_args.args[0] == 'https://api.github.com/repos/SwagLyrics/Swaglyrics-For-Spotify/issues'
        assert fake_post.call_args.kwargs['headers']['Authorization'] == "token fake token"

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

    @patch('swaglyrics_backend.issue_maker.Lyrics')
    def test_that_get_stripper_gets_stripper_from_database(self, fake_db):
        class FakeLyrics:
            def __init__(self, song=None, artist=None, stripper=None):
                self.song = song
                self.artist = artist
                self.stripper = stripper
        from swaglyrics_backend.issue_maker import app
        fake_db.query.filter.return_value.filter.return_value.first.return_value = FakeLyrics(
            song='bad vibes forever',
            artist='XXXTENTACION',
            stripper="XXXTENTACION-bad-vibes-forever"
        )
        with app.test_client() as c:
            resp = c.get('/stripper', data={'song': 'bad vibes forever', 'artist': 'XXXTENTACION'})

        assert resp.data == b"XXXTENTACION-bad-vibes-forever"

    @patch('swaglyrics_backend.issue_maker.discord_genius_logger')
    @patch('swaglyrics_backend.issue_maker.genius_stripper')
    @patch('swaglyrics_backend.issue_maker.Lyrics')
    def test_that_get_stripper_gets_genius_stripper(self, fake_db, fake_stripper, fake_logger):
        from swaglyrics_backend.issue_maker import app, limiter
        fake_db.query.filter.return_value.filter.return_value.first.return_value = None
        fake_stripper.return_value = "XXXTENTACION-bad-vibes-forever"
        with app.test_client() as c:
            limiter.enabled = False  # disable rate limiting
            resp = c.get('/stripper', data={'song': 'bad vibes forever', 'artist': 'XXXTENTACION'})

        assert resp.data == b"XXXTENTACION-bad-vibes-forever"

    @patch('swaglyrics_backend.issue_maker.discord_genius_logger')
    @patch('swaglyrics_backend.issue_maker.genius_stripper')
    @patch('swaglyrics_backend.issue_maker.Lyrics')
    def test_that_get_stripper_returns_not_found_when_no_stripper_found(self, fake_db, fake_stripper, fake_logger):
        from swaglyrics_backend.issue_maker import app, limiter
        fake_db.query.filter.return_value.filter.return_value.first.return_value = None
        fake_stripper.return_value = None
        with app.test_client() as c:
            limiter.enabled = False  # disable rate limiting
            resp = c.get('/stripper', data={'song': 'bad vibes forever', 'artist': 'XXXTENTACION'})

        assert resp.data == b""
        assert resp.status_code == 404

    @patch('swaglyrics_backend.issue_maker.db')
    def test_that_add_stripper_adds_stripper(self, app_mock):
        """
        This test doesn't test database behaviour! Only dealing with unsupported and parsing request
        """
        from swaglyrics_backend.issue_maker import app
        with app.test_client() as c:
            generate_fake_unsupported()
            resp = c.post('/add_stripper', data={'auth': '', 'song': 'Miracle', 'artist': 'Caravan Palace',
                                                 'stripper': 'Caravan-palace-miracle'})
            assert b"Added stripper for Miracle by Caravan Palace to server database successfully, " \
                   b"deleted 1 instances from unsupported.txt" == resp.data

    def test_that_add_stripper_auth_works(self):
        """
        This test doesn't test database behaviour! Only dealing with unsupported and parsing request
        """
        from swaglyrics_backend.issue_maker import app
        with app.test_client() as c:
            resp = c.post('/add_stripper', data={'auth': 'wrong auth', 'song': 'oui', 'artist': 'Jeremih',
                                                 'stripper': 'Jeremih-oui'})

        assert resp.status_code == 403

    def test_that_delete_unsupported_auth_works(self):
        """
        This test doesn't test database behaviour! Only dealing with unsupported and parsing request
        """
        from swaglyrics_backend.issue_maker import app
        with app.test_client() as c:
            resp = c.post('/delete_unsupported', data={'auth': 'wrong auth', 'song': 'oui', 'artist': 'Jeremih'})

        assert resp.status_code == 403

    def test_that_master_unsupported_reads_data(self):
        from swaglyrics_backend.issue_maker import app
        with app.test_client() as c:
            generate_fake_unsupported()
            req = c.get('/master_unsupported')
            assert req.response is not None

    def test_that_delete_line_deletes_line_from_master_unsupported(self):
        from swaglyrics_backend.issue_maker import app
        with app.test_client() as c:
            generate_fake_unsupported()
            response = c.post('/delete_unsupported', data={'auth': '', 'song': 'Supersonics',
                                                           'artist': 'Caravan Palace'})
            assert response.data == b"Removed 1 instances of Supersonics by Caravan " \
                                    b"Palace from unsupported.txt successfully."

    def test_that_test_route_works(self):
        from swaglyrics_backend.issue_maker import app
        with app.test_client() as c:
            resp = c.get('/test')
        assert resp.data == b'69aaa69'

    def test_swaglyrics_version_route(self):
        from swaglyrics_backend.issue_maker import app
        from swaglyrics import __version__ as version
        with app.test_client() as c:
            resp = c.get('/version')
        assert resp.data == version.encode()

    def test_landing_page(self):
        from swaglyrics_backend.issue_maker import app
        generate_fake_unsupported()
        with app.test_client() as c:
            resp = c.get('/')

        assert b'The SwagLyrics Backend and API is housed here.' in resp.data
        assert b'Heroku' not in resp.data
        assert b'Miracle by Caravan Palace' in resp.data

    @patch('swaglyrics_backend.issue_maker.get_ipaddr', return_value='1.2.3.4')
    def test_that_slow_is_rate_limited(self, fake_ip):
        from swaglyrics_backend.issue_maker import app, limiter
        with app.test_client() as c:
            limiter.enabled = True  # enable rate limiting
            resp = c.get('/slow')
            # the second one should be rate limited
            resp_again = c.get('/slow')
        assert resp.data == b'24'
        assert resp_again.status_code == 429

    def test_update_unsupported(self):
        from swaglyrics import __version__
        from swaglyrics_backend.issue_maker import app, limiter
        with app.test_client() as c:
            app.config['TESTING'] = True
            limiter.enabled = False  # disable rate limiting
            generate_fake_unsupported()
            # fix soon
            # self.assertEqual(
            #     update(), 'Please update SwagLyrics to the latest version to get better support :)')

            resp = c.post('/unsupported', data={'version': str(__version__),
                                                'song': 'Miracle',
                                                'artist': 'Caravan Palace'})
            # Test correct output given song and artist that exist in unsupported.txt
            assert resp.data == b"Issue already exists on the GitHub repo. " \
                                b"\nhttps://github.com/SwagLyrics/SwagLyrics-For-Spotify/issues"

    def test_unsupported_key_error(self):
        from swaglyrics_backend.issue_maker import app, limiter

        with app.test_client() as c:
            app.config['TESTING'] = True
            limiter.enabled = False  # disable rate limiting
            # fix soon
            # self.assertEqual(
            #     update(), 'Please update SwagLyrics to the latest version to get better support :)')

            resp = c.post('/unsupported', data={'song': 'Miracle', 'artist': 'Caravan Palace'})

            assert resp.data == b"Please update SwagLyrics to the latest version (v1.2.0), it contains a hotfix for " \
                                b"Genius A/B testing :)"

    def test_unsupported_old_version(self):
        from swaglyrics_backend.issue_maker import app, limiter

        with app.test_client() as c:
            app.config['TESTING'] = True
            limiter.enabled = False  # disable rate limiting
            resp = c.post('/unsupported', data={'version': '1.1.0',
                                                'song': 'Miracle',
                                                'artist': 'Caravan Palace'})

            assert resp.data == b"Please update SwagLyrics to the latest version (v1.2.0), it contains a hotfix for " \
                                b"Genius A/B testing :)"

    def test_unsupported_trivial_case_does_not_make_issue(self):
        from swaglyrics_backend.issue_maker import app, limiter

        with app.test_client() as c:
            app.config['TESTING'] = True
            limiter.enabled = False  # disable rate limiting
            resp = c.post('/unsupported', data={'version': '1.2.0',
                                                'song': 'Navajo',
                                                'artist': 'Masego'})

            assert resp.data == b"Lyrics for Navajo by Masego may not exist on Genius.\n" \
                                b"If you feel there's an error, open a ticket at " \
                                b"https://github.com/SwagLyrics/SwagLyrics-For-Spotify/issues"

    @patch('swaglyrics_backend.issue_maker.check_song', return_value=True)
    @patch('swaglyrics_backend.issue_maker.check_stripper', return_value=False)
    @patch('swaglyrics_backend.issue_maker.create_issue')
    def test_unsupported_not_trivial_case_does_make_issue(self, fake_issue, fake_check, another_fake_check):
        from swaglyrics_backend.issue_maker import app, limiter
        fake_issue.return_value = {
            "status_code": 201,
            "link": "https://github.com/SwagLyrics/SwagLyrics-For-Spotify/issues/2443"  # fake issue creation
        }
        with app.test_client() as c:
            app.config['TESTING'] = True
            limiter.enabled = False  # disable rate limiting
            generate_fake_unsupported()
            resp = c.post('/unsupported', data={'version': '1.2.0',
                                                'song': "Avatar's Love (braces not trivial)",
                                                'artist': 'Rachel Clinton'})

        with open('unsupported.txt') as f:
            data = f.readlines()

        assert "Avatar's Love (braces not trivial) by Rachel Clinton\n" in data
        assert resp.data == b"Lyrics for that song may not exist on Genius. Created issue on the GitHub repo for " \
                            b"Avatar's Love (braces not trivial) by Rachel Clinton to investigate further. " \
                            b"\nhttps://github.com/SwagLyrics/SwagLyrics-For-Spotify/issues/2443"

    @patch('swaglyrics_backend.issue_maker.check_song', return_value=True)
    @patch('swaglyrics_backend.issue_maker.check_stripper', return_value=False)
    @patch('swaglyrics_backend.issue_maker.create_issue')
    def test_unsupported_issue_making_error(self, fake_issue, fake_check, another_fake_check):
        from swaglyrics_backend.issue_maker import app, limiter
        fake_issue.return_value = {
            "status_code": 500,  # error
            "link": ""
        }
        with app.test_client() as c:
            app.config['TESTING'] = True
            limiter.enabled = False  # disable rate limiting
            generate_fake_unsupported()
            resp = c.post('/unsupported', data={'version': '1.2.0',
                                                'song': "purple.laces [string%@*]",
                                                'artist': 'lost spaces'})
        with open('unsupported.txt') as f:
            data = f.readlines()

        assert "purple.laces [string%@*] by lost spaces\n" in data
        assert resp.data == b"Logged purple.laces [string%@*] by lost spaces in the server."

    @patch('swaglyrics_backend.issue_maker.check_song', return_value=False)  # cuz fishy
    @patch('swaglyrics_backend.issue_maker.check_stripper', return_value=False)
    def test_unsupported_fishy_requests_handling(self, fake_check, another_fake_check):
        from swaglyrics_backend.issue_maker import app, limiter
        with app.test_client() as c:
            app.config['TESTING'] = True
            limiter.enabled = False  # disable rate limiting
            resp = c.post('/unsupported', data={'version': '1.2.0',
                                                'song': "evbiurevbiuprvb",  # fake issue spam
                                                'artist': 'bla$bla%bla'})  # special characters to trip the trivial case

        assert resp.data == b"That's a fishy request, that song doesn't seem to exist on Spotify. " \
                            b"\nIf you feel there's an error, open a ticket at " \
                            b"https://github.com/SwagLyrics/SwagLyrics-For-Spotify/issues"
