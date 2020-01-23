import hashlib
import hmac
import os
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
