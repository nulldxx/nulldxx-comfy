"""
Test harness for the node pack.

The node modules import `folder_paths`, `comfy.sd`, `comfy.utils` and `server` at
module scope, and register their aiohttp routes as an import side effect. None of
those modules exist outside a running ComfyUI, so this module installs minimal
stand-ins into `sys.modules` *before* the package is imported.

The repo directory name (`nulldxx-comfy`) contains a hyphen, so it can't be
imported with a plain `import` statement. It is loaded here under the alias
`nulldxx_comfy` so the `from ..common.user_db import ...` relative imports inside
the nodes resolve normally.

This lives outside conftest.py so it is imported exactly once, as an ordinary
module on sys.path, no matter how pytest chooses to load the conftest.
"""
import asyncio
import importlib.util
import json
import os
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------
# ComfyUI stand-ins
# --------------------------------------------------------------------------

def _make_folder_paths():
    """Stub of ComfyUI's `folder_paths` module.

    `base_path` and `loras_dir` are rewritten per test by the `comfy_root`
    fixture; the lookup functions mirror the real ones closely enough for the
    node code, including `get_full_path()` returning None for a missing file.
    """
    mod = types.ModuleType("folder_paths")
    mod.base_path = None
    mod.loras_dir = None

    def get_folder_paths(name):
        if name == "loras" and mod.loras_dir:
            return [str(mod.loras_dir)]
        if mod.base_path is None:
            return []
        if name == "output":
            return [os.path.join(mod.base_path, "output")]
        return [os.path.join(mod.base_path, "models", name)]

    def get_filename_list(name):
        paths = get_folder_paths(name)
        if not paths or not os.path.isdir(paths[0]):
            return []
        root = paths[0]
        found = []
        for dirpath, _dirnames, filenames in os.walk(root):
            for filename in filenames:
                rel = os.path.relpath(os.path.join(dirpath, filename), root)
                found.append(rel.replace(os.sep, "/"))
        return sorted(found)

    def get_full_path(name, filename):
        paths = get_folder_paths(name)
        if not paths:
            return None
        full = os.path.join(paths[0], filename.replace("/", os.sep))
        return full if os.path.isfile(full) else None

    mod.get_folder_paths = get_folder_paths
    mod.get_filename_list = get_filename_list
    mod.get_full_path = get_full_path
    return mod


def _make_server():
    """Stub of ComfyUI's `server` module.

    `PromptServer.instance.routes.post(path)` is used as a decorator at import
    time. Here it records the handler against its path and returns the function
    untouched, so tests can invoke the route handlers directly.
    """
    mod = types.ModuleType("server")
    routes = {}

    class _Routes:
        def post(self, path):
            def decorator(func):
                routes[path] = func
                return func
            return decorator

    class _Instance:
        routes = _Routes()

    class PromptServer:
        instance = _Instance()

    mod.PromptServer = PromptServer
    mod.registered_routes = routes
    return mod


def _make_comfy():
    """Stub of the `comfy.sd` / `comfy.utils` surface the LoRa loader touches."""
    comfy = types.ModuleType("comfy")
    comfy.__path__ = []

    sd = types.ModuleType("comfy.sd")

    def load_lora_for_models(model, clip, lora, strength_model, strength_clip):
        # Record the call so tests can assert CLIP is never given a strength.
        sd.calls.append((model, clip, lora, strength_model, strength_clip))
        return (f"{model}+lora", clip)

    sd.calls = []
    sd.load_lora_for_models = load_lora_for_models

    utils = types.ModuleType("comfy.utils")

    def load_torch_file(path, safe_load=False):
        return utils.next_result

    utils.next_result = {"lora.weight": "tensor"}
    utils.load_torch_file = load_torch_file

    comfy.sd = sd
    comfy.utils = utils
    return comfy, sd, utils


folder_paths = _make_folder_paths()
server = _make_server()
_comfy, _comfy_sd, _comfy_utils = _make_comfy()

sys.modules.setdefault("folder_paths", folder_paths)
sys.modules.setdefault("server", server)
sys.modules.setdefault("comfy", _comfy)
sys.modules.setdefault("comfy.sd", _comfy_sd)
sys.modules.setdefault("comfy.utils", _comfy_utils)


# --------------------------------------------------------------------------
# Package import (must happen after the stubs are installed)
# --------------------------------------------------------------------------

def _load_package():
    spec = importlib.util.spec_from_file_location(
        "nulldxx_comfy",
        REPO_ROOT / "__init__.py",
        submodule_search_locations=[str(REPO_ROOT)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["nulldxx_comfy"] = module
    spec.loader.exec_module(module)
    return module


nulldxx_comfy = _load_package()


# --------------------------------------------------------------------------
# Helpers used directly by the tests
# --------------------------------------------------------------------------

class FakeRequest:
    """Minimal stand-in for an aiohttp request carrying a JSON body."""

    def __init__(self, payload=None, raise_on_json=None):
        self._payload = payload if payload is not None else {}
        self._raise = raise_on_json

    async def json(self):
        if self._raise is not None:
            raise self._raise
        return self._payload


def call_route(handler, payload=None, raise_on_json=None):
    """Invoke an async route handler and return (status, decoded body)."""
    response = asyncio.run(handler(FakeRequest(payload, raise_on_json)))
    return response.status, json.loads(response.body.decode("utf-8"))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def make_lora_file(loras_dir, relative_name, content=b"lora-bytes"):
    """Create a fake LoRa file (any bytes will do - only its hash matters)."""
    path = Path(loras_dir) / relative_name.replace("/", os.sep)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path
