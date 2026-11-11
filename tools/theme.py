"""The active Nyx theme's colours for icons, as nyx-theme resolves them.

Reads the snapshot nyx-theme publishes for every app ($XDG_RUNTIME_DIR/nyx/theme/
system.json). Without one, reads ~/.config/nyx/theme.toml: Follow Omarchy maps
Omarchy's colors.toml on top of Nyx Dark or Light; otherwise the chosen shipped or
user theme applies. Only what icons need is resolved: background, text, light,
swatches, app accents.
"""
import json
import os
from pathlib import Path
import re
import tomllib

HOME = Path.home()
CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', HOME / '.config'))
STATE = Path(os.environ.get('XDG_STATE_HOME', HOME / '.local/state'))
RUNTIME = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'))
SNAPSHOT = RUNTIME / 'nyx/theme/system.json'

SWATCH_NAMES = ['blue', 'violet', 'pink', 'red', 'coral', 'amber', 'green', 'teal', 'graphite']
DARK_SWATCHES = ['#5b9cff', '#9d7bff', '#ff6fae', '#ff6b6b', '#ff7a59', '#f2b545', '#46d08a', '#4cc9d6', '#a3a3ab']
LIGHT_SWATCHES = ['#2f6fea', '#6f4de0', '#c93a7b', '#d93a3a', '#d4532f', '#b7791f', '#1f9e5c', '#1a8fa0', '#5a5a64']
FALLBACK = {'bg': '#1a1b26', 'text': '#c0caf5', 'accent': '#7aa2f7', 'light': False}
OMARCHY_SWATCHES = [('blue', 'blue'), ('violet', 'magenta'), ('pink', 'bright_magenta'), ('red', 'red'),
                    ('coral', 'orange'), ('amber', 'yellow'), ('green', 'green'), ('teal', 'cyan'),
                    ('graphite', 'dark_foreground')]
OMARCHY_ACCENTS = [('files', 'blue'), ('mail', 'magenta'), ('notes', 'yellow'), ('photos', 'orange'),
                   ('calendar', 'red'), ('music', 'magenta'), ('home', 'green'), ('weather', 'cyan'),
                   ('chat', 'cyan'), ('tasks', 'green')]
SCALARS = ['name', 'light', 'bg', 'text', 'accent']
# Launcher glyphs whose app takes its accent under another name (its window class).
ACCENT_KEYS = {'MediaPlayer': 'media', 'PhotoViewer': 'photos', 'Write': 'office', 'Sheets': 'office',
               'Present': 'office', 'Tasks': 'activity'}


def accent_key(glyph_id):
    return ACCENT_KEYS.get(glyph_id, glyph_id.lower())


def color(value):
    """`value` as #rrggbb if it is a hex colour, else None."""
    if not isinstance(value, str) or not re.fullmatch(r'#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})', value):
        return None
    value = value.lower()
    if len(value) == 4:
        value = '#' + ''.join(c * 2 for c in value[1:])
    return value[:7]


def current_id(theme_id):
    return {'nixe-dark': 'nyx-dark', 'nixe-light': 'nyx-light'}.get(theme_id, theme_id)


def read_toml(path):
    try:
        return tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError):
        return None


def over(top, base):
    """Theme file `top` over `base`, as nyx-theme layers them."""
    out = {k: base[k] for k in SCALARS if k in base}
    out.update({k: top[k] for k in SCALARS if k in top})
    for table in ['accents', 'swatches']:
        out[table] = {**base.get(table, {}), **top.get(table, {})}
    return out


def swatches(own, light):
    own = {k: color(v) for k, v in own.items() if color(v)}
    defaults = LIGHT_SWATCHES if light else DARK_SWATCHES
    out = {name: own.get(name, default) for name, default in zip(SWATCH_NAMES, defaults)}
    out.update({k: v for k, v in own.items() if k not in SWATCH_NAMES})
    return out


def look(file, light):
    """Swatches and resolved app accents (an accent may name a swatch)."""
    named = swatches(file.get('swatches', {}), light)
    accents = {}
    for app, value in file.get('accents', {}).items():
        resolved = named.get(value) or color(value)
        if resolved:
            accents[app] = resolved
    return named, accents


def from_file(file):
    light = file['light'] if isinstance(file.get('light'), bool) else FALLBACK['light']
    named, accents = look(file, light)
    return {'light': light, 'bg': color(file.get('bg')) or FALLBACK['bg'],
            'text': color(file.get('text')) or FALLBACK['text'],
            'accent': color(file.get('accent')) or FALLBACK['accent'], 'swatches': named, 'accents': accents}


def from_omarchy(table, shipped):
    get = lambda key: color(table.get(key))
    bg, text, accent = get('background'), get('foreground'), get('accent') or get('blue')
    if not (bg and text and accent):
        return None
    light = table.get('mode') == 'light'
    nyx = shipped.get('nyx-light' if light else 'nyx-dark', {})
    file = {'accents': dict(nyx.get('accents', {})),
            'swatches': {**nyx.get('swatches', {}),
                         **{name: get(key) for name, key in OMARCHY_SWATCHES if get(key)}}}
    named, accents = look(file, light)
    for app, key in OMARCHY_ACCENTS:
        if get(key):
            accents.setdefault(app, get(key))
    return {'light': light, 'bg': bg, 'text': text, 'accent': accent, 'swatches': named, 'accents': accents}


def user_files():
    files = {}
    folder = CONFIG / 'nyx/themes'
    for path in sorted(folder.glob('*.toml')) if folder.is_dir() else []:
        data = read_toml(path)
        if isinstance(data, dict):
            files[current_id(path.stem)] = data
    return files


def theme_by_id(theme_id, shipped):
    users = user_files()
    stem = theme_id.removeprefix('custom:')
    if stem in users and (stem in shipped or theme_id.startswith('custom:')):
        file = users[stem]
        base = shipped.get(current_id(file.get('inherits', '')), shipped.get(stem, {}))
        return over(file, base)
    if theme_id in shipped:
        return over(shipped[theme_id], {})
    return over(shipped.get('tokyo-night', {}), {})


def from_snapshot():
    """The theme as the system resolved it for every app (nyx-theme's snapshot), so
    icons follow any theme the way the apps do. None without a snapshot."""
    try:
        snap = json.loads(SNAPSHOT.read_text())
    except (OSError, ValueError):
        return None
    legacy, swatch = snap.get('legacy', {}), snap.get('swatches', {})
    bg, text, accent = color(legacy.get('bg')), color(legacy.get('text')), color(legacy.get('accent'))
    if not (bg and text and accent and swatch):
        return None
    light = snap.get('theme', {}).get('appearance') == 'light' or legacy.get('light') == 'true'
    named = swatches(swatch, light)
    accents = {app: c for app, value in snap.get('accents', {}).items() if (c := color(value))}
    return {'light': light, 'bg': bg, 'text': text, 'accent': accent, 'swatches': named, 'accents': accents}


def resolve(shipped):
    """The active theme: light, bg, text, accent, swatches, accents, picks."""
    suite = read_toml(CONFIG / 'nyx/theme.toml') or {}
    mode = suite.get('mode', 'omarchy')
    theme = from_snapshot()
    if theme is None and mode == 'omarchy':
        table = read_toml(STATE / 'omarchy/current/theme/colors.toml')
        if table:
            theme = from_omarchy(table, shipped)
    if theme is None:
        theme = from_file(theme_by_id(current_id(str(suite.get('theme', 'tokyo-night'))), shipped))
    picks = suite.get('app_accents', {})
    theme['picks'] = {app: theme['swatches'][name] for app, name in picks.items()
                      if isinstance(name, str) and name in theme['swatches']}
    return theme


def stamp():
    """Identity and change time of every file the theme is read from."""
    paths = [CONFIG / 'nyx/theme.toml', STATE / 'omarchy/current/theme/colors.toml', SNAPSHOT]
    folder = CONFIG / 'nyx/themes'
    paths += sorted(folder.glob('*.toml')) if folder.is_dir() else []
    out = []
    for path in paths:
        try:
            info = path.stat()
            out.append((str(path), info.st_ino, info.st_mtime_ns))
        except OSError:
            out.append((str(path), None, None))
    return out


def load(asset_dir, follow=True):
    """The active theme, or Nyx Dark as shipped when icons don't follow it."""
    shipped = json.loads((Path(asset_dir) / 'themes.json').read_text())
    if follow:
        return resolve(shipped)
    return {**from_file(over(shipped['nyx-dark'], {})), 'picks': {}}


def icon_accent(theme, app, family):
    """An app icon's colour: the swatch picked for the app, else the theme's
    accent for it, else the theme's version of the glyph's own swatch."""
    return theme['picks'].get(app) or theme['accents'].get(app) or theme['swatches'][family]
