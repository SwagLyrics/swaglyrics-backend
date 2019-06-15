import time
import re
import os
import requests
import git
from requests.auth import HTTPBasicAuth
from flask import Flask, request, abort
from unidecode import unidecode
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)
username = os.environ['USERNAME']
gh_token = os.environ['GH_TOKEN']
genius_token = os.environ['GENIUS']
passwd = os.environ['PASSWD']
token = ''
t_expiry = 0

alg = re.compile(r'[^ a-zA-Z0-9]+')
gstr = re.compile(r'(?<=\/)[-a-zA-Z]+(?=-lyrics$)')
brc = re.compile(r'([(\[]feat[^)\]]*[)\]]|- .*)', re.I)  # matches braces with feat included or text after -
aln = re.compile(r'[^ \-a-zA-Z0-9]+')  # matches non space or - or alphanumeric characters
spc = re.compile(' *- *| +')  # matches one or more spaces
wth = re.compile(r'(?: *\(with )([^)]+)\)')  # capture text after with


SQLALCHEMY_DATABASE_URI = "mysql+mysqlconnector://{username}:{password}@{username}.mysql.pythonanywhere-services.com/{username}${databasename}".format(
    username=username,
    password=os.environ['DB_PWD'],
    databasename="strippers",
)
app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
app.config["SQLALCHEMY_POOL_RECYCLE"] = 280
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


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


db.create_all()


def update_token():
    global token, t_expiry
    c_id = os.environ['C_ID']
    secret = os.environ['SECRET']
    r = requests.post('https://accounts.spotify.com/api/token', data={
        'grant_type': 'client_credentials'}, auth=HTTPBasicAuth(c_id, secret))
    token = r.json()['access_token']
    t_expiry = time.time()
    print('updated token', token)

update_token()

def genius_stripper(song, artist):
    url = 'https://api.genius.com/search'
    headers = {"Authorization": "Bearer {token}".format(token=genius_token)}
    params = {'q': '{song} {artist}'.format(song=song, artist=artist)}
    r = requests.get(url, params=params, headers=headers)
    title = '{song} {artist}'.format(song=song, artist=artist)
    title = re.sub(alg, '', title)
    print('stripped title: {title}'.format(title=title))
    if r.status_code == 200:
        data =  r.json()
        if data['meta']['status'] == 200:
            hits = data['response']['hits']
            for hit in hits:
                full_title = hit['result']['full_title']
                print(full_title)
                for word in title.split():
                    if word.lower() not in full_title.lower():
                        print('broke on {word}'.format(word=word))
                        break
                else:
                    path = gstr.search(hit['result']['path'])
                    stripper = path.group()
                    print(stripper)
                    return stripper
            return None


def stripper(song, artist):
	"""
	Generate the url path given the song and artist to format the Genius URL with.
	Strips the song and artist of special characters and unresolved text such as 'feat.' or text within braces.
	Then concatenates both with hyphens replacing the blank spaces.
	Eg.
	>>>stripper('Paradise City', 'Guns n’ Roses')
	Guns-n-Roses-Paradise-City
	Which then formats the url to https://genius.com/Guns-n-Roses-Paradise-City-lyrics
	:param song: currently playing song
	:param artist: song artist
	:return: formatted url path
	"""
	song = re.sub(brc, '', song).strip()  # remove braces and included text with feat and text after '- '
	ft = wth.search(song)  # find supporting artists if any
	if ft:
		song = song.replace(ft.group(), '')  # remove (with supporting artists) from song
		ar = ft.group(1)  # the supporting artist(s)
		if '&' in ar:  # check if more than one supporting artist and add them to artist
			artist += '-{ar}'.format(ar=ar)
		else:
			artist += '-and-{ar}'.format(ar=ar)
	song_data = artist + '-' + song
	# swap some special characters
	url_data = song_data.replace('&', 'and')
	url_data = url_data.replace('/', ' ')  # replace / with space to support more songs, needs testing
	url_data = url_data.replace('é', 'e')
	url_data = re.sub(aln, '', url_data)  # remove punctuation and other characters
	url_data = re.sub(spc, '-', url_data)  # substitute one or more spaces to -
	return url_data

def create_issue(song, artist, version, stripper='not supported yet'):
    json = {
        "title": "{song} by {artist} unsupported.".format(song=song, artist=artist),
        "body": "Check if issue with swaglyrics or whether song lyrics unavailable on Genius. \n<hr>\n <tt><b>stripper -> {stripper}</b>\n\nversion -> {version}</tt>".format(stripper=stripper, version=version),
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
    print('using token', token)
    if t_expiry + 3600 - 300 < time.time():  # check if token expired ( - 300 to add buffer of 5 minutes)
        update_token()
    headers = {"Authorization": "Bearer {}".format(token)}
    r = requests.get('https://api.spotify.com/v1/search', headers=headers, params={'q': '{song} {artist}'.format(song=song, artist=artist), 'type': 'track'})
    try:
        data = r.json()['tracks']['items']
    except KeyError:
        pass
    if data:
        print(data[0]['artists'][0]['name'])
        print(data[0]['name'])
        if data[0]['name'] == song and data[0]['artists'][0]['name'] == artist:
            print('{song} and {artist} legit on Spotify'.format(song=song, artist=artist))
            return True
    else:
        print('{song} and {artist} don\'t seem legit.'.format(song=song, artist=artist))
    return False


@app.route('/unsupported', methods=['POST'])
def update():
    if request.method == 'POST':
        song = request.form['song']
        artist = request.form['artist']
        try:
            version = request.form['version']
        except:
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
                return 'Created issue on the GitHub repo for {song} by {artist}. \n{link}'.format(song=song, artist=artist, link=issue['link'])
            else:
                return 'Logged {song} by {artist} in the server.'.format(song=song, artist=artist)

        return "That's a fishy request, that artist and song doesn't seem to exist on Spotify. \nIf you feel there's an error, open a " \
                  "ticket at https://github.com/SwagLyrics/SwagLyrics-For-Spotify/issues"



@app.route("/stripper", methods=["GET", "POST"])
def get_stripper():
    song = request.form['song']
    artist = request.form['artist']
    lyrics = Lyrics.query.filter(Lyrics.song==song).filter(Lyrics.artist==artist).first()
    if lyrics:
        return lyrics.stripper
    g_stripper = genius_stripper(song, artist)
    if g_stripper:
        print('using genius_stripper: {}'.format(g_stripper))
        return g_stripper
    else:
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
    with open('unsupported.txt', 'r') as f:
        lines = f.readlines()
    with open('unsupported.txt', 'w') as f:
        for line in lines:
            if line != "{song} by {artist}\n".format(song=song, artist=artist):
                f.write(line)
    return "Added stripper for {song} by {artist} to server database successfully.".format(song=song, artist=artist)


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
    with open('unsupported.txt', 'r') as f:
        lines = f.readlines()
    with open('unsupported.txt', 'w') as f:
        cnt = 0
        for line in lines:
            if line == "{song} by {artist}\n".format(song=song, artist=artist):
                cnt += 1
                continue
            f.write(line)
    return f"Removed {cnt} instances of {song} by {artist} from unsupported.txt successfully."


@app.route('/update_server', methods=['POST'])
def webhook():
    if request.method == 'POST':
        repo = git.Repo('/var/www/sites/mysite')
        origin = repo.remotes.origin
        repo.create_head('master',
    origin.refs.master).set_tracking_branch(origin.refs.master).checkout()
        origin.pull()
        return '', 200
    else:
        return '', 400


@app.route('/version')
def version():
    return '0.2.7'


@app.route('/')
def hello():
    with open('unsupported.txt', 'r') as f:
        data = f.read()
    data = ('Unsupported Songs <br>------------------------ <br><br>' + data).replace('\n','<br>')
    return data


@app.route('/test')
def swag():
    return os.environ['SWAG']

