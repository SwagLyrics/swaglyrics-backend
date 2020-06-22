import os
import time
import unittest
from unittest.mock import patch

from requests import Response


class TestBase(unittest.TestCase):
    def setUp(self):
        patch.dict(os.environ, {'WEBHOOK_SECRET': '',
                                'GH_TOKEN': '',
                                'PASSWD': '',
                                'DB_PWD': '',
                                'C_ID': '',
                                'SECRET': '',
                                'USERNAME': '',
                                'GENIUS': ''}).start()

        if "/tests" not in os.getcwd():
            os.chdir("tests")


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

    def test_that_deletes_line(self):
        from swaglyrics_backend.issue_maker import del_line
        song = "Supersonics"
        artist = "Caravan Palace"
        generate_fake_unsupported()
        del_line(song, artist)
        with open('unsupported.txt', 'r') as f:
            lines = f.readlines()
            self.assertFalse(song + " by " + artist in lines)

    @patch('requests.Response.json', return_value=sample_spotify_json)
    @patch('requests.post', return_value=Response())
    def test_update_token(self, requests_mock, json_mock):
        from swaglyrics_backend.issue_maker import get_spotify_token
        from swaglyrics_backend import issue_maker
        get_spotify_token()
        self.assertTrue(issue_maker.spotify_token != '')
        self.assertTrue(issue_maker.spotify_token_expiry != 0)

    @patch('swaglyrics_backend.issue_maker.get_spotify_token', return_value={"access_token": ""})
    @patch('requests.Response.json', return_value={'error': 'yes'})
    @patch('requests.get', return_value=Response())
    def test_check_song_returns_false_on_bad_response(self, requests_mock, response_mock, spotify_mock):
        from swaglyrics_backend.issue_maker import check_song
        from swaglyrics_backend import issue_maker
        issue_maker.t_expiry = time.time() + 3600
        self.assertFalse(check_song("Miracle", "Caravan Palace"))

    @patch('swaglyrics_backend.issue_maker.get_spotify_token', return_value={"access_token": ""})
    @patch('requests.Response.json', return_value={'error', 'yes'})
    @patch('requests.get', return_value=Response())
    @patch('swaglyrics_backend.issue_maker.check_song_instrumental', return_value=False)
    def test_that_check_song_returns_true(self, check_instrumental, mock_get, mock_response, spotify_token):
        from swaglyrics_backend.issue_maker import check_song
        mock_response.return_value = get_correct_spotify_search_json(
            'correct_spotify_data.json')

        self.assertTrue(check_song("Miracle", "Caravan Palace"))

    @patch('swaglyrics_backend.issue_maker.get_spotify_token', return_value={"access_token": ""})
    @patch('requests.Response.json', return_value=unknown_song_json)
    @patch('requests.get', return_value=Response())
    def test_that_check_song_returns_false_on_non_legit_song(self, mock_get, mock_response, spotify_token):
        from swaglyrics_backend.issue_maker import check_song
        self.assertFalse(check_song("Miracle", "Caravan Palace"))

    @patch('requests.Response.json', return_value=None)
    @patch('requests.get', return_value=Response())
    def test_that_stripper_returns_none(self, mock_get, mock_response):
        from swaglyrics_backend.issue_maker import genius_stripper
        self.assertIsNone(genius_stripper("Miracle", "Caravan Palace"))

    @patch('requests.Response.json')
    @patch('requests.get')
    def test_that_stripper_returns_stripper(self, mock_get, mock_response):
        response = Response()
        response.status_code = 200
        mock_get.return_value = response
        mock_response.return_value = get_correct_spotify_search_json(
            'sample_genius_data.json')
        from swaglyrics_backend.issue_maker import genius_stripper
        self.assertEqual(genius_stripper(
            "Miracle", "Caravan Palace"), "Caravan-palace-miracle")

    def test_that_title_mismatches(self):
        from swaglyrics_backend.issue_maker import is_title_mismatched
        self.assertTrue(
            is_title_mismatched(["Bohemian", "Rhapsody", "by", "Queen"], "Miracle by Caravan Palace", 2))

    def test_that_title_not_mismatches(self):
        from swaglyrics_backend.issue_maker import is_title_mismatched
        self.assertFalse(
            is_title_mismatched(["Bohemian", "Rhapsody", "by", "Queen"], "bohemian rhapsody by queen", 2))

    def test_that_title_not_mismatches_with_one_error(self):
        from swaglyrics_backend.issue_maker import is_title_mismatched
        self.assertFalse(is_title_mismatched(["BoHemIaN", "RhaPsoDy", "2011", "bY", "queen"], "bohemian RHAPSODY "
                                                                                              "By QUEEN", 2))

    @patch('swaglyrics_backend.issue_maker.db')
    def test_that_add_stripper_adds_stripper(self, app_mock):
        """
        This test doesn't test database behaviour! Only dealing with unsupported and parsing request
        """
        from swaglyrics_backend.issue_maker import app, add_stripper
        generate_fake_unsupported()
        with app.test_client() as c:
            c.post('/add_stripper', data={'auth': '',
                                          'song': 'Miracle',
                                          'artist': 'Caravan Palace',
                                          'stripper': 'Caravan-palace-miracle'})
            generate_fake_unsupported()
            result = add_stripper()
            self.assertEqual(f"Added stripper for Miracle by Caravan Palace to server database successfully, "
                             f"deleted 1 instances from "
                             "unsupported.txt", result)

    def test_that_master_unsupported_reads_data(self):
        from swaglyrics_backend.issue_maker import app
        with app.test_client() as c:
            generate_fake_unsupported()
            req = c.get('/master_unsupported')
            self.assertIsNotNone(req.response)

    def test_that_delete_line_deletes_line_from_master_unsupported(self):
        from swaglyrics_backend.issue_maker import app, delete_line
        with app.test_client() as c:
            c.post('/delete_unsupported', data={'auth': '',
                                                'song': 'Supersonics',
                                                'artist': 'Caravan Palace'})
            generate_fake_unsupported()
            response = delete_line()
            self.assertEqual(response, "Removed 1 instances of Supersonics by Caravan Palace from "
                                       "unsupported.txt successfully.")

    def test_update(self):
        from swaglyrics import __version__
        from swaglyrics_backend.issue_maker import update
        from flask import Flask

        app = Flask(__name__)
        with app.test_request_context('/'):
            with app.test_client() as c:
                app.config['TESTING'] = True

                c.post('/unsupported', data={'version': '0.9.0',
                                             'song': 'Miracle',
                                             'artist': 'Caravan Palace'})
                generate_fake_unsupported()
                # fix soon
                # self.assertEqual(
                #     update(), 'Please update SwagLyrics to the latest version to get better support :)')

                c.post('/unsupported', data={'version': str(__version__),
                                             'song': 'Miracle',
                                             'artist': 'Caravan Palace'})
                """Test correct output given song and artist that exist in unsupported.txt"""
                self.assertEqual(update(),
                                 "Issue already exists on the GitHub repo. "
                                 "\nhttps://github.com/SwagLyrics/SwagLyrics-For-Spotify/issues")


def get_correct_spotify_search_json(filename):
    import flask
    with open(filename, 'r') as r:
        raw_json = r.read()
        return flask.json.loads(raw_json)


def generate_fake_unsupported():
    with open('unsupported.txt', 'w') as f:
        f.write('Miracle by Caravan Palace\nSupersonics by Caravan Palace\n')
