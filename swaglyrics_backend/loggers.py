# ------------------- discord logging functions ------------------- #
# https://discordapp.com/developers/docs/resources/webhook#execute-webhook

import logging
import os
from datetime import datetime as dt
from typing import Dict, Any, Optional

import requests

# define a JSON-like Dict type hint
JSONDict = Dict[str, Any]


def discord_deploy_logger(payload: JSONDict) -> None:
    """
    sends message to Discord server when deploy from github to backend successful.
    """
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


def discord_genius_logger(song: str, artist: str, g_stripper: Optional[str]) -> None:
    """
    sends message to Discord server when stripper resolved using the backend.
    """
    url = f"https://discord.com/api/webhooks/{os.environ['DISCORD_URL_GENIUS']}?wait=true"
    title = f"Genius Stripper for {song} by {artist}."
    if g_stripper:
        desc = f"Found! {g_stripper}"
        color = 3066993  # green
        lyrics_url = f"https://genius.com/{g_stripper}-lyrics"
    else:
        desc = "Stripper not found. Sad!"
        color = 15158332  # red
        lyrics_url = ""

    json = {
        "embeds": [{
            "title": title,
            "description": desc,
            "url": lyrics_url,
            "timestamp": str(dt.now()),
            "color": color
        }]
    }

    r = requests.post(url, json=json)
    if r.status_code == requests.codes.ok:
        logging.info("sent discord genius message")
    else:
        logging.error(f"discord genius message send failed: {r.status_code}")


def discord_instrumental_logger(song: str, artist: str,
                                instrumental: bool, instrumentalness: float, speechiness: float) -> None:
    """
    sends message to Discord server when instrumentalness checked using the backend.
    """
    # https://discordapp.com/developers/docs/resources/webhook#execute-webhook
    url = f"https://discord.com/api/webhooks/{os.environ['DISCORD_URL_INSTRUMENTAL']}?wait=true"
    title = f"{song} by {artist}."

    json = {
        "embeds": [{
            "title": title,
            "description": f"{'Not ' if not instrumental else ''}Instrumental.",
            "timestamp": str(dt.now()),
            "color": 1501879,
            "fields": [
                {
                    "name": "`Instrumentalness`",
                    "value": str(instrumentalness)
                },
                {
                    "name": "`Speechiness`",
                    "value": str(speechiness)
                }
            ]
        }]
    }

    r = requests.post(url, json=json)
    if r.status_code == requests.codes.ok:
        logging.info("sent discord instrumental message")
    else:
        logging.error(f"discord instrumental message send failed: {r.status_code}")
