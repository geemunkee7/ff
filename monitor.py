#!/usr/bin/env python3
"""monitor.py — fully automated breaking-news waiver alerts, value-gated."""

import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import feedparser
import requests

import config
import yahoo
import value

STATE_FILE = "state.json"
PLAYERS_CACHE = "players_cache.json"
MAX_SEEN = 4000
HTTP_TIMEOUT = 20
UA = {"User-Agent": "challah-famers-alerts/1.0 (personal fantasy tool)"}
SKILL = ("QB", "RB", "WR", "TE")
UNRANKED = 10_000_000


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return _with_defaults(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    return {"seen": [], "queued": [], "injury_status": {}, "last_players_fetch": 0}


def _with_defaults(state):
    for k, v in (("seen", []), ("queued", []), ("injury_status", {}),
                 ("last_players_fetch", 0)):
        state.setdefault(k, v)
    return state


def save_state(state):
    state["seen"] = state["seen"][-MAX_SEEN:]
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=1)


def fingerprint(text):
    if not isinstance(text, str):
        text = str(text)
    return hashlib.sha1(text.lower().encode("utf-8")).hexdigest()[:16]


def now_local():
    try:
        return datetime.now(ZoneInfo(config.LOCAL_TZ))
    except Exception:
        return datetime.now(timezone(timedelta(hours=config.TIMEZONE_OFFSET)))


def in_quiet_hours(dt):
    h = dt.hour
    if config.QUIET_START_HOUR > config.WAKE_HOUR:
        return h >= config.QUIET_START_HOUR or h < config.WAKE_HOUR
    return config.WAKE_HOUR > h >= config.QUIET_START_HOUR


def norm(name):
    if not name or not isinstance(name, str):
        return ""
    n = name.lower().replace(".", "").replace("'", "").replace("\u2019", "")
    n = re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", n)
    return re.sub(r"[^a-z ]", "", n).strip()


def fetch_rss():
    items = []
    for url in config.RSS_FEEDS:
        try:
            resp = requests.get(url, headers=UA, timeout=HTTP_TIMEOUT)
            parsed = feedparser.parse(resp.content)
        except Exception as exc:
            print(f"  ! feed failed {url}: {exc}")
            continue
        source = parsed.feed.get("title", url.split("/")[2])
        for entry in parsed.entries[:40]:
            items.append(
                {
                    "title": entry.get("title", "").strip(),
                    "summary": re.sub(r"<[^>]+>", " ", entry.get("summary", "")).strip()[:400],
                    "link": entry.get("link", ""),
                    "source": source,
                }
            )
    print(f"  fetched {len(items)} headlines")
    return items


def load_player_db(state):
    fresh = time.time() - state.get("last_players_fetch", 0) < 86400
    if fresh and os.path.exists(PLAYERS_CACHE):
        try:
            with open(PLAYERS_CACHE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    try:
        resp = requests.get(config.SLEEPER_PLAYERS_URL, headers=UA, timeout=60)
        data = resp.json()
        with open(PLAYERS_CACHE, "w") as f:
            json.dump(data, f)
        state["last_players_fetch"] = time.time()
        print(f"  refreshed player DB ({len(data)})")
        return data
    except Exception as exc:
        print(f"  ! player DB fetch failed: {exc}")
        if os.path.exists(PLAYERS_CACHE):
            with open(PLAYERS_CACHE) as f:
                return json.load(f)
        return {}


def fetch_trending(players_db):
    try:
        resp = requests.get(config.SLEEPER_TRENDING_URL, headers=UA, timeout=HTTP_TIMEOUT)
        rows = resp.json()
    except Exception as exc:
        print(f"  ! trending fetch failed: {exc}")
        return []
    out = []
    for row in rows:
        p = players_db.get(str(row.get("player_id")), {})
        if p.get("full_name") and p.get("position") in SKILL:
            out.append({"name": p["full_name"], "position": p["position"],
                        "team": p.get("team") or "FA", "count": row.get("count", 0)})
    return out


def current_week():
    try:
        resp = requests.get(config.SLEEPER_STATE_URL, headers=UA, timeout=HTTP_TIMEOUT)
        wk = resp.json().get("week")
        if isinstance(wk, int) and 1 <= wk <= 18:
            return wk
    except Exception as exc:
        print(f"  ! state fetch failed: {exc}")
    from datetime import date
    start = date(2026, 9, 7)
    wk = (now_local().date() - start).days // 7 + 1
    return max(1, min(18, wk))


def fetch_projections(week):
    url = (f"{config.SLEEPER_PROJ_BASE}/{config.SEASON}/{week}"
           "?season_type=regular"
           "&position[]=QB&position[]=RB&position[]=WR"
           "&position[]=TE&position[]=K&position[]=DEF")
    out = {}
    try:
        resp = requests.get(url, headers=UA, timeout=HTTP_TIMEOUT)
        rows = resp.json()
    except Exception as exc:
        print(f"  ! projections fetch failed: {exc}")
        return out
    if not isinstance(rows, list):
        return out
    for row in rows:
        pid = row.get("player_id")
        stats = row.get("stats") or {}
        pts = stats.get("pts_ppr")
        if pid is not None and isinstance(pts, (int, float)):
            out[str(pid)] = pts
    print(f"  projections: {len(out)} players for week {week}")
    return out


def rank_of(rec):
    r = rec.get("search_rank")
    return r if isinstance(r, int) and r > 0 else UNRANKED


def build_relevant_index(players_db, my_roster, taken):
    idx = {}
    mine_n = {norm(n) for n in my_roster}
    taken_n = {norm(n) for n in taken}
    for pid, p in players_db.items():
        name = p.get("full_name")
        if not name:
            continue
        n = norm(name)
        pos = p.get("position")
        dco = p.get("depth_chart_order")
        relevant = (
            n in mine_n
            or n in taken_n
            or (pos in SKILL and isinstance(dco, int) and dco <= 2)
        )
        if relevant:
            rec = dict(p)
            rec["player_id"] = pid
            existing = idx.get(n)
            if existing is None or _better_record(rec, existing, mine_n):
                idx[n] = rec
    return idx


def _better_record(new, old, mine_n):
    new_skill = new.get("position") in SKILL
    old_skill = old.get("position") in SKILL
    if new_skill != old_skill:
        return new_skill
    return rank_of(new) < rank_of(old)


def next_man_up(rec, players_db):
    team = rec.get("team")
    slot = rec.get("depth_chart_position") or rec.get("position")
    order = rec.get("depth_chart_order") or 1
    if not team:
        return None
    cands = []
    for p in players_db.values():
        if p.get("team") != team:
            continue
        if (p.get("depth_chart_position") or p.get("position")) != slot:
            continue
        if p.get("full_name") == rec.get("full_name"):
            continue
        pd = p.get("depth_chart_order")
        if isinstance(pd, int) and pd > order:
            cands.append((pd, rank_of(p), p))
    if not cands:
        return None
    cands.sort(key=lambda t: (t[0], t[1]))
    return cands[0][2]


def recommend_drop(my_roster, players_db):
    by_pos = {}
    for name in my_roster:
        rec = _find_by_name(players_db, name)
        if not rec:
            continue
        pos = rec.get("position")
        if pos not in SKILL:
            continue
        r = rank_of(rec)
        if r >= UNRANKED:
            continue
        by_pos.setdefault(pos, []).append((r, name))
    droppable = []
    for pos, lst in by_pos.items():
        lst.sort()
        keep = config.PROTECT.get(pos, 1)
        droppable += lst[keep:]
    if not droppable:
        return None
    droppable.sort()
    return droppable[-1][1]


def _find_by_name(players_db, name):
    target = norm(name)
    for p in players_db.values():
        if norm(p.get("full_name", "")) == target:
            return p
    return None


def classify(text):
    low = text.lower()
    for kw in config.URGENT_KEYWORDS:
        if kw in low:
            return "URGENT", kw
    for kw in config.WATCH_KEYWORDS:
        if kw in low:
            return "WATCH", kw
    return None, None


def name_in_text(nname, blob):
    if not nname:
        return False
    return re.search(r"(?<![a-z])" + re.escape(nname) + r"(?![a-z])", blob) is not None


def available(name, taken):
    if not taken:
        return True
    return norm(name) not in {norm(t) for t in taken}


def _tier_near(raw_text, canonical_name, article_tier, article_trigger):
    clauses = re.split(r"[;,.\u2014\-]| and | but ", raw_text)
    target = norm(canonical_name)
    for clause in clauses:
        if name_in_text(target, re.sub(r"\s+", " ", norm(clause))):
            t, kw = classify(clause)
            if t:
                return t, kw
            return None, None
    return article_tier, article_trigger


def build_alerts(items, trending, players_db, my_roster, taken, state, val, week):
    alerts = []
    index = build_relevant_index(players_db, my_roster, taken)
    mine_n = {norm(n) for n in my_roster}
    taken_cache = {norm(t) for t in taken}
    drop = recommend_drop(my_roster, players_db) if my_roster else None
    drop_line = f"DROP {drop}" if drop else "check your bench for a drop"

    for item in items:
        text = f"{item['title']} {item['summary']}"
        blob = re.sub(r"\s+", " ", norm(text))
        key = fingerprint(item["title"])
        if key in state["seen"]:
            continue
        tier, trigger = classify(text)
        if not tier:
            continue

        matched = [(n, rec) for n, rec in index.items() if name_in_text(n, blob)]
        if not matched:
            continue
        state["seen"].append(key)

        for nkey, rec in matched:
            name = rec["full_name"]
            is_mine = norm(name) in mine_n
            ptier, ptrig = _tier_near(text, name, tier, trigger)
            if not ptier:
                continue
            tier, trigger = ptier, ptrig
            prio = 1 if tier == "URGENT" else 0

            if is_mine:
                if tier == "URGENT":
                    pos = rec.get("position", "player")
                    body = (f"{item['title']}\n\nYOUR PLAYER. If he's out you need "
                            f"a {pos} this week.\nTrigger: {trigger}\n{item['source']}")
                else:
                    body = (f"{item['title']}\n\nMonitor — no move yet.\n"
                            f"Trigger: {trigger}\n{item['source']}")
                alerts.append({"priority": prio, "title": f"[{tier}] YOUR PLAYER: {name}",
                               "body": body, "link": item["link"]})
                continue

            if tier != "URGENT":
                continue
            if (rec.get("depth_chart_order") or 9) != 1:
                continue
            nmu = next_man_up(rec, players_db)
            if not nmu:
                continue
            nmu_name = nmu["full_name"]
            if norm(nmu_name) in mine_n:
                body = (f"{item['title']}\n\nYou roster {nmu_name} — he's next up. "
                        f"START/HOLD him.\n{item['source']}")
                alerts.append({"priority": prio, "title": f"[{tier}] HOLD: {nmu_name}",
                               "body": body, "link": item["link"]})
            elif norm(nmu_name) not in taken_cache:
                ok, gtier, why = value.gate(nmu_name, my_roster, val, players_db, week, drop)
                if not ok:
                    continue
                body = (f"{item['title']}\n\nCLAIM: {nmu_name} "
                        f"({nmu.get('position')}, {nmu.get('team')}) — next up behind "
                        f"{name}. [{gtier}: {why}]\n{drop_line}\n{item['source']}")
                alerts.append({"priority": prio, "title": f"[{tier}] CLAIM {nmu_name}",
                               "body": body, "link": item["link"]})

    trend_seen_run = set()
    for row in trending:
        if not row.get("name"):
            continue
        if norm(row["name"]) in trend_seen_run:
            continue
        trend_seen_run.add(norm(row["name"]))
        if row["count"] < config.TRENDING_ADD_MIN or norm(row["name"]) in mine_n:
            continue
        if not available(row["name"], taken):
            continue
        key = fingerprint(f"trend::{row['name']}::{now_local():%Y-%m-%d-%H}")
        if key in state["seen"]:
            continue
        ok, gtier, why = value.gate(row["name"], my_roster, val, players_db, week, drop)
        if not ok:
            continue
        state["seen"].append(key)
        alerts.append({"priority": 0,
                       "title": f"[TRENDING] {row['name']} ({row['position']}, {row['team']})",
                       "body": (f"{row['count']:,} adds in {config.TRENDING_LOOKBACK_HOURS}h, "
                                f"free in your league. [{gtier}: {why}]\n{drop_line}"),
                       "link": ""})

    for pid, p in players_db.items():
        name = p.get("full_name")
        if not name or p.get("position") not in SKILL:
            continue
        is_mine = norm(name) in mine_n
        is_starter = (p.get("depth_chart_order") or 9) == 1
        if not (is_mine or is_starter):
            continue
        status = p.get("injury_status") or "Healthy"
        prev = state["injury_status"].get(name)
        state["injury_status"][name] = status
        if prev is None or prev == status:
            continue
        prio = 1 if status in ("Out", "IR", "Doubtful") else 0
        if is_mine:
            body = f"Your player. {prev} -> {status}."
            if prio:
                body += f" You may need a {p.get('position')} this week."
            alerts.append({"priority": prio, "title": f"[STATUS] {name}: {prev} -> {status}",
                           "body": body, "link": ""})
        elif prio:
            rec = dict(p); rec["player_id"] = pid
            nmu = next_man_up(rec, players_db)
            if not nmu:
                continue
            nn = nmu["full_name"]
            if norm(nn) in mine_n:
                body = f"You roster {nn} — next up behind {name}. START/HOLD."
            elif norm(nn) not in taken_cache:
                ok, gtier, why = value.gate(nn, my_roster, val, players_db, week, drop)
                if not ok:
                    continue
                body = f"CLAIM {nn} — next up behind {name}. [{gtier}] {drop_line}."
            else:
                continue
            alerts.append({"priority": prio, "title": f"[STATUS] {name}: {prev} -> {status}",
                           "body": body, "link": ""})

    return alerts


def waiver_reminder(state, drop_line):
    now = now_local()
    if now.weekday() != config.WAIVER_LOCK_WEEKDAY:
        return []
    if now.hour != max(config.WAIVER_LOCK_HOUR - 3, 0):
        return []
    key = fingerprint(f"waiver::{now:%Y-%m-%d}")
    if key in state["seen"]:
        return []
    state["seen"].append(key)
    return [{"priority": 1, "title": "Waiver claims lock in 3 hours",
             "body": f"Put in every claim you might want.\n{drop_line}", "link": ""}]


def push(alert):
    ntfy = os.environ.get("NTFY_TOPIC")
    pot, pou = os.environ.get("PUSHOVER_TOKEN"), os.environ.get("PUSHOVER_USER")
    title, body = alert["title"][:120], alert["body"]
    if alert.get("link"):
        body = f"{body}\n{alert['link']}"
    sent = False
    if ntfy:
        try:
            requests.post(f"https://ntfy.sh/{ntfy}", data=body.encode("utf-8"),
                          headers={"Title": title.encode("utf-8"),
                                   "Priority": "urgent" if alert["priority"] else "high",
                                   "Tags": "football"}, timeout=HTTP_TIMEOUT)
            sent = True
        except Exception as exc:
            print(f"  ! ntfy failed: {exc}")
    if pot and pou:
        try:
            requests.post("https://api.pushover.net/1/messages.json",
                          data={"token": pot, "user": pou, "title": title,
                                "message": body, "priority": alert["priority"]},
                          timeout=HTTP_TIMEOUT)
            sent = True
        except Exception as exc:
            print(f"  ! pushover failed: {exc}")
    if not sent:
        print(f"  (no push)\n  {title}\n  {body}\n")
    return sent


def main():
    now = now_local()
    print(f"run at {now:%Y-%m-%d %H:%M %Z}")
    state = load_state()

    players_db = load_player_db(state)
    items = fetch_rss()
    trending = fetch_trending(players_db)
    week = current_week()
    proj_map = fetch_projections(week)
    val = value.build_valuation(players_db, proj_map)
    my_roster = yahoo.my_roster()
    taken = yahoo.taken_players()
    if not my_roster and taken:
        print("  ! WARNING: your roster read empty but league read worked — "
              "Yahoo auth may be partly broken; YOUR-PLAYER alerts disabled this run")

    drop = recommend_drop(my_roster, players_db) if my_roster else None
    drop_line = f"DROP {drop}" if drop else "check your bench for a drop"

    alerts = build_alerts(items, trending, players_db, my_roster, taken, state, val, week)
    alerts += waiver_reminder(state, drop_line)

    queued = state.get("queued", [])
    if queued and not in_quiet_hours(now):
        print(f"  releasing {len(queued)} queued")
        alerts = queued + alerts
        state["queued"] = []

    quiet = in_quiet_hours(now)
    sent = 0
    for alert in alerts:
        if quiet and alert["priority"] < 1:
            state.setdefault("queued", []).append(alert)
            continue
        push(alert)
        sent += 1
        time.sleep(0.4)

    print(f"  sent {sent}, queued {len(state.get('queued', []))}")
    save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
