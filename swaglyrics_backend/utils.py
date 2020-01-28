import hashlib
import hmac
import os
import time
import jwt
from functools import wraps
from ipaddress import ip_address, ip_network

import requests
from flask import request, abort


def validate_request(req):
    abort_code = 418
    x_hub_signature = req.headers.get('X-Hub-Signature')
    if not is_valid_signature(x_hub_signature, req.data):
        print(f'Deploy signature failed: {x_hub_signature}')
        abort(abort_code)

    if (payload := request.get_json()) is None:
        print(f'Payload is empty: {payload}')
        abort(abort_code)

    return payload


def is_valid_signature(x_hub_signature, data, private_key=os.environ['WEBHOOK_SECRET']):
    """Verify webhook signature"""
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

                if not (ip_header := request.headers.get('CF-Connecting-IP')):
                    # necessary if ip from cloudflare
                    ip_header = request.headers['X-Real-IP']

                request_ip = ip_address(u'{0}'.format(ip_header))
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

# ------------------- authentication functions ------------------- #


def get_jwt(app_id: int, private_key):

    payload = {
        "iat": int(time.time()),
        "exp": int(time.time()) + (10 * 60),
        "iss": app_id,
    }
    encoded = jwt.encode(payload, private_key, algorithm="RS256")
    bearer_token = encoded.decode("utf-8")

    return bearer_token


def get_installation_access_token(jwt: str, installation_id: int):
    # doc: https: // developer.github.com/v3/apps/#create-a-new-installation-token

    access_token_url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    headers = {"Authorization": f"Bearer {jwt}",
               "Accept": "application/vnd.github.machine-man-preview+json"}
    response = requests.post(access_token_url, headers=headers)

    # example response
    # {
    #   "token": "v1.1f699f1069f60xxx",
    #   "expires_at": "2016-07-11T22:14:10Z"
    # }

    return response
