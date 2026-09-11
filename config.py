"""config.py — settings only. NO player names, ever."""

LEAGUE_KEY = "nfl.l.19041"

PROTECT = {"QB": 1, "RB": 2, "WR": 3, "TE": 1, "K": 1, "DEF": 1}

TRENDING_ADD_MIN = 12000
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
