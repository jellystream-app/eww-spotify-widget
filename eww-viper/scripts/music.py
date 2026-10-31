#!/usr/bin/env python3
"""ViperOS Music-Widget Backend: MPRIS (Spotify bevorzugt) + synchrone Lyrics via LRCLIB.
  music.py daemon           -> JSON-Stream für eww (deflisten)
  music.py toggle|next|prev|shuffle|loop|vol <0-100>|seek <0-100>
"""
import bisect, configparser, hashlib, json, os, re, sys, threading, time
import urllib.error, urllib.parse, urllib.request
from pathlib import Path
from gi.repository import Gio, GLib

_cp = configparser.ConfigParser(inline_comment_prefixes=(";",))
try:
    _cp.read(Path(__file__).resolve().parent.parent / "config.ini", encoding="utf-8")
except Exception:
    pass

def conf(key, default, cast=str):
    try:
        return cast(_cp.get("general", key).strip())
    except Exception:
        return default

PREFER = conf("player", "spotify").lower()   # preferred player name prefix
LEAD = conf("lyrics_lead", 0.25, float)      # switch lyric lines slightly early (s)
TICK = conf("poll_ms", 250, int) / 1000
ROWS = 5                                      # max rows each side, visibility is set by render.py

CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "viper-music"
COVERS, LYRICS = CACHE / "covers", CACHE / "lyrics"
COVERS.mkdir(parents=True, exist_ok=True)
LYRICS.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "ViperOS-MusicWidget/1.0 (eww)"}

MPRIS = "org.mpris.MediaPlayer2."
PATH = "/org/mpris/MediaPlayer2"
PLAYER = MPRIS + "Player"
PROPS = "org.freedesktop.DBus.Properties"
CLS = ["cur", "near", "mid", "far"]

bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)


# ---------- D-Bus ----------
def dbus(dest, path, iface, method, params=None, reply="()"):
    r = bus.call_sync(dest, path, iface, method, params, GLib.VariantType(reply),
                      Gio.DBusCallFlags.NONE, 800, None)
    return r.unpack()

def players():
    names = dbus("org.freedesktop.DBus", "/org/freedesktop/DBus",
                 "org.freedesktop.DBus", "ListNames", None, "(as)")[0]
    return [n for n in names if n.startswith(MPRIS)]

def get_all(p): return dbus(p, PATH, PROPS, "GetAll", GLib.Variant("(s)", (PLAYER,)), "(a{sv})")[0]
def get(p, n):  return dbus(p, PATH, PROPS, "Get", GLib.Variant("(ss)", (PLAYER, n)), "(v)")[0]
def put(p, n, v): dbus(p, PATH, PROPS, "Set", GLib.Variant("(ssv)", (PLAYER, n, v)))
def act(p, m, params=None): dbus(p, PATH, PLAYER, m, params)

def pick():
    """Spotify zuerst, läuft dort nichts -> irgendein spielender Player, sonst Spotify/erster."""
    ps = sorted(players(), key=lambda n: 0 if n[len(MPRIS):].lower().startswith(PREFER) else 1)
    for p in ps:
        try:
            if get(p, "PlaybackStatus") == "Playing":
                return p
        except Exception:
            pass
    return ps[0] if ps else None


# ---------- Cover ----------
_inflight = set()

def _dl(url, f):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=8) as r:
            data = r.read()
        tmp = f.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.rename(f)
        for o in sorted(COVERS.glob("*.jpg"), key=lambda x: x.stat().st_mtime)[:-40]:
            o.unlink(missing_ok=True)
    except Exception:
        pass
    finally:
        _inflight.discard(url)

def cover_file(url):
    if not url:
        return ""
    if url.startswith("file://"):
        return urllib.parse.unquote(url[7:])
    url = url.replace("open.spotify.com/image/", "i.scdn.co/image/")
    f = COVERS / (hashlib.md5(url.encode()).hexdigest() + ".jpg")
    if f.exists():
        return str(f)
    if url not in _inflight:
        _inflight.add(url)
        threading.Thread(target=_dl, args=(url, f), daemon=True).start()
    return ""


# ---------- Lyrics (LRCLIB) ----------
TS = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\]")

def parse(lrc):
    items = []
    for line in lrc.splitlines():
        stamps = TS.findall(line)
        if stamps:
            text = TS.sub("", line).strip()
            items += [(int(m) * 60 + float(s), text) for m, s in stamps]
    items.sort(key=lambda x: x[0])
    return [t for t, _ in items], [x for _, x in items]

def http_json(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=6) as r:
        return json.load(r)

def slim(d):
    return {"syncedLyrics": d.get("syncedLyrics") or "", "plainLyrics": d.get("plainLyrics") or ""}

def fetch(artist, title, album, dur):
    """dict = Ergebnis (evtl. leer), None = Netzwerkfehler (nicht cachen)."""
    q = urllib.parse.urlencode({"artist_name": artist, "track_name": title,
                                "album_name": album, "duration": int(dur)})
    try:
        d = http_json(f"https://lrclib.net/api/get?{q}")
        if d.get("syncedLyrics"):
            return slim(d)
    except urllib.error.HTTPError as e:
        if e.code != 404:
            return None
    except Exception:
        return None
    try:
        q = urllib.parse.urlencode({"artist_name": artist, "track_name": title})
        res = [r for r in http_json(f"https://lrclib.net/api/search?{q}") if r.get("syncedLyrics")]
        if res:
            res.sort(key=lambda r: abs((r.get("duration") or 0) - dur))
            return slim(res[0])
        return {}
    except Exception:
        return None

class Lyrics:
    def __init__(self):
        self.reset()

    def reset(self):
        self.key, self.state, self.parsed = None, "idle", ([], [])

    def request(self, key, artist, title, album, dur):
        if key == self.key:
            return
        self.key, self.state, self.parsed = key, "loading", ([], [])
        threading.Thread(target=self._run, args=(key, artist, title, album, dur), daemon=True).start()

    def _run(self, key, artist, title, album, dur):
        f = LYRICS / (hashlib.md5(key.encode()).hexdigest() + ".json")
        data = None
        try:
            if f.exists():
                data = json.loads(f.read_text())
        except Exception:
            data = None
        if data is None:
            data = fetch(artist, title, album, dur)
            if data is not None:
                try: f.write_text(json.dumps(data))
                except Exception: pass
        if key != self.key:
            return
        if data is None:                       # Netzwerkfehler -> später neu versuchen
            self.state = "none"
            time.sleep(15)
            if self.key == key:
                self.key = None
            return
        parsed = parse(data.get("syncedLyrics") or "")
        self.parsed = parsed
        self.state = "ok" if parsed[0] else ("plain" if data.get("plainLyrics") else "none")

lyr = Lyrics()

def lyric_rows(pos):
    n = 2 * ROWS + 1
    out = [{"t": "", "c": CLS[min(abs(i - ROWS), 3)], "d": abs(i - ROWS)} for i in range(n)]
    if lyr.state == "ok":
        times, texts = lyr.parsed
        cur = bisect.bisect_right(times, pos + LEAD) - 1
        for i in range(n):
            idx = cur + i - ROWS
            if 0 <= idx < len(texts):
                out[i]["t"] = texts[idx]
        if not out[ROWS]["t"]:
            out[ROWS]["t"] = "♪"
    else:
        out[ROWS]["t"] = {"loading": "…", "plain": "Keine synchronen Lyrics",
                          "none": "Keine Lyrics gefunden"}.get(lyr.state, "")
    return out


# ---------- State ----------
def fmt(s):
    s = int(max(s, 0))
    return f"{s // 60}:{s % 60:02d}"

def idle(msg="Nichts läuft"):
    lyr.reset()
    return {"active": False, "title": msg, "artist": "", "cover_style": "", "status": "Stopped",
            "play_icon": "media-playback-start-symbolic", "pos_txt": "0:00", "len_txt": "0:00",
            "pct": 0, "vol": 100, "vol_icon": "audio-volume-high-symbolic",
            "shuffle_cls": "off", "loop_cls": "off", "loop_icon": "media-playlist-repeat-symbolic",
            "lyrics": lyric_rows(0)}

def build():
    p = pick()
    if not p:
        return idle()
    pr = get_all(p)
    md = pr.get("Metadata", {}) or {}
    try:
        pos = get(p, "Position") / 1e6
    except Exception:
        pos = 0.0
    title = md.get("xesam:title", "") or ""
    art = md.get("xesam:artist") or []
    artist = ", ".join(art) if isinstance(art, list) else str(art)
    album = md.get("xesam:album", "") or ""
    length = (md.get("mpris:length") or 0) / 1e6
    status = pr.get("PlaybackStatus", "Stopped")
    vol = float(pr.get("Volume", 1.0)) * 100
    loop = pr.get("LoopStatus", "None")
    if title:
        first = art[0] if isinstance(art, list) and art else artist
        lyr.request(f"{first}|{title}|{album}|{int(length)}", first, title, album, length)
    else:
        lyr.reset()
    cf = cover_file(md.get("mpris:artUrl", ""))
    return {
        "active": True,
        "title": title or "Unbekannt",
        "artist": artist,
        "cover_style": f'background-image: url("file://{cf}");' if cf else "",
        "status": status,
        "play_icon": "media-playback-pause-symbolic" if status == "Playing" else "media-playback-start-symbolic",
        "pos_txt": fmt(pos), "len_txt": fmt(length),
        "pct": round(min(100, pos / length * 100), 1) if length else 0,
        "vol": round(vol),
        "vol_icon": ("audio-volume-muted-symbolic" if vol < 1 else "audio-volume-low-symbolic" if vol < 34
                     else "audio-volume-medium-symbolic" if vol < 67 else "audio-volume-high-symbolic"),
        "shuffle_cls": "on" if pr.get("Shuffle") else "off",
        "loop_cls": "off" if loop == "None" else "on",
        "loop_icon": "media-playlist-repeat-song-symbolic" if loop == "Track" else "media-playlist-repeat-symbolic",
        "lyrics": lyric_rows(pos),
    }

def daemon():
    last = None
    while True:
        try:
            out = build()
        except Exception:
            out = idle()
        s = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
        if s != last:
            print(s, flush=True)
            last = s
        time.sleep(TICK)


# ---------- Steuerung ----------
def cmd(a):
    p = pick()
    if not p:
        return
    c = a[0]
    if c == "toggle":
        act(p, "PlayPause")
    elif c == "next":
        act(p, "Next")
    elif c == "prev":
        act(p, "Previous")
    elif c == "shuffle":
        put(p, "Shuffle", GLib.Variant("b", not get(p, "Shuffle")))
    elif c == "loop":
        order = ["None", "Playlist", "Track"]
        cur = get(p, "LoopStatus")
        put(p, "LoopStatus", GLib.Variant("s", order[(order.index(cur) + 1) % 3]))
    elif c == "vol":
        put(p, "Volume", GLib.Variant("d", max(0.0, min(1.0, float(a[1]) / 100))))
    elif c == "seek":
        md = get(p, "Metadata")
        target = int((md.get("mpris:length") or 0) * float(a[1]) / 100)
        try:
            act(p, "SetPosition", GLib.Variant("(ox)", (md["mpris:trackid"], target)))
        except Exception:
            act(p, "Seek", GLib.Variant("(x)", (target - get(p, "Position"),)))

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "daemon":
        daemon()
    else:
        try:
            cmd(args)
        except Exception as e:
            print(e, file=sys.stderr)
