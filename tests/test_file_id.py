"""Tests for common/file_id.py - the content-sampling hash used as a LoRa identity."""
import pytest

from nulldxx_comfy.common.file_id import get_file_id, get_file_id_safe

MB = 1024 * 1024


def test_same_content_gives_same_id(tmp_path):
    a = tmp_path / "a.safetensors"
    b = tmp_path / "b.safetensors"
    a.write_bytes(b"identical content")
    b.write_bytes(b"identical content")

    assert get_file_id(a) == get_file_id(b)


def test_different_content_gives_different_id(tmp_path):
    a = tmp_path / "a.safetensors"
    b = tmp_path / "b.safetensors"
    a.write_bytes(b"content one")
    b.write_bytes(b"content two")

    assert get_file_id(a) != get_file_id(b)


def test_id_is_stable_across_calls(tmp_path):
    path = tmp_path / "model.safetensors"
    path.write_bytes(b"x" * 4096)

    assert get_file_id(path) == get_file_id(path)


def test_size_is_part_of_the_hash(tmp_path):
    """Files whose sampled bytes are identical must still differ by size.

    Both files here have the same first 1MB and the same last 1MB, and differ
    only in the length of the unsampled middle. Only the hashed file size tells
    them apart.
    """
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    head, tail = b"A" * MB, b"B" * MB
    a.write_bytes(head + b"X" * 100 + tail)
    b.write_bytes(head + b"X" * 200 + tail)

    assert get_file_id(a) != get_file_id(b)


def test_empty_file_hashes_without_error(tmp_path):
    path = tmp_path / "empty.bin"
    path.write_bytes(b"")

    assert isinstance(get_file_id(path), str)
    assert len(get_file_id(path)) == 40  # SHA1 hex digest


def test_change_in_first_megabyte_changes_id(tmp_path):
    path = tmp_path / "big.safetensors"
    data = bytearray(b"\x00" * (3 * MB))
    path.write_bytes(bytes(data))
    original = get_file_id(path)

    data[10] = 0xFF
    path.write_bytes(bytes(data))

    assert get_file_id(path) != original


def test_change_in_last_megabyte_changes_id(tmp_path):
    path = tmp_path / "big.safetensors"
    data = bytearray(b"\x00" * (3 * MB))
    path.write_bytes(bytes(data))
    original = get_file_id(path)

    data[-10] = 0xFF
    path.write_bytes(bytes(data))

    assert get_file_id(path) != original


def test_change_in_unsampled_middle_does_not_change_id(tmp_path):
    """Documents the deliberate trade-off: only the first and last 1MB are read.

    A byte in the middle of a large file is invisible to the hash. This keeps
    multi-GB LoRa files cheap to identify, at the cost of not being a checksum.
    """
    path = tmp_path / "big.safetensors"
    data = bytearray(b"\x00" * (3 * MB))
    path.write_bytes(bytes(data))
    original = get_file_id(path)

    data[MB + 500] = 0xFF  # past the first 1MB, before the last 1MB
    path.write_bytes(bytes(data))

    assert get_file_id(path) == original


def test_file_at_exactly_one_megabyte_is_read_once(tmp_path):
    """At exactly 1MB the `file_size > CHUNK_SIZE` branch is skipped."""
    path = tmp_path / "exact.bin"
    path.write_bytes(b"\x01" * MB)

    assert isinstance(get_file_id(path), str)


def test_missing_file_raises(tmp_path):
    with pytest.raises((FileNotFoundError, OSError)):
        get_file_id(tmp_path / "nope.safetensors")


def test_safe_returns_none_for_missing_file_by_default(tmp_path):
    assert get_file_id_safe(tmp_path / "nope.safetensors") is None


def test_safe_returns_supplied_fallback(tmp_path):
    assert get_file_id_safe(tmp_path / "nope.safetensors", "unknown") == "unknown"


def test_safe_returns_real_id_when_readable(tmp_path):
    path = tmp_path / "model.safetensors"
    path.write_bytes(b"real content")

    assert get_file_id_safe(path) == get_file_id(path)


def test_safe_handles_a_directory(tmp_path):
    """A directory raises IsADirectoryError (an OSError) - it must not escape."""
    assert get_file_id_safe(tmp_path, "unknown") == "unknown"
