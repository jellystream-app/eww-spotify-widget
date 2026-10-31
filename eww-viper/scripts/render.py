#!/usr/bin/env python3
"""Generates eww.yuck and eww.scss from config.ini. Run via mode.sh / start.sh."""
import configparser
from pathlib import Path
from string import Template

CFG_DIR = Path(__file__).resolve().parent.parent
INI = CFG_DIR / "config.ini"

DEFAULTS = {
    "general": {"monitor": "0", "scale": "1.0", "font": "Inter", "player": "spotify",
                "lyrics_lead": "0.25", "poll_ms": "250", "windowtype": "desktop"},
    "style": {"text_color": "#ffffff", "text_opacity": "1.0", "artist_opacity": "0.75",
              "dim_opacity": "0.45", "blur": "true", "blur_strength": "1.0",
              "text_shadow": "true", "cover_radius": "28", "cover_shadow": "true"},
    "full": {"position": "center", "offset_x": "0", "offset_y": "0", "cover_size": "300",
             "width": "560", "lyric_rows": "3", "show_cover": "true", "show_title": "true",
             "show_progress": "true", "show_lyrics": "true"},
    "compact": {"position": "left", "offset_x": "48", "offset_y": "0", "cover_size": "200",
                "lyrics_width": "500", "lyric_rows": "2", "show_cover": "true",
                "show_title": "true", "show_progress": "true", "show_lyrics": "true"},
}

ANCHORS = {"center": "center", "top": "top center", "bottom": "bottom center",
           "left": "center left", "right": "center right", "top-left": "top left",
           "top-right": "top right", "bottom-left": "bottom left", "bottom-right": "bottom right"}

cp = configparser.ConfigParser(inline_comment_prefixes=(";",))
cp.read_dict(DEFAULTS)
try:
    cp.read(INI, encoding="utf-8")
except Exception as e:
    print(f"config.ini unreadable, using defaults: {e}")


def get(sec, key):
    return cp.get(sec, key, fallback=DEFAULTS[sec][key]).strip()

def num(sec, key):
    try:
        return float(get(sec, key))
    except ValueError:
        print(f"invalid number for [{sec}] {key}, using default")
        return float(DEFAULTS[sec][key])

def flag(sec, key):
    return get(sec, key).lower() in ("1", "true", "yes", "on")

def anchor(sec):
    p = get(sec, "position").lower().replace("_", "-").replace(" ", "-")
    if p not in ANCHORS:
        print(f"unknown position '{p}' in [{sec}], using default")
        p = DEFAULTS[sec]["position"]
    return ANCHORS[p]

def rgb(h):
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (255, 255, 255)


class T(Template):
    delimiter = "@"
    idpattern = r"[A-Z0-9_]+"


# ---------- shared values ----------
sc = max(0.3, num("general", "scale"))
S = lambda v: max(1, round(v * sc))
R, G, B = rgb(get("style", "text_color"))
op = num("style", "text_opacity")

def rgba(alpha, base=None):
    r, g, b = base or (R, G, B)
    return f"rgba({r}, {g}, {b}, {max(0.0, min(1.0, alpha)):.2f})"

def a(alpha):
    return rgba(alpha * op)

blur = flag("style", "blur") and num("style", "blur_strength") > 0
bs = num("style", "blur_strength")
dim = num("style", "dim_opacity")
rad = lambda r: max(1, round(r * bs * sc))

if blur:
    NEAR = f"color: {a(dim)}; text-shadow: 0 0 {rad(2)}px {a(0.55)};"
    MID = f"color: transparent; text-shadow: 0 0 {rad(5)}px {a(0.5)};"
    FAR = f"color: transparent; text-shadow: 0 0 {rad(9)}px {a(0.35)};"
else:
    NEAR = f"color: {a(dim)}; text-shadow: none;"
    MID = f"color: {a(dim * 0.7)}; text-shadow: none;"
    FAR = f"color: {a(dim * 0.5)}; text-shadow: none;"

mon = get("general", "monitor")
V = {
    "FONT": get("general", "font"),
    "MON": mon if mon.isdigit() else f'"{mon}"',
    "WT": get("general", "windowtype"),
    "GLOW": "0 1px 3px rgba(0, 0, 0, 0.8), 0 2px 14px rgba(0, 0, 0, 0.55)" if flag("style", "text_shadow") else "none",
    "TXT": a(1.0),
    "ARTIST_C": a(num("style", "artist_opacity")),
    "TROUGH": a(0.28),
    "NEAR": NEAR, "MID": MID, "FAR": FAR,
    "PAD": S(40), "S4": S(4), "S12": S(12), "BAR_H": S(5),
    "F_TIME": S(12), "TIME_W": S(34),
}

# ---------- FULL ----------
C = num("full", "cover_size")
rows = int(max(0, min(5, num("full", "lyric_rows"))))
W = max(S(num("full", "width")), S(C) + 2 * S(40))
V.update({
    "CS": S(C), "W": W, "X": round(num("full", "offset_x")), "Y": round(num("full", "offset_y")),
    "ANCHOR": anchor("full"), "ROWS": rows,
    "LH": S(40 + 2 * rows * 34 + 50),
    "BAR_W": S(C + 40),
    "RAD": S(num("style", "cover_radius")),
    "COVER_SHADOW": f"0 {S(30)}px {S(70)}px rgba(0, 0, 0, 0.55)" if flag("style", "cover_shadow") else "none",
    "F_TITLE": S(24), "F_ARTIST": S(15), "F_CUR": S(25), "F_L": S(19), "LP": S(5),
    "M_META": S(28), "M_PROG": S(24), "M_LYR": S(30),
    "TLIM": max(10, int((W - 2 * S(40)) / (S(24) * 0.62))),
    "ALIM": max(14, min(60, int((W - 2 * S(40)) / (S(15) * 0.55)))),
})
full_kids = []
if flag("full", "show_cover"): full_kids.append("(cover)")
if flag("full", "show_title"): full_kids.append("(meta)")
if flag("full", "show_progress"): full_kids.append("(progressbar)")
if flag("full", "show_lyrics"): full_kids.append("(lyrics)")
V["FULL_KIDS"] = "\n    ".join(full_kids) or '(label :text "")'

# ---------- COMPACT ----------
c = num("compact", "cover_size")
crows = int(max(0, min(5, num("compact", "lyric_rows"))))
cc = S(c)
gap = S(36)
c_left_on = any(flag("compact", k) for k in ("show_cover", "show_title", "show_progress"))
c_lyr_on = flag("compact", "show_lyrics")
cw = 2 * S(40) + (cc if c_left_on else 0) + ((gap + S(num("compact", "lyrics_width"))) if c_lyr_on else 0)
if c_left_on and c_lyr_on:
    pass
V.update({
    "CC": cc, "CW": cw, "CX": round(num("compact", "offset_x")), "CY": round(num("compact", "offset_y")),
    "CANCHOR": anchor("compact"), "CROWS": crows, "GAP": gap,
    "CRAD": S(num("style", "cover_radius") * 0.7),
    "CCOVER_SHADOW": f"0 {S(20)}px {S(50)}px rgba(0, 0, 0, 0.5)" if flag("style", "cover_shadow") else "none",
    "CTLIM": max(8, int(c / 11)), "CALIM": max(10, int(c / 7.2)),
    "CBAR": max(S(30), cc - S(100)), "CBAR_H": S(4),
    "CF_TITLE": S(16), "CF_ARTIST": S(13), "CF_TIME": S(11), "CTIME_W": S(28),
    "CF_CUR": S(21), "CF_L": S(15), "CLP": S(4), "CM_TITLE": S(16), "CM_ART": S(2), "CM_PROG": S(14),
})
left = []
if flag("compact", "show_cover"):
    left.append('(box :class "cover-s" :halign "start" :width @{CC} :height @{CC} :style {music.cover_style})')
if flag("compact", "show_title"):
    left.append('(label :class "c-title"  :halign "start" :xalign 0 :text {music.title}  :limit-width @{CTLIM})')
    left.append('(label :class "c-artist" :halign "start" :xalign 0 :text {music.artist} :limit-width @{CALIM})')
if flag("compact", "show_progress"):
    left.append('''(box :class "c-progress" :orientation "h" :space-evenly false :spacing @{S8} :halign "start" :width @{CC}
      (label :class "time" :text {music.pos_txt})
      (progress :class "c-bar" :hexpand true :value {music.pct} :orientation "h")
      (label :class "time" :text {music.len_txt}))''')
V["S8"] = S(8)
V["C_LEFT_KIDS"] = T("\n    ".join(left) or '(label :text "")').safe_substitute(V)
ckids = []
if c_left_on: ckids.append("(c-left)")
if c_lyr_on: ckids.append("(c-lyrics)")
V["C_KIDS"] = "\n    ".join(ckids) or '(label :text "")'

# ---------- templates ----------
YUCK = T('''\
;; GENERATED by scripts/render.py from config.ini - edit config.ini, not this file
(deflisten music
  :initial `{"active":false,"title":"Nothing playing","artist":"","cover_style":"","pos_txt":"0:00","len_txt":"0:00","pct":0,"lyrics":[]}`
  "python3 ~/.config/eww-viper/scripts/music.py daemon")

;; ---------- full ----------
(defwidget cover []
  (box :class "cover" :halign "center" :width @{CS} :height @{CS}
       :style {music.cover_style}))

(defwidget meta []
  (box :class "meta" :orientation "v" :space-evenly false :halign "center"
    (label :class "title"  :text {music.title}  :limit-width @{TLIM})
    (label :class "artist" :text {music.artist} :limit-width @{ALIM})))

(defwidget progressbar []
  (box :class "progress" :orientation "h" :space-evenly false :spacing @{S12} :halign "center"
    (label :class "time" :text {music.pos_txt})
    (progress :class "bar" :value {music.pct} :orientation "h")
    (label :class "time" :text {music.len_txt})))

(defwidget lyrics []
  (box :class "lyrics" :orientation "v" :space-evenly false :valign "start" :halign "center" :height @{LH}
    (for l in {music.lyrics}
      (label :class "lyric ${l.c}" :visible {l.d <= @{ROWS}} :text {l.t} :wrap true :xalign 0.5 :justify "center"))))

(defwidget player []
  (box :class "root" :orientation "v" :space-evenly false :halign "center"
    @{FULL_KIDS}))

(defwindow viper-music
  :monitor @{MON}
  :geometry (geometry :x "@{X}px" :y "@{Y}px" :width "@{W}px" :height "0px" :anchor "@{ANCHOR}")
  :stacking "bg"
  :windowtype "@{WT}"
  (player))

;; ---------- compact ----------
(defwidget c-left []
  (box :class "c-left" :orientation "v" :space-evenly false :valign "center"
    @{C_LEFT_KIDS}))

(defwidget c-lyrics []
  (box :class "c-lyrics" :orientation "v" :space-evenly false :valign "start" :halign "start" :hexpand true :height @{CC}
    (box :orientation "v" :space-evenly false :valign "center" :vexpand true
      (for l in {music.lyrics}
        (label :class "cl ${l.c}" :visible {l.d <= @{CROWS}} :text {l.t}
               :wrap true :xalign 0 :justify "left")))))

(defwindow viper-music-compact
  :monitor @{MON}
  :geometry (geometry :x "@{CX}px" :y "@{CY}px" :width "@{CW}px" :height "0px" :anchor "@{CANCHOR}")
  :stacking "bg"
  :windowtype "@{WT}"
  (box :class "c-root" :orientation "h" :space-evenly false :spacing @{GAP}
    @{C_KIDS}))
''')

SCSS = T('''\
// GENERATED by scripts/render.py from config.ini - edit config.ini, not this file
* { all: unset; font-family: "@{FONT}", "Inter", "Adwaita Sans", "Cantarell", sans-serif; }
window { background-color: transparent; }

$glow: @{GLOW};

.time { color: @{ARTIST_C}; font-size: @{F_TIME}px; min-width: @{TIME_W}px; text-shadow: $glow; }

// ---------- full ----------
.root { padding: @{PAD}px; }
.cover {
  border-radius: @{RAD}px;
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  box-shadow: @{COVER_SHADOW};
}
.meta   { margin-top: @{M_META}px; }
.title  { color: @{TXT}; font-size: @{F_TITLE}px; font-weight: 700; text-shadow: $glow; }
.artist { color: @{ARTIST_C}; font-size: @{F_ARTIST}px; margin-top: @{S4}px; text-shadow: $glow; }
.progress { margin-top: @{M_PROG}px; }
.bar trough   { min-width: @{BAR_W}px; min-height: @{BAR_H}px; border-radius: 99px; background-color: @{TROUGH}; }
.bar progress { min-height: @{BAR_H}px; border-radius: 99px; background-color: @{TXT}; }
.lyrics { margin-top: @{M_LYR}px; }
.lyric { font-weight: 700; padding: @{LP}px 0; }
.lyric.cur  { color: @{TXT}; font-size: @{F_CUR}px; text-shadow: $glow; }
.lyric.near { @{NEAR} font-size: @{F_L}px; }
.lyric.mid  { @{MID} font-size: @{F_L}px; }
.lyric.far  { @{FAR} font-size: @{F_L}px; }

// ---------- compact ----------
.c-root { padding: @{PAD}px; }
.cover-s {
  border-radius: @{CRAD}px;
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  box-shadow: @{CCOVER_SHADOW};
}
.c-title  { color: @{TXT}; font-size: @{CF_TITLE}px; font-weight: 700; margin-top: @{CM_TITLE}px; text-shadow: $glow; }
.c-artist { color: @{ARTIST_C}; font-size: @{CF_ARTIST}px; margin-top: @{CM_ART}px; text-shadow: $glow; }
.c-progress { margin-top: @{CM_PROG}px; }
.c-progress .time { font-size: @{CF_TIME}px; min-width: @{CTIME_W}px; }
.c-bar trough   { min-width: @{CBAR}px; min-height: @{CBAR_H}px; border-radius: 99px; background-color: @{TROUGH}; }
.c-bar progress { min-height: @{CBAR_H}px; border-radius: 99px; background-color: @{TXT}; }
.cl { font-weight: 700; padding: @{CLP}px 0; }
.cl.cur  { color: @{TXT}; font-size: @{CF_CUR}px; text-shadow: $glow; }
.cl.near { @{NEAR} font-size: @{CF_L}px; }
.cl.mid  { @{MID} font-size: @{CF_L}px; }
.cl.far  { @{FAR} font-size: @{CF_L}px; }
''')

(CFG_DIR / "eww.yuck").write_text(YUCK.substitute(V))
(CFG_DIR / "eww.scss").write_text(SCSS.substitute(V))
