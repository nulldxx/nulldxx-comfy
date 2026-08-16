from .nodes.prompt_db import PromptDB
from .nodes.prompt_stack import PromptStack
from .nodes.lora_loader_with_triggerdb import LoRaLoaderWithTriggerDB

NODE_CLASS_MAPPINGS = {
    "PromptDB": PromptDB,
    "PromptStack": PromptStack,
    "LoRaLoaderWithTriggerDB": LoRaLoaderWithTriggerDB
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PromptDB": "Prompt Database",
    "PromptStack": "Prompt Stack",
    "LoRaLoaderWithTriggerDB": "LoRa Loader with Trigger DB"
}

# Web directory for ComfyUI to serve JavaScript files
WEB_DIRECTORY = "./web"

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']
