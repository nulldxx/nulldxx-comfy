# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

A ComfyUI custom node pack combining prompt database management with LoRa trigger word storage. It
provides three nodes:

- **PromptDB** ("Prompt Database", category `text`) — single prompt editor backed by a category/prompt JSON database
- **PromptStack** ("Prompt Stack", category `text`) — stacks multiple database prompts into one output string
- **LoRaLoaderWithTriggerDB** ("LoRa Loader with Trigger DB", category `loaders`) — loads a LoRa and persists its trigger words

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
- `PromptStack.stack_prompts()`: scans `**kwargs` for `prompt_N_category` keys, resolves each enabled entry against `prompts.json`, and joins the results with `separator`

**API Endpoints** (`nodes/prompt_db.py`, served via ComfyUI's aiohttp server):
- `/prompt_db_categories` (POST): list categories
- `/prompt_db_prompts` (POST): list prompt names in a category
- `/prompt_db_text` (POST): fetch a prompt's text
- `/prompt_db_save` (POST): create/update a prompt
- `/prompt_db_create` (POST): create a new category and/or empty prompt

**JavaScript** (`web/prompt_db.js`, `web/prompt_stack.js`): register extensions `PromptDB` and
`PromptStack`, hook `beforeRegisterNodeDef`, and keep dropdowns in sync with the database. Prompt
Stack also handles add/remove of entries and restoring them from a saved workflow.

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
1. **File ID-based lookup (primary)**: If the LoRa file has a `file_id` in the database, lookup uses content-based matching (survives file moves/renames)
   - **Path correction**: If found by file_id but the path has changed (file was moved), the database key is automatically updated to the new path
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
- Falls back to `torch.load()` for PyTorch checkpoint files
- Looks for common metadata keys used by Kohya and other training tools
- Cleans extracted words (removes dataset artifacts like `1_girl` → `girl`)

### Path Handling
- Use `folder_paths.get_folder_paths("loras")` to get LoRa directory
- Use `folder_paths.get_full_path("loras", filename)` to resolve full path
- Always normalize paths with forward slashes for database keys
- Handle subfolders properly (LoRa files can be in nested directories)
- Never re-implement user-db path resolution — import `get_user_db_path` from `common/user_db.py`

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

Since these are ComfyUI custom nodes, testing requires a running ComfyUI instance. Outside ComfyUI
only syntax checks are possible — `folder_paths`, `comfy.sd` and `server` don't exist:

```bash
python -m compileall -q nodes common __init__.py
node --check web/prompt_db.js
```

In ComfyUI:

1. Install (or symlink) the pack in ComfyUI's `custom_nodes` directory
2. Restart ComfyUI server
3. Verify all three nodes appear: "Prompt Database" and "Prompt Stack" under *text*, "LoRa Loader with Trigger DB" under *loaders*
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
