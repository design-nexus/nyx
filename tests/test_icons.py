"""Focused filesystem integration coverage; never touches the live desktop."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('icons', Path(__file__).resolve().parents[1] / 'tools/icons.py')
icons = importlib.util.module_from_spec(spec)
spec.loader.exec_module(icons)


class IconCommands(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.user, self.system = root / 'applications', root / 'system'
        self.user.mkdir()
        self.system.mkdir()
        self.state = root / 'nyx/icons'
        self.output = root / 'icons/hicolor/scalable/apps'
        self.config = root / 'config'
        self.refreshes = []
        self.system_icons = root / 'system-icons'
        self.patch = patch.multiple(icons, DATA=root, APPS=self.user, STATE=self.state, OUTPUT=self.output,
                                    CONFIG=self.config, UNITS=self.config / 'systemd/user',
                                    HOOK=self.config / 'omarchy/hooks/theme-set.d/40-nyx-icons',
                                    roots=lambda: [self.user, self.system],
                                    system_icons=lambda: [self.system_icons],
                                    refresh=lambda: self.refreshes.append(1), systemctl=lambda *args: None)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        theme_patch = patch.multiple(icons.theme_tools, CONFIG=self.config, STATE=root / 'state')
        theme_patch.start()
        self.addCleanup(theme_patch.stop)
        self.firefox = '[Desktop Entry]\nType=Application\nName=Firefox\nExec=firefox %U\nIcon=firefox\n\n[Desktop Action Private]\nExec=firefox --private\nIcon=private\n'
        (self.system / 'firefox.desktop').write_text(self.firefox)
        logo = root / 'logo.svg'
        logo.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><circle cx="32" cy="32" r="25" fill="#dd8833"/></svg>')
        self.local = '[Desktop Entry]\nType=Application\nName=Custom\nExec=custom --flag\nIcon=' + str(logo) + '\n'
        (self.user / 'custom.desktop').write_text(self.local)
        (self.user / 'custom.desktop').chmod(0o750)
        (self.user / 'hidden.desktop').write_text('[Desktop Entry]\nHidden=true\n')
        (self.system / 'hidden.desktop').write_text(self.firefox)
        (self.system / 'io.github.design_nexus.nyx.Files.desktop').write_text(self.firefox)

    def run_command(self, action):
        result = io.StringIO()
        with contextlib.redirect_stdout(result):
            status = icons.run(action)
        return status, result.getvalue()

    def records(self):
        return json.loads((self.state / 'manifest.json').read_text())['entries']

    def test_generate_refresh_and_restore(self):
        before = sorted(str(p) for p in self.user.parent.rglob('*'))
        self.assertEqual(self.run_command('check')[0], 0)
        self.assertEqual(before, sorted(str(p) for p in self.user.parent.rglob('*')))
        status, output = self.run_command('generate')
        self.assertEqual(status, 0, output)
        self.assertEqual(set(self.records()), {'firefox.desktop', 'custom.desktop'})
        self.assertIn('generated (original logo)', output)
        self.assertIn('generated (curated)', output)
        managed = (self.user / 'firefox.desktop').read_text()
        self.assertIn('[Desktop Action Private]\nExec=firefox --private\nIcon=private', managed)
        self.assertEqual((self.user / 'custom.desktop').stat().st_mode & 0o777, 0o750)
        mtimes = {p: p.stat().st_mtime_ns for p in self.output.glob('*')}
        self.assertIn('2 current', self.run_command('generate')[1])
        self.assertEqual(mtimes, {p: p.stat().st_mtime_ns for p in self.output.glob('*')})
        (self.system / 'firefox.desktop').write_text(self.firefox.replace('firefox %U', 'firefox --new %U'))
        self.assertIn('outdated: Firefox', self.run_command('check')[1])
        self.assertEqual(self.run_command('generate')[0], 0)
        self.assertIn('Exec=firefox --new %U', (self.user / 'firefox.desktop').read_text())
        self.assertEqual(self.run_command('restore')[0], 0)
        self.assertFalse((self.user / 'firefox.desktop').exists())
        self.assertEqual((self.user / 'custom.desktop').read_text(), self.local)
        self.assertEqual(self.records(), {})
        self.assertFalse(list(self.output.glob('*')))

    def test_conflict_and_removed_upstream(self):
        self.run_command('generate')
        local = self.user / 'custom.desktop'
        edited = local.read_text() + '# user edit\n'
        local.write_text(edited)
        self.assertEqual(self.run_command('generate')[0], 1)
        self.assertEqual(local.read_text(), edited)
        (self.system / 'firefox.desktop').unlink()
        self.assertIn('obsolete', self.run_command('check')[1])
        self.run_command('generate')
        self.assertFalse((self.user / 'firefox.desktop').exists())
        self.assertEqual(self.run_command('restore')[0], 1)
        self.assertEqual(local.read_text(), edited)
        local.write_text(self.records()['custom.desktop']['managed'])
        self.assertEqual(self.run_command('restore')[0], 0)
        self.assertEqual(local.read_text(), self.local)

    # Theme following

    def suite(self, text):
        (self.config / 'nyx').mkdir(parents=True, exist_ok=True)
        (self.config / 'nyx/theme.toml').write_text(text)

    def install_nyx_icons(self, *names):
        _, renderer, _, glyphs = icons.assets()
        self.output.mkdir(parents=True, exist_ok=True)
        for name in names:
            # What each app's installer copies: the shipped Nyx Dark rendering.
            (self.output / icons.NYX_ICON.format(name)).write_text(renderer.render_glyph(glyphs[name]))
        return renderer

    def nyx_icon(self, name):
        return (self.output / icons.NYX_ICON.format(name)).read_text()

    def test_nyx_dark_keeps_shipped_icons(self):
        self.suite('mode = "theme"\ntheme = "nyx-dark"\n')
        self.install_nyx_icons('Files', 'Settings', 'Weather')
        before = {p: p.read_text() for p in self.output.glob('*')}
        status, output = self.run_command('sync')
        self.assertEqual(status, 0, output)
        self.assertIn('3 current', output)
        self.assertEqual(before, {p: p.read_text() for p in self.output.glob('*')})
        self.assertEqual(self.refreshes, [])

    def test_light_theme_gives_a_light_tile(self):
        self.suite('mode = "theme"\ntheme = "nyx-light"\n')
        renderer = self.install_nyx_icons('Files')
        self.run_command('sync')
        tile = renderer.tile_for('#f7f7f8', '#18181b', True)
        self.assertIn(tile['tile_top'], self.nyx_icon('Files'))
        self.assertNotIn(renderer.TILE['tile_top'], self.nyx_icon('Files'))

    def test_follows_omarchy_colours(self):
        self.suite('mode = "omarchy"\ntheme = "nyx-dark"\n')
        colors = Path(self.temp.name) / 'state/omarchy/current/theme/colors.toml'
        colors.parent.mkdir(parents=True)
        colors.write_text('mode = "dark"\nbackground = "#1e1e2e"\nforeground = "#cdd6f4"\naccent = "#89b4fa"\n'
                          'blue = "#89b4fa"\ncyan = "#94e2d5"\nmagenta = "#f5c2e7"\n')
        renderer = self.install_nyx_icons('Files', 'Weather')
        self.run_command('sync')
        self.assertIn(renderer.tile_for('#1e1e2e', '#cdd6f4', False)['tile_top'], self.nyx_icon('Files'))
        self.assertIn(renderer.glyph_colors('#89b4fa')[0], self.nyx_icon('Files'))
        self.assertIn(renderer.glyph_colors('#94e2d5')[0], self.nyx_icon('Weather'))

    def test_picked_swatch_wins(self):
        self.suite('mode = "theme"\ntheme = "nyx-dark"\n[app_accents]\nfiles = "violet"\n')
        renderer = self.install_nyx_icons('Files')
        self.run_command('sync')
        self.assertIn(renderer.TUNED['violet'][0], self.nyx_icon('Files'))
        self.assertNotIn(renderer.TUNED['blue'][0], self.nyx_icon('Files'))

    def test_custom_theme_inherits(self):
        self.suite('mode = "theme"\ntheme = "custom:mine"\n')
        (self.config / 'nyx/themes').mkdir(parents=True)
        (self.config / 'nyx/themes/mine.toml').write_text('inherits = "nyx-light"\nbg = "#fafafa"\n')
        asset_dir = icons.assets()[0]
        theme = icons.theme_tools.load(asset_dir)
        self.assertTrue(theme['light'])
        self.assertEqual(theme['bg'], '#fafafa')
        self.assertEqual(theme['swatches']['blue'], '#2f6fea')
        self.assertEqual(theme['accents']['files'], '#2f6fea')

    def test_second_sync_writes_nothing(self):
        self.suite('mode = "theme"\ntheme = "nyx-light"\n')
        self.install_nyx_icons('Files', 'Notes')
        self.run_command('sync')
        self.assertEqual(self.refreshes, [1])
        mtimes = {p: p.stat().st_mtime_ns for p in self.output.glob('*')}
        self.assertIn('2 current', self.run_command('sync')[1])
        self.assertEqual(mtimes, {p: p.stat().st_mtime_ns for p in self.output.glob('*')})
        self.assertEqual(self.refreshes, [1])

    def test_sync_recolours_only_opted_in_launchers(self):
        self.suite('mode = "theme"\ntheme = "nyx-dark"\n')
        self.run_command('sync')
        self.assertFalse((self.state / 'manifest.json').exists())
        self.assertFalse((self.user / 'firefox.desktop').exists())
        self.run_command('generate')
        asset = self.output / self.records()['firefox.desktop']['asset']
        dark = asset.read_text()
        self.suite('mode = "theme"\ntheme = "nyx-light"\n')
        self.assertIn('outdated: Firefox', self.run_command('check')[1])
        self.run_command('sync')
        self.assertNotEqual(dark, asset.read_text())
        self.assertEqual(set(self.records()), {'firefox.desktop', 'custom.desktop'})

    def test_sync_follows_a_change_made_during_it(self):
        self.suite('mode = "theme"\ntheme = "nyx-dark"\n')
        renderer = self.install_nyx_icons('Files')
        real, calls = icons.run, []
        def run(action, quiet=False):
            status = real(action, quiet)
            if not calls:
                # An app saves a new theme while the first pass is running.
                new = self.config / 'nyx/theme.toml.new'
                new.write_text('mode = "theme"\ntheme = "nyx-light"\n')
                new.replace(self.config / 'nyx/theme.toml')
            calls.append(action)
            return status
        with patch.object(icons, 'run', run), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(icons.sync(), 0)
        self.assertEqual(calls, ['sync', 'sync'])
        self.assertIn(renderer.tile_for('#f7f7f8', '#18181b', True)['tile_top'], self.nyx_icon('Files'))

    def test_follow_on_and_off(self):
        self.suite('mode = "theme"\ntheme = "nyx-light"\n')
        (self.config / 'omarchy').mkdir()
        renderer = self.install_nyx_icons('Files')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(icons.follow(True), 0)
        path_unit = (icons.UNITS / 'nyx-icons.path').read_text()
        self.assertIn(f'PathChanged={self.config}/nyx\n', path_unit)
        self.assertIn(f'PathChanged={self.output}', path_unit)
        service = (icons.UNITS / 'nyx-icons.service').read_text()
        self.assertIn('icons sync --quiet', service)
        self.assertIn('StartLimitIntervalSec=0', service)
        self.assertIn('ExecStartPre=/usr/bin/sleep 1', service)
        self.assertIn('icons sync --quiet', icons.HOOK.read_text())
        self.assertNotIn(renderer.TILE['tile_top'], self.nyx_icon('Files'))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(icons.follow(False), 0)
        self.assertFalse(icons.HOOK.exists())
        self.assertFalse((icons.UNITS / 'nyx-icons.path').exists())
        _, _, _, glyphs = icons.assets()
        self.assertEqual(self.nyx_icon('Files'), renderer.render_glyph(glyphs['Files']))

    def test_system_icons_get_a_user_copy(self):
        # Apps installed by the system (NyxOS) leave their icon outside the user's folder.
        _, renderer, _, glyphs = icons.assets()
        self.system_icons.mkdir()
        shipped = renderer.render_glyph(glyphs['Files'])
        (self.system_icons / icons.NYX_ICON.format('Files')).write_text(shipped)
        self.suite('mode = "theme"\ntheme = "nyx-dark"\n')
        self.assertIn('1 current', self.run_command('sync')[1])
        self.assertFalse(self.output.exists())
        self.suite('mode = "theme"\ntheme = "nyx-light"\n')
        self.assertIn('recoloured: Files', self.run_command('sync')[1])
        self.assertIn(renderer.tile_for('#f7f7f8', '#18181b', True)['tile_top'], self.nyx_icon('Files'))
        self.assertEqual((self.system_icons / icons.NYX_ICON.format('Files')).read_text(), shipped)
        self.assertIn('1 current', self.run_command('sync')[1])

    def test_follow_with_managed_units(self):
        (self.config / 'omarchy').mkdir(parents=True)
        with patch.object(icons, 'MANAGED_UNITS', True), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(icons.follow(False), 0)
            self.assertTrue((self.state / 'follow-off').exists())
            self.assertEqual(icons.follow(True), 0)
        self.assertFalse((self.state / 'follow-off').exists())
        self.assertFalse(icons.UNITS.exists())
        self.assertFalse(icons.HOOK.exists())


if __name__ == '__main__':
    unittest.main()
