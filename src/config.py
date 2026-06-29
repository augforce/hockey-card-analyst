"""Load the interpretation config (PLAN sections 5, 7b).

`config/interpretation.yaml` is the methodology turned into deterministic
lookups: tier bands, caveats, position rules, goalie reading rules, and the
claim-to-metric dimension dictionary. Engine modules read it from here.

Not listed in PLAN section 10's tree — added as the single place that resolves
and parses the config so every engine module shares one loader.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import yaml

# src/config.py -> src/ -> repo root -> config/
_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
DEFAULT_CONFIG_PATH = _CONFIG_DIR / "interpretation.yaml"
DEFAULT_GLOSSARY_PATH = _CONFIG_DIR / "glossary.yaml"


@lru_cache(maxsize=None)
def load_config(path: Optional[str] = None) -> dict[str, Any]:
    """Parse the interpretation YAML and return it as a dict.

    `path` defaults to the repo's config/interpretation.yaml. Results are cached
    per path; the returned dict is shared, so treat it as read-only.
    """
    target = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    with target.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"interpretation config at {target} did not parse to a mapping")
    return data


@lru_cache(maxsize=None)
def load_glossary(path: Optional[str] = None) -> dict[str, Any]:
    """Parse the metric glossary YAML and return it as a dict.

    `path` defaults to the repo's config/glossary.yaml. Same caching/read-only
    contract as load_config; the glossary is the single source for metric meaning.
    """
    target = Path(path) if path is not None else DEFAULT_GLOSSARY_PATH
    with target.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict) or "metrics" not in data:
        raise ValueError(f"glossary at {target} did not parse to a mapping with `metrics`")
    return data
