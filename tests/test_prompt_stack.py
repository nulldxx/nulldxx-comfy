"""Tests for the PromptStack node and its dynamic-input plumbing."""
import pytest

from comfy_stubs import read_json, write_json
from nulldxx_comfy.nodes.prompt_db import DEFAULT_PROMPTS
from nulldxx_comfy.nodes.prompt_stack import (
    AnyType,
    FlexibleOptionalInputType,
    PromptStack,
    any_type,
)


@pytest.fixture
def prompts_file(user_db):
    return user_db / "prompts.json"


@pytest.fixture
def stack(comfy_root, prompts_file):
    """A PromptStack backed by a small, predictable database."""
    write_json(
        prompts_file,
        {
            "poses": {"sitting": "person sitting", "standing": "person standing"},
            "styles": {"cinematic": "cinematic lighting"},
        },
    )
    return PromptStack()


# --------------------------------------------------------------------------
# AnyType / FlexibleOptionalInputType
# --------------------------------------------------------------------------

def test_any_type_is_never_unequal():
    assert not (any_type != "MODEL")
    assert not (any_type != "STRING")
    assert not (any_type != 12345)


def test_any_type_is_still_a_string():
    assert isinstance(any_type, str)
    assert AnyType("*") == "*"


def test_flexible_input_claims_to_contain_everything():
    flexible = FlexibleOptionalInputType(any_type)

    assert "prompt_1_category" in flexible
    assert "anything_at_all" in flexible


def test_flexible_input_returns_the_declared_entry_when_present():
    flexible = FlexibleOptionalInputType(any_type, {"separator": ("STRING", {})})

    assert flexible["separator"] == ("STRING", {})


def test_flexible_input_falls_back_to_the_wildcard_type():
    flexible = FlexibleOptionalInputType(any_type, {"separator": ("STRING", {})})

    assert flexible["prompt_99_name"] == (any_type,)


def test_flexible_input_without_data_always_returns_the_wildcard():
    flexible = FlexibleOptionalInputType(any_type)

    assert flexible["whatever"] == (any_type,)


# --------------------------------------------------------------------------
# INPUT_TYPES
# --------------------------------------------------------------------------

def test_input_types_seeds_the_shared_database(comfy_root, prompts_file):
    PromptStack.INPUT_TYPES()

    assert read_json(prompts_file) == DEFAULT_PROMPTS


def test_input_types_declares_the_first_entry(comfy_root, prompts_file):
    write_json(prompts_file, {"poses": {"sitting": "person sitting"}})

    optional = PromptStack.INPUT_TYPES()["optional"]

    assert optional["prompt_1_category"][0] == ["poses"]
    assert optional["prompt_1_enabled"][1]["default"] is True


def test_input_types_falls_back_when_the_database_is_empty(comfy_root, prompts_file):
    write_json(prompts_file, {})

    optional = PromptStack.INPUT_TYPES()["optional"]

    assert optional["prompt_1_category"][0] == ["default"]
    assert optional["prompt_1_name"][0] == ["new prompt"]


def test_input_types_optional_block_accepts_dynamic_widgets(comfy_root):
    optional = PromptStack.INPUT_TYPES()["optional"]

    # ComfyUI validates submitted widgets against this mapping; it must accept
    # entries the frontend added after the node was registered.
    assert "prompt_7_category" in optional


# --------------------------------------------------------------------------
# stack_prompts
# --------------------------------------------------------------------------

def test_stacks_a_single_prompt(stack):
    result = stack.stack_prompts(
        prompt_1_category="poses", prompt_1_name="sitting", prompt_1_enabled=True
    )

    assert result == ("person sitting",)


def test_joins_multiple_prompts_with_the_separator(stack):
    result = stack.stack_prompts(
        separator=", ",
        prompt_1_category="poses",
        prompt_1_name="sitting",
        prompt_1_enabled=True,
        prompt_2_category="styles",
        prompt_2_name="cinematic",
        prompt_2_enabled=True,
    )

    assert result == ("person sitting, cinematic lighting",)


def test_honours_a_custom_separator(stack):
    result = stack.stack_prompts(
        separator=" | ",
        prompt_1_category="poses",
        prompt_1_name="sitting",
        prompt_1_enabled=True,
        prompt_2_category="styles",
        prompt_2_name="cinematic",
        prompt_2_enabled=True,
    )

    assert result == ("person sitting | cinematic lighting",)


def test_skips_disabled_entries(stack):
    result = stack.stack_prompts(
        prompt_1_category="poses",
        prompt_1_name="sitting",
        prompt_1_enabled=False,
        prompt_2_category="styles",
        prompt_2_name="cinematic",
        prompt_2_enabled=True,
    )

    assert result == ("cinematic lighting",)


def test_entries_are_ordered_numerically_not_lexically(stack):
    """prompt_10 must come after prompt_2, so indices are compared as integers."""
    result = stack.stack_prompts(
        prompt_10_category="styles",
        prompt_10_name="cinematic",
        prompt_10_enabled=True,
        prompt_2_category="poses",
        prompt_2_name="sitting",
        prompt_2_enabled=True,
    )

    assert result == ("person sitting, cinematic lighting",)


def test_gaps_in_the_indices_are_fine(stack):
    """Removing the middle entry in the UI leaves a hole in the numbering."""
    result = stack.stack_prompts(
        prompt_1_category="poses",
        prompt_1_name="sitting",
        prompt_1_enabled=True,
        prompt_5_category="styles",
        prompt_5_name="cinematic",
        prompt_5_enabled=True,
    )

    assert result == ("person sitting, cinematic lighting",)


def test_entries_default_to_enabled(stack):
    """A workflow saved before the enabled flag existed has no such kwarg."""
    result = stack.stack_prompts(prompt_1_category="poses", prompt_1_name="sitting")

    assert result == ("person sitting",)


def test_unknown_category_is_skipped(stack):
    result = stack.stack_prompts(
        prompt_1_category="deleted category",
        prompt_1_name="sitting",
        prompt_1_enabled=True,
        prompt_2_category="styles",
        prompt_2_name="cinematic",
        prompt_2_enabled=True,
    )

    assert result == ("cinematic lighting",)


def test_unknown_prompt_name_is_skipped(stack):
    result = stack.stack_prompts(
        prompt_1_category="poses", prompt_1_name="deleted", prompt_1_enabled=True
    )

    assert result == ("",)


def test_entry_with_no_category_is_skipped(stack):
    result = stack.stack_prompts(
        prompt_1_category="", prompt_1_name="sitting", prompt_1_enabled=True
    )

    assert result == ("",)


def test_malformed_widget_names_are_ignored(stack):
    """A non-numeric index must not raise - it is simply not an entry."""
    result = stack.stack_prompts(
        prompt_x_category="poses",
        prompt_x_name="sitting",
        prompt_1_category="poses",
        prompt_1_name="standing",
        prompt_1_enabled=True,
    )

    assert result == ("person standing",)


def test_no_entries_yields_an_empty_string(stack):
    assert stack.stack_prompts() == ("",)


def test_missing_database_yields_an_empty_string(comfy_root):
    node = PromptStack()
    node.prompts_file = str(comfy_root / "does-not-exist.json")

    result = node.stack_prompts(
        prompt_1_category="poses", prompt_1_name="sitting", prompt_1_enabled=True
    )

    assert result == ("",)


def test_corrupt_database_yields_an_empty_string(comfy_root, prompts_file):
    prompts_file.parent.mkdir(parents=True, exist_ok=True)
    prompts_file.write_text("{not json", encoding="utf-8")
    node = PromptStack()

    result = node.stack_prompts(
        prompt_1_category="poses", prompt_1_name="sitting", prompt_1_enabled=True
    )

    assert result == ("",)


def test_preview_text_is_not_part_of_the_output(stack):
    result = stack.stack_prompts(
        preview_text="ignore me",
        prompt_1_category="poses",
        prompt_1_name="sitting",
        prompt_1_enabled=True,
    )

    assert result == ("person sitting",)
