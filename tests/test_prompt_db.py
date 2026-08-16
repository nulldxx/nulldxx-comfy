"""Tests for the PromptDB node and its /prompt_db_* routes."""
import pytest

from comfy_stubs import call_route, read_json, write_json
from nulldxx_comfy.nodes.prompt_db import DEFAULT_PROMPTS, PromptDB


@pytest.fixture
def prompts_file(user_db):
    return user_db / "prompts.json"


# --------------------------------------------------------------------------
# Seeding and INPUT_TYPES
# --------------------------------------------------------------------------

def test_constructor_seeds_the_database(comfy_root, prompts_file):
    PromptDB()

    assert read_json(prompts_file) == DEFAULT_PROMPTS


def test_constructor_does_not_overwrite_an_existing_database(comfy_root, prompts_file):
    write_json(prompts_file, {"mine": {"kept": "text"}})

    PromptDB()

    assert read_json(prompts_file) == {"mine": {"kept": "text"}}


def test_input_types_seeds_the_database(comfy_root, prompts_file):
    PromptDB.INPUT_TYPES()

    assert read_json(prompts_file) == DEFAULT_PROMPTS


def test_input_types_lists_categories(comfy_root, prompts_file):
    write_json(prompts_file, {"alpha": {"a": "A"}, "beta": {"b": "B"}})

    required = PromptDB.INPUT_TYPES()["required"]

    assert required["category"][0] == ["alpha", "beta"]
    assert required["category"][1]["default"] == "alpha"


def test_input_types_collects_prompt_names_from_every_category(comfy_root, prompts_file):
    write_json(prompts_file, {"alpha": {"a": "A"}, "beta": {"b": "B", "c": "C"}})

    names = PromptDB.INPUT_TYPES()["required"]["prompt_name"][0]

    assert sorted(names) == ["a", "b", "c"]


def test_default_prompt_is_the_first_prompt_of_the_first_category(comfy_root, prompts_file):
    write_json(prompts_file, {"zeta": {"zzz": "Z", "aaa": "A"}, "alpha": {"one": "1"}})

    required = PromptDB.INPUT_TYPES()["required"]

    # "zeta" is first by insertion order, and "zzz" is its first prompt, even
    # though the name list itself is sorted alphabetically.
    assert required["prompt_name"][1]["default"] == "zzz"
    assert required["prompt_name"][0][0] == "zzz"


def test_input_types_falls_back_when_the_database_is_empty(comfy_root, prompts_file):
    write_json(prompts_file, {})

    required = PromptDB.INPUT_TYPES()["required"]

    assert required["category"][0] == ["default"]
    assert required["prompt_name"][0] == ["new prompt"]


def test_input_types_survives_corrupt_json(comfy_root, prompts_file):
    prompts_file.parent.mkdir(parents=True, exist_ok=True)
    prompts_file.write_text("{not json", encoding="utf-8")

    required = PromptDB.INPUT_TYPES()["required"]

    assert required["category"][0] == ["default"]


def test_prompt_text_widget_is_multiline(comfy_root):
    required = PromptDB.INPUT_TYPES()["required"]

    assert required["prompt_text"][0] == "STRING"
    assert required["prompt_text"][1]["multiline"] is True


# --------------------------------------------------------------------------
# Node execution
# --------------------------------------------------------------------------

def test_get_prompt_passes_the_edited_text_through(comfy_root):
    node = PromptDB()

    assert node.get_prompt("styles", "cinematic", "edited text") == ("edited text",)


def test_get_prompt_ignores_the_database(comfy_root, prompts_file):
    """The node returns what the widget holds, not what is stored."""
    write_json(prompts_file, {"styles": {"cinematic": "stored text"}})
    node = PromptDB()

    assert node.get_prompt("styles", "cinematic", "widget text") == ("widget text",)


# --------------------------------------------------------------------------
# /prompt_db_categories
# --------------------------------------------------------------------------

def test_categories_route_lists_categories(comfy_root, prompts_file, routes):
    write_json(prompts_file, {"alpha": {}, "beta": {}})

    status, body = call_route(routes["/prompt_db_categories"])

    assert status == 200
    assert body["categories"] == ["alpha", "beta"]


def test_categories_route_returns_empty_without_a_database(comfy_root, routes):
    status, body = call_route(routes["/prompt_db_categories"])

    assert body["categories"] == []


# --------------------------------------------------------------------------
# /prompt_db_prompts
# --------------------------------------------------------------------------

def test_prompts_route_lists_a_category(comfy_root, prompts_file, routes):
    write_json(prompts_file, {"styles": {"a": "A", "b": "B"}, "other": {"c": "C"}})

    _status, body = call_route(routes["/prompt_db_prompts"], {"category": "styles"})

    assert body["prompts"] == ["a", "b"]


def test_prompts_route_returns_empty_for_an_unknown_category(comfy_root, prompts_file, routes):
    write_json(prompts_file, {"styles": {"a": "A"}})

    _status, body = call_route(routes["/prompt_db_prompts"], {"category": "missing"})

    assert body["prompts"] == []


def test_prompts_route_requires_a_category(comfy_root, routes):
    _status, body = call_route(routes["/prompt_db_prompts"], {})

    assert body["prompts"] == []


# --------------------------------------------------------------------------
# /prompt_db_text
# --------------------------------------------------------------------------

def test_text_route_returns_the_stored_prompt(comfy_root, prompts_file, routes):
    write_json(prompts_file, {"styles": {"cinematic": "dramatic shadows"}})

    _status, body = call_route(
        routes["/prompt_db_text"], {"category": "styles", "prompt_name": "cinematic"}
    )

    assert body["prompt_text"] == "dramatic shadows"


def test_text_route_returns_empty_for_an_unknown_prompt(comfy_root, prompts_file, routes):
    write_json(prompts_file, {"styles": {"cinematic": "dramatic shadows"}})

    _status, body = call_route(
        routes["/prompt_db_text"], {"category": "styles", "prompt_name": "missing"}
    )

    assert body["prompt_text"] == ""


def test_text_route_requires_both_arguments(comfy_root, routes):
    _status, body = call_route(routes["/prompt_db_text"], {"category": "styles"})

    assert body["prompt_text"] == ""


def test_text_route_reports_a_bad_request_body(comfy_root, routes):
    status, body = call_route(
        routes["/prompt_db_text"], raise_on_json=ValueError("bad body")
    )

    assert status == 500
    assert body["prompt_text"] == ""


# --------------------------------------------------------------------------
# /prompt_db_save
# --------------------------------------------------------------------------

def test_save_route_updates_an_existing_prompt(comfy_root, prompts_file, routes):
    write_json(prompts_file, {"styles": {"cinematic": "old"}})

    _status, body = call_route(
        routes["/prompt_db_save"],
        {"category": "styles", "prompt_name": "cinematic", "prompt_text": "new"},
    )

    assert body["success"] is True
    assert read_json(prompts_file)["styles"]["cinematic"] == "new"


def test_save_route_creates_a_missing_category(comfy_root, prompts_file, routes):
    write_json(prompts_file, {"styles": {"cinematic": "old"}})

    call_route(
        routes["/prompt_db_save"],
        {"category": "brand new", "prompt_name": "first", "prompt_text": "text"},
    )

    db = read_json(prompts_file)
    assert db["brand new"] == {"first": "text"}
    assert db["styles"] == {"cinematic": "old"}  # untouched


def test_save_route_creates_the_file_when_absent(comfy_root, prompts_file, routes):
    call_route(
        routes["/prompt_db_save"],
        {"category": "styles", "prompt_name": "cinematic", "prompt_text": "text"},
    )

    assert read_json(prompts_file) == {"styles": {"cinematic": "text"}}


def test_save_route_accepts_empty_text(comfy_root, prompts_file, routes):
    """Clearing a prompt is a legitimate edit."""
    write_json(prompts_file, {"styles": {"cinematic": "old"}})

    _status, body = call_route(
        routes["/prompt_db_save"],
        {"category": "styles", "prompt_name": "cinematic", "prompt_text": ""},
    )

    assert body["success"] is True
    assert read_json(prompts_file)["styles"]["cinematic"] == ""


def test_save_route_rejects_a_missing_name(comfy_root, routes):
    _status, body = call_route(
        routes["/prompt_db_save"], {"category": "styles", "prompt_text": "text"}
    )

    assert body["success"] is False


def test_save_route_preserves_unicode(comfy_root, prompts_file, routes):
    call_route(
        routes["/prompt_db_save"],
        {"category": "styles", "prompt_name": "emoji", "prompt_text": "a café 🎨"},
    )

    assert read_json(prompts_file)["styles"]["emoji"] == "a café 🎨"


# --------------------------------------------------------------------------
# /prompt_db_create
# --------------------------------------------------------------------------

def test_create_route_makes_an_empty_prompt(comfy_root, prompts_file, routes):
    _status, body = call_route(
        routes["/prompt_db_create"], {"category": "new cat", "prompt_name": "new one"}
    )

    assert body["success"] is True
    assert read_json(prompts_file)["new cat"]["new one"] == ""


def test_create_route_reports_a_new_category(comfy_root, routes):
    _status, body = call_route(
        routes["/prompt_db_create"], {"category": "new cat", "prompt_name": "p"}
    )

    assert "Created new category" in body["message"]


def test_create_route_reports_an_existing_category(comfy_root, prompts_file, routes):
    write_json(prompts_file, {"styles": {"a": "A"}})

    _status, body = call_route(
        routes["/prompt_db_create"], {"category": "styles", "prompt_name": "b"}
    )

    assert "existing category" in body["message"]
    assert read_json(prompts_file)["styles"] == {"a": "A", "b": ""}


def test_create_route_overwrites_an_existing_prompt_with_empty_text(
    comfy_root, prompts_file, routes
):
    """Known behaviour: creating over an existing name blanks it."""
    write_json(prompts_file, {"styles": {"a": "has text"}})

    call_route(routes["/prompt_db_create"], {"category": "styles", "prompt_name": "a"})

    assert read_json(prompts_file)["styles"]["a"] == ""


def test_create_route_requires_both_arguments(comfy_root, routes):
    _status, body = call_route(routes["/prompt_db_create"], {"category": "styles"})

    assert body["success"] is False
