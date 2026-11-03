import importlib.util
import inspect
import sys
from functools import lru_cache
from pathlib import Path

from tracelume.config import get_settings
from tracelume.plugins.base import Plugin


def _load_module(path: Path) -> object:
    name = f"tracelume_plugin_{path.parent.name}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@lru_cache
def load_plugins(plugins_dir: Path | None = None) -> dict[str, Plugin]:
    root = plugins_dir or get_settings().plugins_dir
    found: dict[str, Plugin] = {}
    for path in sorted(root.glob("*/plugin.py")):
        if path.parent.name.startswith("_"):
            continue  # templates
        mod = _load_module(path)
        for _, obj in inspect.getmembers(mod, inspect.isclass):
            if issubclass(obj, Plugin) and obj is not Plugin and not inspect.isabstract(obj):
                found[obj.meta.name] = obj()
    return found


def get_plugin(name: str) -> Plugin:
    plugins = load_plugins()
    if name not in plugins:
        raise KeyError(f"unknown plugin {name!r}")
    return plugins[name]
