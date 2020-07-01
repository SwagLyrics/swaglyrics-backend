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
    @patch('requests.Response.json', return_value=unknown_song_json)
    @patch('requests.get', return_value=Response())
    def test_that_check_song_returns_false_on_non_legit_song(self, mock_get, mock_response, spotify_token):
        from swaglyrics_backend.issue_maker import check_song
        assert not check_song("Miracle", "Caravan Palace")

    @patch('requests.Response.json', return_value=None)
    @patch('requests.get', return_value=Response())
    def test_that_stripper_returns_none(self, mock_get, mock_response):
        from swaglyrics_backend.issue_maker import genius_stripper
        assert genius_stripper("Miracle", "Caravan Palace") is None

    @patch('requests.Response.json', return_value=get_spotify_json('sample_genius_data.json'))
    @patch('requests.get')
    def test_that_stripper_returns_stripper(self, mock_get, fake_response):
        from swaglyrics_backend.issue_maker import genius_stripper
        response = Response()
        response.status_code = 200
        mock_get.return_value = response
        assert genius_stripper("Miracle", "Caravan Palace") == "Caravan-palace-miracle"

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

    @patch('swaglyrics_backend.issue_maker.requests.post')
    def test_discord_genius_logger_works_when_stripper_found(self, fake_post):
        # figure out a way to also test embed creation
        response = Response()
        response.status_code = 200
        fake_post.return_value = response
        from swaglyrics_backend.issue_maker import discord_genius_logger
        with self.assertLogs() as logs:
            discord_genius_logger('Hello', 'Adele', 'Adele-hello')
        assert "sent discord genius message" in logs.output[0]

    @patch('swaglyrics_backend.issue_maker.requests.post')
    def test_discord_genius_logger_handles_error(self, fake_post):
        response = Response()
        response.status_code = 500
        fake_post.return_value = response
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
        response = Response()
        response.status_code = 529
        fake_post.return_value = response
        from swaglyrics_backend.issue_maker import discord_instrumental_logger
        with self.assertLogs() as logs:
            discord_instrumental_logger('Up There', 'Frontliner & Geck-o', True, 0.31, 0.12)
        assert "discord instrumental message send failed: 529" in logs.output[0]

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
            assert b"Added stripper for Miracle by Caravan Palace to server database successfully, "\
                   b"deleted 1 instances from unsupported.txt" == resp.data

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
            assert response.data == b"Removed 1 instances of Supersonics by Caravan "\
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
        from swaglyrics_backend.issue_maker import app
        with app.test_client() as c:
            resp = c.get('/slow')
            # the second one should be rate limited
            resp_again = c.get('/slow')
        assert resp.data == b'24'
        assert resp_again.status_code == 429

    def test_update_unsupported(self):
        from swaglyrics import __version__
        from swaglyrics_backend.issue_maker import app

        with app.test_client() as c:
            app.config['TESTING'] = True
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
