import json
import logging
import os
import re
import time
from datetime import datetime as dt
from typing import Optional, List, Dict, Any

import git
import requests
from flask import Flask, request, abort, render_template
from flask_limiter import Limiter
from flask_limiter.util import get_ipaddr
from flask_sqlalchemy import SQLAlchemy
from requests.auth import HTTPBasicAuth
from swaglyrics import __version__
from swaglyrics.cli import stripper, spc

from swaglyrics_backend.utils import request_from_github, validate_request, get_jwt, get_installation_access_token

# start flask app
app = Flask(__name__)

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# request limiter base rules
limiter = Limiter(
    app,
    key_func=get_ipaddr,
    default_limits=["1000 per day"]
)

# define a JSON-like Dict type hint
JSONDict = Dict[str, Any]

# database env variables
username = os.environ['USERNAME']
passwd = os.environ['PASSWD']

# github variables
gh_token = ''
gh_token_expiry = 0

# declare the Spotify token and expiry time
spotify_token = ''
spotify_token_expiry = 0

gh_issue_text = "If you feel there's an error, open a ticket at " \
                "https://github.com/SwagLyrics/SwagLyrics-For-Spotify/issues"
# update_text = 'Please update SwagLyrics to the latest version to get better support :)'
update_text = 'Please update SwagLyrics to the latest version (v1.2.0), it contains a hotfix for Genius A/B testing :)'

# genius stripper regex
alg = re.compile(r'[^\sa-zA-Z0-9]+')
gstr = re.compile(r'(?<=/)[-a-zA-Z0-9]+(?=-lyrics$)')
aug = re.compile(r'(\([^)]*\)|- .*)')  # remove braces and included text and text after '- ' to search better on Genius

# webhook regex
wdt = re.compile(r'(.+) by (.+) unsupported.')

# artist and song regex
asrg = re.compile(r'[A-Za-z\s]+')

SQLALCHEMY_DATABASE_URI = "mysql+mysqlconnector://{username}:{password}@{username}.mysql.pythonanywhere-services." \
                          "com/{username}${databasename}".format(
                                                                username=username,
                                                                password=os.environ['DB_PWD'],
                                                                databasename="strippers"
                                                            )
app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
app.config["SQLALCHEMY_POOL_RECYCLE"] = 280
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

"""
 you should manually initialize the db for first run
 >>> from issue_maker import db
 >>> db.create_all()
"""


class Lyrics(db.Model):
    __tablename__ = "all_strippers"

    id = db.Column(db.Integer, primary_key=True)
    song = db.Column(db.String(4096))
    artist = db.Column(db.String(4096))
    stripper = db.Column(db.String(4096))

    def __init__(self, song, artist, stripper):
        self.song = song
        self.artist = artist
        self.stripper = stripper


# ------------------- important functions begin here ------------------- #

def get_github_token() -> str:
    """
    Returns the github auth token, update if expired.
    :return: github token
    """
    global gh_token, gh_token_expiry
    # 3 minutes buffer
    if gh_token_expiry - 180 > time.time():
        logging.info(f"using github token: {gh_token[:22]}")
        return gh_token
    logging.info("updating github token")
    private_pem = os.environ['PRIVATE_PEM']
    jwt = get_jwt(os.environ['APP_ID'], private_pem)
    response = get_installation_access_token(jwt, os.environ['INST_ID']).json()
    gh_token = response["token"]
    gh_token_expiry = dt.strptime(response["expires_at"], "%Y-%m-%dT%H:%M:%S%z").timestamp()
    logging.info(f"github token updated: {gh_token[:22]}")
    return gh_token


def get_spotify_token() -> str:
    """
    Return the spotify auth token, update if expired.
    :return: spotify token
    """
    global spotify_token, spotify_token_expiry
    # check if token expired ( - 300 to add buffer of 5 minutes)
    if spotify_token_expiry - 300 > time.time():
        logging.info(f'using spotify token: {spotify_token[:41]}')
        return spotify_token
    r = requests.post('https://accounts.spotify.com/api/token', data={
        'grant_type': 'client_credentials'}, auth=HTTPBasicAuth(os.environ['C_ID'], os.environ['SECRET']))
    spotify_token = r.json()['access_token']
    # token valid for an hour
    spotify_token_expiry = time.time() + 3600
    logging.info(f'updated spotify token: {spotify_token[:41]}')
    return spotify_token


def genius_stripper(song: str, artist: str) -> Optional[str]:
    """
    Try to obtain a stripper via the Genius API, given song and artist.

    The title passed to the function is compared to the title obtained from Genius to make sure it's a match.
    At least half the words should match between the two, this is not very strict so as to reduce false negatives.
    :param song: the song name
    :param artist: the artist
    :return: stripper
    """
    title = f'{song} by {artist}'
    logging.info(f'getting stripper from Genius for {title}')
    url = 'https://api.genius.com/search'
    headers = {"Authorization": f"Bearer {os.environ['GENIUS']}"}
    song = spc.sub(' ', aug.sub('', song))  # strip extra info from song and combine spaces
    logging.info(f'stripped song: {song}')
    params = {'q': f'{song} {artist}'}
    r = requests.get(url, params=params, headers=headers)
    # remove punctuation before comparison
    title = re.sub(alg, '', title)
    logging.info(f'stripped title: {title}')

    words = title.split()
    max_err = len(words) // 2

    # allow half length mismatch
    logging.info(f'max_err is set to {max_err}')

    if r.status_code == 200:
        data = r.json()
        if data['meta']['status'] == 200:
            hits = data['response']['hits']
            for hit in hits:
                full_title = hit['result']['full_title']
                logging.info(f'    full title: {full_title}')
                # remove punctuation before comparison
                full_title = re.sub(alg, '', full_title)
                logging.info(f'    stripped full title: {full_title}')

                if not is_title_mismatched(words, full_title, max_err):
                    # return stripper as no mismatch
                    path = gstr.search(hit['result']['path'])
                    try:
                        stripper = path.group()
                        logging.info(f'stripper found: {stripper}')
                        return stripper
                    except AttributeError:
                        logging.warning(f'Path did not end in lyrics: {path}')

            logging.info('stripper not found')
            return None


def is_title_mismatched(words: List[str], full_title: str, max_err: int) -> bool:
    mismatch = [word for word in words if word.lower() not in full_title.lower()]
    logging.debug(f"broke on {mismatch}")
    return len(mismatch) > max_err


def create_issue(song: str, artist: str, version: str, stripper: str = 'not supported yet') -> JSONDict:
    """
    Create an issue on the SwagLyrics for Spotify repo when a song, artist pair is not supported.
    :param song: the song name
    :param artist: the artist
    :param version: swaglyrics version of client
    :param stripper: stripper generated from the client
    :return: json response with the status code and link to issue
    """
    json = {
        "title": f"{song} by {artist} unsupported.",
        "body": "Check if issue with swaglyrics or whether song lyrics unavailable on Genius. \n<hr>\n <tt><b>"
                f"stripper -> {stripper}</b>\n\nversion -> {version}</tt>",
        "labels": ["unsupported song"]
    }
    headers = {
                "Authorization": f"token {get_github_token()}",
                "Accept": "application/vnd.github.machine-man-preview+json"
    }

    r = requests.post('https://api.github.com/repos/SwagLyrics/Swaglyrics-For-Spotify/issues',
                      headers=headers, json=json)

    return {
        'status_code': r.status_code,
        'link': r.json()['html_url']
    }


def check_song(song: str, artist: str) -> bool:
    """
    Check if song, artist pair exist on Spotify or not using the Spotify API. Also checks if song is instrumental
    in which case it would not have lyrics.

    This is done to verify if the data received is legit or not. An exact comparison is done since the data is
    supposed to be from Spotify in the first place.
    :param song: the song to check
    :param artist: the artist of song
    :return: Boolean depending if it was found on Spotify or not
    """
    headers = {"Authorization": f"Bearer {get_spotify_token()}"}
    r = requests.get('https://api.spotify.com/v1/search', headers=headers, params={'q': f'{song} {artist}',
                                                                                   'type': 'track'})
    try:
        data = r.json()['tracks']['items']
    except KeyError:
        return False
    if data:
        track = data[0]
        logging.info(f"song: {track['name']}, artist: {track['artists'][0]['name']}")
        if track['name'] == song and track['artists'][0]['name'] == artist:
            logging.info(f'{song} and {artist} legit on Spotify')
            if not check_song_instrumental(track, headers):
                return True
            logging.info(f'{song} by {artist} seems to be instrumental')
    else:
        logging.info(f'{song} and {artist} don\'t seem legit.')

    return False


def check_song_instrumental(track: JSONDict, headers: Dict[str, str]) -> bool:
    """
    Helper function to determine if song is instrumental using spotify audio features API.

    Returns true if it considers a song to be instrumental.
    """
    metadata = requests.get(f'https://api.spotify.com/v1/audio-features/{track["id"]}', headers=headers).json()
    if metadata["instrumentalness"] > 0.45 and metadata["speechiness"] < 0.04:
        return True
    return False


def check_stripper(song: str, artist: str) -> bool:
    # check if song has a lyrics page on genius
    r = requests.get(f'https://genius.com/{stripper(song, artist)}-lyrics')
    return r.status_code == requests.codes.ok


def del_line(song: str, artist: str) -> int:
    # delete song and artist from unsupported.txt
    with open('unsupported.txt', 'r') as f:
        lines = f.readlines()
    with open('unsupported.txt', 'w') as f:
        cnt = 0
        for line in lines:
            if line == f"{song} by {artist}\n":
                cnt += 1
                continue
            f.write(line)
    # return number of lines deleted
    return cnt


def discord_deploy(payload: JSONDict) -> None:
    """
    sends message to Discord server when deploy from github to backend successful.
    """
    # https://discordapp.com/developers/docs/resources/webhook#execute-webhook
    url = f"https://discord.com/api/webhooks/{os.environ['DISCORD_URL']}?wait=true"
    head_commit = payload["head_commit"]
    author = head_commit["author"]
    json = {
        "embeds": [{
            "title": head_commit["message"].split('\n')[0],  # split in case commits squashed
            "description": f"Updated [PythonAnywhere server](https://api.swaglyrics.dev) to commit "
                           f"`{head_commit['id']}`.",
            "url": head_commit["url"],
            "thumbnail": {
                "url": "https://avatars2.githubusercontent.com/u/48502066?v=4"
            },
            "timestamp": head_commit["timestamp"],
            "color": 1501879,
            "author": {
                "name": author["name"],
                "url": f"https://github.com/{author['username']}",
                "icon_url": f"https://github.com/{author['username']}.png",
            }
        }]
    }

    r = requests.post(url, json=json)
    if r.status_code == requests.codes.ok:
        logging.info("sent discord message")
    else:
        logging.error(f"discord message send failed: {r.status_code}")


# ------------------- routes begin here ------------------- #


@app.route('/unsupported', methods=['POST'])
@limiter.limit("1/5seconds;20/day")
def update():
    if request.method == 'POST':
        song = request.form['song']
        artist = request.form['artist']
        stripped = stripper(song, artist)

        try:
            version = request.form['version']
        except KeyError:
            return update_text

        logging.info(f"{song=}, {artist=}, {stripped=}, {version=}")
        if version < '1.2.0':
            return update_text

        with open('unsupported.txt', 'r', encoding='utf-8') as f:
            data = f.read()
        if f'{song} by {artist}' in data:
            return 'Issue already exists on the GitHub repo. \n' \
                   'https://github.com/SwagLyrics/SwagLyrics-For-Spotify/issues'

        # check if song, artist trivial (all letters and spaces)
        if re.fullmatch(asrg, song) and re.fullmatch(asrg, artist):
            return f'Lyrics for {song} by {artist} may not exist on Genius.\n' + gh_issue_text

        # check if song exists on spotify and does not have lyrics on genius
        if check_song(song, artist) and not check_stripper(song, artist):
            with open('unsupported.txt', 'a', encoding='utf-8') as f:
                f.write(f'{song} by {artist}\n')

            issue = create_issue(song, artist, version, stripped)

            if issue['status_code'] == 201:
                logging.info(f'Created issue on the GitHub repo for {song} by {artist}.')
                return 'Lyrics for that song may not exist on Genius. ' \
                       f'Created issue on the GitHub repo for {song} by {artist} to investigate ' \
                       f'further. \n{issue["link"]}'
            else:
                return f'Logged {song} by {artist} in the server.'

        return "That's a fishy request, that song doesn't seem to exist on Spotify. \n" + gh_issue_text


@app.route("/stripper", methods=["GET", "POST"])
@limiter.limit("1/5seconds;60/hour;200/day")
def get_stripper():
    song = request.form['song']
    artist = request.form['artist']
    lyrics = Lyrics.query.filter(Lyrics.song == song).filter(Lyrics.artist == artist).first()
    if lyrics:
        return lyrics.stripper
    g_stripper = genius_stripper(song, artist)
    if g_stripper:
        logging.info(f'using genius_stripper: {g_stripper}')
        return g_stripper
    else:
        logging.info('did not find stripper to return :(')
        return '', 404


@app.route("/add_stripper", methods=["GET", "POST"])
def add_stripper():
    auth = request.form['auth']
    if auth != passwd:
        abort(403)
    song = request.form['song']
    artist = request.form['artist']
    stripper = request.form['stripper']
    lyrics = Lyrics(song=song, artist=artist, stripper=stripper)
    db.session.add(lyrics)
    db.session.commit()
    cnt = del_line(song, artist)
    return f"Added stripper for {song} by {artist} to server database successfully, deleted {cnt} instances from " \
           "unsupported.txt"


@app.route("/master_unsupported", methods=["GET", "POST"])
def master_unsupported():
    with open('unsupported.txt', 'r') as f:
        data = f.read()
    return data


# delete song from unsupported.txt when it becomes available
@app.route("/delete_unsupported", methods=["POST"])
def delete_line():
    auth = request.form['auth']
    if auth != passwd:
        abort(403)
    song = request.form['song']
    artist = request.form['artist']
    cnt = del_line(song, artist)
    return f"Removed {cnt} instances of {song} by {artist} from unsupported.txt successfully."


@app.route('/issue_closed', methods=['POST'])
@request_from_github()  # verify that request origin is github
@limiter.exempt  # disable limiter for firehose
def github_webhook():
    """
    `github_webhook` function handles all notification from GitHub relating to the org. Documentation for the webhooks can
    be found at https://developer.github.com/webhooks/
    """
    if request.method != 'POST':
        return 'OK'
    else:
        not_relevant = "Event type not unsupported song issue closed."

        event = request.headers.get('X-GitHub-Event')  # type of event
        payload = validate_request(request)

        # Respond to ping as 200 OK
        if event == "ping":
            return json.dumps({'msg': 'pong'})

        #
        elif event == "issues":
            try:
                label = payload['issue']['labels'][0]['name']
                # should be unsupported song for our purposes
                repo = payload['repository']['name']
                # should be from the SwagLyrics for Spotify repo
            except IndexError:
                return not_relevant

            """
            If the issue is concerning the `SwagLyrics-For-Spotify repo, the issue is being closed and the issue had
            the tag `unsupported song` then remove line from unsupported.txt
            """
            if payload['action'] == 'closed' and label == 'unsupported song' and repo == 'SwagLyrics-For-Spotify':
                title = payload['issue']['title']
                title = wdt.match(title)
                song = title.group(1)
                artist = title.group(2)
                logging.info(f'{song} by {artist} is to be deleted.')
                cnt = del_line(song, artist)
                return f'Deleted {cnt} instances from unsupported.txt'

        else:
            return json.dumps({'msg': 'Wrong event type'})

        return not_relevant


@app.route('/update_server', methods=['POST'])
@request_from_github()
@limiter.exempt
def update_webhook():
    # Make sure request is of type post
    if request.method != 'POST':
        return 'OK'

    event = request.headers.get('X-GitHub-Event')

    if event == "ping":
        return json.dumps({'msg': 'Hi!'})
    elif event == "push":
        payload = validate_request(request)

        if payload['ref'] != 'refs/heads/master':
            return json.dumps({'msg': 'Not master; ignoring'})

        repo = git.Repo('/var/www/sites/mysite')
        origin = repo.remotes.origin

        pull_info = origin.pull()

        if len(pull_info) == 0:
            return json.dumps({'msg': "Didn't pull any information from remote!"})
        if pull_info[0].flags > 128:
            return json.dumps({'msg': "Didn't pull any information from remote!"})

        commit_hash = pull_info[0].commit.hexsha
        build_commit = f'build_commit = "{commit_hash}"'
        logging.info(f'{build_commit}')
        if commit_hash == payload["after"]:
            # since payload is from github and pull info is what we pulled from git
            discord_deploy(payload)
        else:
            logging.error(f'weird mismatch: {commit_hash=} {payload["after"]=}')
        return f'Updated PythonAnywhere server to commit {commit_hash}'
    else:
        return json.dumps({'msg': "Wrong event type"})


# returns the latest version of swaglyrics as a string
@app.route('/version')
def latest_version():
    return __version__


# test path to check if changes propagate and env variables work
@app.route('/test')
def swag():
    """
    there are two env vars configured to test this route, BLAZEIT and SWAG.
    the values are changed and this route is checked to see if changes are live.
    """
    env_var = os.environ['SWAG']
    logging.info(f'this is a test. {env_var=}')
    return env_var


# Route to test rate limiter is functioning correctly
@app.route("/slow")
@limiter.limit("1 per day")
def slow():
    return "24"


# Dispatch webpage for website home
@app.route('/')
@limiter.exempt
def hello():
    with open('unsupported.txt', 'r', encoding="utf-8") as f:
        data = f.readlines()
    return render_template('hello.html', unsupported_songs=data)


if __name__ == "__main__":
    app.run()
