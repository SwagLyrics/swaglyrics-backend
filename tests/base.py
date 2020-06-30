import json
import os
import unittest
from unittest.mock import patch


def get_spotify_json(filename):
    filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    with open(filename, 'r') as f:
        raw_json = f.read()
        return json.loads(raw_json)


def generate_fake_unsupported():
    with open('unsupported.txt', 'w') as f:
        f.write('Miracle by Caravan Palace\nSupersonics by Caravan Palace\n')


class TestBase(unittest.TestCase):
    def setUp(self):
        patch.dict(os.environ, {
            'WEBHOOK_SECRET': '',
            'GH_TOKEN': '',
            'PASSWD': '',
            'DB_PWD': '',
            'C_ID': '',
            'SECRET': '',
            'USERNAME': '',
            'GENIUS': '',
            'DISCORD_URL_GENIUS': '',
            'SWAG': '69aaa69'
        }).start()

        if "/tests" not in os.getcwd():
            os.chdir("tests")
