"""Bind the staged MkDocs tree to the same source inputs as Astro."""

import json
from pathlib import Path
from runpy import run_path

input_identity = run_path(str(Path(__file__).with_name("site_identity.py")))[
    "input_identity"
]


def on_post_build(config):
    path = Path(config.site_dir) / "renderer-input.json"
    path.write_text(json.dumps(input_identity(), indent=2) + "\n")
