#!/usr/bin/python3
"""Generate Nyx launcher icons in the active Nyx theme's colours."""
import argparse
import colorsys
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

HOME = Path.home()
DATA = Path(os.environ.get('XDG_DATA_HOME', HOME / '.local/share'))
CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', HOME / '.config'))
APPS = DATA / 'applications'
STATE = DATA / 'nyx/icons'
OUTPUT = DATA / 'icons/hicolor/scalable/apps'
HOOK = CONFIG / 'omarchy/hooks/theme-set.d/40-nyx-icons'
UNITS = CONFIG / 'systemd/user'
NYX = HOME / '.local/bin/nyx'
NYX_ICON = 'io.github.design_nexus.nyx.{}.svg'
HOOK_MARK = '# Installed by nyx icons follow on'
# Set where the system supplies nyx-icons.path and nyx-icons.service (NyxOS), so
# `follow` only switches following on and off.
MANAGED_UNITS = os.environ.get('NYX_ICONS_MANAGED_UNITS') == '1'
# A read-only check must not create bytecode next to the bundled renderer.
sys.dont_write_bytecode = True


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


theme_tools = load_module('nyx_icon_theme', Path(__file__).resolve().parent / 'theme.py')


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()


def atomic(path, content, mode=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.nyx-tmp')
    tmp.write_text(content)
    if mode is not None:
        tmp.chmod(mode)
    tmp.replace(path)


def write_if_changed(path, content, mode=None):
    if path.is_file() and path.read_text() == content:
        return False
    atomic(path, content, mode)
    return True


def fields(text):
    section = ''
    result = {}
    for line in text.splitlines():
        if line.startswith('['):
            section = line.strip()
        elif section == '[Desktop Entry]' and '=' in line and not line.startswith('#'):
            key, value = line.split('=', 1)
            result[key] = value
    return result


def replace_icon(text, icon):
    lines = text.splitlines(keepends=True)
    section = False
    for index, line in enumerate(lines):
        if line.startswith('['):
            if section:
                lines.insert(index, 'Icon=' + icon + '\n')
                return ''.join(lines)
            section = line.strip() == '[Desktop Entry]'
        elif section and line.startswith('Icon='):
            lines[index] = 'Icon=' + icon + '\n'
            return ''.join(lines)
    if section:
        return ''.join(lines).rstrip('\n') + '\nIcon=' + icon + '\n'
    raise ValueError('Missing [Desktop Entry]')


def roots():
    values = [APPS]
    values += [Path(p) / 'applications' for p in os.environ.get(
        'XDG_DATA_DIRS', '/usr/local/share:/usr/share').split(':') if p]
    values += [DATA / 'flatpak/exports/share/applications',
               Path('/var/lib/flatpak/exports/share/applications')]
    return list(dict.fromkeys(values))


def discover(records):
    found = {}
    for root in roots():
        if not root.is_dir():
            continue
        for path in sorted(root.rglob('*.desktop')):
            identity = '-'.join(path.relative_to(root).parts)
            if identity in found:
                continue
            record = records.get(identity)
            # Our local override must not hide upstream changes, hiding or removal.
            if record and not record['local'] and path == APPS / identity:
                continue
            found[identity] = path
    # Keep local originals available even while their Icon points at a managed asset.
    return found


def system_icons():
    """Icon folders of packages installed outside the user's data folder."""
    return [Path(p) / 'icons/hicolor/scalable/apps' for p in os.environ.get(
        'XDG_DATA_DIRS', '/usr/local/share:/usr/share').split(':') if p]


def installed_nyx_icon(name):
    """The icon a Nyx app installed: the user's copy, else a system package's."""
    if (OUTPUT / name).is_file():
        return OUTPUT / name
    return next((d / name for d in system_icons() if (d / name).is_file()), None)


def assets():
    candidates = [Path(__file__).resolve().parent / 'assets',
                  Path(__file__).resolve().parents[1] / 'assets/icons']
    for path in candidates:
        if (path / 'third-party-glyphs.json').is_file():
            module = load_module('nyx_icon_renderer', path / 'make_icons.py')
            registry = json.loads((path / 'third-party-glyphs.json').read_text())
            glyphs = json.loads((path / 'app-glyphs.json').read_text())
            return path, module, registry, glyphs
    raise ValueError('Icon assets are missing; reinstall the Nyx CLI icon tools.')


def following():
    return not (STATE / 'follow-off').exists()


class Logos:
    def __init__(self):
        try:
            os.environ.setdefault('NO_AT_BRIDGE', '1')
            import gi
            gi.require_version('Gtk', '3.0')
            from gi.repository import Gtk, GdkPixbuf
        except (ImportError, ValueError) as error:
            raise ValueError('Icon lookup requires python-gobject and gtk3.') from error
        self.theme = Gtk.IconTheme.get_default()
        if self.theme is None:
            self.theme = Gtk.IconTheme.new()
            self.theme.set_custom_theme('hicolor')
        self.pixbuf = GdkPixbuf.Pixbuf

    def resolve(self, name):
        if not name:
            return None
        if name.startswith('/'):
            path = Path(name)
            return path if path.is_file() else None
        info = self.theme.lookup_icon(name, 128, 0)
        if info and info.get_filename():
            path = Path(info.get_filename())
            if path.is_file():
                return path
        for root in [DATA, *[Path(p) for p in os.environ.get(
                'XDG_DATA_DIRS', '/usr/local/share:/usr/share').split(':') if p]]:
            for suffix in ['', '.svg', '.png', '.xpm']:
                path = root / 'pixmaps' / (name + suffix)
                if path.is_file():
                    return path
        return None

    def render(self, path, renderer, tile):
        # Decode to pixels first: arbitrary source SVG content is never embedded.
        image = self.pixbuf.new_from_file_at_scale(str(path), 128, 128, True)
        pixels, channels, stride = image.get_pixels(), image.get_n_channels(), image.get_rowstride()
        accents = []
        for y in range(0, image.get_height(), 3):
            for x in range(0, image.get_width(), 3):
                i = y * stride + x * channels
                if channels == 4 and pixels[i + 3] < 160:
                    continue
                rgb = tuple(value / 255 for value in pixels[i:i + 3])
                h, s, v = colorsys.rgb_to_hsv(*rgb)
                if s > .25 and v > .3:
                    accents.append((s * v, h))
        hue = sorted(accents)[len(accents) // 2][1] if accents else .62
        def color(s, v):
            return '#' + ''.join(f'{round(c * 255):02x}' for c in colorsys.hsv_to_rgb(hue, s, v))
        ok, png = image.save_to_bufferv('png', [], [])
        if not ok:
            raise ValueError('Could not rasterize logo')
        return renderer.render_logo(png, color(.38, .95), color(.65, .78), tile)


def refresh():
    for executable, args in [('gtk-update-icon-cache', ['-f', '-t', '-q', str(DATA / 'icons/hicolor')]),
                             ('update-desktop-database', [str(APPS)])]:
        # Without launchers of its own the user has no desktop database to update.
        if executable == 'update-desktop-database' and not APPS.is_dir():
            continue
        if shutil.which(executable):
            result = subprocess.run([executable, *args], capture_output=True, text=True)
            if result.returncode:
                print(f'Warning: {executable}: {result.stderr.strip()}', file=sys.stderr)


def umbra_command():
    """The Umbra icon themes' command, when they're installed and in use."""
    exe = shutil.which('umbra-icons') or str(HOME / '.local/bin/umbra-icons')
    try:
        settings = json.loads((CONFIG / 'umbra/settings.json').read_text())
    except (OSError, ValueError):
        return None
    return exe if Path(exe).is_file() and settings.get('look') else None


def umbra(theme, report):
    """Rebuild Umbra in the Nyx theme's colours, so folder and file icons match it."""
    exe = umbra_command()
    if not exe:
        return
    palette = {'name': 'Nyx', 'light': theme['light'], 'bg': theme['bg'], 'text': theme['text'],
               'accent': theme['accent'], 'swatches': {k: v for k, v in theme['swatches'].items()
                                                       if k in theme_tools.SWATCH_NAMES}}
    path = STATE / 'umbra-palette.json'
    written = write_if_changed(path, json.dumps(palette, indent=2, sort_keys=True) + '\n')
    built = DATA / 'icons/Umbra/umbra.json'
    try:
        current = json.loads(built.read_text()).get('palette', {})
        stale = any(current.get(k) != palette[k] for k in ('light', 'bg', 'text', 'accent', 'swatches'))
    except (OSError, ValueError):
        stale = True
    if not (written or stale):
        report('current', 'Umbra')
        return
    result = subprocess.run([exe, 'refresh', '--palette', str(path), '--quiet'], capture_output=True, text=True)
    report('recoloured' if result.returncode == 0 else 'error', 'Umbra' if result.returncode == 0
           else f'Umbra: {result.stderr.strip()}')


def save(records):
    atomic(STATE / 'manifest.json', json.dumps({'version': 1, 'entries': records}, indent=2) + '\n')


def unchanged_override(identity, record):
    path = APPS / identity
    return path.is_file() and path.read_text() == record['managed']


def restore_one(identity, record):
    target = APPS / identity
    if not unchanged_override(identity, record):
        # Already removed/restored files can safely release their assets.
        if target.exists() and (not record['local'] or target.read_text() != record['original']):
            return False
    elif record['local']:
        atomic(target, record['original'], record['mode'])
    else:
        target.unlink()
    icon = OUTPUT / record['asset']
    if icon.is_file() and digest(icon.read_bytes()) == record['output_hash']:
        icon.unlink()
    return True


def run(action, quiet=False):
    manifest = STATE / 'manifest.json'
    state = json.loads(manifest.read_text()) if manifest.exists() else {'version': 1, 'entries': {}}
    if state.get('version') != 1:
        raise ValueError('Unsupported icon manifest version')
    records = state['entries']
    counts = {}
    def report(status, name):
        counts[status] = counts.get(status, 0) + 1
        if status == 'error' and quiet:
            print(f'{status}: {name}', file=sys.stderr)
        elif status != 'current' and not quiet:
            print(f'{status}: {name}')
    changed = False
    # `generate` opts third-party launchers in; from then on a sync also gives newly
    # installed apps Nyx icons, until `restore` opts out.
    opted_in = STATE / 'third-party'
    if action == 'generate':
        STATE.mkdir(parents=True, exist_ok=True)
        opted_in.touch()
    elif action == 'restore':
        opted_in.unlink(missing_ok=True)
    adopt = action == 'generate' or (action == 'sync' and opted_in.exists())
    if action == 'restore':
        for identity, record in list(records.items()):
            if restore_one(identity, record):
                del records[identity]
                save(records)
                report('restored', identity)
            else:
                report('conflict (launcher edited; left intact)', identity)
        refresh()
    else:
        asset_dir, renderer, registry, glyphs = assets()
        curated = {identity: value['glyph'] for value in registry.values() for identity in value['desktop_ids']}
        renderer_hash = digest((asset_dir / 'make_icons.py').read_bytes())
        theme = theme_tools.load(asset_dir, follow=following())
        tile = renderer.tile_for(theme['bg'], theme['text'], theme['light'])
        palette = digest(json.dumps([tile, theme['swatches']], sort_keys=True))
        # Nyx's own icons, as installed by each app: recoloured in place. Icons from
        # system packages can't be changed; their recoloured copy goes in the user's
        # folder, which icon lookup prefers.
        for glyph_id, glyph in glyphs.items():
            path = OUTPUT / NYX_ICON.format(glyph_id)
            installed = installed_nyx_icon(path.name)
            if installed is None:
                continue
            family = renderer.family(glyph['light'])
            svg = renderer.themed(glyph, theme_tools.icon_accent(theme, theme_tools.accent_key(glyph_id), family), tile)
            if installed.read_text() == svg:
                report('current', glyph_id)
            elif action == 'check':
                report('outdated', glyph_id)
            else:
                atomic(path, svg, 0o644)
                changed = True
                report('recoloured', glyph_id)
        logos = None
        eligible = set()
        for identity, source in discover(records).items():
            record = records.get(identity)
            if action == 'sync' and not record and not adopt:
                continue
            try:
                raw = source.read_text()
                if record:
                    if not unchanged_override(identity, record):
                        eligible.add(identity)
                        report('conflict (launcher edited; left intact)', identity)
                        continue
                    if record['local']:
                        raw = record['original']
                entry = fields(raw)
                if entry.get('Type') != 'Application' or entry.get('Hidden') == 'true' or entry.get('NoDisplay') == 'true':
                    continue
                if identity.startswith(('io.github.design_nexus.nyx.', 'io.github.design_nexus.nixe.')) or re.match(r'^(?:\S*/)?(?:nyx|nixe)-', entry.get('Exec', '')):
                    continue
                eligible.add(identity)
                label = entry.get('Name', identity)
                glyph = curated.get(identity)
                logo = None
                if glyph is None:
                    if logos is None:
                        logos = Logos()
                    logo = logos.resolve(entry.get('Icon', ''))
                    if logo is None:
                        report('unavailable (source icon missing)', label)
                        continue
                fingerprint = digest(raw + renderer_hash + palette + (json.dumps(glyph, sort_keys=True) if glyph else digest(logo.read_bytes())))
                if record and record['fingerprint'] == fingerprint:
                    output = OUTPUT / record['asset']
                    if output.is_file() and digest(output.read_bytes()) == record['output_hash']:
                        report('current', label)
                        continue
                if action == 'check':
                    report('outdated' if record else 'missing', label)
                    continue
                if glyph:
                    svg = renderer.themed(glyph, theme['swatches'][renderer.family(glyph['light'])], tile)
                else:
                    svg = logos.render(logo, renderer, tile)
                asset = 'nyx-third-party-' + digest(identity)[:24] + '.svg'
                managed = replace_icon(raw, str(OUTPUT / asset))
                original = record['original'] if record else raw
                local = record['local'] if record else source == APPS / identity
                mode = record['mode'] if record and local else source.stat().st_mode & 0o777
                changed |= write_if_changed(OUTPUT / asset, svg)
                records[identity] = dict(original=original, local=local, mode=mode,
                    managed=managed, fingerprint=fingerprint, asset=asset, output_hash=digest(svg))
                # Record ownership before changing the launcher so interruption is recoverable.
                save(records)
                changed |= write_if_changed(APPS / identity, managed, mode)
                report('generated (curated)' if glyph else 'generated (original logo)', label)
            except Exception as error:
                eligible.add(identity)
                report('error', f'{identity}: {error}')
        # Sync only recolours; cleaning up removed apps is left to generate.
        stale = set(records) - eligible if action != 'sync' else set()
        for identity in stale:
            if action == 'check':
                report('obsolete', identity)
            elif restore_one(identity, records[identity]):
                del records[identity]
                save(records)
                changed = True
                report('cleaned', identity)
            else:
                report('conflict (launcher edited; left intact)', identity)
        if changed:
            refresh()
        if action in ('sync', 'generate'):
            umbra(theme, report)
    if not quiet:
        print(', '.join(f'{value} {key}' for key, value in counts.items()) or 'No matching applications.')
    # Edited launchers are the user's choice; automatic syncs don't fail over them.
    conflicts = action != 'sync' and any(key.startswith('conflict') for key in counts)
    return 1 if 'error' in counts or conflicts else 0


def sync(quiet=False):
    """Recolour for the theme, again if it changed while recolouring: a change
    made during a run is folded into that run by systemd, not started anew."""
    for _ in range(3):
        before = theme_tools.stamp()
        status = run('sync', quiet)
        if theme_tools.stamp() == before:
            break
    return status


def systemctl(*args):
    if not shutil.which('systemctl'):
        return
    result = subprocess.run(['systemctl', '--user', *args], capture_output=True, text=True)
    if result.returncode:
        print(f'Warning: systemctl --user {" ".join(args)}: {result.stderr.strip()}', file=sys.stderr)


def units():
    command = f'{NYX} icons sync --quiet'
    # Bursts (clicking through swatches, an app copying several icons) must not hit
    # systemd's start limit; the pause lets one sync cover the whole burst.
    service = ('[Unit]\nDescription=Recolour Nyx icons for the current theme\nStartLimitIntervalSec=0\n\n'
               f'[Service]\nType=oneshot\nExecStartPre=/usr/bin/sleep 1\nExecStart={command}\n')
    # Folders, not theme.toml itself: apps replace it by rename, which a file watch misses.
    # The launcher folders catch apps installed later, by packages as well as by hand.
    # The snapshot's folder too: a theme resolves into it after theme.toml changes.
    snapshot = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}')) / 'nyx/theme'
    folders = [CONFIG / 'nyx', CONFIG / 'nyx/themes', OUTPUT, *[root for root in roots() if root.is_dir()],
               *([snapshot] if snapshot.is_dir() else [])]
    watch = ''.join(f'PathChanged={path}\n' for path in dict.fromkeys(folders))
    path = ('[Unit]\nDescription=Recolour Nyx icons when the Nyx theme changes or an app is installed\n\n'
            f'[Path]\n{watch}Unit=nyx-icons.service\n\n[Install]\nWantedBy=default.target\n')
    # The hook hands the work to the service so a theme switch doesn't wait for it.
    hook = (f'#!/bin/bash\n{HOOK_MARK}: recolour Nyx icons for the new Omarchy theme.\n'
            f'systemctl --user start --no-block nyx-icons.service 2>/dev/null || exec {command}\n')
    return service, path, hook


def follow(on):
    """Make icons follow the theme automatically, or put the Nyx Dark look back."""
    service, path, hook = units()
    if on:
        (STATE / 'follow-off').unlink(missing_ok=True)
        # A watch on a missing folder stops systemd seeing changes beside it.
        (CONFIG / 'nyx/themes').mkdir(parents=True, exist_ok=True)
        if not MANAGED_UNITS:
            if (CONFIG / 'omarchy').is_dir():
                write_if_changed(HOOK, hook, 0o755)
            write_if_changed(UNITS / 'nyx-icons.service', service, 0o644)
            write_if_changed(UNITS / 'nyx-icons.path', path, 0o644)
            systemctl('daemon-reload')
            systemctl('enable', 'nyx-icons.path')
            systemctl('reset-failed', 'nyx-icons.path', 'nyx-icons.service')
            # A running path unit keeps its old watches until restarted.
            systemctl('restart', 'nyx-icons.path')
    else:
        if not MANAGED_UNITS:
            if (UNITS / 'nyx-icons.path').exists():
                systemctl('disable', '--now', 'nyx-icons.path')
            for unit in ['nyx-icons.path', 'nyx-icons.service']:
                (UNITS / unit).unlink(missing_ok=True)
            if HOOK.is_file() and HOOK_MARK in HOOK.read_text():
                HOOK.unlink()
            systemctl('daemon-reload')
        STATE.mkdir(parents=True, exist_ok=True)
        (STATE / 'follow-off').touch()
    print('Icons follow the theme.' if on else 'Icons use the Nyx Dark look.')
    return sync(quiet=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'generate', 'sync', 'restore', 'follow'])
    parser.add_argument('state', nargs='?', choices=['on', 'off'], help='for follow')
    parser.add_argument('--quiet', action='store_true', help='print only problems')
    args = parser.parse_args()
    if (args.action == 'follow') != (args.state is not None):
        parser.error('use: follow on | follow off')
    try:
        if args.action == 'check':
            return run(args.action, args.quiet)
        STATE.mkdir(parents=True, exist_ok=True)
        with (STATE / 'lock').open('w') as lock:
            # Automatic syncs queue behind each other so the latest theme wins.
            wait = args.action in ('sync', 'follow')
            fcntl.flock(lock, fcntl.LOCK_EX if wait else fcntl.LOCK_EX | fcntl.LOCK_NB)
            if args.action == 'follow':
                return follow(args.state == 'on')
            if args.action == 'sync':
                return sync(args.quiet)
            return run(args.action, args.quiet)
    except (OSError, ValueError) as error:
        print(f'nyx icons: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
