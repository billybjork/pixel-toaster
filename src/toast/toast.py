#!/usr/bin/env python3
import argparse
import logging
import sys
import json
import subprocess
import platform
import shutil
import os
from pathlib import Path
from typing import Tuple, Optional
from dotenv import load_dotenv
from file_manager import (
    FileManager,
    VIDEO_EXTENSIONS,
    IMAGE_EXTENSIONS,
    AUDIO_EXTENSIONS
)
from command_generator import CommandGenerator
from command_executor import CommandExecutor
import openai

# --- Determine paths ---
# Get the path of the script file, resolving symlinks
try:
    # Resolve symlinks to get the *actual* file path
    REAL_SCRIPT_FILE = os.path.realpath(__file__)
except NameError:
    # __file__ might not be defined if running interactively or packaged weirdly
    REAL_SCRIPT_FILE = os.path.abspath(sys.argv[0]) # Fallback using argv

# TODO: a lot of this is going to instead come from your ~/.toast_bjork
SCRIPT_DIR = os.path.dirname(REAL_SCRIPT_FILE) # Directory of the real script file
CURRENT_WORKDIR = os.getcwd()
USER_HOME = Path.home()
USER_CONFIG_DIR = USER_HOME / ".config" / "toast" # Standard XDG base dir location
USER_CONFIG_DOTENV = USER_CONFIG_DIR / ".env"
# *** Define .env path relative to the *real* script directory ***
SCRIPT_DIR_DOTENV = Path(SCRIPT_DIR) / ".env"

# --- Setup Logging Early ---
# Use basicConfig for initial setup before main() is called
# Configure logging (important for seeing debug messages)
# Use a basic formatter initially, will be updated in main if verbose
logging.basicConfig(
    level=logging.INFO, # Default to INFO
    format="[%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logging.info(f"--- Initializing Toast ---")

# --- Ensure modules in SCRIPT_DIR are importable ---
# This helps if the script is run directly or symlinked,
# maybe less so if installed via setup.py's entry_points.
if SCRIPT_DIR not in sys.path:
     # Insert at the beginning to prioritize modules next to the real script
     sys.path.insert(0, SCRIPT_DIR)
     logging.debug(f"Inserted script directory into sys.path: {SCRIPT_DIR}")

# TODO: move this to `utils.py`
def print_art():
    art = r"""
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣄⠀⠀⠀⢀⡀⠀⠀⠀⣀⡀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢰⣟⠁⠀⠀⣴⡏⠁⠀⠀⣾⡋⠁⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⠿⠄⠀⠈⠻⠷⠀⠀⠈⢹⣷⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣤⣤⣤⣤⣤⣤⣤⣤⣤⣀⠀⠠⣤⣀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠰⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠀⣹⣿⡿⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⠛⠛⠀⠛⠛⠛⠛⠉⠛⠛⠛⠀⠐⠛⠛⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⣠⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣦⠀⠀⠀
⠀⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀
⠀⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀
⠀⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠿⠛⠛⠿⣿⡇⠀⠀
⠀⠀⠀⠀⠀⠀⠸⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠏⢠⣾⣿⣦⠘⠇⠀⠀
⠀⠀⢀⣤⡀⠀⢰⣶⣶⣶⣶⣶⣶⣶⣶⣶⣶⣶⣶⣶⣶⣆⠘⢿⣿⠟⢠⡆⠀⠀
⠀⠀⠘⠛⠛⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣤⣤⣶⣿⡇⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⢠⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⣄⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠘⠛⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⠛⠀⠀⠀⠀⠀⠀
"""
    print(art)

# TODO: move this to its own loader class

# --- System Info Gathering ---
def get_ffmpeg_executable() -> str:
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path is None: raise FileNotFoundError("Missing ffmpeg executable.")
    return ffmpeg_path
# TODO: let these functions breath, eg put space between beginning and end.
# TODO: use a linter if you don't already, it should catch this
def get_ffmpeg_version(ffmpeg_exe: str) -> str:
    try: result = subprocess.run([ffmpeg_exe, "-version"], capture_output=True, text=True, check=False, timeout=5); output = result.stdout if "ffmpeg version" in result.stdout.lower() else result.stderr; first_line = output.splitlines()[0].strip() if output and output.splitlines() else "Could not determine version"; return first_line if "version" in first_line.lower() else output
    except Exception as e: logging.warning(f"Could not get ffmpeg version: {e}"); return "Unknown"
def get_os_info() -> Tuple[str, str]:
    os_type = platform.system(); return os_type, f"{os_type} {platform.release()} {platform.machine()}"

# TODO: cleaner way to do this
def get_default_shell() -> Optional[str]:
     shell = os.getenv("SHELL")
     if shell: return shell
     # Basic platform specific fallbacks
     if platform.system() == "Windows": return os.getenv("COMSPEC", "cmd.exe")
     if platform.system() in ["Linux", "Darwin"]:
         if os.path.exists('/bin/bash'): return '/bin/bash'
         if os.path.exists('/bin/sh'): return '/bin/sh'
     return None

# --- Main Execution Logic ---
# TODO: main.py instead of here, and keep the logic in it as light as possible
def main():
    parser = argparse.ArgumentParser(
        description="toast: Natural language FFmpeg command generator."
    )
    parser.add_argument("query", nargs="+", help="Your natural language prompt for FFmpeg.")
    parser.add_argument("--dry-run", action="store_true", help="Show the generated command without executing it.")
    parser.add_argument("--file", type=str, help="Specify an input file explicitly.")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output.")
    args = parser.parse_args()

    # Reconfigure logging level if verbose AFTER parsing args
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.getLogger().setLevel(log_level) # Update root logger level

    # Log paths again now that logging level is set correctly
    logging.debug(f"Verbose logging enabled.")
    logging.debug(f"(DEBUG) Real Script File: {REAL_SCRIPT_FILE}")
    logging.debug(f"(DEBUG) Real Script Directory: {SCRIPT_DIR}")
    logging.debug(f"(DEBUG) Current Working Directory: {CURRENT_WORKDIR}")
    logging.debug(f"(DEBUG) User Config Dir target: {USER_CONFIG_DIR}")
    # Log the result of the dotenv loading attempt from the main block
    logging.debug(f"(DEBUG) Dotenv search path 1 (User Config): {os.environ.get('TOAST_DOTENV_USER_PATH', 'N/A')}")
    logging.debug(f"(DEBUG) Dotenv search path 2 (Script Dir): {os.environ.get('TOAST_DOTENV_SCRIPT_PATH', 'N/A')}")
    logging.debug(f"(DEBUG) Dotenv loaded successfully from: {os.environ.get('TOAST_DOTENV_LOADED_FROM', 'Not loaded')}")

    # --- Gather System and File Context ---
    try:
        ffmpeg_executable = get_ffmpeg_executable()
        ffmpeg_version = get_ffmpeg_version(ffmpeg_executable)
        os_type, os_info = get_os_info()
        default_shell = get_default_shell() or "Not detected"
    except FileNotFoundError as e:
        logging.error(f"Initialization failed: {e}")
        sys.exit(1)
    except Exception as e:
        # TODO: update all your logging like this, also make an alias from logging to log
        # so you can just do log.warning, insterad of logging
        # logging.warning(",... %s ", args.verbose)
        # logging.warning("Could not gather some system info: %s", args.verbose) # Show traceback if verbose
        logging.warning(f"Could not gather some system info: {e}", exc_info=args.verbose) # Show traceback if verbose
        ffmpeg_executable = "ffmpeg"; ffmpeg_version = "Unknown"
        os_type, os_info = "Unknown", "Unknown"; default_shell = "Unknown"

    system_context = {
        "os_type": os_type, "os_info": os_info, "shell": default_shell,
        "ffmpeg_version": ffmpeg_version, "ffmpeg_executable_path": ffmpeg_executable,
        "current_directory": CURRENT_WORKDIR,
    }

    # --- File Context ---
    file_manager = FileManager(directory=CURRENT_WORKDIR) # Operate relative to CWD
    user_query_str = " ".join(args.query)
    explicit_file_path = None
    if args.file:
         # Ensure path is absolute for clarity
         explicit_file_path = os.path.abspath(args.file) if not os.path.isabs(args.file) else args.file
    else:
         # extract_explicit_filename should ideally return abs path or None
         explicit_file_path = file_manager.extract_explicit_filename(user_query_str)

    file_context_message = "" # Initialize
    if explicit_file_path:
        if os.path.isfile(explicit_file_path):
             system_context["explicit_input_file"] = explicit_file_path
             file_context_message = f"An explicit input file was provided: '{explicit_file_path}'. Please ensure the command uses this exact path."
             logging.info(f"Using explicit file: {explicit_file_path}")
        else:
             logging.warning(f"Explicitly specified file not found: {explicit_file_path}")
             file_context_message = f"User tried to specify a file '{args.file or 'in query'}' which resolved to '{explicit_file_path}', but it was not found. Inform the user if a file is needed."
    else:
        # List files logic (returns absolute paths)
        # *** Use directly imported constants ***
        all_media_extensions = VIDEO_EXTENSIONS | IMAGE_EXTENSIONS | AUDIO_EXTENSIONS
        found_files = file_manager.list_files(all_media_extensions)
        if found_files:
             max_files_to_list = 15
             files_to_mention_abs = found_files[:max_files_to_list]
             # Try to get relative paths for display/prompt context if simple
             relative_files = []
             for f_abs in files_to_mention_abs:
                 try: rel_path = os.path.relpath(f_abs, CURRENT_WORKDIR); relative_files.append(rel_path)
                 except ValueError: relative_files.append(f_abs) # Different drive etc.

             system_context["detected_files_in_directory"] = files_to_mention_abs # Store absolute paths
             file_list_str = ", ".join([f"'{f}'" for f in relative_files])
             message = f"Found these media files in the current directory ({CURRENT_WORKDIR}): {file_list_str}."
             if len(found_files) > max_files_to_list: message += f" (and {len(found_files) - max_files_to_list} more...)"
             file_context_message = message
             logging.info(f"Found media files (showing relative paths if possible): {', '.join(relative_files)}")
             logging.debug(f"Absolute paths of found files: {', '.join(files_to_mention_abs)}")
        else:
             file_context_message = f"No common media files detected in the current directory ({CURRENT_WORKDIR})."
             logging.info(f"No relevant media files detected in the current directory ({CURRENT_WORKDIR}).")

    system_context["file_context_message"] = file_context_message

    # --- Instantiate Core Components ---
    command_generator = CommandGenerator()
    command_executor = CommandExecutor()

    # --- Interaction Loop ---
    conversation_history = []
    # Initialize with the first user prompt
    current_user_prompt = user_query_str
    max_retry_attempts = 3 # Renamed from clarification attempts
    attempts = 0
    logging.info("Starting command generation and execution loop...")

    while attempts < max_retry_attempts:
         attempts += 1
         logging.info(f"--- Attempt #{attempts} ---")

         # Ensure there's a prompt to send, add it to history
         if not current_user_prompt:
             logging.error("No user prompt available for this attempt. This shouldn't happen.")
             break
         if not conversation_history or conversation_history[-1].get("content") != current_user_prompt:
             conversation_history.append({"role": "user", "content": current_user_prompt})
         # Clear current_user_prompt after adding to history so it's not accidentally reused if LLM fails before setting a new one
         current_user_prompt = None

         try:
             # --- 1. Generate Command ---
             raw_response = command_generator.generate_command(conversation_history, system_context)
             logging.debug(f"LLM raw response: {raw_response}")
             cleaned_json = command_generator.clean_json_response(raw_response)
             logging.debug(f"LLM cleaned response: {cleaned_json}")

             # --- 2. Parse Response ---
             try:
                 parsed_response = json.loads(cleaned_json)
                 explanation_data = parsed_response.get("explanation", "No explanation provided.")
                 command_to_execute = parsed_response.get("command", "").strip()
                 # Add assistant's response (the structured JSON) to history
                 conversation_history.append({"role": "assistant", "content": cleaned_json})
             except json.JSONDecodeError as e:
                 logging.error(f"Failed to parse JSON response from LLM: {e}")
                 logging.error(f"Raw response was: {raw_response}")
                 # Prepare prompt for LLM to fix its JSON
                 current_user_prompt = f"The previous response was not valid JSON. Please provide the response strictly in the required JSON format.\nPrevious invalid response:\n{raw_response}"
                 # Remove the failed user prompt if it was the last entry to avoid duplication
                 if conversation_history and conversation_history[-1]["role"] == "user":
                     conversation_history.pop()
                 continue # Retry generation

             # --- 3. Handle Cases Without a Command ---
             if not command_to_execute:
                 logging.warning("LLM did not provide a command.")
                 # Print explanation / refusal reason
                 print("\nExplanation / Response:")
                 if isinstance(explanation_data, list): print("- " + "\n- ".join(explanation_data))
                 else: print(f"- {explanation_data}")
                 print("\nCannot proceed without a command.")
                 break # Exit loop, cannot execute or retry without a command

             # --- 4. Display Information ---
             print("\nExplanation:")
             if isinstance(explanation_data, list): print("- " + "\n- ".join(explanation_data))
             else: print(f"- {explanation_data}")
             print(f"\nProposed Command:\n\t{command_to_execute}\n")

             # --- 5. Handle Dry Run ---
             if args.dry_run:
                 logging.info("Dry-run mode enabled. Command not executed.")
                 print("[Dry Run] Command generated but not executed.")
                 break # Exit loop successfully after showing command

             # --- 6. Execute Command ---
             print("Executing command...")
             logging.info(f"Executing command: {command_to_execute}")
             success, output = command_executor.execute_with_retries(command_to_execute) # Using simple execute now

             # --- 7. Handle Execution Result ---
             if success:
                 logging.info("Command executed successfully!")
                 if output:
                     logging.debug(f"Command output:\n{output}")
                     print(f"Output:\n{output}") # Show output to user on success too
                 print_art()
                 break # Success! Exit the loop.
             else:
                 # Execution failed, prepare for LLM retry
                 logging.error("Command execution failed.")
                 error_output_for_llm = output if output else "Command failed with no specific output."
                 logging.error(f"Failure Output:\n{error_output_for_llm}")
                 print(f"\n[ERROR] Command failed:\n{error_output_for_llm}\n")
                 print("Asking the LLM to retry based on the error...")
                 # Prepare the next user prompt with error context
                 current_user_prompt = f"The last command attempt failed:\nCommand: `{command_to_execute}`\nError Output:\n```\n{error_output_for_llm}\n```\nPlease analyze the error and the original request history to provide a corrected command."
                 # Remove the assistant's failed command response from history before adding the new user error prompt
                 if conversation_history and conversation_history[-1]["role"] == "assistant":
                    conversation_history.pop()
                 continue # Go to the next iteration of the while loop to retry with the LLM

         # --- Error Handling for LLM Interaction ---
         except openai.APIError as e:
             logging.error(f"OpenAI API error: {e}", exc_info=args.verbose)
             # Remove the potentially problematic user prompt if it was the last entry
             if conversation_history and conversation_history[-1]["role"] == "user":
                 conversation_history.pop()
             print(f"Error communicating with the LLM API: {e}. Check connection/key/quota.", file=sys.stderr)
             break # Exit loop on API errors
         except Exception as e:
             logging.exception("An unexpected error occurred in the main loop:") # Log full traceback
             # Remove the potentially problematic user prompt if it was the last entry
             if conversation_history and conversation_history[-1]["role"] == "user":
                 conversation_history.pop()
             print(f"An unexpected error occurred: {e}. Aborting.", file=sys.stderr)
             break # Exit loop on other unexpected errors

    # --- Loop Exit Conditions ---
    if attempts >= max_retry_attempts and current_user_prompt:
        # This condition means the loop finished because it hit max attempts *after* a failure
        logging.warning("Maximum retry attempts reached after command failure. Exiting.")
        print("\nMaximum retry attempts reached. The command could not be successfully executed.")
    elif not current_user_prompt and attempts >= max_retry_attempts:
         # This means loop finished due to max attempts, but last action wasn't necessarily a failure reported to user
         logging.warning("Maximum attempts reached (possibly during JSON parsing or initial generation). Exiting.")
         print("\nMaximum attempts reached. Could not successfully generate and execute the command.")

    logging.info("Toast finished.")
    # Determine exit code: 0 for success (or dry run), 1 for failure
    # Success is indicated by breaking the loop *before* hitting max attempts AND not due to error/no command.
    # We can check if the loop completed normally (i.e., hit the `break` after success or dry run)
    # A simple way: assume failure if we exited the loop due to attempt limit or caught exception.
    # Check if the loop was broken internally (success/dry-run/no-command/api-error) vs finishing all attempts after failure.
    # We already broke on success/dry-run/etc. So if we are here and attempts >= max_retry_attempts, it's likely a failure chain.
    # If current_user_prompt is set, it means the last step was preparing for a retry that didn't happen.
    exit_code = 0 if not current_user_prompt and attempts < max_retry_attempts else 1
    # Refine: If dry run, always exit 0 if loop finished or broke due to dry run.
    if args.dry_run and (attempts < max_retry_attempts or not command_to_execute): # Check if dry run break happened or LLM didn't give command
        exit_code = 0
    # If success break happened (print_art was called), exit code should be 0. This is implicitly handled.

    sys.exit(exit_code)

if __name__ == "__main__":
    # --- Load .env file with Priority Order ---
    api_key = os.getenv("OPENAI_API_KEY")
    loaded_from = None
    dotenv_loaded = False # Track if any dotenv load succeeded

    # 1. Check Environment Variable FIRST
    if api_key:
        logging.info("Found OPENAI_API_KEY in environment variables.")
        loaded_from = "Environment Variable"
    else:
        logging.info("OPENAI_API_KEY not found in environment variables.")
        # 2. Try User Config Dir (~/.config/toast/.env)
        logging.info(f"Looking for .env file in user config: {USER_CONFIG_DOTENV}")
        os.environ['TOAST_DOTENV_USER_PATH'] = str(USER_CONFIG_DOTENV) # For logging in main()
        if USER_CONFIG_DOTENV.is_file():
            logging.info(f"Found user config .env file. Attempting to load.")
            try:
                # Pass stream explicitly if verbose logging is needed from dotenv
                dotenv_loaded = load_dotenv(dotenv_path=USER_CONFIG_DOTENV, verbose=logging.getLogger().isEnabledFor(logging.DEBUG), override=True)
                api_key = os.getenv("OPENAI_API_KEY") # Check again after loading
                if api_key and dotenv_loaded:
                     loaded_from = str(USER_CONFIG_DOTENV)
                     logging.info(f"Successfully loaded OPENAI_API_KEY from user config.")
                elif dotenv_loaded:
                     logging.warning(f"Loaded {USER_CONFIG_DOTENV}, but key still not found in env.")
                else:
                     logging.warning(f"Found {USER_CONFIG_DOTENV}, but load_dotenv() returned False.")
            except Exception as e:
                logging.warning(f"Error loading {USER_CONFIG_DOTENV}: {e}", exc_info=True)
        else:
             logging.info(f"User config .env file not found.")

        # 3. Try **Real** Script Directory (Development/Symlink Fallback) ONLY if not loaded yet
        if not api_key:
             # *** Use SCRIPT_DIR_DOTENV which is based on REAL_SCRIPT_FILE ***
             logging.info(f"Looking for .env file in real script directory: {SCRIPT_DIR_DOTENV}")
             os.environ['TOAST_DOTENV_SCRIPT_PATH'] = str(SCRIPT_DIR_DOTENV) # For logging in main()
             if SCRIPT_DIR_DOTENV.is_file():
                 logging.info(f"Found real script directory .env file. Attempting to load.")
                 try:
                     dotenv_loaded = load_dotenv(dotenv_path=SCRIPT_DIR_DOTENV, verbose=logging.getLogger().isEnabledFor(logging.DEBUG), override=True)
                     api_key = os.getenv("OPENAI_API_KEY") # Check again
                     if api_key and dotenv_loaded:
                         loaded_from = str(SCRIPT_DIR_DOTENV)
                         logging.info(f"Successfully loaded OPENAI_API_KEY from real script directory.")
                     elif dotenv_loaded:
                         logging.warning(f"Loaded {SCRIPT_DIR_DOTENV}, but key still not found in env.")
                     else:
                         logging.warning(f"Found {SCRIPT_DIR_DOTENV}, but load_dotenv() returned False.")
                 except Exception as e:
                      logging.warning(f"Error loading {SCRIPT_DIR_DOTENV}: {e}", exc_info=True)

             else:
                 logging.info(f"Real script directory .env file not found.")

    # --- Final Check for API Key ---
    if not api_key:
        # Print error to stderr for visibility even if logging isn't working fully
        # TODO: use a differnet more structured logger
        eprint = lambda *a, **k: print(*a, file=sys.stderr, **k)
        eprint(f"\n[ERROR] OPENAI_API_KEY could not be found.")
        eprint(f"        Search Order:")
        eprint(f"        1. Environment Variable 'OPENAI_API_KEY'")
        eprint(f"        2. User Config File: {USER_CONFIG_DOTENV}")
        eprint(f"        3. Real Script Directory File: {SCRIPT_DIR_DOTENV} (resolves symlinks)")
        eprint(f"\n        Recommendation: Set the OPENAI_API_KEY environment variable globally,")
        eprint(f"        or create the user config directory ({USER_CONFIG_DIR})")
        eprint(f"        and place your .env file inside it.")
        sys.exit(1)
    else:
        masked_key = api_key[:4] + "..." + api_key[-4:]
        logging.info(f"OpenAI API Key loaded successfully (masked: {masked_key}) from: {loaded_from if loaded_from else 'Unknown Source'}")
        os.environ['TOAST_DOTENV_LOADED_FROM'] = loaded_from if loaded_from else "Not loaded via dotenv"

    # --- Configure OpenAI Library ---
    try:
        # Ensure the key is actually set for the library if loaded via dotenv
        # The library should pick it up from os.environ automatically, but explicit doesn't hurt
        openai.api_key = api_key
        logging.info("OpenAI library imported and API key configured.")
    except Exception as e:
        # This catch block might be redundant if the import itself fails earlier,
        # but kept for safety in case configuration itself throws an error.
        logging.exception("Error configuring OpenAI library:")
        sys.exit(1)

    # --- Run Main Application ---
    logging.info("Starting main application logic...")
    # Wrap main call in try/except for final catch-all
    try:
        main()
    except SystemExit as e:
         # Let SystemExit pass through (used for clean exits with specific codes)
         sys.exit(e.code) # Ensure the exit code from main() is propagated
    except KeyboardInterrupt:
         print("\n[INFO] Execution interrupted by user.", file=sys.stderr)
         sys.exit(130) # Standard exit code for Ctrl+C
    except Exception as e:
         logging.exception("An unhandled exception occurred outside the main loop:")
         sys.exit(1) # General error exit code
