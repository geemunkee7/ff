"""config.py — settings only. NO player names, ever."""

LEAGUE_KEY = "nfl.l.19041"

PROTECT = {"QB": 1, "RB": 2, "WR": 3, "TE": 1, "K": 1, "DEF": 1}

TRENDING_ADD_MIN = 35000
TRENDING_LOOKBACK_HOURS = 6

LOCAL_TZ = "America/New_York"
TIMEZONE_OFFSET = -4
QUIET_START_HOUR = 23
WAKE_HOUR = 6
WAIVER_LOCK_WEEKDAY = 1
WAIVER_LOCK_HOUR = 22

URGENT_KEYWORDS = [
    "torn", "acl", "achilles", "carted", "ruled out", "out for the season",
    "season-ending", "placed on injured reserve", "to ir", "suspended",
    "was released", "was waived", "has been traded", "traded to",
    "will not play", "won't play",
    "benched", "named the starter", "activated from",
    "inactive", "inactives", "surgery", "suffered a fracture", "fractured",
    "no timetable", "out indefinitely", "designated to return", "on the pup",
    "left the game with", "left with an", "exited with", "did not return",
    "questionable to return", "walked off", "carted off", "downgraded to out",
    "will miss", "expected to be sidelined", "placed on ir",
]

WATCH_KEYWORDS = [
    "questionable", "doubtful", "did not practice", "limited participant",
    "dnp", "mri", "x-rays", "week-to-week", "day-to-day", "high-ankle",
    "hamstring", "concussion protocol", "sprain", "strain", "illness",
    "in a walking boot", "expected to miss", "downgraded", "upgraded",
    "full participant", "cleared", "lead back", "first-team reps", "limped",
]

RSS_FEEDS = [
    "https://www.espn.com/espn/rss/nfl/news",
    "https://profootballtalk.nbcsports.com/feed/",
    "https://www.cbssports.com/rss/headlines/nfl/",
    "https://sports.yahoo.com/nfl/rss.xml",
    "https://www.reddit.com/r/fantasyfootball/new/.rss",
    "https://www.reddit.com/r/nfl/search.rss?q=flair%3ANews&restrict_sr=on&sort=new",
]

SLEEPER_TRENDING_URL = (
    "https://api.sleeper.app/v1/players/nfl/trending/add"
    f"?lookback_hours={TRENDING_LOOKBACK_HOURS}&limit=25"
)
SLEEPER_PLAYERS_URL = "https://api.sleeper.app/v1/players/nfl"

LINEUP = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DEF": 1}
FLEX_SLOTS = 1
PATH_BYE_WEEKS = 2

TEAM_BYES = {
    "CAR": 5, "KC": 5,
    "CIN": 6, "DET": 6, "MIA": 6, "MIN": 6,
    "BUF": 7, "JAX": 7, "LAC": 7, "WAS": 7,
    "HOU": 8, "NO": 8, "NYG": 8, "SF": 8,
    "PIT": 9, "TEN": 9,
    "CHI": 10, "DEN": 10, "PHI": 10, "TB": 10,
    "ATL": 11, "CLE": 11, "GB": 11, "LAR": 11, "NE": 11, "SEA": 11,
    "BAL": 13, "IND": 13, "LV": 13, "NYJ": 13,
    "ARI": 14, "DAL": 14,
}

SLEEPER_STATE_URL = "https://api.sleeper.app/v1/state/nfl"
SLEEPER_PROJ_BASE = "https://api.sleeper.app/projections/nfl"
SEASON = 2026
