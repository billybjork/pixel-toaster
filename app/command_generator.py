import os
import json
import re
import logging
import openai
from typing import List, Dict, Optional

log = logging.getLogger(__name__) # Use module-specific logger

class CommandGenerator:
    SYSTEM_PROMPT_TEMPLATE = """\

You are an expert assistant specialized in generating FFmpeg commands based on user requests.
Your goal is to provide a single, correct, and safe FFmpeg command or shell loop.

RETURN FORMAT:
Strictly output a JSON object with TWO keys: "explanation" and "command". Do NOT include markdown formatting (```json ... ```) or any other text outside the JSON object.
- "explanation": A list of strings, where each string briefly explains a part or flag of the generated command/loop. Explain ALL parts.
- "command": A single string containing the complete command(s) to be executed (this might be a single FFmpeg command OR a shell loop containing an FFmpeg command).

SYSTEM CONTEXT:
The command will be executed on the user's system with the following details:
- Operating System: {os_info} ({os_type})
- Default Shell: {shell} (Assume bash/zsh compatible unless shell is explicitly 'cmd.exe')
- FFmpeg Version: {ffmpeg_version}
- FFmpeg Path: {ffmpeg_executable_path}
- Current Directory: {current_directory}
{file_context}

COMMAND GENERATION RULES:
1.  **Command Structure:** Generate a single command string. This string might contain just one FFmpeg command OR a shell loop structure calling FFmpeg.
2.  **Batch Processing (VERY IMPORTANT):**
    *   If the user request implies processing **multiple files** (e.g., using words like "all", "every", "batch", or a wildcard like `*.ext`) AND the FILE CONTEXT (`detected_files_in_directory:`) lists multiple relevant files, you **MUST** generate a **shell loop** suitable for the detected `{shell}`.
    *   **Do NOT generate a command for only the first detected file in batch requests.**
    *   **Wildcard Case Sensitivity:** Be mindful of case sensitivity in file patterns (e.g., `.mov` vs `.MOV`). If possible, generate a pattern that matches common variations. For bash/zsh, you might use extended globbing if enabled (`shopt -s extglob; for file in *.@(mov|MOV); ...`) or simply list both patterns if safe (`for file in *.mov *.MOV; ...`). If unsure, use a pattern matching the case shown in `detected_files_in_directory` or generate separate loops/patterns if mixed cases are likely. **Avoid patterns that might fail with "no matches found" errors if possible.** Use `nullglob` (`shopt -s nullglob; for ...`) in bash/zsh if the loop should simply do nothing when no files match.
    *   **Example Loop (bash/zsh with case handling & nullglob):** `sh -c 'shopt -s nullglob extglob; for file in "$PWD"/*.@(mov|MOV); do "{ffmpeg_executable_path}" -i "$file" [OPTIONS] "${{file%.*}}_toasted.${{file##*.}}" -y; done'` (Uses `sh -c` for robustness, sets nullglob/extglob, uses `$PWD` for CWD, tries to preserve original extension case in output). Adapt the pattern `@(mov|MOV)` based on the user request. Ensure proper quoting (`"$file"`, `"${{...}}"`)!
    *   If only one relevant file is detected or specified (`explicit_input_file:`), generate a single FFmpeg command, not a loop.
3.  **Input Files (Single Command):** Use the specific input file path from `explicit_input_file:` or the single relevant file from `detected_files_in_directory:`. Ensure it's correctly quoted.
4.  **Output Filenames:** Generate sensible output filenames. Append `_toasted`. Preserve original extension if possible using parameter expansion (e.g., `${{file##*.}}`). Place output files in the `{current_directory}` unless the user specifies otherwise.
5.  **Overwrite Confirmation (`-y` flag - CRITICAL):** **ALWAYS** include the `-y` flag at the end of the FFmpeg command (inside the loop if applicable) to automatically overwrite output files.
6.  **Trimming (IMPORTANT):** Use the `-t <duration>` output option: `-ss 0 -i <input> -t <duration> ... <output> -y`. Optionally add `-c copy`. **Avoid using only video filters like `-vf trim` for duration limiting.**
7.  **Quoting:** Crucial for filenames, paths, filter arguments, *especially* within shell loops and `sh -c '...'` contexts. Double-check escaping if needed.
8.  **Safety:** No malicious/destructive commands. If unsafe/impossible, set "command" to "" and explain.
9.  **Clarity:** Explain all parts of the command/loop.
10. **Error Handling:** If given a previous error (like "no matches found" or FFmpeg errors), analyze it and provide a corrected command/loop. If "no matches found", fix the file pattern (case, path) or use `nullglob`.

"""

    # --- __init__ Method ---
    # Accepts model name from config, assumes API key is globally set
    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.1):
        """
        Initializes the CommandGenerator.

        Args:
            model: The name of the OpenAI model to use (e.g., "gpt-4o-mini").
                   This should be passed from the loaded configuration.
            temperature: The sampling temperature for the LLM.
        """
        # API key is assumed to be set globally via openai.api_key = loaded_key in main.py
        self.model = model
        self.temperature = temperature
        log.debug(f"CommandGenerator initialized with model: {self.model}, temperature: {self.temperature}")


    # --- clean_json_response Method ---
    # Remains unchanged
    def clean_json_response(self, response_str: str) -> str:
        """
        Cleans common markdown formatting issues around JSON responses from LLMs.
        Attempts to extract the outermost JSON object. Robustly handles variations.
        """
        if not isinstance(response_str, str):
             log.warning(f"clean_json_response received non-string input: {type(response_str)}")
             return "" # Return empty string for non-string input

        response_str = response_str.strip()

        # 1. Remove markdown code blocks (```json ... ``` or ``` ... ```)
        match = re.match(r"^\s*```(?:json)?\s*(.*)\s*```\s*$", response_str, re.DOTALL | re.IGNORECASE)
        if match:
             response_str = match.group(1).strip()

        # 2. Find the first '{' and the last '}' to define the JSON boundaries
        try:
            start_index = response_str.index("{")
            end_index = response_str.rindex("}") + 1
            response_str = response_str[start_index:end_index]
        except ValueError:
            # If no '{' or '}' found, it's likely not JSON.
            log.warning("Could not find JSON object boundaries '{...}' in LLM response after cleaning markdown.")
            # Let's check if it *might* be valid JSON without braces (unlikely for object)
            # but return the cleaned string for now, parsing will fail later if needed.
            return response_str # Return stripped string, parse attempt will clarify

        # 3. Optional: Further checks/cleaning if needed (e.g., removing trailing commas - complex)
        # For now, rely on json.loads to validate

        return response_str


    # --- generate_command Method ---
    # Remains largely unchanged, but logs the model being used and uses self.model
    def generate_command(self, conversation_history: List[Dict[str, str]], system_context: Dict[str, str]) -> str:
        """
        Generates the FFmpeg command using the LLM, incorporating context and conversation history.
        Uses the model specified during initialization and the globally configured API key.
        """
        # --- Format File Context (remains the same) ---
        file_context_str = "\nFILE CONTEXT:\n"
        explicit_file = system_context.get("explicit_input_file")
        detected_files = system_context.get("detected_files_in_directory")
        cwd = system_context.get("current_directory", ".")

        if explicit_file:
            file_context_str += f"- Explicit input file provided: '{explicit_file}' (Use this exact path)\n"
        if detected_files:
            relative_files_for_prompt = []
            for f_abs in detected_files:
                 try:
                     rel_path = os.path.relpath(f_abs, cwd)
                     if len(rel_path) < len(f_abs) and '../' not in rel_path[3:]:
                         relative_files_for_prompt.append(rel_path)
                     else:
                         relative_files_for_prompt.append(f_abs)
                 except ValueError:
                     relative_files_for_prompt.append(f_abs)

            files_list_str = ", ".join([f"'{f}'" for f in relative_files_for_prompt])
            file_context_str += f"- Media files found in directory '{cwd}': {files_list_str}\n"
            file_context_str += f"- Note: In the generated command, use full absolute paths for these files where necessary (e.g., '{detected_files[0]}' ...).\n"

        summary_msg = system_context.get("file_context_message","")
        if summary_msg and not explicit_file and not detected_files:
             file_context_str += f"- Additional context: {summary_msg}\n"
        elif not explicit_file and not detected_files:
             file_context_str += f"- No specific input file provided or common media files detected in the directory '{cwd}'.\n"


        # --- Construct System Prompt (remains the same) ---
        try:
            formatted_system_prompt = self.SYSTEM_PROMPT_TEMPLATE.format(
                os_info=system_context.get('os_info', 'Unknown'),
                os_type=system_context.get('os_type', 'Unknown'),
                shell=system_context.get('shell', 'Unknown'),
                ffmpeg_version=system_context.get('ffmpeg_version', 'Unknown'),
                ffmpeg_executable_path=system_context.get('ffmpeg_executable_path', 'ffmpeg'),
                current_directory=cwd,
                file_context=file_context_str
            )
        except KeyError as e:
             log.error(f"Missing key in system_context for prompt formatting: {e}")
             raise ValueError(f"System context dictionary is missing required key: {e}") from e

        # --- Prepare Messages (remains the same) ---
        messages = [{"role": "system", "content": formatted_system_prompt}]
        valid_history = [msg for msg in conversation_history if msg.get("content")]
        messages.extend(valid_history)

        log.debug(f"Sending messages to LLM (model: {self.model}): {json.dumps(messages, indent=2)}")

        # --- Make API Call (uses self.model, relies on global API key) ---
        try:
            # NOTE: openai.api_key is used implicitly by the library if set globally
            response = openai.chat.completions.create(
                model=self.model, # Use the model name stored in self.model
                messages=messages,
                temperature=self.temperature,
                response_format={"type": "json_object"} # Request JSON output
            )
            content = response.choices[0].message.content
            log.debug(f"LLM raw choice content: {content}")

            if not content:
                 log.warning("LLM returned empty content.")
                 # Return structure indicating failure but parsable
                 return json.dumps({"explanation": ["LLM returned empty content."], "command": ""})

            return content

        # --- Error Handling (remains the same, includes specific OpenAI errors) ---
        except openai.APIConnectionError as e:
            log.error(f"OpenAI API connection error: {e}")
            raise # Re-raise to be caught by the main loop in app.py
        except openai.RateLimitError as e:
            log.error(f"OpenAI API rate limit exceeded: {e}")
            raise
        except openai.AuthenticationError as e:
            # This might indicate the globally set key is invalid
            log.error(f"OpenAI API authentication error (invalid key?): {e}")
            raise
        except openai.PermissionDeniedError as e:
            log.error(f"OpenAI API permission denied error: {e}")
            raise
        except openai.APIStatusError as e:
            log.error(f"OpenAI API status error: {e.status_code} - {e.response}")
            raise
        except Exception as e:
            # Catch any other unexpected errors during the API call
            log.exception(f"Unexpected error during OpenAI API call:") # Use exception to log traceback
            raise # Re-raise for handling in the main loop