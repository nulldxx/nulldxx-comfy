"""
Shared user database path resolution for the node pack.

All nodes store their JSON databases under `{ComfyUI_root}/user/default/user-db/`,
so the logic for locating that directory lives here rather than being duplicated
per node module.
"""
import os
import folder_paths


def get_comfy_path():
    """Get the ComfyUI root directory with fallback methods"""
    try:
        # Method 1: Use folder_paths.base_path if available
        if hasattr(folder_paths, 'base_path'):
            return folder_paths.base_path

        # Method 2: Use checkpoints folder path
        checkpoint_paths = folder_paths.get_folder_paths("checkpoints")
        if checkpoint_paths:
            # Go up from models/checkpoints to the root
            checkpoint_path = checkpoint_paths[0]
            if "models" in checkpoint_path:
                return checkpoint_path.split("models")[0].rstrip(os.sep)

        # Method 3: Use output folder path
        output_paths = folder_paths.get_folder_paths("output")
        if output_paths:
            # Go up from output to the root
            output_path = output_paths[0]
            if "output" in output_path:
                return output_path.split("output")[0].rstrip(os.sep)

        # Method 4: Use current working directory as fallback
        return os.getcwd()
    except Exception as e:
        # If we can't determine the path, try to find the ComfyUI directory by going up
        current_dir = os.path.dirname(os.path.abspath(__file__))
        while current_dir != os.path.dirname(current_dir):  # Stop at root
            if os.path.exists(os.path.join(current_dir, "main.py")) and os.path.exists(os.path.join(current_dir, "comfy")):
                return current_dir
            current_dir = os.path.dirname(current_dir)
        return os.getcwd()


def get_user_db_path():
    """Get the user database directory"""
    try:
        comfy_path = get_comfy_path()
        user_db_path = os.path.join(comfy_path, "user", "default", "user-db")
        os.makedirs(user_db_path, exist_ok=True)
        return user_db_path
    except Exception as e:
        print(f"Error creating user database directory: {e}")
        # Legacy fallback: the LoRa trigger database used to live alongside the LoRas
        try:
            lora_paths = folder_paths.get_folder_paths("loras")
            if lora_paths:
                return lora_paths[0]
        except Exception:
            pass
        return get_comfy_path()  # fallback to root
