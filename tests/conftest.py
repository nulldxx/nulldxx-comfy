"""Shared fixtures.

The heavy lifting - installing the ComfyUI stand-ins and loading the pack under
an importable alias - happens in comfy_stubs.py, which this imports.
"""
import pytest

from comfy_stubs import folder_paths, server


@pytest.fixture
def comfy_root(tmp_path, monkeypatch):
    """Point the stubbed ComfyUI at a throwaway root directory.

    The node code resolves its database through the real `get_user_db_path()`,
    so everything lands in `{tmp}/ComfyUI/user/default/user-db/`.
    """
    root = tmp_path / "ComfyUI"
    loras = root / "models" / "loras"
    loras.mkdir(parents=True)
    monkeypatch.setattr(folder_paths, "base_path", str(root))
    monkeypatch.setattr(folder_paths, "loras_dir", str(loras))
    return root


@pytest.fixture
def user_db(comfy_root):
    """The user-db directory for the current test's ComfyUI root."""
    path = comfy_root / "user" / "default" / "user-db"
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def loras_dir(comfy_root):
    return comfy_root / "models" / "loras"


@pytest.fixture
def routes():
    """Mapping of route path -> handler, captured when the pack was imported."""
    return server.registered_routes
