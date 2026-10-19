"""Load the dependency-light protocol package without running HA setup.

The protocol and constants use only the standard library. These unit tests do
not exercise Home Assistant integration setup.
"""
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
for name, path in (
    ("custom_components", ROOT / "custom_components"),
    ("custom_components.nuvo_t2fam", ROOT / "custom_components" / "nuvo_t2fam"),
):
    module = types.ModuleType(name)
    module.__path__ = [str(path)]
    sys.modules[name] = module
