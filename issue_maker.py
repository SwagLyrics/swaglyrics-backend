import time
import re
import os
import requests
import git
import json
from requests.auth import HTTPBasicAuth
from flask import Flask, request, abort, render_template
from swaglyrics.cli import stripper
from swaglyrics import __version__
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_ipaddr

from utils import is_valid_signature, request_from_github

app = Flask(__name__)
limiter = Limiter(
    app,
    key_func=get_ipaddr,
    default_limits=["1000 per day"]
)

username = os.environ['USERNAME']
gh_token = os.environ['GH_TOKEN']
passwd = os.environ['PASSWD']

# declare the Spotify token and expiry time
token = ''
t_expiry = 0

gh_issue_text = "If you feel there's an error, open a ticket at " \
                "https://github.com/SwagLyrics/SwagLyrics-For-Spotify/issues"
update_text = 'Please update SwagLyrics to the latest version to get better support :)'

# genius stripper regex
alg = re.compile(r'[^\sa-zA-Z0-9]+')
gstr = re.compile(r'(?<=/)[-a-zA-Z0-9]+(?=-lyrics$)')
# webhook regex
wdt = re.compile(r'(.+) by (.+) unsupported.')
# artist and song regex
asrg = re.compile(r'[A-Za-z\s]+')

SQLALCHEMY_DATABASE_URI = "mysql+mysqlconnector://{username}:{password}@{username}.mysql.pythonanywhere-services." \
                          "com/{username}${databasename}".format(
                                                                username=username,
                                                                password=os.environ['DB_PWD'],
                                                                databasename="strippers",
                                                            )
app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
app.config["SQLALCHEMY_POOL_RECYCLE"] = 280
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


# you should manually initialize the db for first run
# >>> from issue_maker import db
# >>> db.create_all()


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


def update_token():
    """
    Update the global Spotify Access Token variable and expiry time.
    :return:
    """
    global token, t_expiry
    r = requests.post('https://accounts.spotify.com/api/token', data={
        'grant_type': 'client_credentials'}, auth=HTTPBasicAuth(os.environ['C_ID'], os.environ['SECRET']))
    token = r.json()['access_token']
    t_expiry = time.time()
    print('updated token', token[:41])


# initialize the Spotify token and expiry time
update_token()


def genius_stripper(song, artist):
    """
    Try to obtain a stripper via the Genius API, given song and artist.

    The title passed to the function is compared to the title obtained from Genius to make sure it's a match.
    At least half the words should match between the two, this is not very strict so as to reduce false negatives.
    :param song: the song name
    :param artist: the artist
    :return: stripper
    """
    title = f'{song} by {artist}'
    print(f'getting stripper from Genius for {title}')
    url = 'https://api.genius.com/search'
    headers = {"Authorization": "Bearer {token}".format(token=os.environ['GENIUS'])}
    params = {'q': f'{song} {artist}'}
    r = requests.get(url, params=params, headers=headers)
    # remove punctuation before comparison
    title = re.sub(alg, '', title)
    print(f'stripped title: {title}')

    words = title.split()

    max_err = len(words) // 2
    # allow half length mismatch
    print(f'max_err is set to {max_err}')

    if r.status_code == 200:
        data = r.json()
        if data['meta']['status'] == 200:
            hits = data['response']['hits']
            for hit in hits:
                full_title = hit['result']['full_title']
                print(f'full title: {full_title}')
                # remove punctuation before comparison
                full_title = re.sub(alg, '', full_title)
                print(f'stripped full title: {full_title}')

                err_cnt = 0

                for word in words:
                    if word.lower() not in full_title.lower():
                        err_cnt += 1
                        print(f'broke on {word}')
                        if err_cnt > max_err:
                            break
                else:
                    # return stripper as no mismatch
                    path = gstr.search(hit['result']['path'])
                    try:
                        stripper = path.group()
                        print(f'stripper found: {stripper}')
                        return stripper
                    except AttributeError:
                        print(f'Path did not end in lyrics: {path}')

            print('stripper not found')
            return None


def create_issue(song, artist, version, stripper='not supported yet'):
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
    r = requests.post('https://api.github.com/repos/SwagLyrics/swaglyrics-for-spotify/issues',
                      auth=HTTPBasicAuth(username, gh_token), json=json)

    return {
        'status_code': r.status_code,
        'link': r.json()['html_url']
    }


def check_song(song, artist):
    """
    Check if song, artist pair exist on Spotify or not using the Spotify API.

    This is done to verify if the data received is legit or not. An exact comparison is done since the data is
    supposed to be from Spotify in the first place.
    :param song: the song to check
    :param artist: the artist of song
    :return: Boolean depending if it was found on Spotify or not
    """
    global token, t_expiry
    print('using token', token[:41])
    if t_expiry + 3600 - 300 < time.time():  # check if token expired ( - 300 to add buffer of 5 minutes)
        update_token()
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get('https://api.spotify.com/v1/search', headers=headers, params={'q': f'{song} {artist}',
                                                                                   'type': 'track'})
    try:
        data = r.json()['tracks']['items']
    except KeyError:
        return False
    if data:
        print(data[0]['artists'][0]['name'], data[0]['name'])
        if data[0]['name'] == song and data[0]['artists'][0]['name'] == artist:
            print(f'{song} and {artist} legit on Spotify')
            return True
    else:
        print(f'{song} and {artist} don\'t seem legit.')
    return False


# def check_stripper(song, artist):
#     # check if song has a lyrics page on genius
#     r = requests.get(f'https://genius.com/{stripper(song, artist)}-lyrics')
#     return r.status_code == requests.codes.ok


def del_line(song, artist):
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

        print(song, artist, stripped, version)
        if version < '1.1.1':
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
        if check_song(song, artist):
            with open('unsupported.txt', 'a', encoding='utf-8') as f:
                f.write(f'{song} by {artist}\n')

            issue = create_issue(song, artist, version, stripped)

            if issue['status_code'] == 201:
                print(f'Created issue on the GitHub repo for {song} by {artist}.')
                return 'Lyrics for that song may not exist on Genius. ' \
                       'Created issue on the GitHub repo for {song} by {artist} to investigate ' \
                       'further. \n{link}'.format(song=song, artist=artist, link=issue['link'])
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
        print('using genius_stripper: {}'.format(g_stripper))
        return g_stripper
    else:
        print('did not find stripper to return :(')
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
@request_from_github()
@limiter.exempt
def issue_webhook():
    if request.method != 'POST':
        return 'OK'
    else:
        abort_code = 418

        not_relevant = "Event type not unsupported song issue closed."

        event = request.headers.get('X-GitHub-Event')
        if event == "ping":
            return json.dumps({'msg': 'Hi!'})
        if event != "issues":
            return json.dumps({'msg': "Wrong event type"})

        x_hub_signature = request.headers.get('X-Hub-Signature')
        # webhook content type should be application/json for request.data to have the payload
        # request.data is empty in case of x-www-form-urlencoded
        if not is_valid_signature(x_hub_signature, request.data):
            print('Deploy signature failed: {sig}'.format(sig=x_hub_signature))
            abort(abort_code)

        payload = request.get_json()
        if payload is None:
            print(f'Deploy payload is empty: {payload}')
            abort(abort_code)

        try:
            label = payload['issue']['labels'][0]['name']
            # should be unsupported song for our purposes
            repo = payload['repository']['name']
            # should be from the SwagLyrics for Spotify repo
        except IndexError:
            return not_relevant

        if payload['action'] == 'closed' and label == 'unsupported song' and repo == 'SwagLyrics-For-Spotify':
            # delete line from unsupported.txt if issue closed
            title = payload['issue']['title']
            title = wdt.match(title)
            song = title.group(1)
            artist = title.group(2)
            print(f'{song} by {artist} is to be deleted.')
            cnt = del_line(song, artist)
            return f'Deleted {cnt} instances from unsupported.txt'

        return not_relevant


@app.route('/update_server', methods=['POST'])
@request_from_github()
@limiter.exempt
def update_webhook():
    if request.method != 'POST':
        return 'OK'
    else:
        abort_code = 418

        event = request.headers.get('X-GitHub-Event')
        if event == "ping":
            return json.dumps({'msg': 'Hi!'})
        if event != "push":
            return json.dumps({'msg': "Wrong event type"})

        x_hub_signature = request.headers.get('X-Hub-Signature')
        # webhook content type should be application/json for request.data to have the payload
        # request.data is empty in case of x-www-form-urlencoded
        if not is_valid_signature(x_hub_signature, request.data):
            print('Deploy signature failed: {sig}'.format(sig=x_hub_signature))
            abort(abort_code)

        payload = request.get_json()
        if payload is None:
            print(f'Deploy payload is empty: {payload}')
            abort(abort_code)

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
        print(f'{build_commit}')
        return 'Updated PythonAnywhere server to commit {commit}'.format(commit=commit_hash)


@app.route('/version')
def latest_version():
    # latest swaglyrics version
    return __version__


@app.route('/test')
def swag():
    return os.environ['BLAZEIT']


@app.route("/slow")
@limiter.limit("1 per day")
def slow():
    return "24"


@app.route('/')
@limiter.exempt
def hello():
    with open('unsupported.txt', 'r', encoding="utf-8") as f:
        data = f.readlines()
    return render_template('hello.html', unsupported_songs=data)
