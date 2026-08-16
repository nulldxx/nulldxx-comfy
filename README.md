# nulldxx ComfyUI Nodes

A ComfyUI custom node pack for database-driven prompt and LoRa trigger-word management. Store and
organise reusable prompts in categories, stack them into a final prompt, and keep per-LoRa trigger
words that persist between sessions.

The three nodes are designed to work together: the LoRa loader emits the trigger words for the LoRa
you've selected, and **Prompt Stack** (or any prompt combiner, such as **CR Combine Prompt**) merges
them with prompt fragments from your database.

| Node | Category | Purpose |
|---|---|---|
| **Prompt Database** | `text` | Single prompt editor with category/prompt selection |
| **Prompt Stack** | `text` | Stack multiple prompts from different categories into one output |
| **LoRa Loader with Trigger DB** | `loaders` | LoRa loader with persistent trigger word storage |

All data lives in `user/default/user-db/` inside your ComfyUI directory — `prompts.json` for the
prompt nodes and `lora-triggers.json` for the LoRa loader.

## Installation

### Method 1: ComfyUI Manager (Recommended)
1. Install via ComfyUI Manager using this Git URL:
   ```
   https://github.com/nulldxx/nulldxx-comfy.git
   ```

### Method 2: Manual Installation
1. Clone into your ComfyUI custom_nodes folder:
   ```bash
   cd ComfyUI/custom_nodes
   git clone https://github.com/nulldxx/nulldxx-comfy.git
   ```
2. Restart ComfyUI

## Prompt Database

<img width="1048" height="927" alt="image" src="https://github.com/user-attachments/assets/2a7cd75b-024e-47c7-99a3-be0944e8c3ab" />

### Features

- **Category-based Organization**: Organize prompts into logical categories
- **Dropdown Selection**: Easy category and prompt selection via dropdown menus
- **Editable Prompts**: Edit prompt text directly in the node
- **Persistent Storage**: All prompts stored in `user/default/user-db/prompts.json`
- **Save/Load Functionality**: Save changes back to the database instantly
- **Create or Update Prompts**: Add new categories and prompts, or update existing ones
- **No Inputs Required**: Standalone text generation node

### Usage

1. Add the "Prompt Database" node from the "text" category
2. Select a category from the first dropdown menu
3. Select a prompt name from the second dropdown menu
4. The prompt text will automatically load in the text area
5. Edit the prompt text if desired
6. To add a new category or prompt, simply type a new category or prompt name in the text fields below the dropdowns
7. Click "💾 Save" to create a new category or prompt, or to update an existing one
8. Connect the output to other nodes that accept text input

#### How to Add or Update Prompts and Categories
- **To add a new category:** Enter a new category name in the "Add/Update Category" text field, enter a prompt name, and click "💾 Save". The new category and prompt will be created.
- **To add a new prompt to an existing category:** Select the category from the dropdown, enter a new prompt name in the "Add/Update Prompt Name" text field, and click "💾 Save".
- **To update an existing prompt:** Select the category and prompt from the dropdowns, edit the prompt text, and click "💾 Save".
- The text fields below the dropdowns always reflect the current selection, but you can overwrite them to create new entries.

### Node Details
**Inputs:** None - this is a standalone text generation node
**Outputs:** `prompt_text`: The selected/edited prompt text as a string

## Prompt Stack

The **Prompt Stack** node combines multiple prompts from different categories into a single output
string. This is useful for building complex prompt chains or modular prompt templates.

### Features
- **Multiple Prompt Entries**: Add as many prompt entries as you need, each with its own category and prompt selection.
- **Dynamic Dropdowns**: Category and prompt dropdowns are dynamically populated from your prompt database. If you add new categories or prompts, they will appear automatically.
- **Enable/Disable Entries**: Each prompt entry can be enabled or disabled individually.
- **Custom Separator**: Choose how prompts are joined (default is `, `).
- **Easy Add/Remove**: Use the ➕ button to add new entries and ❌ to remove them.
- **Automatic Restoration**: When loading a saved workflow, all prompt entries and their selections are restored, and dropdowns are updated to reflect the current database.

### Usage
1. Add the **Prompt Stack** node from the "text" category in ComfyUI.
2. For each prompt entry:
   - Toggle the enabled checkbox to include/exclude the prompt.
   - Select a category from the dropdown (populated from your database).
   - Select a prompt name from the dropdown (updates automatically when category changes).
3. Use the **➕ Add Prompt Entry** button to add more prompts to the stack.
4. Use the **❌ Remove Entry X** button to remove individual entries (except the first one).
5. Set the separator string (default is `, `) to control how prompts are joined.
6. The output will be all enabled prompts concatenated with the separator.
7. Connect the output to other nodes that accept text input.

### Example Output
If you have three enabled prompt entries with prompts:
- "masterpiece, best quality"
- "cinematic lighting, dramatic shadows"
- "person standing in portrait pose"

And your separator is `, `, the output will be:

```
masterpiece, best quality, cinematic lighting, dramatic shadows, person standing in portrait pose
```

### Node Details
**Inputs:** None - this is a standalone text generation node
**Outputs:** `stacked_prompts`: All enabled prompts concatenated with the separator as a string

#### Technical Details
- **Dropdowns**: Both category and prompt dropdowns are kept in sync with the database. When the node is loaded or categories/prompts change, dropdowns update automatically.
- **Persistence**: All prompt selections and enabled states are saved with the workflow and restored on load.
- **No Inputs Required**: The node is standalone and does not require any input connections.

## LoRa Loader with Trigger DB

Loads a LoRa and remembers its trigger words, so you don't have to. Connect its trigger outputs to
**Prompt Stack** or a prompt combiner such as **CR Combine Prompt** to build your final prompt.

LoRa loader with Trigger DB being used to apply triggers as part of a combination prompt with CR Combine Prompt:

![image](https://github.com/user-attachments/assets/e9a8fca0-e33c-4785-8b54-1c31f9b25518)

### Features

- **Dual Trigger Fields**: Separate "All Triggers" and "Active Triggers" text fields
- **Auto-loading**: Automatically loads saved triggers when selecting a LoRa
- **Load/Save Buttons**: Explicit buttons for loading and saving trigger words
- **Load Metadata Button**: Attempts to extract trigger words directly from the LoRa file's metadata (see below)
- **Persistent Database**: Stores trigger words in JSON format between sessions in `user/default/user-db/lora-triggers.json`
- **Stores all/active triggers**: Can be used to store all the triggers but also just the one you're currently using

### Usage

1. Add the "LoRa Loader with Trigger DB" node from the "loaders" category
2. Select a LoRa from the dropdown - triggers auto-load if fields are empty
3. Use "All Triggers" for comprehensive trigger words, "Active Triggers" for current selection
4. Click "📥 Load Triggers" to load saved data or "💾 Save Triggers" to save current data
5. Click "🔍 Load Metadata" to attempt to extract trigger words directly from the LoRa file's metadata
6. Connect outputs to your workflow

### Load Metadata Button

The **"🔍 Load Metadata"** button tries to automatically extract trigger words from the selected LoRa file's metadata. If the LoRa was trained with tools like Kohya or includes trigger word information in its metadata, this button will populate the "All Triggers" and "Active Triggers" fields with those words.

- **How it works:**
  - Reads the LoRa file's metadata and looks for common keys such as `trained_words`, `ss_tag_strings`, `ss_tag_frequency`, or any key containing "trigger" or "word".
  - Cleans and deduplicates the extracted words, then fills both trigger fields.
- **Limitations:**
  - This feature only works if the LoRa file actually contains trigger word metadata. Not all LoRas include this information—especially older or manually edited files.
  - If no trigger words are found, the fields will remain unchanged and a message will be logged.

### Node Details

**Inputs:**
- `model`: Base model to apply LoRa to
- `lora_name`: LoRa selection dropdown
- `strength_model`: LoRa strength value (-20.0 to 20.0)
- `all_triggers`: Text field for all available trigger words
- `active_triggers`: Text field for currently active trigger words

**Outputs:**
- `model`: Model with LoRa applied
- `all_triggers`: All triggers as string output
- `active_triggers`: Active triggers as string output

## Database Structure

### Prompts — `user/default/user-db/prompts.json`

```json
{
  "poses": {
    "posing with camera": "a person posing with a camera, professional photography pose, confident stance",
    "casual sitting": "person sitting casually, relaxed posture, natural lighting",
    "standing portrait": "person standing in portrait pose, direct eye contact, professional setting"
  },
  "styles": {
    "cinematic": "cinematic lighting, dramatic shadows, film grain, professional cinematography",
    "artistic": "artistic composition, creative lighting, expressive style, fine art photography",
    "minimalist": "clean composition, minimal background, simple elegant style"
  },
  "quality": {
    "high quality": "masterpiece, best quality, ultra detailed, 8k resolution, professional photography",
    "artistic quality": "artistic masterpiece, fine art, museum quality, exceptional detail",
    "photorealistic": "photorealistic, hyperrealistic, lifelike, professional photo quality"
  }
}
```

The file is seeded with the sample categories above (**poses**, **styles**, **quality**) on first
run. To create new categories or prompts, type a new category or prompt name in the text fields and
click "💾 Save". Alternately, you can edit the raw JSON file — most LLMs are excellent at adding
whole sections of JSON to this file given a good prompt. See `example_prompts.json` for the seed
content.

### LoRa triggers — `user/default/user-db/lora-triggers.json`

```json
{
  "lora_name": {
    "all_triggers": "masterpiece, best quality, detailed",
    "active_triggers": "masterpiece, best quality",
    "file_id": "abc123def456..."
  }
}
```

**Key Features:**
- **Content-based tracking**: Each LoRa is tracked by its file content ID, so triggers persist even if you rename or move the file
- **Automatic migration**: The database automatically handles older formats and adds file IDs when you save triggers
- **Cross-platform compatible**: Works consistently across Windows, Linux, and Mac

The database file is created automatically and handles migration from older formats.

## Acknowledgements

Prompt selection persistence across workflow tab switches was contributed upstream by
[garyw](https://github.com/clownvary).

## License

This project is licensed under the same license as specified in the LICENSE file.
