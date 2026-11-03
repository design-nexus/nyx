# Nyx

Desktop apps for [Omarchy](https://omarchy.org), built with GTK 4 and Rust. They share
one look: a flat, monospace window that takes its colors from your Omarchy theme and
changes with it, fits a half-screen tile, and works from the keyboard.

| App | What it is |
| --- | --- |
| [Glimpse](https://github.com/design-nexus/nyx-glimpse) | A local universal search panel with plugins |
| [Store](https://github.com/design-nexus/nyx-store) | Discover, install and update apps from Omarchy, Arch, AUR and custom sources |
| [Settings](https://github.com/design-nexus/nyx-settings) | A control panel for Omarchy |
| [Git](https://github.com/design-nexus/nyx-git) | Native Git client: visual commit graph, diffs, staging, branches and stashes |
| [Passwords](https://github.com/design-nexus/nyx-passwords) | A password manager for your Vaultwarden server: logins, one-time codes and secure notes |
| [Contacts](https://github.com/design-nexus/nyx-contacts) | A local address book: contacts, favorites, lists, birthdays and import/export |
| [Activity](https://github.com/design-nexus/nyx-activity) | System activity: processes, usage, startup apps |
| [Torrents](https://github.com/design-nexus/nyx-torrents) | A BitTorrent client, built on libtorrent |
| [PDF](https://github.com/design-nexus/nyx-pdf) | A PDF viewer and editor |
| [Notepad](https://github.com/design-nexus/nyx-notepad) | A plain-text notepad with tabs |
| [Music](https://github.com/design-nexus/nyx-music) | A music player for your library, radio and podcasts |
| [Media Player](https://github.com/design-nexus/nyx-media-player) | A video player for movies and TV shows |
| [Theater](https://github.com/design-nexus/nyx-theater) | Your Plex and Jellyfin movies and shows together |
| [Chat](https://github.com/design-nexus/nyx-chat) | A chat client for Ollama |
| [Fonts](https://github.com/design-nexus/nyx-fonts) | A font manager for Google Fonts and Nerd Fonts |
| [Archive](https://github.com/design-nexus/nyx-archive) | An archive manager, built on 7-Zip |
| [Office](https://github.com/design-nexus/nyx-office) | Write, Sheets and Present: documents, spreadsheets and slides |
| [Photos](https://github.com/design-nexus/nyx-photos) | A photo gallery and editor, with a stand-alone Photo Viewer |
| [Weather](https://github.com/design-nexus/nyx-weather) | Forecasts, radar, hourly conditions, air quality and severe-weather alerts |
| [News](https://github.com/design-nexus/nyx-news) | A local RSS, Atom, and JSON Feed reader |
| [Capture](https://github.com/design-nexus/nyx-capture) | Screenshots, annotation, and OCR |
| [Containers](https://github.com/design-nexus/nyx-containers) | Incus and Docker: containers, VMs, Compose, images, networks, volumes |
| [Mail](https://github.com/design-nexus/nyx-mail) | Your mail accounts in one inbox, readable offline: Google, Microsoft 365, Outlook.com, Fastmail, iCloud and IMAP |
| [Calendar](https://github.com/design-nexus/nyx-calendar) | The calendars from your online accounts and this computer in one place |
| [Reminders](https://github.com/design-nexus/nyx-reminders) | Your task lists from Google Tasks, Microsoft To Do, Nextcloud, Fastmail, iCloud and this computer |
| [Files](https://github.com/design-nexus/nyx-files) | A file manager, with cloud storage through [Cloud](https://github.com/design-nexus/nyx-cloud) |
| [Notes](https://github.com/design-nexus/nyx-notes) | A Markdown workspace for Markdown folders and Obsidian vaults |
| [Calculator](https://github.com/design-nexus/nyx-calculator) | A desktop calculator |
| [Home](https://github.com/design-nexus/nyx-home) | A desktop frontend for your Home Assistant, with desktop automations |
| [Maps](https://github.com/design-nexus/nyx-maps) | A map app |
| [Transfer](https://github.com/design-nexus/nyx-transfer) | File transfers between this computer and SFTP, FTP, FTPS and WebDAV servers |
| [Clipboard](https://github.com/design-nexus/nyx-clipboard) | Clipboard history, snippets, actions and verification codes, on Super + Ctrl + V |
| [Switcher](https://github.com/design-nexus/nyx-switcher) | Window and app switching on Alt + Tab, Super + Tab and Alt + `, most recently used first |
| [Assistant](https://github.com/design-nexus/nyx-assistant) | A local voice assistant: push-to-talk, wake word, desktop commands (not part of `all`; builds with CUDA when it's there) |

Settings also takes device [extensions](https://github.com/design-nexus/nyx-settings/tree/main/extensions) (ASUS, Logitech, Razer, Corsair, RGB
lighting, headsets, game controllers, drawing tablets, monitors, NVIDIA, webcams,
Stream Decks and the assistant), installed from Settings → Extensions.

## Install

Install the apps you want, or all of them:

```sh
curl -fsSL https://raw.githubusercontent.com/design-nexus/nyx/main/install.sh | bash -s -- music pdf
curl -fsSL https://raw.githubusercontent.com/design-nexus/nyx/main/install.sh | bash -s -- all
```

Only the apps you name are downloaded. Archives are verified against the suite manifest.
Use `NYX_BUILD=1` for a source build. The installer adds what the apps need
from the Arch repositories, installs to `~/.local`, and adds the `nyx` command. Add
`--default` to make the apps open their file types.

```sh
nyx list                 # the apps, and which are installed
nyx install chat         # add another
nyx update               # install supported releases for installed apps
nyx uninstall chat       # remove one (--purge also removes its settings and data)
```

Nyx app icons follow the theme: their tile takes the theme's background and their
glyph the app's accent (the swatch picked in its settings, or the theme's). Third-party
launcher icons can use Nyx tiles and curated Nyx glyphs too:

```sh
nyx icons check          # report missing or outdated icons; change nothing
nyx icons generate       # generate and apply third-party icons, recolour Nyx icons
nyx icons sync           # recolour installed Nyx icons and generated third-party icons
nyx icons restore        # restore original third-party launcher icons
nyx icons follow off     # stop following the theme; back to the Nyx Dark look
nyx icons follow on      # follow it again (the installer turns this on)
```

Following the theme installs an Omarchy theme-set hook
(`~/.config/omarchy/hooks/theme-set.d/40-nyx-icons`) and a systemd user path unit,
`nyx-icons.path`. The unit runs `nyx icons sync` when `~/.config/nyx/theme.toml` or
a theme in `~/.config/nyx/themes/` changes, and when an app installs its icon. There
is no running daemon. A sync writes only icons that change, then refreshes the icon
cache. Recognized third-party apps use curated glyphs in the theme's nearest swatch;
other apps keep their original logo colors on the theme's tile, and only apps
already opted in with `generate` are recoloured.
The commands use local assets and require the system Python, python-gobject and
GTK 3. Launcher overrides and restoration records stay under the user's data
directory. Edited launchers are reported as conflicts and left intact. Run
`generate` again after installing apps to give their launchers Nyx icons.
Application-internal branding is unchanged; running apps and launchers may retain
cached icons until reopened. To refresh the bundled design resources during development,
run `python3 tools/package-icons.py /path/to/nyx-design`.


## Shared settings

The theme is shared: choose one in any app and the others follow. It is kept in
`~/.config/nyx/theme.toml`, and themes in `~/.config/nyx/themes/` are offered in
every app. Each app keeps its own settings in `~/.config/nyx-<app>/settings.toml`.

Notepad, Archive and Weather open as floating windows; their Hyprland rules are in
`~/.config/hypr/nyx.lua`.

## Building

```sh
bin/nyx dev setup
bin/nyx dev build music
bin/nyx dev test music
bin/nyx release check --structure-only
```

Source ownership and immutable shared dependencies are recorded in `suite.toml`.
[Core](https://github.com/design-nexus/nyx-core) contains the shared application,
account and sync foundation. [Design](https://github.com/design-nexus/nyx-design)
contains GTK widgets, themes, icons and playback controls. Its
[STYLE.md](https://github.com/design-nexus/nyx-design/blob/main/STYLE.md) is canonical.
The root Cargo workspace is retained only for rollback; active application work
belongs in the independent checkouts. [Release procedures](docs/RELEASES.md) cover
pinned build inputs, artifacts, CI and coordinated API changes.

## License

MIT

## Multi-repository development

[Migration audit and rollout](MULTIREPO_MIGRATION.md) records the reviewed baseline,
repository boundaries, history-preserving commands, and all 24 independently released applications.
Shared workspaces: [Core](https://github.com/design-nexus/nyx-core) and
[Design](https://github.com/design-nexus/nyx-design).
Installation and updates use checksummed releases from the owning repositories.
Apps without a release yet are built from their repository at the revision `suite.toml`
pins. The pre-split monorepo is in this repository's history at `baseline`.

```sh
bin/nyx dev status
bin/nyx dev build archive
bin/nyx dev test archive
bin/nyx release check --structure-only
```

`suite.toml` pins repository revisions and application mappings. `.nyx-local.json`
(ignored) overrides local checkout locations. By default, `nyx dev setup` places
repositories beside this umbrella checkout (for example, `~/Projects/nyx-core`).
`NYX_DEV_HOME` selects a different clone directory. Source publication is recorded in
[the publication receipt](docs/migration/publication.json). `nyx release check`
checks supported releases, source compatibility, artifacts, and checksums.
Build inputs are pinned in `build-environment.json`; runtime/GUI/provider behavior
retains its existing contracts and is not exercised by routine migration checks.
