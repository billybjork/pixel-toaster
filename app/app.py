import argparse
import logging
import sys
import json
import os
import shutil
from typing import Dict, Any

from .file_manager import (
    FileManager,
    VIDEO_EXTENSIONS,
    IMAGE_EXTENSIONS,
    AUDIO_EXTENSIONS
)
from .command_generator import CommandGenerator
from .command_executor import CommandExecutor
from . import utils
import openai

# Assume these constants are available from the entry point's setup
# We might need to pass them if they aren't global or easily recalculated
# For now, rely on CWD being correct as set by the OS.
CURRENT_WORKDIR = os.getcwd()

def run_toast_app(args: argparse.Namespace) -> int:
    """
    Runs the main logic of the Toast application.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    logging.info("Starting Toast application core logic...")

    # --- Gather System and File Context ---
    try:
        # Use functions from the utils module (imported relatively)
        ffmpeg_executable = utils.get_ffmpeg_executable()
        ffmpeg_version = utils.get_ffmpeg_version(ffmpeg_executable)
        os_type, os_info = utils.get_os_info()
        default_shell = utils.get_default_shell() or "Not detected"
    except FileNotFoundError as e:
        logging.error(f"Initialization failed: {e}")
        utils.eprint(f"[ERROR] Initialization failed: {e}") # Also print to stderr via utils
        return 1 # Exit code 1 for failure
    except Exception as e:
        # Use alias log = logging if desired, otherwise keep as is
        logging.warning(f"Could not gather some system info: {e}", exc_info=args.verbose) # Show traceback if verbose
        # Provide defaults but log the issue
        ffmpeg_executable = shutil.which("ffmpeg") or "ffmpeg" # Best guess using shutil directly here
        ffmpeg_version = "Unknown"
        os_type, os_info = utils.get_os_info() # Try again for OS info via utils
        if not os_type: os_type = "Unknown"
        if not os_info: os_info = "Unknown"
        default_shell = utils.get_default_shell() or "Unknown" # Try again for shell via utils

    system_context: Dict[str, Any] = {
        "os_type": os_type,
        "os_info": os_info,
        "shell": default_shell,
        "ffmpeg_version": ffmpeg_version,
        "ffmpeg_executable_path": ffmpeg_executable,
        "current_directory": CURRENT_WORKDIR, # Use CWD determined at start
    }
    logging.debug(f"System Context: {system_context}")

    # --- File Context ---
    file_manager = FileManager(directory=CURRENT_WORKDIR) # Operate relative to CWD
    user_query_str = " ".join(args.query)
    explicit_file_path = None
    if args.file:
         # Ensure path is absolute for clarity and consistency
         explicit_file_path = os.path.abspath(args.file) if not os.path.isabs(args.file) else args.file
         logging.debug(f"Explicit file specified via --file: {explicit_file_path}")
    else:
         # extract_explicit_filename should ideally return abs path or None
         explicit_file_path = file_manager.extract_explicit_filename(user_query_str)
         if explicit_file_path:
             logging.debug(f"Explicit file extracted from query: {explicit_file_path}")

    file_context_message = "" # Initialize
    if explicit_file_path:
        if os.path.isfile(explicit_file_path):
             system_context["explicit_input_file"] = explicit_file_path
             # Make message slightly clearer for LLM
             file_context_message = f"An explicit input file was provided ('{explicit_file_path}'). Use this exact path for the input."
             logging.info(f"Using explicit file: {explicit_file_path}")
        else:
             # Log warning, and inform LLM that the specified file wasn't found
             logging.warning(f"Explicitly specified file not found: {explicit_file_path}")
             file_context_message = f"User specified an input file ('{args.file or 'from query'}', resolved to '{explicit_file_path}'), but it was not found. Inform the user if a file is needed or if the path is incorrect."
             # Don't add it to system_context if not found
    else:
        # List files logic (returns absolute paths)
        # Use constants imported relatively from .file_manager
        all_media_extensions = VIDEO_EXTENSIONS | IMAGE_EXTENSIONS | AUDIO_EXTENSIONS
        found_files = file_manager.list_files(all_media_extensions)
        if found_files:
             max_files_to_list = 15 # Keep the limit
             files_to_mention_abs = found_files[:max_files_to_list]
             # Try to get relative paths for display/prompt context if simple
             relative_files = []
             for f_abs in files_to_mention_abs:
                 try:
                     rel_path = os.path.relpath(f_abs, CURRENT_WORKDIR)
                     relative_files.append(rel_path)
                 except ValueError:
                     # Handle cases like different drives on Windows
                     relative_files.append(f_abs)

             # Store absolute paths in context for the LLM's use in commands
             system_context["detected_files_in_directory"] = files_to_mention_abs
             # Use relative paths (or absolute if needed) for the context message
             file_list_str = ", ".join([f"'{f}'" for f in relative_files])
             message = f"Found media files in the current directory ('{CURRENT_WORKDIR}'): {file_list_str}."
             if len(found_files) > max_files_to_list:
                 message += f" (and {len(found_files) - max_files_to_list} more...)"
             file_context_message = message
             logging.info(f"Found media files (showing relative paths if possible): {', '.join(relative_files)}")
             logging.debug(f"Absolute paths of found files (first {max_files_to_list}): {', '.join(files_to_mention_abs)}")
        else:
             # No explicit file, and no detected files
             file_context_message = f"No explicit input file was provided, and no common media files were detected in the current directory ('{CURRENT_WORKDIR}')."
             logging.info(f"No relevant media files detected in the current directory ({CURRENT_WORKDIR}).")

    # Add the message to the system context for the LLM
    system_context["file_context_message"] = file_context_message
    logging.debug(f"File Context Message for LLM: {file_context_message}")

    # --- Instantiate Core Components ---
    try:
        # Use CommandGenerator and CommandExecutor imported relatively
        command_generator = CommandGenerator() # Assumes API key is set globally via main.py
        command_executor = CommandExecutor()
    except Exception as e:
        logging.exception("Failed to instantiate core components:")
        utils.eprint(f"[ERROR] Failed to set up core components: {e}") # Use utils
        return 1

    # --- Interaction Loop ---
    conversation_history = []
    current_user_prompt = user_query_str
    max_retry_attempts = 3 # Max LLM/execution retry cycles
    attempts = 0
    last_generated_command = "" # Keep track for exit code logic
    success = False # Track overall success

    logging.info("Starting command generation and execution loop...")

    while attempts < max_retry_attempts:
        attempts += 1
        logging.info(f"--- Attempt #{attempts} ---")

        # Ensure there's a prompt to send, add it to history
        if not current_user_prompt:
            logging.error("No user prompt available for this attempt. This shouldn't happen.")
            # Exit gracefully if this state is reached unexpectedly
            return 1
        # Add user prompt if it's new (don't add retry prompts if they are identical)
        if not conversation_history or conversation_history[-1].get("content") != current_user_prompt:
            conversation_history.append({"role": "user", "content": current_user_prompt})
        # Clear current_user_prompt after adding to history so it's not accidentally reused
        current_user_prompt = None
        # Reset command tracker for this attempt
        last_generated_command = ""

        try:
            # --- 1. Generate Command ---
            logging.debug("Generating command via LLM...")
            raw_response = command_generator.generate_command(conversation_history, system_context)
            logging.debug(f"LLM raw response: {raw_response}")
            cleaned_json = command_generator.clean_json_response(raw_response)
            logging.debug(f"LLM cleaned response: {cleaned_json}")

            # --- 2. Parse Response ---
            try:
                parsed_response = json.loads(cleaned_json)
                explanation_data = parsed_response.get("explanation", "No explanation provided.")
                command_to_execute = parsed_response.get("command", "").strip()
                last_generated_command = command_to_execute # Store for potential dry run exit
                # Add assistant's *valid* response to history
                conversation_history.append({"role": "assistant", "content": cleaned_json})
            except json.JSONDecodeError as e:
                logging.error(f"Failed to parse JSON response from LLM: {e}")
                logging.error(f"Raw response was: {raw_response}")
                # Prepare prompt for LLM to fix its JSON
                current_user_prompt = f"The previous response was not valid JSON. Please provide the response strictly in the required JSON format.\nPrevious invalid response:\n{raw_response}"
                # (Logic above handles not adding identical prompts)
                continue # Retry generation with the correction request

            # --- 3. Handle Cases Without a Command ---
            if not command_to_execute:
                logging.warning("LLM did not provide a command.")
                print("\nExplanation / Response:")
                if isinstance(explanation_data, list): print("- " + "\n- ".join(explanation_data))
                else: print(f"- {explanation_data}")
                print("\nCannot proceed without a command.")
                # Consider this a failure unless explanation suggests success (unlikely)
                success = False
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
                success = True # Dry run counts as success for exit code
                break # Exit loop successfully after showing command

            # --- 6. Execute Command ---
            print("Executing command...")
            logging.info(f"Executing command: {command_to_execute}")
            # Use the executor's retry logic for execution robustness
            exec_success, output = command_executor.execute_with_retries(command_to_execute)

            # --- 7. Handle Execution Result ---
            if exec_success:
                logging.info("Command executed successfully!")
                if output:
                    logging.debug(f"Command output:\n{output}")
                    print(f"Output:\n{output}") # Show output to user on success too
                utils.print_art() # Use utility function via utils
                success = True # Mark overall success
                break # Success! Exit the loop.
            else:
                # Execution failed, prepare for LLM retry
                logging.error("Command execution failed.")
                error_output_for_llm = output if output else "Command failed with no specific output."
                logging.error(f"Failure Output:\n{error_output_for_llm}")
                print(f"\n[ERROR] Command failed:\n{error_output_for_llm}\n")

                # Check if we have attempts left before asking LLM to retry
                if attempts < max_retry_attempts:
                    print("Asking the LLM to retry based on the error...")
                    # Prepare the next user prompt with error context
                    current_user_prompt = (
                        f"The last command attempt failed:\n"
                        f"Command: `{command_to_execute}`\n"
                        f"Error Output:\n```\n{error_output_for_llm}\n```\n"
                        f"Please analyze the error and the original request history "
                        f"to provide a corrected command."
                    )
                    # Remove the assistant's failed command response from history
                    # before adding the new user error prompt for the next cycle
                    if conversation_history and conversation_history[-1]["role"] == "assistant":
                       conversation_history.pop()
                    # Continue to the next iteration of the while loop to retry with the LLM
                else:
                     # Max attempts reached *after* a failure, don't prepare another prompt
                     logging.warning("Maximum retry attempts reached after command failure.")
                     success = False
                     # Break explicitly here, the loop condition will also catch it
                     break

        # --- Error Handling for LLM Interaction (API errors, etc.) ---
        except openai.APIError as e:
             logging.error(f"OpenAI API error: {e}", exc_info=args.verbose)
             utils.eprint(f"Error communicating with the LLM API: {e}. Check connection/key/quota.") # Use utils
             success = False
             break # Exit loop on API errors
        except Exception as e:
             logging.exception("An unexpected error occurred in the main loop:") # Log full traceback
             utils.eprint(f"An unexpected error occurred: {e}. Aborting.") # Use utils
             success = False
             break # Exit loop on other unexpected errors

    # --- Loop Finished ---
    # Determine final status based on loop exit condition and success flag

    if success:
        logging.info("Toast finished successfully.")
        return 0 # Exit code 0 for success
    else:
        # Check specific conditions for failure messages
        if attempts >= max_retry_attempts:
             # Check if we were about to retry (current_user_prompt was set) or failed earlier
             if current_user_prompt:
                 # Means last action was a failure setting up retry
                 logging.warning("Maximum retry attempts reached after command failure. Exiting.")
                 print("\nMaximum retry attempts reached. The command could not be successfully executed.")
             elif not last_generated_command and not args.dry_run:
                 # Failed before generating a command (e.g., JSON parse loop maxed out)
                  logging.warning("Maximum attempts reached, failed to generate a valid command. Exiting.")
                  print("\nMaximum attempts reached. Could not successfully generate a command.")
             else:
                  # Generic max attempts message if other conditions don't fit
                  logging.warning("Maximum attempts reached. Exiting.")
                  print("\nMaximum attempts reached. Could not successfully complete the operation.")

        elif not last_generated_command and not args.dry_run:
             # Exited loop early without success and without generating a command
             logging.warning("Exited without generating a command (e.g., LLM refusal or early error).")
             # Message already printed in loop ("Cannot proceed...")
        else:
             # Other failure (e.g., API error break, unexpected exception)
             logging.warning("Toast finished with errors.")
             # Error message already printed by exception handlers

        return 1 # Exit code 1 for failure