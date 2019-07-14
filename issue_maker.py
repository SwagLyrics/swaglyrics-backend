import time
import re
import os
import requests
import git
import hmac
import hashlib
import json
from requests.auth import HTTPBasicAuth
from ipaddress import ip_address, ip_network
from functools import wraps
from flask import Flask, request, abort
from swaglyrics.cli import stripper
from swaglyrics import __version__ as version
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)
username = os.environ['USERNAME']
gh_token = os.environ['GH_TOKEN']
passwd = os.environ['PASSWD']

token = ''
t_expiry = 0

# genius stripper regex
alg = re.compile(r'[^\sa-zA-Z0-9]+')
gstr = re.compile(r'(?<=/)[-a-zA-Z0-9]+(?=-lyrics$)')
# webhook regex
wdt = re.compile(r'(.+) by (.+) unsupported.')

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


# manually initialize the db for first run

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


def update_token():
    global token, t_expiry
    r = requests.post('https://accounts.spotify.com/api/token', data={
        'grant_type': 'client_credentials'}, auth=HTTPBasicAuth(os.environ['C_ID'], os.environ['SECRET']))
    token = r.json()['access_token']
    t_expiry = time.time()
    print('updated token', token[:41])


update_token()


def genius_stripper(song, artist):
    title = f'{song} by {artist}'
    print(f'getting stripper from Genius for {title}')
    url = 'https://api.genius.com/search'
    headers = {"Authorization": "Bearer {token}".format(token=os.environ['GENIUS'])}
    params = {'q': f'{title}'}
    r = requests.get(url, params=params, headers=headers)
    title = re.sub(alg, '', title)
    print(f'stripped title: {title}')

    words = title.split()

    if r.status_code == 200:
        data = r.json()
        if data['meta']['status'] == 200:
            hits = data['response']['hits']
            for hit in hits:
                full_title = hit['result']['full_title']
                print(f'full title: {full_title}')
                full_title = re.sub(alg, '', full_title)
                print(f'stripped full title: {full_title}')

                err_cnt = 0
                max_err = len(words) // 2
                # allow half length mismatch
                print(f'max_err is set to {max_err}')

                for word in words:
                    if word.lower() not in full_title.lower():
                        err_cnt += 1
                        print(f'broke on {word}')
                        if err_cnt > max_err:
                            break
                else:
                    path = gstr.search(hit['result']['path'])
                    stripper = path.group()
                    print(f'stripper found: {stripper}')
                    return stripper

            print('stripper not found')
            return None


def create_issue(song, artist, version, stripper='not supported yet'):
    json = {
        "title": "{song} by {artist} unsupported.".format(song=song, artist=artist),
        "body": "Check if issue with swaglyrics or whether song lyrics unavailable on Genius. \n<hr>\n <tt><b>"
                "stripper -> {stripper}</b>\n\nversion -> {version}</tt>".format(stripper=stripper, version=version),
        "labels": ["unsupported song"]
    }
    r = requests.post('https://api.github.com/repos/SwagLyrics/swaglyrics-for-spotify/issues',
                      auth=HTTPBasicAuth(username, gh_token), json=json)

    return {
        'status_code': r.status_code,
        'link': r.json()['html_url']
    }


def check_song(song, artist):
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
        print(data[0]['artists'][0]['name'])
        print(data[0]['name'])
        if data[0]['name'] == song and data[0]['artists'][0]['name'] == artist:
            print('{song} and {artist} legit on Spotify'.format(song=song, artist=artist))
            return True
    else:
        print('{song} and {artist} don\'t seem legit.'.format(song=song, artist=artist))
    return False


def del_line(song, artist):
    # delete song and artist from unsupported.txt
    with open('unsupported.txt', 'r') as f:
        lines = f.readlines()
    with open('unsupported.txt', 'w') as f:
        cnt = 0
        for line in lines:
            if line == "{song} by {artist}\n".format(song=song, artist=artist):
                cnt += 1
                continue
            f.write(line)
    # return number of lines deleted
    return cnt


def is_valid_signature(x_hub_signature, data, private_key=os.environ['WEBHOOK_SECRET']):
    hash_algorithm, github_signature = x_hub_signature.split('=', 1)
    algorithm = hashlib.__dict__.get(hash_algorithm)
    encoded_key = bytes(private_key, 'latin-1')
    mac = hmac.new(encoded_key, msg=data, digestmod=algorithm)
    return hmac.compare_digest(mac.hexdigest(), github_signature)


def request_from_github(abort_code=418):
    """Provide decorator to handle request from github on the webhook."""

    def decorator(f):
        """Decorate the function to check if a request is a GitHub hook request."""

        @wraps(f)
        def decorated_function(*args, **kwargs):
            if request.method != 'POST':
                return 'OK'
            else:
                # Do initial validations on required headers
                if 'X-Github-Event' not in request.headers:
                    abort(abort_code)
                if 'X-Github-Delivery' not in request.headers:
                    abort(abort_code)
                if 'X-Hub-Signature' not in request.headers:
                    abort(abort_code)
                if not request.is_json:
                    abort(abort_code)
                if 'User-Agent' not in request.headers:
                    abort(abort_code)
                ua = request.headers.get('User-Agent')
                if not ua.startswith('GitHub-Hookshot/'):
                    abort(abort_code)

                request_ip = ip_address(u'{0}'.format(request.headers['X-Real-IP']))
                meta_json = requests.get('https://api.github.com/meta').json()
                hook_blocks = meta_json['hooks']

                # Check if the POST request is from GitHub
                for block in hook_blocks:
                    if ip_address(request_ip) in ip_network(block):
                        break
                else:
                    print("Unauthorized attempt to deploy by IP {ip}".format(ip=request_ip))
                    abort(abort_code)
                return f(*args, **kwargs)

        return decorated_function

    return decorator


@app.route('/unsupported', methods=['POST'])
def update():
    if request.method == 'POST':
        song = request.form['song']
        artist = request.form['artist']
        try:
            version = request.form['version']
        except KeyError:
            return 'Please update SwagLyrics to the latest version to get the latest support :)'
        stripped = stripper(song, artist)
        print(song, artist, stripped)

        with open('unsupported.txt', 'r') as f:
            data = f.read()
        if '{song} by {artist}'.format(song=song, artist=artist) in data:
            return 'Issue already exists on the GitHub repo. \n' \
                  'https://github.com/SwagLyrics/SwagLyrics-For-Spotify/issues'

        if check_song(song, artist):
            with open('unsupported.txt', 'a') as f:
                f.write('{song} by {artist}\n'.format(song=song, artist=artist))

            issue = create_issue(song, artist, version, stripped)
            if issue['status_code'] == 201:
                print('Created issue on the GitHub repo for {song} by {artist}.'.format(song=song, artist=artist))
                return 'Created issue on the GitHub repo for {song} by {artist}. \n{link}'.format(
                    song=song, artist=artist, link=issue['link'])
            else:
                return 'Logged {song} by {artist} in the server.'.format(song=song, artist=artist)

        return "That's a fishy request, that artist and song doesn't seem to exist on Spotify. \n" \
               "If you feel there's an error, open a ticket at " \
               "https://github.com/SwagLyrics/SwagLyrics-For-Spotify/issues"


@app.route("/stripper", methods=["GET", "POST"])
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
        return "Stripper Not Found"


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
    return "Added stripper for {song} by {artist} to server database successfully, deleted {cnt} instances from " \
           "unsupported.txt".format(song=song, artist=artist, cnt=cnt)


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
            print('Deploy payload is empty: {payload}'.format(
                payload=payload))
            abort(abort_code)

        try:
            label = payload['issue']['labels'][0]['name']
            # should be unsupported song for our purposes
        except IndexError:
            return not_relevant

        if payload['action'] == 'closed' and label == 'unsupported song':
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
            print('Deploy payload is empty: {payload}'.format(
                payload=payload))
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
    return version


@app.route('/')
def hello():
    with open('unsupported.txt', 'r') as f:
        data = f.read()
    data = ('Unsupported Songs <br>------------------------ <br><br>' + data).replace('\n', '<br>')
    return data


@app.route('/test')
def swag():
    return os.environ['SWAG']
