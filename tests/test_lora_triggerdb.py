"""Tests for the LoRa trigger database: extraction, cleaning, lookup and migration."""
import comfy.sd
import pytest

from comfy_stubs import call_route, make_lora_file, read_json, write_json
from nulldxx_comfy.common.file_id import get_file_id
from nulldxx_comfy.nodes.lora_loader_with_triggerdb import (
    LoRaLoaderWithTriggerDB,
    build_file_id_to_key_map,
    clean_trigger_word,
    extract_triggers_from_metadata,
    read_lora_metadata,
)


@pytest.fixture
def triggers_file(user_db):
    return user_db / "lora-triggers.json"


# --------------------------------------------------------------------------
# extract_triggers_from_metadata
# --------------------------------------------------------------------------

def test_extracts_from_kohya_tag_frequency_dict():
    meta = {"ss_tag_frequency": {"1girl": 40, "smile": 12}}

    assert extract_triggers_from_metadata(meta) == ["1girl", "smile"]


def test_extracts_from_a_json_encoded_string():
    meta = {"ss_tag_frequency": '{"1girl": 40, "smile": 12}'}

    assert extract_triggers_from_metadata(meta) == ["1girl", "smile"]


def test_extracts_from_a_comma_separated_string():
    meta = {"trained_words": "wizard hat, glowing staff , robes"}

    assert extract_triggers_from_metadata(meta) == ["wizard hat", "glowing staff", "robes"]


def test_extracts_from_a_list():
    meta = {"trained_words": ["wizard", "staff"]}

    assert extract_triggers_from_metadata(meta) == ["wizard", "staff"]


def test_list_entries_are_coerced_to_strings():
    meta = {"trained_words": [1, 2.5, "three"]}

    assert extract_triggers_from_metadata(meta) == ["1", "2.5", "three"]


def test_known_keys_are_tried_in_priority_order():
    meta = {"trained_words": ["second"], "ss_tag_frequency": {"first": 1}}

    assert extract_triggers_from_metadata(meta) == ["first"]


def test_falls_back_to_any_key_mentioning_trigger():
    meta = {"custom_trigger_list": ["alpha", "beta"]}

    assert extract_triggers_from_metadata(meta) == ["alpha", "beta"]


def test_falls_back_to_any_key_mentioning_word():
    meta = {"my_words": "alpha, beta"}

    assert extract_triggers_from_metadata(meta) == ["alpha", "beta"]


def test_unrelated_metadata_yields_nothing():
    meta = {"ss_learning_rate": "0.0001", "modelspec.title": "My LoRa"}

    assert extract_triggers_from_metadata(meta) == []


def test_non_dict_metadata_yields_nothing():
    assert extract_triggers_from_metadata(None) == []
    assert extract_triggers_from_metadata("a string") == []
    assert extract_triggers_from_metadata(["a", "list"]) == []


def test_empty_metadata_yields_nothing():
    assert extract_triggers_from_metadata({}) == []


# --------------------------------------------------------------------------
# clean_trigger_word
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1_girl", "girl"),
        ("20_wizard hat", "wizard hat"),
        ("girl", "girl"),
        ("v2_style", "v2_style"),          # only a leading number is stripped
        ("1_2_thing", "2_thing"),          # only the first prefix is stripped
        ("", ""),
    ],
)
def test_cleaning_strips_dataset_folder_prefixes(raw, expected):
    assert clean_trigger_word(raw) == expected


@pytest.mark.parametrize("raw", ["img", "IMG", "img_dir", "image_dir", "1_img"])
def test_dataset_artefacts_are_filtered_out(raw):
    assert clean_trigger_word(raw) is None


# --------------------------------------------------------------------------
# build_file_id_to_key_map
# --------------------------------------------------------------------------

def test_map_includes_entries_with_a_file_id():
    db = {"flux/a": {"all_triggers": "x", "file_id": "aaa"}}

    assert build_file_id_to_key_map(db) == {"aaa": "flux/a"}


def test_map_skips_entries_without_a_file_id():
    db = {"flux/a": {"all_triggers": "x"}, "flux/b": {"file_id": "bbb"}}

    assert build_file_id_to_key_map(db) == {"bbb": "flux/b"}


def test_map_skips_legacy_string_entries():
    db = {"old": "trigger words", "new": {"file_id": "bbb"}}

    assert build_file_id_to_key_map(db) == {"bbb": "new"}


def test_map_keeps_the_last_key_for_a_duplicated_file_id():
    """Duplicate LoRa files (or several 'unknown' markers) collapse to one key.

    Harmless in practice: a lookup only ever uses a file_id computed from a file
    that exists, so the shared 'unknown' marker is never matched.
    """
    db = {"first": {"file_id": "same"}, "second": {"file_id": "same"}}

    assert build_file_id_to_key_map(db) == {"same": "second"}


def test_map_of_an_empty_database_is_empty():
    assert build_file_id_to_key_map({}) == {}


# --------------------------------------------------------------------------
# Key normalisation and lookup
# --------------------------------------------------------------------------

def test_base_name_strips_the_extension(comfy_root):
    node = LoRaLoaderWithTriggerDB()

    assert node.get_lora_base_name("my-lora.safetensors") == "my-lora"


def test_base_name_normalises_windows_separators(comfy_root):
    node = LoRaLoaderWithTriggerDB()

    assert node.get_lora_base_name("flux\\sub\\my-lora.safetensors") == "flux/sub/my-lora"


def test_base_name_keeps_dots_inside_the_name(comfy_root):
    node = LoRaLoaderWithTriggerDB()

    assert node.get_lora_base_name("my.lora.v2.safetensors") == "my.lora.v2"


def test_normalise_key_only_touches_separators(comfy_root):
    node = LoRaLoaderWithTriggerDB()

    assert node.normalize_lora_key("flux\\a.safetensors") == "flux/a.safetensors"


def test_lookup_finds_an_exact_key(comfy_root):
    node = LoRaLoaderWithTriggerDB()
    db = {"flux/my-lora": {"all_triggers": "found"}}

    assert node.find_lora_in_db(db, "flux/my-lora.safetensors")["all_triggers"] == "found"


def test_lookup_matches_a_key_stored_with_backslashes(comfy_root):
    """Databases written on Windows before normalisation must still resolve."""
    node = LoRaLoaderWithTriggerDB()
    db = {"flux\\my-lora": {"all_triggers": "found"}}

    assert node.find_lora_in_db(db, "flux/my-lora.safetensors")["all_triggers"] == "found"


def test_lookup_matches_a_windows_query_against_a_normalised_key(comfy_root):
    node = LoRaLoaderWithTriggerDB()
    db = {"flux/my-lora": {"all_triggers": "found"}}

    assert node.find_lora_in_db(db, "flux\\my-lora.safetensors")["all_triggers"] == "found"


def test_lookup_returns_empty_when_absent(comfy_root):
    node = LoRaLoaderWithTriggerDB()

    assert node.find_lora_in_db({"other": {}}, "flux/my-lora.safetensors") == {}


# --------------------------------------------------------------------------
# read_lora_metadata
# --------------------------------------------------------------------------

def test_metadata_of_a_missing_file_is_empty(tmp_path):
    assert read_lora_metadata(str(tmp_path / "nope.safetensors")) == {}


def test_metadata_of_an_unsupported_extension_is_empty(tmp_path):
    path = tmp_path / "model.ckpt"
    path.write_bytes(b"data")

    assert read_lora_metadata(str(path)) == {}


def test_metadata_of_a_corrupt_safetensors_file_is_empty(tmp_path):
    """A truncated file must return {} rather than raise into the route."""
    pytest.importorskip("safetensors")
    path = tmp_path / "model.safetensors"
    path.write_bytes(b"not really a safetensors file")

    assert read_lora_metadata(str(path)) == {}


# --------------------------------------------------------------------------
# Node execution
# --------------------------------------------------------------------------

def test_zero_strength_skips_loading(comfy_root):
    node = LoRaLoaderWithTriggerDB()
    before = len(comfy.sd.calls)

    result = node.load_lora("MODEL", "a.safetensors", 0, "all", "active")

    assert result == ("MODEL", "all", "active")
    assert len(comfy.sd.calls) == before


def test_lora_is_applied_to_the_model_only(comfy_root, loras_dir):
    make_lora_file(loras_dir, "my-lora.safetensors")
    node = LoRaLoaderWithTriggerDB()
    comfy.sd.calls.clear()

    model, all_triggers, active = node.load_lora("MODEL", "my-lora.safetensors", 0.8, "a", "b")

    assert model == "MODEL+lora"
    assert (all_triggers, active) == ("a", "b")
    _model, clip, _lora, strength_model, strength_clip = comfy.sd.calls[-1]
    assert clip is None
    assert strength_model == 0.8
    assert strength_clip == 0


def test_triggers_pass_through_unchanged(comfy_root, loras_dir):
    make_lora_file(loras_dir, "my-lora.safetensors")
    node = LoRaLoaderWithTriggerDB()

    _model, all_triggers, active = node.load_lora(
        "MODEL", "my-lora.safetensors", 1.0, "one, two", "one"
    )

    assert all_triggers == "one, two"
    assert active == "one"


def test_input_types_lists_available_loras(comfy_root, loras_dir):
    make_lora_file(loras_dir, "flux/sub-lora.safetensors")
    make_lora_file(loras_dir, "top-lora.safetensors")

    required = LoRaLoaderWithTriggerDB.INPUT_TYPES()["required"]

    assert set(required["lora_name"][0]) == {"flux/sub-lora.safetensors", "top-lora.safetensors"}


def test_input_types_copes_with_no_loras_installed(comfy_root):
    required = LoRaLoaderWithTriggerDB.INPUT_TYPES()["required"]

    assert required["lora_name"][0] == []
    assert required["lora_name"][1]["default"] == ""


# --------------------------------------------------------------------------
# /lora_triggers_save
# --------------------------------------------------------------------------

def test_save_writes_triggers_and_a_file_id(comfy_root, loras_dir, triggers_file, routes):
    lora = make_lora_file(loras_dir, "my-lora.safetensors")

    _status, body = call_route(
        routes["/lora_triggers_save"],
        {
            "lora_name": "my-lora.safetensors",
            "all_triggers": "one, two",
            "active_triggers": "one",
        },
    )

    assert body["success"] is True
    entry = read_json(triggers_file)["my-lora"]
    assert entry["all_triggers"] == "one, two"
    assert entry["active_triggers"] == "one"
    assert entry["file_id"] == get_file_id(lora)


def test_save_normalises_a_windows_style_key(comfy_root, loras_dir, triggers_file, routes):
    make_lora_file(loras_dir, "flux/my-lora.safetensors")

    call_route(
        routes["/lora_triggers_save"],
        {"lora_name": "flux\\my-lora.safetensors", "all_triggers": "one", "active_triggers": ""},
    )

    assert "flux/my-lora" in read_json(triggers_file)


def test_save_trims_surrounding_whitespace(comfy_root, loras_dir, triggers_file, routes):
    make_lora_file(loras_dir, "my-lora.safetensors")

    call_route(
        routes["/lora_triggers_save"],
        {"lora_name": "my-lora.safetensors", "all_triggers": "  one, two  ", "active_triggers": " one "},
    )

    entry = read_json(triggers_file)["my-lora"]
    assert entry["all_triggers"] == "one, two"
    assert entry["active_triggers"] == "one"


def test_save_preserves_fields_added_by_other_tools(comfy_root, loras_dir, triggers_file, routes):
    make_lora_file(loras_dir, "my-lora.safetensors")
    write_json(triggers_file, {"my-lora": {"all_triggers": "old", "notes": "keep me"}})

    call_route(
        routes["/lora_triggers_save"],
        {"lora_name": "my-lora.safetensors", "all_triggers": "new", "active_triggers": ""},
    )

    entry = read_json(triggers_file)["my-lora"]
    assert entry["notes"] == "keep me"
    assert entry["all_triggers"] == "new"


def test_save_converts_a_legacy_string_entry(comfy_root, loras_dir, triggers_file, routes):
    make_lora_file(loras_dir, "my-lora.safetensors")
    write_json(triggers_file, {"my-lora": "legacy triggers"})

    call_route(
        routes["/lora_triggers_save"],
        {"lora_name": "my-lora.safetensors", "all_triggers": "new", "active_triggers": "n"},
    )

    entry = read_json(triggers_file)["my-lora"]
    assert isinstance(entry, dict)
    assert entry["all_triggers"] == "new"


def test_save_leaves_other_entries_alone(comfy_root, loras_dir, triggers_file, routes):
    make_lora_file(loras_dir, "my-lora.safetensors")
    write_json(triggers_file, {"other": {"all_triggers": "untouched", "file_id": "xyz"}})

    call_route(
        routes["/lora_triggers_save"],
        {"lora_name": "my-lora.safetensors", "all_triggers": "new", "active_triggers": ""},
    )

    db = read_json(triggers_file)
    assert db["other"] == {"all_triggers": "untouched", "file_id": "xyz"}


def test_save_without_a_file_still_records_triggers(comfy_root, triggers_file, routes):
    """The LoRa may not be on disk; the entry is written without a file_id."""
    _status, body = call_route(
        routes["/lora_triggers_save"],
        {"lora_name": "ghost.safetensors", "all_triggers": "one", "active_triggers": ""},
    )

    assert body["success"] is True
    assert "file_id" not in read_json(triggers_file)["ghost"]


def test_save_rejects_empty_triggers(comfy_root, loras_dir, triggers_file, routes):
    make_lora_file(loras_dir, "my-lora.safetensors")

    _status, body = call_route(
        routes["/lora_triggers_save"],
        {"lora_name": "my-lora.safetensors", "all_triggers": "   ", "active_triggers": ""},
    )

    assert body["success"] is False
    assert not triggers_file.exists()


def test_save_rejects_a_missing_lora_name(comfy_root, routes):
    _status, body = call_route(routes["/lora_triggers_save"], {"all_triggers": "one"})

    assert body["success"] is False


# --------------------------------------------------------------------------
# /lora_triggers
# --------------------------------------------------------------------------

def test_load_returns_stored_triggers(comfy_root, loras_dir, triggers_file, routes):
    make_lora_file(loras_dir, "my-lora.safetensors")
    write_json(
        triggers_file,
        {"my-lora": {"all_triggers": "one, two", "active_triggers": "one", "file_id": "stale"}},
    )

    _status, body = call_route(routes["/lora_triggers"], {"lora_name": "my-lora.safetensors"})

    assert body == {"all_triggers": "one, two", "active_triggers": "one"}


def test_load_requires_a_lora_name(comfy_root, routes):
    _status, body = call_route(routes["/lora_triggers"], {"lora_name": ""})

    assert body == {"all_triggers": "", "active_triggers": ""}


def test_load_of_an_unknown_lora_is_empty(comfy_root, loras_dir, triggers_file, routes):
    make_lora_file(loras_dir, "my-lora.safetensors")
    write_json(triggers_file, {"other": {"all_triggers": "x", "file_id": "zzz"}})

    _status, body = call_route(routes["/lora_triggers"], {"lora_name": "my-lora.safetensors"})

    assert body == {"all_triggers": "", "active_triggers": ""}


def test_load_without_a_database_is_empty(comfy_root, loras_dir, routes):
    make_lora_file(loras_dir, "my-lora.safetensors")

    _status, body = call_route(routes["/lora_triggers"], {"lora_name": "my-lora.safetensors"})

    assert body == {"all_triggers": "", "active_triggers": ""}


def test_load_migrates_a_legacy_string_entry(comfy_root, loras_dir, triggers_file, routes):
    make_lora_file(loras_dir, "my-lora.safetensors")
    write_json(triggers_file, {"my-lora": "legacy triggers"})

    _status, body = call_route(routes["/lora_triggers"], {"lora_name": "my-lora.safetensors"})

    assert body["all_triggers"] == "legacy triggers"
    assert body["active_triggers"] == ""
    entry = read_json(triggers_file)["my-lora"]
    assert entry["all_triggers"] == "legacy triggers"
    assert entry["active_triggers"] == ""


def test_load_backfills_the_file_id_of_an_existing_file(
    comfy_root, loras_dir, triggers_file, routes
):
    lora = make_lora_file(loras_dir, "my-lora.safetensors")
    write_json(triggers_file, {"my-lora": {"all_triggers": "one", "active_triggers": ""}})

    call_route(routes["/lora_triggers"], {"lora_name": "my-lora.safetensors"})

    assert read_json(triggers_file)["my-lora"]["file_id"] == get_file_id(lora)


def test_load_marks_a_missing_file_as_unknown(comfy_root, loras_dir, triggers_file, routes):
    make_lora_file(loras_dir, "present.safetensors")
    write_json(
        triggers_file,
        {"deleted-lora": {"all_triggers": "one", "active_triggers": ""}},
    )

    call_route(routes["/lora_triggers"], {"lora_name": "present.safetensors"})

    assert read_json(triggers_file)["deleted-lora"]["file_id"] == "unknown"


def test_migration_backfills_every_entry_not_just_the_requested_one(
    comfy_root, loras_dir, triggers_file, routes
):
    make_lora_file(loras_dir, "a.safetensors", b"content-a")
    b = make_lora_file(loras_dir, "flux/b.safetensors", b"content-b")
    write_json(
        triggers_file,
        {
            "a": {"all_triggers": "one", "active_triggers": ""},
            "flux/b": {"all_triggers": "two", "active_triggers": ""},
        },
    )

    call_route(routes["/lora_triggers"], {"lora_name": "a.safetensors"})

    assert read_json(triggers_file)["flux/b"]["file_id"] == get_file_id(b)


def test_migration_leaves_existing_file_ids_alone(comfy_root, loras_dir, triggers_file, routes):
    make_lora_file(loras_dir, "my-lora.safetensors")
    write_json(
        triggers_file,
        {"my-lora": {"all_triggers": "one", "active_triggers": "", "file_id": "handmade"}},
    )

    call_route(routes["/lora_triggers"], {"lora_name": "my-lora.safetensors"})

    assert read_json(triggers_file)["my-lora"]["file_id"] == "handmade"


def test_load_finds_a_moved_lora_by_content(comfy_root, loras_dir, triggers_file, routes):
    """The file moved to a new folder; the same bytes must still find its triggers."""
    moved = make_lora_file(loras_dir, "flux/new-home/my-lora.safetensors", b"same bytes")
    write_json(
        triggers_file,
        {
            "old-home/my-lora": {
                "all_triggers": "one, two",
                "active_triggers": "one",
                "file_id": get_file_id(moved),
            }
        },
    )

    _status, body = call_route(
        routes["/lora_triggers"], {"lora_name": "flux/new-home/my-lora.safetensors"}
    )

    assert body == {"all_triggers": "one, two", "active_triggers": "one"}


def test_load_rewrites_the_key_of_a_moved_lora(comfy_root, loras_dir, triggers_file, routes):
    moved = make_lora_file(loras_dir, "flux/new-home/my-lora.safetensors", b"same bytes")
    write_json(
        triggers_file,
        {"old-home/my-lora": {"all_triggers": "one", "file_id": get_file_id(moved)}},
    )

    call_route(routes["/lora_triggers"], {"lora_name": "flux/new-home/my-lora.safetensors"})

    db = read_json(triggers_file)
    assert "old-home/my-lora" not in db
    assert db["flux/new-home/my-lora"]["all_triggers"] == "one"


def test_load_of_a_renamed_lora_finds_it_by_content(comfy_root, loras_dir, triggers_file, routes):
    renamed = make_lora_file(loras_dir, "better-name.safetensors", b"same bytes")
    write_json(
        triggers_file,
        {"old-name": {"all_triggers": "one", "active_triggers": "", "file_id": get_file_id(renamed)}},
    )

    _status, body = call_route(routes["/lora_triggers"], {"lora_name": "better-name.safetensors"})

    assert body["all_triggers"] == "one"
    assert "better-name" in read_json(triggers_file)


def test_load_does_not_rewrite_the_key_when_the_path_is_unchanged(
    comfy_root, loras_dir, triggers_file, routes
):
    lora = make_lora_file(loras_dir, "my-lora.safetensors")
    write_json(triggers_file, {"my-lora": {"all_triggers": "one", "file_id": get_file_id(lora)}})

    call_route(routes["/lora_triggers"], {"lora_name": "my-lora.safetensors"})

    assert list(read_json(triggers_file)) == ["my-lora"]


def test_load_falls_back_to_path_when_the_file_is_absent(comfy_root, triggers_file, routes):
    """No file on disk means no file_id, so the path lookup must still work."""
    write_json(triggers_file, {"ghost": {"all_triggers": "one", "active_triggers": "", "file_id": "unknown"}})

    _status, body = call_route(routes["/lora_triggers"], {"lora_name": "ghost.safetensors"})

    assert body["all_triggers"] == "one"


def test_load_matches_a_key_stored_with_backslashes(comfy_root, loras_dir, triggers_file, routes):
    make_lora_file(loras_dir, "flux/my-lora.safetensors")
    write_json(
        triggers_file,
        {"flux\\my-lora": {"all_triggers": "one", "active_triggers": "", "file_id": "unknown"}},
    )

    _status, body = call_route(routes["/lora_triggers"], {"lora_name": "flux/my-lora.safetensors"})

    assert body["all_triggers"] == "one"


def test_load_reports_a_bad_request_body(comfy_root, routes):
    status, body = call_route(routes["/lora_triggers"], raise_on_json=ValueError("bad body"))

    assert status == 500
    assert body == {"all_triggers": "", "active_triggers": ""}


def test_load_survives_a_corrupt_database(comfy_root, loras_dir, triggers_file, routes):
    make_lora_file(loras_dir, "my-lora.safetensors")
    triggers_file.parent.mkdir(parents=True, exist_ok=True)
    triggers_file.write_text("{not json", encoding="utf-8")

    _status, body = call_route(routes["/lora_triggers"], {"lora_name": "my-lora.safetensors"})

    assert body == {"all_triggers": "", "active_triggers": ""}


def test_save_then_load_round_trips(comfy_root, loras_dir, routes):
    make_lora_file(loras_dir, "flux/my-lora.safetensors")

    call_route(
        routes["/lora_triggers_save"],
        {
            "lora_name": "flux/my-lora.safetensors",
            "all_triggers": "one, two, three",
            "active_triggers": "two",
        },
    )
    _status, body = call_route(
        routes["/lora_triggers"], {"lora_name": "flux/my-lora.safetensors"}
    )

    assert body == {"all_triggers": "one, two, three", "active_triggers": "two"}


# --------------------------------------------------------------------------
# /lora_metadata
# --------------------------------------------------------------------------

def test_metadata_route_requires_a_lora_name(comfy_root, routes):
    _status, body = call_route(routes["/lora_metadata"], {"lora_name": ""})

    assert body["success"] is False


def test_metadata_route_reports_failure_for_a_missing_lora(comfy_root, routes):
    _status, body = call_route(routes["/lora_metadata"], {"lora_name": "ghost.safetensors"})

    assert body["success"] is False


def test_metadata_route_reports_failure_when_there_is_no_metadata(
    comfy_root, loras_dir, routes
):
    make_lora_file(loras_dir, "plain.ckpt")

    _status, body = call_route(routes["/lora_metadata"], {"lora_name": "plain.ckpt"})

    assert body["success"] is False
    assert "metadata" in body["message"].lower()


def test_metadata_route_cleans_and_deduplicates(comfy_root, loras_dir, routes, monkeypatch):
    """Extraction is exercised through the route with metadata reading stubbed out."""
    make_lora_file(loras_dir, "my-lora.safetensors")
    module = routes["/lora_metadata"].__globals__
    monkeypatch.setitem(
        module,
        "read_lora_metadata",
        lambda path: {"ss_tag_frequency": {"1_girl": 4, "girl": 2, "img": 1, "2_smile": 3}},
    )

    _status, body = call_route(routes["/lora_metadata"], {"lora_name": "my-lora.safetensors"})

    assert body["success"] is True
    assert body["all_triggers"] == "girl, smile"       # deduplicated, 'img' filtered
    assert body["active_triggers"] == body["all_triggers"]


def test_metadata_route_reports_failure_when_everything_is_filtered_out(
    comfy_root, loras_dir, routes, monkeypatch
):
    make_lora_file(loras_dir, "my-lora.safetensors")
    module = routes["/lora_metadata"].__globals__
    monkeypatch.setitem(
        module, "read_lora_metadata", lambda path: {"trained_words": ["img", "image_dir"]}
    )

    _status, body = call_route(routes["/lora_metadata"], {"lora_name": "my-lora.safetensors"})

    assert body["success"] is False
