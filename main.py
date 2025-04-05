import argparse
import logging
import sys
import os
from pathlib import Path
from typing import List, Dict, Any

# Keep path determination simple - only need script dir if loading adjacent modules
try:
    REAL_SCRIPT_FILE = os.path.realpath(__file__)
except NameError:
    REAL_SCRIPT_FILE = os.path.abspath(sys.argv[0])
SCRIPT_DIR = os.path.dirname(REAL_SCRIPT_FILE)
CURRENT_WORKDIR = os.getcwd() # Still useful for context perhaps

# Add SCRIPT_DIR to sys.path if needed for local imports (especially if not installed as package)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
    # No logging here yet, setup basicConfig first

# --- Import Config Manager EARLY ---
# It handles its own logging internally if needed during init
try:
    from app import config_manager
except ImportError as e:
     # Minimal logging before config is loaded
     sys.stderr.write(f"[CRITICAL] Failed to import config_manager: {e}\n")
     sys.stderr.write(f"Ensure app/config_manager.py exists relative to main.py.\n")
     sys.exit(1)


# --- Setup Logging ---
# Basic config first, might be reconfigured after loading config
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)] # Default to stdout
)
log = logging.getLogger() # Get root logger


# --- Now import other components ---
try:
    from app import app as toast_app_module
    from app import utils
    import openai
except ImportError as e:
    log.exception("Failed to import core application modules.")
    utils.eprint(f"[CRITICAL] Failed to import core app modules (app, utils, openai): {e}")
    utils.eprint("Ensure app/app.py, app/utils.py, etc., exist and required libraries (openai) are installed.")
    sys.exit(1)

def configure_logging(config: Dict[str, Any], verbose: bool):
    """Configures logging based on loaded config and CLI args."""
    cli_level = logging.DEBUG if verbose else logging.INFO
    config_level_str = config.get("log_level", "INFO").upper()
    config_level = getattr(logging, config_level_str, logging.INFO)

    # Use the more verbose level between CLI and config
    final_level = min(cli_level, config_level) # DEBUG < INFO

    log.setLevel(final_level)

    # Remove existing handlers (like the basicConfig one)
    for handler in log.handlers[:]:
        log.removeHandler(handler)

    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(final_level)
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    console_handler.setFormatter(formatter)
    log.addHandler(console_handler)

    # Add file handler if enabled in config
    if config.get("log_to_file", False):
        try:
            # Ensure log directory exists (usually same as config dir)
            config_manager.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(config_manager.LOG_FILE_PATH)
            file_handler.setLevel(final_level) # Log same level to file
            file_handler.setFormatter(formatter)
            log.addHandler(file_handler)
            log.info(f"Logging to file: {config_manager.LOG_FILE_PATH}")
        except Exception as e:
            log.error(f"Failed to set up file logging to {config_manager.LOG_FILE_PATH}: {e}", exc_info=True)
            utils.eprint(f"[ERROR] Could not configure file logging: {e}")

    log.info(f"Logging configured. Level set to: {logging.getLevelName(final_level)}")


def main(sys_args: List[str]):
    """
    Main function: Loads config, parses args, sets up logging & OpenAI, runs the app.
    """
    # --- Load Configuration ---
    try:
        config = config_manager.load_config()
    except SystemExit: # Propagate exit from config loading errors
        raise
    except Exception as e:
        log.exception("Critical error during configuration loading.")
        utils.eprint(f"[CRITICAL] Failed to load configuration: {e}")
        sys.exit(1)

    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(
        description="pixel-toaster: Natural language FFmpeg command generator.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("query", nargs="+", help="Your natural language prompt for FFmpeg.")
    parser.add_argument("--dry-run", action="store_true", help="Show generated command without executing.")
    parser.add_argument("--file", type=str, help="Specify input file explicitly.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose debug output (overrides config level).")
    # Add other args as needed

    args = parser.parse_args(sys_args)

    # --- Configure Logging (using loaded config and args) ---
    configure_logging(config, args.verbose)
    log.debug(f"Loaded configuration: {config}") # Log sensitive data only in debug
    log.debug(f"Parsed arguments: {args}")

    # --- Configure OpenAI Client ---
    api_key = config.get("openai_api_key")
    if not api_key:
        # This *shouldn't* happen if load_config/initialize_config worked, but double-check.
        log.critical("OpenAI API Key is missing after configuration load. Exiting.")
        utils.eprint("[CRITICAL] OpenAI API Key not available. Please ensure setup completed correctly.")
        sys.exit(1)

    try:
        openai.api_key = api_key
        # Maybe add a check here if needed: e.g., list models (can be slow/costly)
        # openai.models.list()
        log.info("OpenAI library configured with API key.")
    except Exception as e:
        log.exception("Error configuring OpenAI library:")
        utils.eprint(f"[ERROR] Failed to configure OpenAI library: {e}")
        sys.exit(1)

    # --- Run the Core Application Logic ---
    log.info("Handing control to the application runner...")
    # Pass parsed args AND the loaded config to the app runner
    # **Note:** Passing the whole config dict is often simpler than cherry-picking.
    # The app runner can then access `config['llm_model']` etc. if needed.
    exit_code = toast_app_module.run_toast_app(args, config)
    log.info(f"Application runner finished with exit code {exit_code}.")
    return exit_code

# --- Script Execution Guard ---
if __name__ == "__main__":
    final_exit_code = 1 # Default to error
    try:
        final_exit_code = main(sys.argv[1:])
    except SystemExit as e:
        log.info(f"SystemExit caught with code: {e.code}")
        final_exit_code = e.code if isinstance(e.code, int) else 1
    except KeyboardInterrupt:
        utils.eprint("\n[INFO] Execution interrupted by user (Ctrl+C).")
        final_exit_code = 130
    except Exception as e:
        # Catch-all for unexpected errors *during main()* that weren't handled
        # Use root logger which should be configured by now
        log.exception("An unhandled exception occurred during main execution:")
        utils.eprint(f"[CRITICAL ERROR] An unexpected error occurred: {e}")
        final_exit_code = 1
    finally:
        log.info(f"Pixel Toaster exiting with final code: {final_exit_code}")
        logging.shutdown() # Ensure log handlers flush buffers
        sys.exit(final_exit_code)