"""yahoo.py — live reads from your Yahoo league. No player names stored."""

import base64
import os
import time
import urllib.parse
import urllib.request
import json

import config

TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
BASE = "https://fantasysports.yahooapis.com/fantasy/v2"
UA = {"User-Agent": "challah-famers-alerts/1.0"}

_access = {"token": None, "expires": 0}


def _basic_auth():
    return base64.b64encode(
        f"{os.environ['YCID']}:{os.environ['YSEC']}".encode()
    ).decode()


def get_access_token():
    if _access["token"] and time.time() < _access["expires"] - 60:
        return _access["token"]
    data = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "redirect_uri": "https://localhost/",
            "refresh_token": os.environ["YTOK"],
        }
    ).encode()
    req = urllib.request.Request(
        TOKEN_URL,
        data=data,
        headers={
            "Authorization": f"Basic {_basic_auth()}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    resp = json.load(urllib.request.urlopen(req, timeout=30))
    _access["token"] = resp["access_token"]
    _access["expires"] = time.time() + resp.get("expires_in", 3600)
    return _access["token"]


def _api_get(path):
    token = get_access_token()
    url = f"{BASE}/{path}"
    url += "&format=json" if "?" in url else "?format=json"
    req = urllib.request.Request(url, headers={**UA, "Authorization": f"Bearer {token}"})
    return json.load(urllib.request.urlopen(req, timeout=30))


def _collect(node, key, out):
    if isinstance(node, dict):
        if key in node and isinstance(node[key], (str, int)):
            out.append(node[key])
        for v in node.values():
            _collect(v, key, out)
    elif isinstance(node, list):
        for v in node:
            _collect(v, key, out)


def _collect_names(node, out):
    if isinstance(node, dict):
        if "name" in node and isinstance(node["name"], dict):
            full = node["name"].get("full")
            if full:
                out.add(full)
        for v in node.values():
            _collect_names(v, out)
    elif isinstance(node, list):
        for v in node:
            _collect_names(v, out)


def my_team_key():
    data = _api_get(
        f"users;use_login=1/games;game_keys=nfl/"
        f"leagues;league_keys={config.LEAGUE_KEY}/teams"
    )
    keys = []
    _collect(data, "team_key", keys)
    return keys[0] if keys else None


def my_roster():
    try:
        tk = my_team_key()
        if not tk:
            print("  ! yahoo: could not find your team key")
            return set()
        data = _api_get(f"team/{tk}/roster")
        names = set()
        _collect_names(data, names)
        print(f"  yahoo: {len(names)} players on your team")
        return names
    except Exception as exc:
        print(f"  ! yahoo my_roster failed: {exc}")
        return set()


def taken_players():
    names = set()
    start = 0
    try:
        while True:
            data = _api_get(
                f"league/{config.LEAGUE_KEY}/players;status=T;start={start};count=25"
            )
            before = len(names)
            _collect_names(data, names)
            if len(names) == before:
                break
            start += 25
            if start > 400:
                break
    except Exception as exc:
        print(f"  ! yahoo taken_players failed: {exc}")
        return set()
    print(f"  yahoo: {len(names)} rostered leaguewide")
    return names
