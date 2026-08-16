"""Contract tests for the pack itself: node registration and the web directory.

These guard the things that silently break workflows rather than raising errors -
a renamed node ID, a node whose FUNCTION points at nothing, or a JS file moved
into a subdirectory where its `../../scripts/app.js` import no longer resolves.
"""
import compileall
import json

import pytest

import nulldxx_comfy
from comfy_stubs import REPO_ROOT

EXPECTED_NODES = {
    "PromptDB": "Prompt Database",
    "PromptStack": "Prompt Stack",
    "LoRaLoaderWithTriggerDB": "LoRa Loader with Trigger DB",
}


def test_all_nodes_are_registered():
    assert set(nulldxx_comfy.NODE_CLASS_MAPPINGS) == set(EXPECTED_NODES)


def test_display_names_are_preserved():
    """Renaming these breaks workflows saved against the pre-merge packs."""
    assert nulldxx_comfy.NODE_DISPLAY_NAME_MAPPINGS == EXPECTED_NODES


def test_every_class_has_a_display_name():
    assert set(nulldxx_comfy.NODE_CLASS_MAPPINGS) == set(
        nulldxx_comfy.NODE_DISPLAY_NAME_MAPPINGS
    )


@pytest.mark.parametrize("node_id", sorted(EXPECTED_NODES))
def test_node_declares_the_comfyui_contract(node_id):
    cls = nulldxx_comfy.NODE_CLASS_MAPPINGS[node_id]

    assert hasattr(cls, "INPUT_TYPES")
    assert isinstance(cls.RETURN_TYPES, tuple)
    assert isinstance(cls.RETURN_NAMES, tuple)
    assert len(cls.RETURN_TYPES) == len(cls.RETURN_NAMES)
    assert isinstance(cls.CATEGORY, str) and cls.CATEGORY


@pytest.mark.parametrize("node_id", sorted(EXPECTED_NODES))
def test_function_attribute_names_a_real_method(node_id):
    cls = nulldxx_comfy.NODE_CLASS_MAPPINGS[node_id]

    assert callable(getattr(cls, cls.FUNCTION, None))


@pytest.mark.parametrize("node_id", sorted(nulldxx_comfy.NODE_CLASS_MAPPINGS))
def test_nodes_appear_in_the_packs_own_menu_folder(node_id):
    category = nulldxx_comfy.NODE_CLASS_MAPPINGS[node_id].CATEGORY

    assert category == "nulldxx" or category.startswith("nulldxx/")


def test_web_directory_is_declared():
    assert nulldxx_comfy.WEB_DIRECTORY == "./web"
    assert (REPO_ROOT / "web").is_dir()


def test_web_directory_is_flat():
    """Nesting a JS file breaks its `../../scripts/app.js` import at runtime."""
    subdirs = [p.name for p in (REPO_ROOT / "web").iterdir() if p.is_dir()]

    assert subdirs == []


def test_every_registered_node_has_its_javascript():
    js_files = {p.name for p in (REPO_ROOT / "web").glob("*.js")}

    assert js_files == {
        "prompt_db.js",
        "prompt_stack.js",
        "lora_loader_with_triggerdb.js",
    }


def test_routes_are_registered_on_import(routes):
    """Routes register as an import side effect; a missing import loses the API."""
    expected = {
        "/prompt_db_categories",
        "/prompt_db_prompts",
        "/prompt_db_text",
        "/prompt_db_save",
        "/prompt_db_create",
        "/lora_triggers",
        "/lora_triggers_save",
        "/lora_metadata",
    }

    assert expected <= set(routes)


def test_example_prompts_matches_the_seed_database():
    """example_prompts.json documents what a fresh install writes to prompts.json."""
    from nulldxx_comfy.nodes.prompt_db import DEFAULT_PROMPTS

    example = json.loads((REPO_ROOT / "example_prompts.json").read_text(encoding="utf-8"))

    assert example == DEFAULT_PROMPTS


@pytest.mark.parametrize("source_dir", ["nodes", "common"])
def test_package_directories_compile(source_dir):
    """Cheap syntax check, mirroring the documented `compileall` smoke test."""
    assert compileall.compile_dir(str(REPO_ROOT / source_dir), quiet=2, force=True)
