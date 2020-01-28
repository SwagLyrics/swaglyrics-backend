# swaglyrics-backend

[![Discord Server](https://badgen.net/badge/discord/join%20chat/7289DA?icon=discord)](https://discord.gg/DSUZGK4)
[![Build Status](https://travis-ci.com/SwagLyrics/swaglyrics-backend.svg?branch=master)](https://travis-ci.com/SwagLyrics/swaglyrics-backend)
[![codecov](https://codecov.io/gh/SwagLyrics/swaglyrics-backend/branch/master/graph/badge.svg)](https://codecov.io/gh/SwagLyrics/swaglyrics-backend)

Server side code to make an issue on the [main repo](https://github.com/SwagLyrics/SwagLyrics-For-Spotify) when the 
program encounters a song it can't fetch lyrics for. 

Works using the GitHub API and Flask.

The [main program](https://github.com/SwagLyrics/SwagLyrics-For-Spotify/blob/fbe9428e3458e6cce1396133b84c229ccd974a9e/swaglyrics/cli.py#L57) is configured to send a POST request to the server.

Need to document and add unit testing.

### Rate Limits
In order to prevent spam and/or abuse of endpoints, rate limiting has been set such that it wouldn't affect a normal 
user.

Since SwagLyrics checks for track change every 5 seconds, requests on endpoints `/stripper` and `/unsupported` are 
allowed once per 5 seconds only.

### Sponsors
[![PythonAnywhere](https://www.pythonanywhere.com/static/anywhere/images/PA-logo-small.png)](https://www.pythonanywhere.com/)

swaglyrics-backend is proudly sponsored by [PythonAnywhere](https://www.pythonanywhere.com/).
