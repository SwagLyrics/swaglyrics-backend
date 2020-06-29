import json
import os


def get_spotify_json(filename):
    filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    with open(filename, 'r') as f:
        raw_json = f.read()
        return json.loads(raw_json)


def generate_fake_unsupported():
    with open('unsupported.txt', 'w') as f:
        f.write('Miracle by Caravan Palace\nSupersonics by Caravan Palace\n')