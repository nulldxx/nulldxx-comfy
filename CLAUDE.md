# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

A ComfyUI custom node pack combining prompt database management with LoRa trigger word storage. It
provides three nodes:

- **PromptDB** ("Prompt Database", category `nulldxx`) — single prompt editor backed by a category/prompt JSON database
- **PromptStack** ("Prompt Stack", category `nulldxx`) — stacks multiple database prompts into one output string
- **LoRaLoaderWithTriggerDB** ("LoRa Loader with Trigger DB", category `nulldxx`) — loads a LoRa and persists its trigger words

The pack was formed by merging two previously separate repositories (`comfy-prompt-db` and
`comfy-lora-loader-with-triggerdb`). Node IDs and display names were preserved from both, so
workflows saved against the old packs continue to load.

## Layout

```
__init__.py                          # merged NODE_CLASS_MAPPINGS / NODE_DISPLAY_NAME_MAPPINGS, WEB_DIRECTORY
pyproject.toml                       # ComfyUI Registry metadata ([tool.comfy])
nodes/
  prompt_db.py                       # PromptDB node + /prompt_db_* API routes + DEFAULT_PROMPTS
  prompt_stack.py                    # PromptStack node
  lora_loader_with_triggerdb.py      # LoRaLoaderWithTriggerDB node + /lora_* API routes
common/
  user_db.py                         # get_comfy_path(), get_user_db_path() — shared by all nodes
  file_id.py                         # get_file_id(), get_file_id_safe()
  json_store.py                      # write_json_atomic() — every database save goes through this
web/                                 # FLAT — the JS imports "../../scripts/app.js"; nesting breaks it
  prompt_db.js
  prompt_stack.js
  lora_loader_with_triggerdb.js
  prompt_db.css                      # currently unused (no JS references these class names)
example_prompts.json                 # copy of the seed content written to prompts.json
```

Both databases live under `{ComfyUI_root}/user/default/user-db/`, resolved by
`common/user_db.py:get_user_db_path()`. `get_comfy_path()` tries, in order: `folder_paths.base_path`,
deriving the root from the checkpoints folder, deriving it from the output folder, then the cwd; on
exception it walks up from the module looking for `main.py` + `comfy/`. `get_user_db_path()` falls
back to the loras folder (the LoRa loader's legacy location) if the user-db directory can't be created.

## Architecture

### Prompt nodes

**`nodes/prompt_db.py`**:
- `DEFAULT_PROMPTS`: module-level seed database (poses/styles/quality), written to `prompts.json` on first run
- `PromptDB.INPUT_TYPES()`: reads `prompts.json` to build the category and prompt-name dropdowns; the default prompt is the first prompt of the first category
- `PromptDB.get_prompt()`: pass-through, returns the edited `prompt_text`

**`nodes/prompt_stack.py`**:
- `AnyType` / `FlexibleOptionalInputType`: allow an arbitrary number of dynamically added widgets (`prompt_N_category`, `prompt_N_name`, `prompt_N_enabled`)
- `PromptStack.stack_prompts()`: scans `**kwargs` for `prompt_N_category` keys, resolves each enabled entry against `prompts.json`, and joins the results with `separator`. If the database cannot be read and there is at least one enabled entry it raises, rather than handing the sampler a silently empty prompt

**API Endpoints** (`nodes/prompt_db.py`, served via ComfyUI's aiohttp server):
- `/prompt_db_categories` (POST): list categories
- `/prompt_db_prompts` (POST): list prompt names in a category
- `/prompt_db_text` (POST): fetch a prompt's text
- `/prompt_db_save` (POST): create/update a prompt
- `/prompt_db_create` (POST): create a new category and/or empty prompt

**JavaScript** (`web/prompt_db.js`, `web/prompt_stack.js`): register extensions `PromptDB` and
`PromptStack`, hook `beforeRegisterNodeDef`, and keep dropdowns in sync with the database. Prompt
Stack also handles add/remove of entries and restoring them from a saved workflow.

Three things in `web/prompt_stack.js` are load-bearing and easy to undo by accident:

- **Entry numbers are allocated as `max + 1` and compacted after a removal.** ComfyUI maps widgets to
  node inputs by name, so two widgets called `prompt_3_category` collapse into one and an entry
  disappears from the generated prompt. Never derive the next number from a count.
- **Widgets are identified by `w.name` or by the `_promptStackEntry` / `_promptStackControl` tags,
  never by `w.label`.** `addWidget(type, name, ...)` stores that caption as `name`; `label` is only
  set from `options.label`, so a filter on `label` silently matches nothing.
- **Entries are persisted in `node.properties.promptStack_entries`** (plus a legacy top-level copy
  read back for older workflows). `properties` is part of the node schema, so it survives workflow
  normalisation; `onSerialize(o)` must write into `o` because LiteGraph discards its return value.

### LoRa loader

**`nodes/lora_loader_with_triggerdb.py`**:
- `LoRaLoaderWithTriggerDB`: loads a LoRa and applies it to the base model
- `read_lora_metadata()`: reads metadata from `.safetensors`, `.pt`, or `.bin` LoRa files
- `extract_triggers_from_metadata()`: extracts trigger words from metadata keys like `ss_tag_frequency`, `ss_tag_strings`, `trained_words`
- `clean_trigger_word()`: cleans extracted triggers (removes leading numbers/underscores, filters unwanted words)
- `build_file_id_to_key_map()`: reverse map of `file_id` -> database key, used for content-based lookup

**API Endpoints**:
- `/lora_triggers` (POST): Load saved trigger words for a LoRa model
- `/lora_triggers_save` (POST): Save trigger words to the database
- `/lora_metadata` (POST): Extract trigger words from LoRa file metadata

**JavaScript** (`web/lora_loader_with_triggerdb.js`):
- Extends the node with custom widgets (buttons for Load Triggers, Load Metadata, Save Triggers)
- Auto-loads saved triggers when LoRa selection changes (with 500ms debounce)
- Handles widget callbacks to preserve ComfyUI's native filtering behavior

**File ID Utilities** (`common/file_id.py`):
- `get_file_id(filepath)`: Generates fast SHA1 hash ID for files by sampling first 1MB, last 1MB, and file size
- `get_file_id_safe(filepath, fallback)`: Safe wrapper with error handling that returns fallback on failure
- Designed for large LoRa files (multi-GB) to avoid reading entire file content

## Database Storage

### Prompts — `{ComfyUI_root}/user/default/user-db/prompts.json`

```json
{
  "category": {
    "prompt name": "prompt text"
  }
}
```

Created from `DEFAULT_PROMPTS` if missing. There is no versioning or migration for this file — the
schema has always been two levels of plain string mapping.

### LoRa triggers — `{ComfyUI_root}/user/default/user-db/lora-triggers.json`

**Schema** (Current):
```json
{
  "subfolder/lora_name": {
    "all_triggers": "comprehensive, list, of, triggers",
    "active_triggers": "subset, of, triggers",
    "file_id": "abc123def456..."
  }
}
```

**Legacy Formats** (Backward Compatible):
```json
{
  "old_model": "trigger words as string",
  "legacy_model": {
    "all_triggers": "triggers",
    "active_triggers": "triggers"
  }
}
```

**Lookup Strategy**:
0. **Exact path match wins**: two copies of the same LoRa share a `file_id`, so an entry keyed by the
   current path is always used in preference to a content match
1. **File ID-based lookup**: If the LoRa file has a `file_id` in the database, lookup uses content-based matching (survives file moves/renames)
   - **Path correction**: If found by file_id but the path has changed, the database key is updated
     to the new path — but only once the old path is confirmed gone. If that file still exists this
     is a duplicate rather than a move, and re-keying would delete the other copy's entry
2. **Path-based lookup (fallback)**: If no `file_id` is found, falls back to path matching with cross-platform normalization
3. **Auto-migration on save**: When triggers are saved, `file_id` is automatically added to the entry
4. **Global auto-migration on load**: When ANY LoRa is loaded, scans the entire database and upgrades ALL entries missing file_ids:
   - If the file exists: Calculates and adds the real `file_id`
   - If the file is missing: Marks the entry with `file_id: "unknown"`
   - Database is saved once after all migrations complete
   - Migration happens once, subsequent loads use the file_ids

**Cross-Platform Key Normalization**:
- All LoRa paths use forward slashes (`/`) for consistent key matching across Windows/Linux/Mac
- Database keys are relative paths from the LoRa folder (e.g., `flux/my-lora`, not absolute paths)
- Keys stored without file extensions (e.g., `subfolder/model` not `subfolder/model.safetensors`)
- Database lookup handles both exact matches and normalized path comparisons
- File IDs provide additional robustness against path changes
- When a LoRa is moved, the database key is automatically updated to match the new location

## Development Patterns

### Node Implementation
- ComfyUI nodes must define `INPUT_TYPES` classmethod and `RETURN_TYPES`/`RETURN_NAMES` class attributes
- The function name in `FUNCTION` attribute must match a method that processes inputs
- Widget additions in JavaScript use `this.addWidget(type, label, value, callback, options)`
- `{ serialize: false }` option prevents button state from being saved in workflows
- New nodes go in `nodes/`, shared helpers in `common/`, and must be registered in the root `__init__.py`

### API Integration
- Register routes via `@server.PromptServer.instance.routes.post(path)`
- Routes are registered at import time, so a node module must be imported from `__init__.py` for its API to exist
- Frontend uses `api.fetchApi(endpoint, options)` imported from ComfyUI's API module
- Keep route prefixes namespaced per node family (`/prompt_db_*`, `/lora_*`) to avoid collisions
- All LoRa database operations handle migration from old string format to new dict format with `all_triggers`/`active_triggers`

### Web assets
- `web/` must stay flat: every JS file imports `../../scripts/app.js`, which resolves correctly only
  at the top level of the web directory
- ComfyUI auto-loads `.js` files from `WEB_DIRECTORY`; CSS is not auto-loaded

### Metadata Extraction
- Supports `.safetensors` (preferred), `.pt`, and `.bin` formats
- Uses `safetensors.torch.safe_open()` for safetensors files
- Falls back to `torch.load(..., weights_only=True)` for PyTorch checkpoint files — a `.pt`/`.bin`
  LoRa is user-supplied data, and unpickling it would run whatever code it carries
- Looks for common metadata keys used by Kohya and other training tools
- Kohya's `ss_tag_frequency` is nested (`{dataset_dir: {tag: count}}`); `tags_from_frequency_dict()`
  flattens it, or the extracted "triggers" are dataset folder names
- Cleans extracted words (removes dataset artifacts like `1_girl` → `girl`)

### Path Handling
- Use `folder_paths.get_folder_paths("loras")` to get LoRa directory
- Use `folder_paths.get_full_path("loras", filename)` to resolve full path
- Always normalize paths with forward slashes for database keys
- Handle subfolders properly (LoRa files can be in nested directories)
- Never re-implement user-db path resolution — import `get_user_db_path` from `common/user_db.py`
- `folder_paths.get_full_path()` returns `None` when a file has been renamed or deleted since the
  workflow was saved, and `os.path.isfile(None)` raises `TypeError` — always guard the result

### Saving a database
- Write with `write_json_atomic()` from `common/json_store.py`, never `open(path, 'w')` — a reader
  (a queued PromptStack execution, another tab) can otherwise parse a half-written file

### File ID Generation
- Import with `from ..common.file_id import get_file_id, get_file_id_safe`
- File IDs are content-based hashes (SHA1 of size + first/last 1MB)
- Much faster than full file hashing for multi-GB LoRa files
- Potential use cases:
  - Alternative database keys (more stable than file paths)
  - Detecting duplicate LoRa files with different names
  - Tracking LoRa files across directory reorganizations
- Use `get_file_id_safe()` when you need graceful error handling

## Testing the Nodes

### Automated tests

```bash
pip install -r requirements-dev.txt
pytest tests/          # must be invoked with the tests/ path, see below
node --check web/prompt_db.js
```

`.github/workflows/tests.yml` runs the same on every push and pull request, across Python
3.10–3.13, plus a `node --check` of every file in `web/`.

**Layout:**

```
tests/
  pytest.ini           # config lives HERE, not in pyproject.toml (see below)
  comfy_stubs.py       # ComfyUI stand-ins + package loader + assertion helpers
  conftest.py          # fixtures only (comfy_root, user_db, loras_dir, routes)
  test_file_id.py      # content-sampling hash
  test_json_store.py   # atomic JSON writes
  test_user_db.py      # ComfyUI root resolution and its four fallbacks
  test_prompt_db.py    # PromptDB node + /prompt_db_* routes
  test_prompt_stack.py # AnyType, FlexibleOptionalInputType, stack_prompts()
  test_lora_triggerdb.py # trigger extraction/cleaning, DB migration, file_id lookup
  test_package.py      # node registration, route registration, flat web/ dir
```

**How the harness works** — `tests/comfy_stubs.py` installs fake `folder_paths`, `comfy.sd`,
`comfy.utils` and `server` modules into `sys.modules`, then loads the repo under the alias
`nulldxx_comfy` (the directory name has a hyphen, so it isn't importable directly). The `server`
stub's `routes.post()` decorator records handlers instead of registering them, so route handlers
can be invoked directly via `call_route()`. The `comfy_root` fixture points the stub at a tmp
directory, so the real `get_user_db_path()` runs and the databases land in throwaway files.

**Two gotchas:**
- Run `pytest tests/`, not bare `pytest`. The config is in `tests/pytest.ini` specifically so
  pytest's rootdir is `tests/`. With the repo root as rootdir, pytest sees the root `__init__.py`,
  treats the root as a package, and fails importing it (relative imports, no parent package).
  Moving the config into `pyproject.toml` reintroduces this.
- `tests/comfy_stubs.py` is deliberately not `conftest.py`, so it is imported exactly once as an
  ordinary module and the stub state is never duplicated.

What is *not* covered: real LoRa loading, aiohttp wire-level behaviour, and all the JavaScript
beyond a syntax check.

### Manual checks in ComfyUI

1. Install (or symlink) the pack in ComfyUI's `custom_nodes` directory
2. Restart ComfyUI server
3. Verify all three nodes appear under a single *nulldxx* folder in the node menu: "Prompt Database", "Prompt Stack" and "LoRa Loader with Trigger DB"
4. **Prompt Database**: dropdowns populate, selecting a prompt loads its text, 💾 Save writes to `prompts.json`
5. **Prompt Stack**: ➕ adds entries, preview updates, entries restore after a workflow reload
6. **LoRa Loader**: LoRa dropdown populates; buttons appear (📥 Load Triggers, 🔍 Load Metadata, 💾 Save Triggers); auto-loading works when switching LoRas; `lora-triggers.json` is created; metadata extraction works for files with embedded trigger words

## Key Implementation Details

### Auto-Loading Behavior (LoRa loader)
- Triggers auto-load when LoRa selection changes (both via dropdown change event and callback override)
- Dual approach ensures compatibility: DOM event listener + callback wrapper
- 500ms debounce prevents excessive API calls during typing/filtering
- Preserves ComfyUI's original filtering functionality by calling original callback first

### Database Migration (LoRa loader)
- Handles legacy format (string) → new format (dict with `all_triggers`/`active_triggers`)
- Migrates path separators to forward slashes for cross-platform compatibility
- Finds entries using normalized path matching even if stored with backslashes
- Automatically adds `file_id` to entries when triggers are saved
- File ID-based lookup uses `build_file_id_to_key_map()` helper to create reverse mapping
- Gracefully handles mixed database with entries both with and without file IDs
- Saving preserves unknown fields on an entry, so external tools can annotate the database

### Model Application
- Only applies LoRa to the model (not CLIP) via `comfy.sd.load_lora_for_models(model, None, lora, strength_model, 0)`
- Returns model with LoRa applied and passes through trigger strings unchanged
- Trigger strings are outputs for connecting to Prompt Stack or another prompt combiner node
