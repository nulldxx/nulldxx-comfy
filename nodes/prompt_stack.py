import os
import json
from ..common.user_db import get_user_db_path
from .prompt_db import DEFAULT_PROMPTS

class AnyType(str):
  """A special class that is always equal in not equal comparisons. Credit to pythongosssss"""

  def __ne__(self, __value: object) -> bool:
    return False

# Nicked from ggthree's FlexibleOptionalInputType
class FlexibleOptionalInputType(dict):
    def __init__(self, type, data: dict | None = None):
        self.type = type
        self.data = data
        if self.data is not None:
            for k, v in self.data.items():
                self[k] = v

    def __getitem__(self, key):
        if self.data is not None and key in self.data:
            val = self.data[key]
            return val
        return (self.type, )

    def __contains__(self, key):
        return True

any_type = AnyType("*")

class PromptStack:
    """A node that allows stacking multiple prompts from the database into a single output"""
    
    def __init__(self):
        self.user_db_path = get_user_db_path()
        self.prompts_file = os.path.join(self.user_db_path, "prompts.json")
        self.ensure_prompts_file()
    
    def ensure_prompts_file(self):
        """Create prompts.json file if it doesn't exist"""
        if not os.path.exists(self.prompts_file):
            try:
                os.makedirs(os.path.dirname(self.prompts_file), exist_ok=True)
                with open(self.prompts_file, 'w', encoding='utf-8') as f:
                    json.dump(DEFAULT_PROMPTS, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"Error creating prompts.json: {e}")

    @classmethod
    def INPUT_TYPES(cls):
        # Load categories and prompts from the database
        categories = []
        prompt_names = []
        
        try:
            user_db_path = get_user_db_path()
            prompts_file = os.path.join(user_db_path, "prompts.json")
            
            if not os.path.exists(prompts_file):
                try:
                    os.makedirs(os.path.dirname(prompts_file), exist_ok=True)
                    with open(prompts_file, 'w', encoding='utf-8') as f:
                        json.dump(DEFAULT_PROMPTS, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    print(f"Error creating prompts.json: {e}")
            
            if os.path.exists(prompts_file):
                with open(prompts_file, 'r', encoding='utf-8') as f:
                    prompts_db = json.load(f)
                    categories = list(prompts_db.keys())

                    # Get ALL prompt names from ALL categories for validation.
                    # Sorted, because set iteration order varies between
                    # processes and would reshuffle the dropdown - and with it
                    # the declared default - on every ComfyUI restart.
                    prompt_names_set = set()
                    for category in categories:
                        category_prompts = prompts_db.get(category, {})
                        prompt_names_set.update(category_prompts.keys())
                    prompt_names = sorted(prompt_names_set)

                    # The default has to be a prompt that exists in the default
                    # category, or a freshly added node resolves to nothing.
                    if categories:
                        first_category_prompts = list(prompts_db.get(categories[0], {}).keys())
                        if first_category_prompts and first_category_prompts[0] in prompt_names:
                            default_prompt = first_category_prompts[0]
                            prompt_names.remove(default_prompt)
                            prompt_names.insert(0, default_prompt)

        except Exception as e:
            print(f"Error loading categories for PromptStack INPUT_TYPES: {e}")
        
        # Ensure we have at least one category and prompt
        if not categories:
            categories = ["default"]
        if not prompt_names:
            prompt_names = ["new prompt"]
        
        return {
            "required": {
                "separator": ("STRING", {"default": ", ", "multiline": False}),
                "preview_text": ("STRING", {"multiline": True, "default": "Preview of stacked prompts will appear here..."}),
            },
            "optional": FlexibleOptionalInputType(any_type, {
                "prompt_1_category": (categories, {"default": categories[0]}),
                "prompt_1_name": (prompt_names, {"default": prompt_names[0] if prompt_names else ""}),
                "prompt_1_enabled": ("BOOLEAN", {"default": True}),
            }),
            "hidden": {},
        }
    
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("stacked_prompts",)
    FUNCTION = "stack_prompts"
    CATEGORY = "nulldxx"
    
    def stack_prompts(self, separator=", ", preview_text="", **kwargs):
        stacked_prompts = []
        prompts_db = {}
        db_error = None
        if os.path.exists(self.prompts_file):
            try:
                with open(self.prompts_file, 'r', encoding='utf-8') as f:
                    prompts_db = json.load(f)
            except Exception as e:
                # Do not swallow this: with an empty database every lookup
                # below returns "" and the workflow would quietly generate
                # against no prompt at all.
                db_error = e
                print(f"[PromptStack] Error reading {self.prompts_file}: {e}")
        else:
            print(f"[PromptStack] Prompt database not found: {self.prompts_file}")

        # Find all prompt entries by scanning for keys like prompt_N_category
        prompt_indices = set()
        for key in kwargs.keys():
            if key.startswith('prompt_') and key.endswith('_category'):
                try:
                    idx = int(key.split('_')[1])
                    prompt_indices.add(idx)
                except Exception:
                    continue
        enabled_entries = 0
        for idx in sorted(prompt_indices):
            cat = kwargs.get(f'prompt_{idx}_category', None)
            name = kwargs.get(f'prompt_{idx}_name', None)
            enabled = kwargs.get(f'prompt_{idx}_enabled', True)
            if enabled and cat and name:
                enabled_entries += 1
                prompt_text = prompts_db.get(cat, {}).get(name, "")
                if prompt_text:
                    stacked_prompts.append(prompt_text)
                else:
                    print(f"[PromptStack] Entry {idx}: no text for '{name}' in category '{cat}'")

        # An unreadable database plus entries to resolve means the output is
        # wrong rather than empty by choice - fail visibly in the UI instead of
        # handing the sampler a blank prompt.
        if db_error is not None and enabled_entries:
            raise RuntimeError(
                f"PromptStack could not read the prompt database "
                f"({self.prompts_file}): {db_error}"
            )

        result = separator.join(stacked_prompts)
        return (result,)
