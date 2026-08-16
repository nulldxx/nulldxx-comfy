"""Tests for common/user_db.py - locating the ComfyUI root and the user-db dir."""
import os

import folder_paths
import pytest

from nulldxx_comfy.common.user_db import get_comfy_path, get_user_db_path


@pytest.fixture
def clean_tmp_path(tmp_path_factory):
    """A tmp dir whose full path contains neither "models" nor "output".

    Methods 2 and 3 of get_comfy_path() derive the root by splitting the path on
    those words, so a tmp dir named after the test can trip them by accident.
    """
    return tmp_path_factory.mktemp("root")


def test_base_path_is_preferred(comfy_root):
    assert get_comfy_path() == str(comfy_root)


def test_user_db_path_is_under_user_default(comfy_root):
    expected = os.path.join(str(comfy_root), "user", "default", "user-db")

    assert get_user_db_path() == expected


def test_user_db_directory_is_created(comfy_root):
    path = get_user_db_path()

    assert os.path.isdir(path)


def test_user_db_path_is_idempotent(comfy_root):
    assert get_user_db_path() == get_user_db_path()


def test_falls_back_to_checkpoints_folder(monkeypatch, clean_tmp_path):
    """Method 2: derive the root from the checkpoints folder when base_path is absent."""
    root = clean_tmp_path / "Comfy"
    monkeypatch.delattr(folder_paths, "base_path")
    monkeypatch.setattr(
        folder_paths,
        "get_folder_paths",
        lambda name: [str(root / "models" / "checkpoints")] if name == "checkpoints" else [],
    )

    assert get_comfy_path() == str(root)


def test_checkpoints_fallback_handles_a_root_under_a_models_directory(
    monkeypatch, clean_tmp_path
):
    """An install can itself live under a directory called "models"."""
    root = clean_tmp_path / "models" / "Comfy"
    monkeypatch.delattr(folder_paths, "base_path")
    monkeypatch.setattr(
        folder_paths,
        "get_folder_paths",
        lambda name: [str(root / "models" / "checkpoints")] if name == "checkpoints" else [],
    )

    assert get_comfy_path() == str(root)


def test_falls_back_to_output_folder(monkeypatch, clean_tmp_path):
    """Method 3: derive the root from the output folder."""
    root = clean_tmp_path / "Comfy"
    monkeypatch.delattr(folder_paths, "base_path")

    def get_folder_paths(name):
        if name == "output":
            return [str(root / "output")]
        return []

    monkeypatch.setattr(folder_paths, "get_folder_paths", get_folder_paths)

    assert get_comfy_path() == str(root)


def test_falls_back_to_cwd(monkeypatch, tmp_path):
    """Method 4: nothing else resolved, so use the working directory."""
    monkeypatch.delattr(folder_paths, "base_path")
    monkeypatch.setattr(folder_paths, "get_folder_paths", lambda name: [])
    monkeypatch.chdir(tmp_path)

    assert get_comfy_path() == os.getcwd()


def test_falls_back_to_loras_dir_when_user_db_cannot_be_created(monkeypatch, tmp_path):
    """A read-only root must not crash the node - the legacy LoRa folder is used."""
    loras = tmp_path / "loras"
    loras.mkdir()
    monkeypatch.setattr(folder_paths, "base_path", str(tmp_path))
    monkeypatch.setattr(folder_paths, "get_folder_paths", lambda name: [str(loras)])

    def boom(*args, **kwargs):
        raise PermissionError("read-only filesystem")

    monkeypatch.setattr(os, "makedirs", boom)

    assert get_user_db_path() == str(loras)
