"""
value.py — the value gate.

Decides whether an available player is worth alerting about, instead of firing on
every "a backup exists" event. A candidate clears the gate only if adding him would
plausibly change your lineup now or soon.

  ros  = rest-of-season value  (Sleeper search_rank; lower = better)
  proj = this-week value        (Sleeper weekly projected PPR points; higher = better)

Balanced policy:
  1. Beats one of your current STARTERS (rest-of-season) -> alert.
  2. Else beats your worst BENCH player AND has a near-term PATH to starting
     (your starter at his position on bye within N weeks, OR he's the handcuff to
     an RB you roster, OR the starter ahead of him is hurt) -> alert.
  3. Else -> suppress.
Plus: the incoming player must be better (ros) than whoever you'd drop.
"""

import config

SKILL = ("QB", "RB", "WR", "TE")
FLEX_POS = ("RB", "WR", "TE")
UNRANKED = 10_000_000


def _norm(name):
    import re
    if not name or not isinstance(name, str):
        return ""
    n = name.lower().replace(".", "").replace("'", "").replace("\u2019", "")
    n = re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", n)
    return re.sub(r"[^a-z ]", "", n).strip()


def ros_of(rec):
    r = rec.get("search_rank")
    return r if isinstance(r, int) and r > 0 else UNRANKED


def build_valuation(players_db, proj_map):
    """name_norm -> compact value record for every player we might weigh."""
    val = {}
    for pid, p in players_db.items():
        name = p.get("full_name")
        if not name:
            continue
        val[_norm(name)] = {
            "name": name,
            "pos": p.get("position"),
            "team": p.get("team"),
            "dco": p.get("depth_chart_order"),
            "injury": p.get("injury_status"),
            "ros": ros_of(p),
            "proj": proj_map.get(str(pid)),
        }
    return val


def _starters_and_bench(my_roster, val):
    """Split your roster into starters (by lineup slots) and bench, using ros."""
    by_pos = {}
    for name in my_roster:
        v = val.get(_norm(name))
        if not v or v["pos"] not in (SKILL + ("K", "DEF")):
            continue
        by_pos.setdefault(v["pos"], []).append((v["ros"], name))
    for pos in by_pos:
        by_pos[pos].sort()

    starters = {}
    used = set()
    for pos, need in config.LINEUP.items():
        picks = [n for _, n in by_pos.get(pos, [])][:need]
        starters[pos] = picks
        used.update(picks)

    flex_pool = []
    for pos in FLEX_POS:
        for r, n in by_pos.get(pos, []):
            if n not in used:
                flex_pool.append((r, n))
    flex_pool.sort()
    flex = [n for _, n in flex_pool[:config.FLEX_SLOTS]]
    used.update(flex)
    starters["FLEX"] = flex

    bench = []
    for pos, lst in by_pos.items():
        for r, n in lst:
            if n not in used:
                bench.append((r, n))
    bench.sort()
    return starters, bench, by_pos


def _worst_starter_ros(pos, starters, val):
    names = list(starters.get(pos, []))
    if pos in FLEX_POS:
        names += starters.get("FLEX", [])
    if not names:
        return UNRANKED
    return max(val[_norm(n)]["ros"] for n in names)


def _worst_bench_ros(bench, val):
    if not bench:
        return -1
    return bench[-1][0]


def _team_on_bye_soon(team, week):
    bye = config.TEAM_BYES.get(team)
    if not bye:
        return False
    return week <= bye <= week + config.PATH_BYE_WEEKS


def _has_path(cand, my_roster, val, players_db, week, starters):
    pos = cand["pos"]

    for n in starters.get(pos, []) + (starters.get("FLEX", []) if pos in FLEX_POS else []):
        if _team_on_bye_soon(val[_norm(n)]["team"], week):
            return True

    if pos == "RB":
        for n in my_roster:
            v = val.get(_norm(n))
            if not v or v["pos"] != "RB":
                continue
            if v["team"] == cand["team"] and (v["dco"] or 9) == 1:
                return True

    if cand.get("team") and (cand.get("dco") or 9) >= 2:
        for p in players_db.values():
            if p.get("team") != cand["team"]:
                continue
            if (p.get("depth_chart_position") or p.get("position")) != pos:
                continue
            if (p.get("depth_chart_order") or 9) == 1:
                if p.get("injury_status") in ("Out", "IR", "Doubtful", "Questionable"):
                    return True
    return False


def gate(cand_name, my_roster, val, players_db, week, drop_name):
    """Returns (alert: bool, tier: str, reason: str)."""
    cand = val.get(_norm(cand_name))
    if not cand or cand["pos"] not in (SKILL + ("K", "DEF")):
        return False, "", ""

    starters, bench, _ = _starters_and_bench(my_roster, val)

    if drop_name:
        d = val.get(_norm(drop_name))
        if d and cand["ros"] >= d["ros"]:
            return False, "", "not better than your drop candidate"

    if cand["ros"] < _worst_starter_ros(cand["pos"], starters, val):
        return True, "upgrade", "beats one of your starters (rest-of-season)"

    if cand["ros"] < _worst_bench_ros(bench, val):
        if _has_path(cand, my_roster, val, players_db, week, starters):
            return True, "stash", "startable soon (bye/handcuff/injury ahead)"

    return False, "", "not an upgrade and no near-term path"
