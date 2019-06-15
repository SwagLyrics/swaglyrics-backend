# swaglyrics-issue-maker
Server side code to make an issue on the [main repo](https://github.com/SwagLyrics/SwagLyrics-For-Spotify) when the 
program encounters a song it can't fetch lyrics for.

This is hosted on [pythonanywhere](https://aadibajpai.pythonanywhere.com). 

Works using the GitHub API and Flask.

The [main program](https://github.com/SwagLyrics/SwagLyrics-For-Spotify/blob/fbe9428e3458e6cce1396133b84c229ccd974a9e/swaglyrics/cli.py#L57) is configured to send a POST request to the server.

Need to document and add unit testing
