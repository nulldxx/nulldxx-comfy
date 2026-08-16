"""Tests for the atomic JSON writer shared by the database saves."""
import json
import os

import pytest

from comfy_stubs import read_json
from nulldxx_comfy.common.json_store import write_json_atomic


def test_writes_a_new_file(tmp_path):
    target = tmp_path / "db.json"

    write_json_atomic(str(target), {"a": 1})

    assert read_json(target) == {"a": 1}


def test_creates_missing_parent_directories(tmp_path):
    target = tmp_path / "user" / "default" / "user-db" / "db.json"

    write_json_atomic(str(target), {"a": 1})

    assert read_json(target) == {"a": 1}


def test_replaces_existing_content(tmp_path):
    target = tmp_path / "db.json"
    target.write_text(json.dumps({"old": True}), encoding="utf-8")

    write_json_atomic(str(target), {"new": True})

    assert read_json(target) == {"new": True}


def test_leaves_no_temp_files_behind(tmp_path):
    target = tmp_path / "db.json"

    write_json_atomic(str(target), {"a": 1})

    assert [p.name for p in tmp_path.iterdir()] == ["db.json"]


def test_a_failed_write_leaves_the_old_file_intact(tmp_path):
    """The point of the temp file: readers never see a half-written database."""
    target = tmp_path / "db.json"
    target.write_text(json.dumps({"old": True}), encoding="utf-8")

    class Unserialisable:
        pass

    with pytest.raises(TypeError):
        write_json_atomic(str(target), {"bad": Unserialisable()})

    assert read_json(target) == {"old": True}
    assert [p.name for p in tmp_path.iterdir()] == ["db.json"]


def test_writes_utf8_without_escaping(tmp_path):
    target = tmp_path / "db.json"

    write_json_atomic(str(target), {"prompt": "café, naïve"})

    assert "café" in target.read_text(encoding="utf-8")


def test_path_without_a_directory_component(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    write_json_atomic("db.json", {"a": 1})

    assert read_json(tmp_path / "db.json") == {"a": 1}
    assert os.path.isfile(tmp_path / "db.json")
