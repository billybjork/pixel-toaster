import argparse
import logging as log
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

def run_toast_app(args: argparse.Namespace, config: Dict[str, Any]) -> int:
    """
    Runs the main logic of the Toast application.

    Args:
        args: Parsed command-line arguments.
        config: Loaded application configuration dictionary.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    # Use a distinct variable name for the logger to avoid shadowing the module-level alias.
    logger = log.getLogger(__name__)  # Use module-specific logger
    logger.info("Starting Pixel Toaster application core logic...")
    logger.debug(f"Received configuration: {config}")  # Log config only in debug
    logger.debug(f"Received arguments: {args}")

    # --- Get Current Working Directory ---
    # Get CWD *when the function is called*, not at module import time
    current_workdir = os.getcwd()
    logger.debug(f"Operating in directory: {current_workdir}")

    # --- Gather System and File Context ---
    # (Keep dynamic detection for ffmpeg, OS etc. - less likely to be static config)
    try:
        ffmpeg_executable = utils.get_ffmpeg_executable()
        ffmpeg_version = utils.get_ffmpeg_version(ffmpeg_executable)
        os_type, os_info = utils.get_os_info()
        default_shell = utils.get_default_shell() or "Not detected"
    except FileNotFoundError as e:
        logger.error(f"Initialization failed: {e}", exc_info=args.verbose)
        utils.eprint(f"[ERROR] Initialization failed: {e}")
        return 1
    except Exception as e:
        logger.warning(f"Could not gather some system info: {e}", exc_info=args.verbose)
        ffmpeg_executable = shutil.which("ffmpeg") or "ffmpeg"
        ffmpeg_version = "Unknown"
        os_type, os_info = utils.get_os_info()
        if not os_type:
            os_type = "Unknown"
        if not os_info:
            os_info = "Unknown"
        default_shell = utils.get_default_shell() or "Unknown"

    system_context: Dict[str, Any] = {
        "os_type": os_type,
        "os_info": os_info,
        "shell": default_shell,
        "ffmpeg_version": ffmpeg_version,
        "ffmpeg_executable_path": ffmpeg_executable,
        "current_directory": current_workdir,  # Use dynamically determined CWD
    }
    logger.debug(f"System Context: {system_context}")

    # --- File Context ---
    # Use current_workdir determined above
    file_manager = FileManager(directory=current_workdir)
    user_query_str = " ".join(args.query)
    explicit_file_path = None
    if args.file:
        explicit_file_path = os.path.abspath(args.file) if not os.path.isabs(args.file) else args.file
        logger.debug(f"Explicit file specified via --file: {explicit_file_path}")
    else:
        explicit_file_path = file_manager.extract_explicit_filename(user_query_str)
        if explicit_file_path:
            logger.debug(f"Explicit file extracted from query: {explicit_file_path}")

    file_context_message = ""
    if explicit_file_path:
        if os.path.isfile(explicit_file_path):
            system_context["explicit_input_file"] = explicit_file_path
            file_context_message = (
                f"An explicit input file was provided ('{explicit_file_path}'). Use this exact path for the input."
            )
            logger.info(f"Using explicit file: {explicit_file_path}")
        else:
            logger.warning(f"Explicitly specified file not found: {explicit_file_path}", exc_info=args.verbose)
            file_context_message = (
                f"User specified an input file ('{args.file or 'from query'}', resolved to '{explicit_file_path}'), "
                "but it was not found. Inform the user if a file is needed or if the path is incorrect."
            )
    else:
        all_media_extensions = VIDEO_EXTENSIONS | IMAGE_EXTENSIONS | AUDIO_EXTENSIONS
        found_files = file_manager.list_files(all_media_extensions)
        if found_files:
            max_files_to_list = 15
            files_to_mention_abs = found_files[:max_files_to_list]
            relative_files = []
            for f_abs in files_to_mention_abs:
                try:
                    rel_path = os.path.relpath(f_abs, current_workdir)
                    relative_files.append(rel_path)
                except ValueError:
                    relative_files.append(f_abs)
            system_context["detected_files_in_directory"] = files_to_mention_abs
            file_list_str = ", ".join([f"'{f}'" for f in relative_files])
            message = f"Found media files in the current directory ('{current_workdir}'): {file_list_str}."
            if len(found_files) > max_files_to_list:
                message += f" (and {len(found_files) - max_files_to_list} more...)"
            file_context_message = message
            logger.info(f"Found media files (showing relative paths if possible): {', '.join(relative_files)}")
            logger.debug(f"Absolute paths of found files (first {max_files_to_list}): {', '.join(files_to_mention_abs)}")
        else:
            file_context_message = (
                f"No explicit input file was provided, and no common media files were detected in the current directory "
                f"('{current_workdir}')."
            )
            logger.info(f"No relevant media files detected in the current directory ({current_workdir}).")

    system_context["file_context_message"] = file_context_message
    logger.debug(f"File Context Message for LLM: {file_context_message}")

    # --- Instantiate Core Components ---
    try:
        # Use the model specified in the config
        llm_model = config.get("llm_model", "gpt-4o-mini")  # Fallback just in case
        logger.info(f"Using LLM model: {llm_model}")
        # API key is already set globally by main.py
        command_generator = CommandGenerator(model=llm_model)
        command_executor = CommandExecutor()
    except Exception as e:
        logger.error("Failed to instantiate core components:", exc_info=args.verbose)
        utils.eprint(f"[ERROR] Failed to set up core components: {e}")
        return 1

    # --- Interaction Loop ---
    conversation_history = []
    current_user_prompt = user_query_str
    max_retry_attempts = 3
    attempts = 0
    last_generated_command = ""
    success = False

    logger.info("Starting command generation and execution loop...")

    while attempts < max_retry_attempts:
        attempts += 1
        logger.info(f"--- Attempt #{attempts} ---")

        if not current_user_prompt:
            logger.error("No user prompt available for this attempt.")
            return 1
        if not conversation_history or conversation_history[-1].get("content") != current_user_prompt:
            conversation_history.append({"role": "user", "content": current_user_prompt})
        current_user_prompt = None
        last_generated_command = ""

        try:
            # --- 1. Generate Command ---
            logger.debug("Generating command via LLM...")
            # Pass system_context which includes dynamic info + CWD
            raw_response = command_generator.generate_command(conversation_history, system_context)
            logger.debug(f"LLM raw response: {raw_response}")
            cleaned_json = command_generator.clean_json_response(raw_response)
            logger.debug(f"LLM cleaned response: {cleaned_json}")

            # --- 2. Parse Response ---
            try:
                parsed_response = json.loads(cleaned_json)
                explanation_data = parsed_response.get("explanation", "No explanation provided.")
                command_to_execute = parsed_response.get("command", "").strip()
                last_generated_command = command_to_execute
                conversation_history.append({"role": "assistant", "content": cleaned_json})
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response from LLM: {e}", exc_info=args.verbose)
                logger.error(f"Raw response was: {raw_response}")
                current_user_prompt = (
                    "The previous response was not valid JSON. Please provide the response strictly in the required JSON format.\n"
                    f"Previous invalid response:\n{raw_response}"
                )
                # Remove assistant's bad response if added
                if conversation_history and conversation_history[-1]["role"] == "assistant":
                    conversation_history.pop()
                # Continue to retry generation
                continue

            # --- 3. Handle Cases Without a Command ---
            if not command_to_execute:
                logger.warning("LLM did not provide a command.")
                print("\nExplanation / Response:")
                if isinstance(explanation_data, list):
                    print("- " + "\n- ".join(explanation_data))
                else:
                    print(f"- {explanation_data}")
                print("\nCannot proceed without a command.")
                success = False
                break

            # --- 4. Display Information ---
            print("\nExplanation:")
            if isinstance(explanation_data, list):
                print("- " + "\n- ".join(explanation_data))
            else:
                print(f"- {explanation_data}")
            print(f"\nProposed Command:\n\t{command_to_execute}\n")

            # --- 5. Handle Dry Run ---
            if args.dry_run:
                logger.info("Dry-run mode enabled. Command not executed.")
                print("[Dry Run] Command generated but not executed.")
                success = True
                break

            # --- 6. Execute Command ---
            print("Executing command...")
            logger.info(f"Executing command: {command_to_execute}")
            exec_success, output = command_executor.execute_with_retries(command_to_execute)

            # --- 7. Handle Execution Result ---
            if exec_success:
                logger.info("Command executed successfully!")
                if output:
                    logger.debug(f"Command output:\n{output}")
                    print(f"Output:\n{output}")
                utils.print_art()
                success = True
                break
            else:
                logger.error("Command execution failed.", exc_info=args.verbose)
                error_output_for_llm = output if output else "Command failed with no specific output."
                logger.error(f"Failure Output:\n{error_output_for_llm}", exc_info=args.verbose)
                print(f"\n[ERROR] Command failed:\n{error_output_for_llm}\n")

                if attempts < max_retry_attempts:
                    print("Asking the LLM to retry based on the error...")
                    current_user_prompt = (
                        f"The last command attempt failed:\n"
                        f"Command: `{command_to_execute}`\n"
                        f"Error Output:\n```\n{error_output_for_llm}\n```\n"
                        "Please analyze the error and the original request history to provide a corrected command."
                    )
                    if conversation_history and conversation_history[-1]["role"] == "assistant":
                        conversation_history.pop()
                    # Continue to the next iteration
                else:
                    logger.warning("Maximum retry attempts reached after command failure.", exc_info=args.verbose)
                    success = False
                    break

        # --- Error Handling for LLM Interaction ---
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}", exc_info=args.verbose)
            utils.eprint(f"Error communicating with the LLM API: {e}. Check connection/key/quota.")
            success = False
            break
        except Exception as e:
            logger.error("An unexpected error occurred in the main loop:", exc_info=args.verbose)
            utils.eprint(f"An unexpected error occurred: {e}. Aborting.")
            success = False
            break

    # --- Loop Finished ---
    if success:
        logger.info("Pixel Toaster finished successfully.")
        return 0
    else:
        # Failure message logic (similar to before)
        if attempts >= max_retry_attempts:
            if current_user_prompt:  # Indicates failure setting up retry
                logger.warning("Maximum retry attempts reached after command failure. Exiting.", exc_info=args.verbose)
                print("\nMaximum retry attempts reached. The command could not be successfully executed.")
            elif not last_generated_command and not args.dry_run:
                logger.warning("Maximum attempts reached, failed to generate a valid command. Exiting.", exc_info=args.verbose)
                print("\nMaximum attempts reached. Could not successfully generate a command.")
            else:
                logger.warning("Maximum attempts reached. Exiting.", exc_info=args.verbose)
                print("\nMaximum attempts reached. Could not successfully complete the operation.")
        elif not last_generated_command and not args.dry_run:
            logger.warning("Exited without generating a command (e.g., LLM refusal or early error).", exc_info=args.verbose)
        else:
            logger.warning("Pixel Toaster finished with errors.", exc_info=args.verbose)
            # Error message likely printed by exception handlers or execution failure block

        return 1