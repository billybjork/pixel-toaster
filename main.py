import argparse
import logging
import sys
import os
import shutil
from pathlib import Path
from typing import Optional, List
from dotenv import load_dotenv

# --- Determine paths ---
# Get the path of the script file, resolving symlinks
try:
    # Resolve symlinks to get the *actual* file path
    REAL_SCRIPT_FILE = os.path.realpath(__file__)
except NameError:
    # __file__ might not be defined if running interactively or packaged weirdly
    REAL_SCRIPT_FILE = os.path.abspath(sys.argv[0]) # Fallback using argv

# Directory of the real script file (main.py)
SCRIPT_DIR = os.path.dirname(REAL_SCRIPT_FILE)
# Current working directory when the script is invoked
CURRENT_WORKDIR = os.getcwd()
USER_HOME = Path.home()
# Standard XDG base dir location for config
USER_CONFIG_DIR = USER_HOME / ".config" / "toast"
USER_CONFIG_DOTENV = USER_CONFIG_DIR / ".env"
# Define .env path relative to the *real* script directory (main.py)
SCRIPT_DIR_DOTENV = Path(SCRIPT_DIR) / ".env"

# --- Setup Logging Early ---
# Use basicConfig for initial setup before main() is called
# Configure logging (important for seeing debug messages)
logging.basicConfig(
    level=logging.INFO, # Default to INFO
    format="[%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger() # Get root logger for potential level updates later
log.info(f"--- Initializing Toast ---")
log.debug(f"Real Script File: {REAL_SCRIPT_FILE}")
log.debug(f"Script Directory: {SCRIPT_DIR}")
log.debug(f"User Config Dir Target: {USER_CONFIG_DIR}")
log.debug(f"Script Dir .env Target: {SCRIPT_DIR_DOTENV}")

# --- Ensure modules in SCRIPT_DIR are importable ---
# This helps if the script is run directly from its directory or symlinked.
# If installed as a package, this might be less critical but doesn't hurt.
if SCRIPT_DIR not in sys.path:
     # NOTE: Adding SCRIPT_DIR might not be necessary if running main.py
     # from the root, as the 'app' package should be findable relative to main.py.
     # Keep it for now, but it could potentially be removed if imports work reliably without it.
     sys.path.insert(0, SCRIPT_DIR)
     log.debug(f"Inserted script directory into sys.path: {SCRIPT_DIR}")

# --- Import Core Application and Utilities AFTER sys.path adjustment ---
try:
    # Import the app module from the app package
    from app import app as toast_app_module
    # Import the utils module from the app package
    from app import utils
    # Import openai here, needed for configuration and specific error types
    import openai
    log.debug("Core application modules imported successfully.")
except ImportError as e:
    log.exception("Failed to import core application modules (app, utils, openai).")
    log.error(f"        Script Directory: {SCRIPT_DIR}")
    log.error(f"        Current sys.path: {sys.path}")
    # Updated Error Message:
    log.error(f"        Ensure app/app.py, app/utils.py, app/file_manager.py, app/command_generator.py, app/command_executor.py")
    log.error(f"        exist relative to main.py and that app/__init__.py exists.")
    log.error(f"        Also ensure 'openai' and 'python-dotenv' libraries are installed ('pip install openai python-dotenv').")
    sys.exit(1)


def setup_environment() -> Optional[str]:
    """
    Loads .env file with priority order and returns the loaded API key.
    Handles logging and user feedback for key loading.
    Returns the API key string if found, None otherwise.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    loaded_from = None
    dotenv_loaded = False # Track if any dotenv load succeeded

    # 1. Check Environment Variable FIRST
    if api_key:
        log.info("Found OPENAI_API_KEY in environment variables.")
        loaded_from = "Environment Variable"
    else:
        log.info("OPENAI_API_KEY not found in environment variables. Searching .env files...")
        # Define search paths for clarity
        search_paths = [
            ("User Config", USER_CONFIG_DOTENV),
            ("Script Dir", SCRIPT_DIR_DOTENV) # .env next to main.py
        ]
        os.environ['TOAST_DOTENV_USER_PATH'] = str(USER_CONFIG_DOTENV) # For logging context
        os.environ['TOAST_DOTENV_SCRIPT_PATH'] = str(SCRIPT_DIR_DOTENV) # For logging context

        for name, path in search_paths:
            log.info(f"Looking for .env file in {name}: {path}")
            if path.is_file():
                log.info(f"Found {name} .env file. Attempting to load.")
                try:
                    # Pass stream explicitly if verbose logging is needed from dotenv
                    dotenv_loaded = load_dotenv(
                        dotenv_path=path,
                        verbose=log.isEnabledFor(logging.DEBUG),
                        override=True # Let later files override earlier ones if needed (though we stop on first key find)
                    )
                    api_key = os.getenv("OPENAI_API_KEY") # Check again after loading
                    if api_key:
                         loaded_from = str(path)
                         log.info(f"Successfully loaded OPENAI_API_KEY from {name} .env file.")
                         break # Stop searching once key is found
                    elif dotenv_loaded:
                         log.warning(f"Loaded {path}, but OPENAI_API_KEY not found within it.")
                    else:
                         # load_dotenv() returns False if file is empty or parsing fails silently
                         log.warning(f"Found {path}, but load_dotenv() indicated no variables were loaded.")
                except Exception as e:
                    log.warning(f"Error loading {path}: {e}", exc_info=log.isEnabledFor(logging.DEBUG))
            else:
                 log.info(f"{name} .env file not found.")
            # If key found, no need to check further locations
            if api_key:
                break

    # --- Final Check for API Key ---
    if not api_key:
        # Print error using utility function (now imported from app.utils)
        utils.eprint(f"\n[ERROR] OPENAI_API_KEY could not be found.")
        utils.eprint(f"        Search Order:")
        utils.eprint(f"        1. Environment Variable 'OPENAI_API_KEY'")
        utils.eprint(f"        2. User Config File: {USER_CONFIG_DOTENV}")
        utils.eprint(f"        3. Script Directory File: {SCRIPT_DIR_DOTENV}")
        utils.eprint(f"\n        Recommendation: Set the OPENAI_API_KEY environment variable globally,")
        utils.eprint(f"        or create the user config directory ({USER_CONFIG_DIR})")
        utils.eprint(f"        and place your key in a .env file inside it (OPENAI_API_KEY=your_key_here).")
        return None # Indicate failure
    else:
        # Mask key for logging
        masked_key = api_key[:4] + "..." + api_key[-4:]
        log.info(f"OpenAI API Key loaded successfully (masked: {masked_key}) from: {loaded_from or 'Unknown Source'}")
        os.environ['TOAST_DOTENV_LOADED_FROM'] = loaded_from or "Not loaded via dotenv" # For app context logging
        return api_key # Return the found key

def main(sys_args: List[str]):
    """
    Main function: Parses arguments, sets up logging, runs the app.
    """
    parser = argparse.ArgumentParser(
        description="toast: Natural language FFmpeg command generator.",
        formatter_class=argparse.RawTextHelpFormatter # Preserve newlines in help
    )
    parser.add_argument("query", nargs="+", help="Your natural language prompt for FFmpeg.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the generated command without executing it."
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Specify an input file explicitly, overriding detection from the query."
    )
    parser.add_argument(
        "--verbose",
        "-v", # Add short flag
        action="store_true",
        help="Enable verbose debug output."
    )
    # TODO: Consider adding --version argument later
    # parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')

    args = parser.parse_args(sys_args)

    # --- Reconfigure Logging Level After Parsing Args ---
    log_level = logging.DEBUG if args.verbose else logging.INFO
    log.setLevel(log_level) # Update root logger level
    # Update handler level too if using specific handlers, basicConfig handles root.
    # For basicConfig, setting root logger level is usually sufficient.

    log.debug("Verbose logging enabled.")
    # Log context details again if verbose, now that level is set
    log.debug(f"(DEBUG) Real Script File: {REAL_SCRIPT_FILE}")
    log.debug(f"(DEBUG) Real Script Directory: {SCRIPT_DIR}")
    log.debug(f"(DEBUG) Current Working Directory: {CURRENT_WORKDIR}")
    log.debug(f"(DEBUG) User Config Dir target: {USER_CONFIG_DIR}")
    log.debug(f"(DEBUG) Dotenv search path 1 (User Config): {os.environ.get('TOAST_DOTENV_USER_PATH', 'N/A')}")
    log.debug(f"(DEBUG) Dotenv search path 2 (Script Dir): {os.environ.get('TOAST_DOTENV_SCRIPT_PATH', 'N/A')}")
    log.debug(f"(DEBUG) Dotenv loaded successfully from: {os.environ.get('TOAST_DOTENV_LOADED_FROM', 'Not loaded')}")
    log.debug(f"Parsed arguments: {args}")


    # --- Run the Core Application Logic ---
    # Pass the parsed args to the application runner function (imported from app.app)
    log.info("Handing control to the application runner...")
    # Updated Call:
    exit_code = toast_app_module.run_toast_app(args)
    log.info(f"Application runner finished with exit code {exit_code}.")
    return exit_code


# --- Script Execution Guard ---
if __name__ == "__main__":
    # --- Environment Setup (API Key Loading) ---
    loaded_api_key = setup_environment()

    if loaded_api_key is None:
        # Error message already printed by setup_environment
        sys.exit(1) # Exit if key is not found

    # --- Configure OpenAI Library ---
    try:
        # Set the API key for the openai library instance
        openai.api_key = loaded_api_key
        # Optionally, perform a lightweight test call or check configuration
        # e.g., openai.models.list() # Might be too slow/costly for startup
        log.info("OpenAI library configured with API key.")
    except Exception as e:
        # Catch potential errors during library configuration
        log.exception("Error configuring OpenAI library:")
        utils.eprint(f"[ERROR] Failed to configure OpenAI library: {e}") # Use utils.eprint
        sys.exit(1)

    # --- Run Main Application ---
    final_exit_code = 1 # Default to error
    try:
        # Pass command line arguments (excluding script name) to main
        final_exit_code = main(sys.argv[1:])
    except SystemExit as e:
         # Let SystemExit pass through (used for clean exits with specific codes)
         log.debug(f"SystemExit caught with code: {e.code}")
         final_exit_code = e.code # Ensure the exit code from main() is used
    except KeyboardInterrupt:
         utils.eprint("\n[INFO] Execution interrupted by user (Ctrl+C).") # Use utils.eprint
         final_exit_code = 130 # Standard exit code for Ctrl+C
    except FileNotFoundError as e:
         # Catch critical file not found errors that might occur *before* app logic
         # (e.g., issues finding ffmpeg if checked early, though moved to app)
         log.error(f"Critical file not found: {e}", exc_info=log.isEnabledFor(logging.DEBUG))
         utils.eprint(f"[ERROR] A required file or program was not found: {e}") # Use utils.eprint
         final_exit_code = 1
    except Exception as e:
         # Catch-all for any other unexpected errors during setup or main call
         log.exception("An unhandled exception occurred at the top level:")
         utils.eprint(f"[CRITICAL ERROR] An unexpected error occurred: {e}") # Use utils.eprint
         final_exit_code = 1 # General error exit code
    finally:
         log.info(f"Toast exiting with final code: {final_exit_code}")
         sys.exit(final_exit_code)