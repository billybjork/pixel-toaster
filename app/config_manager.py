import os
import json
import logging
import getpass
from pathlib import Path
from typing import Dict, Any, Optional

# Follow XDG Base Directory Specification for user-specific config
# https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html
XDG_CONFIG_HOME = os.environ.get('XDG_CONFIG_HOME')
if XDG_CONFIG_HOME and os.path.isdir(XDG_CONFIG_HOME):
    CONFIG_DIR = Path(XDG_CONFIG_HOME) / "pixel-toaster"
else:
    # Default fallback: ~/.config/pixel-toaster
    CONFIG_DIR = Path.home() / ".config" / "pixel-toaster"

CONFIG_FILE_PATH = CONFIG_DIR / "config.json"
LOG_FILE_PATH = CONFIG_DIR / "toast.log" # Centralized log file location

DEFAULT_CONFIG = {
    "openai_api_key": None,
    "llm_model": "gpt-4o-mini", # Default model
    "log_level": "INFO",
    "log_to_file": True,
    # Add other future config options here with defaults
    # e.g., "default_output_dir": null, "command_history_limit": 50
}

log = logging.getLogger(__name__) # Use module-specific logger

def load_config() -> Dict[str, Any]:
    """
    Loads configuration from the JSON file. If the file doesn't exist
    or is invalid, it triggers the initialization process.
    Returns the loaded (or initialized) configuration dictionary.
    """
    if CONFIG_FILE_PATH.is_file():
        try:
            with open(CONFIG_FILE_PATH, 'r') as f:
                user_config = json.load(f)

            # Merge user config with defaults (user overrides defaults)
            config = DEFAULT_CONFIG.copy()
            config.update(user_config)

            # --- Validation ---
            if not config.get("openai_api_key"):
                log.warning(f"OpenAI API key missing in config file: {CONFIG_FILE_PATH}")
                print(f"[WARNING] OpenAI API key not found in {CONFIG_FILE_PATH}.")
                return initialize_config() # Re-initialize if key is missing

            log.info(f"Configuration loaded successfully from {CONFIG_FILE_PATH}")
            return config

        except json.JSONDecodeError:
            log.error(f"Invalid JSON format in config file: {CONFIG_FILE_PATH}", exc_info=True)
            print(f"[ERROR] Corrupted configuration file found at {CONFIG_FILE_PATH}.")
            print("Please fix or delete the file and run again.")
            # Optionally: backup the corrupted file before prompting initialization
            # shutil.move(CONFIG_FILE_PATH, f"{CONFIG_FILE_PATH}.corrupted_{int(time.time())}")
            # return initialize_config() # Or force exit
            raise SystemExit(1) # Exit if config is corrupted
        except Exception as e:
            log.error(f"Error loading config file {CONFIG_FILE_PATH}: {e}", exc_info=True)
            print(f"[ERROR] Could not read configuration file: {e}")
            raise SystemExit(1)
    else:
        log.info(f"Configuration file not found at {CONFIG_FILE_PATH}. Starting initialization.")
        return initialize_config()

def initialize_config() -> Dict[str, Any]:
    """
    Guides the user through the first-time setup process,
    collects necessary information (like API key), and saves it.
    Returns the newly created configuration dictionary.
    """
    print("--- Pixel Toaster First-Time Setup ---")
    print(f"Configuration will be saved to: {CONFIG_FILE_PATH}")

    api_key = None
    while not api_key:
        # Use getpass for secure input (doesn't echo to terminal)
        api_key = getpass.getpass("Please enter your OpenAI API Key (starts with 'sk-'): ")
        if not api_key.startswith("sk-") or len(api_key) < 50: # Basic validation
            print("[ERROR] Invalid API Key format. Please ensure it starts with 'sk-' and is complete.")
            api_key = None # Force retry

    # Create the config dictionary
    new_config = DEFAULT_CONFIG.copy()
    new_config["openai_api_key"] = api_key
    # Could add prompts for other defaults here if needed (e.g., preferred model)

    try:
        # Ensure the directory exists
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        log.info(f"Created configuration directory: {CONFIG_DIR}")
    except OSError as e:
        log.error(f"Failed to create configuration directory {CONFIG_DIR}: {e}", exc_info=True)
        print(f"[ERROR] Could not create configuration directory: {e}")
        raise SystemExit(1)

    try:
        # Save the configuration file
        with open(CONFIG_FILE_PATH, 'w') as f:
            json.dump(new_config, f, indent=4)
        # Secure the file permissions (optional but recommended for files with secrets)
        # os.chmod(CONFIG_FILE_PATH, 0o600) # Read/write only for owner
        log.info(f"Configuration saved successfully to {CONFIG_FILE_PATH}")
        print("Configuration saved successfully.")
        return new_config
    except IOError as e:
        log.error(f"Failed to save configuration file {CONFIG_FILE_PATH}: {e}", exc_info=True)
        print(f"[ERROR] Could not write configuration file: {e}")
        raise SystemExit(1)

def get_config_value(key: str, default: Optional[Any] = None) -> Any:
    """Helper function to safely get a value from the loaded config."""
    # This assumes config is loaded once at startup.
    # For more dynamic needs, you might reload or pass the config dict around.
    try:
        config = load_config() # Simple approach: load each time needed (cached if module loaded)
        return config.get(key, default)
    except Exception:
        log.error(f"Failed to load config to get key '{key}'. Returning default.")
        return default
