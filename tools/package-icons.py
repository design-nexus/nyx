#!/usr/bin/env python3
"""Bundle canonical Nyx icon resources for offline CLI use."""
from pathlib import Path
import json
import shutil
import sys
import tomllib

root = Path(__file__).resolve().parents[1]
design = Path(sys.argv[1]) if len(sys.argv) > 1 else root.parent / 'nyx-design'
source = design / 'crates/nyx-icons'
target = root / 'assets/icons'
target.mkdir(parents=True, exist_ok=True)
for name in ['make_icons.py', 'app-glyphs.json', 'third-party-glyphs.json']:
    shutil.copy2(source / name, target / name)
# The shipped themes, so `nyx icons sync` can follow a Nyx theme without the apps.
themes = {path.stem: tomllib.loads(path.read_text())
          for path in sorted((design / 'crates/nyx-theme-core/themes').glob('*.toml'))}
if 'nyx-dark' not in themes:
    sys.exit(f"no shipped themes in {design / 'crates/nyx-theme-core/themes'}")
(target / 'themes.json').write_text(json.dumps(themes, indent=1, sort_keys=True) + '\n')
print('Bundled canonical Nyx icon resources.')
