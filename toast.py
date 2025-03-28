#!/usr/bin/env python3
"""
pixl-toastr: A natural language FFmpeg command generator.
This tool uses ChatGPT (via the OpenAI API) to convert natural language prompts
into executable FFmpeg commands.
"""

import os
import sys
import json
import subprocess
import openai
import logging
import argparse
import re
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# ---------------------------------------------------------------------
# Logging configuration with timestamp
logging.basicConfig(
    format="%(asctime)s - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)

# Media file extensions
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".aac", ".flac"}

# System prompt: Note the explicit instruction to return only raw JSON (no markdown).
SYSTEM_PROMPT = """\
You are an FFmpeg command generator. 
Return your result strictly as a JSON object with exactly the following schema, and do not include any markdown formatting or additional text:

{"command": "the ffmpeg command"}

GENERAL RULES:
1. Output exactly one valid FFmpeg command.
2. Do not use shell loops, piping, semicolons, or any extraneous syntax.
3. If multiple input files are needed, use built-in FFmpeg techniques.
4. If an input filename is known or provided, include it in the command.
5. Always start the command with 'ffmpeg'.
6. Do not include any explanation or markdown formatting; return only raw JSON.
"""

MAX_RETRIES = 3

def clean_json_response(response_str):
    """
    Extract a JSON object from the LLM response:
      - Remove markdown code block markers if present.
      - Extract the text between the first '{' and the last '}'.
    """
    response_str = response_str.strip()
    if response_str.startswith("```") and response_str.endswith("```"):
        lines = response_str.splitlines()
        if len(lines) >= 3:
            response_str = "\n".join(lines[1:-1])
        else:
            response_str = response_str.strip("```")
    try:
        start = response_str.index("{")
        end = response_str.rindex("}") + 1
        response_str = response_str[start:end]
    except ValueError:
        pass
    return response_str

def fix_command_quotes(command):
    """
    Fix quoting issues in the generated FFmpeg command.
    
    This function:
      1. Looks for a -vf argument and extracts its filter string.
      2. In the filter chain, finds scale filters written as scale=min(400,iw)
         and wraps the min() expression in single quotes to produce:
         scale='min(400,iw)'
      3. Then, ensures the entire -vf filter string is wrapped in double quotes.
    """
    pattern = r'(-vf\s+)(["\'])(.*?)\2'
    match = re.search(pattern, command)
    if match:
        prefix = match.group(1)
        orig_quote = match.group(2)
        filters = match.group(3)
        # Fix the scale filter: wrap min(...) in single quotes if not already
        filters_fixed = re.sub(
            r'scale\s*=\s*min\(([^)]+)\)',
            lambda m: "scale='min({})'".format(m.group(1)),
            filters,
            flags=re.IGNORECASE
        )
        # Remove any stray double quotes within filters_fixed
        filters_fixed = filters_fixed.replace('"', '')
        new_vf = prefix + '"' + filters_fixed + '"'
        command = re.sub(pattern, new_vf, command, count=1)
    return command

def extract_explicit_filename(user_query):
    """
    Return a filename if a token in the user query looks like a file name with a known extension.
    This avoids mistakenly capturing numbers (e.g. "12.5").
    """
    pattern = r'\b(?=[A-Za-z0-9_-]*[A-Za-z])[A-Za-z0-9_-]+\.(?:mp4|mov|mkv|avi|webm|png|jpg|jpeg|bmp|tiff|gif)\b'
    matches = re.findall(pattern, user_query, re.IGNORECASE)
    return matches[0] if matches else None

def detect_single_file_in_dir(dir_path, exts):
    """
    Return the filename if exactly one file in dir_path matches any extension in exts.
    Otherwise, return None.
    """
    matches = []
    for f in os.listdir(dir_path):
        full_path = os.path.join(dir_path, f)
        if os.path.isfile(full_path):
            _, ext = os.path.splitext(f)
            if ext.lower() in exts:
                matches.append(f)
    return matches[0] if len(matches) == 1 else None

def list_files_in_dir(dir_path, exts):
    """
    Return a list of filenames in dir_path that match any extension in exts.
    """
    matches = []
    for f in os.listdir(dir_path):
        full_path = os.path.join(dir_path, f)
        if os.path.isfile(full_path):
            _, ext = os.path.splitext(f)
            if ext.lower() in exts:
                matches.append(f)
    return matches

def analyze_prompt_for_filetype(user_query):
    """
    Determine if the user query explicitly names a file.
    If not, use keywords to guess the file type.
    Returns (detected_ext_set, explicit_filename_found).
    """
    explicit_filename = extract_explicit_filename(user_query)
    if explicit_filename:
        return (None, explicit_filename)
    lower_query = user_query.lower()
    if "video" in lower_query or "mp4" in lower_query or "mov" in lower_query or "mkv" in lower_query:
        return (VIDEO_EXTENSIONS, None)
    elif "image" in lower_query or "png" in lower_query or "jpg" in lower_query:
        return (IMAGE_EXTENSIONS, None)
    elif "audio" in lower_query or "mp3" in lower_query or "wav" in lower_query:
        return (AUDIO_EXTENSIONS, None)
    elif "gif" in lower_query:
        return (VIDEO_EXTENSIONS, None)
    return (None, None)

def replace_placeholder_with_file(command, actual_file):
    """
    Replace any generic placeholder filename (like 'input.mp4') with the actual filename.
    """
    if actual_file not in command:
        pattern = r"input\.[a-z0-9]+"
        command = re.sub(pattern, actual_file, command, flags=re.IGNORECASE)
    return command

def generate_ffmpeg_command(user_query, error_message=None):
    """
    Call the OpenAI Chat API with the user query (and optional error context)
    and return the raw response.
    """
    if error_message:
        user_query += f"\nThe previous command failed with this error:\n{error_message}\nTry another approach."
    response = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_query}
        ],
        temperature=0.0
    )
    return response.choices[0].message.content

def run_ffmpeg_command(command):
    """
    Execute the given command string via subprocess and return (success, output).
    """
    try:
        completed_process = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True
        )
        if completed_process.returncode == 0:
            return True, completed_process.stdout
        else:
            return False, completed_process.stderr
    except Exception as e:
        return False, str(e)

def main():
    parser = argparse.ArgumentParser(
        description="pixl-toastr: Natural language FFmpeg command generator."
    )
    parser.add_argument("query", nargs="+", help="Your natural language prompt for FFmpeg.")
    parser.add_argument("--dry-run", action="store_true", help="Show the generated command without executing it.")
    parser.add_argument("--file", type=str, help="Specify an input file explicitly.")
    parser.add_argument("--confirm", action="store_true", help="Ask for confirmation before executing the command.")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output.")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    user_query = " ".join(args.query)
    logging.info(f"Interpreting your request: {user_query}")

    detected_file = None
    # Use the explicit file flag if provided
    if args.file:
        logging.info(f"Using explicit file: {args.file}")
        detected_file = args.file
        user_query += f"\n(Use the file '{detected_file}' as input.)"
    else:
        ext_set, explicit_file = analyze_prompt_for_filetype(user_query)
        if explicit_file:
            logging.info(f"Found an explicit file in the prompt: {explicit_file}")
            detected_file = explicit_file
        elif ext_set is not None:
            found_file = detect_single_file_in_dir(".", ext_set)
            if found_file:
                logging.info(f"Found a single matching file: {found_file}")
                detected_file = found_file
                user_query += f"\n(We found a single file named '{found_file}' in the directory. Please use that as input.)"
            else:
                files = list_files_in_dir(".", ext_set)
                if files:
                    logging.info(f"Found multiple files: {', '.join(files)}")
                    file_list = ", ".join(files)
                    user_query += f"\n(Found these files in the directory: {file_list}. Please choose the correct one as input.)"
    
    attempt = 0
    error_message = None

    while attempt < MAX_RETRIES:
        attempt += 1
        logging.info(f"--- Attempt #{attempt} ---")
        json_string = generate_ffmpeg_command(user_query, error_message)
        logging.debug(f"LLM response (raw): {json_string}")
        
        cleaned_json = clean_json_response(json_string)
        logging.debug(f"LLM response (cleaned): {cleaned_json}")
        
        try:
            parsed = json.loads(cleaned_json)
            ffmpeg_command = parsed.get("command", "").strip()
        except json.JSONDecodeError as e:
            logging.error("LLM did not return valid JSON after cleaning.")
            error_message = f"JSON parse error: {e}. Original response: {json_string}"
            time.sleep(2 ** attempt)
            continue

        if not ffmpeg_command or not ffmpeg_command.startswith("ffmpeg"):
            logging.error("Invalid command received from LLM:")
            logging.error(cleaned_json)
            error_message = f"Invalid command: {cleaned_json}"
            time.sleep(2 ** attempt)
            continue

        if detected_file:
            ffmpeg_command = replace_placeholder_with_file(ffmpeg_command, detected_file)
        
        ffmpeg_command = fix_command_quotes(ffmpeg_command)
        logging.info(f"Proposed command: {ffmpeg_command}")

        # Optional user confirmation before executing
        if args.confirm:
            confirm = input("Execute this command? (y/N): ").strip().lower()
            if confirm != "y":
                logging.info("Command execution cancelled by user.")
                sys.exit(0)

        if args.dry_run:
            logging.info("Dry-run mode enabled. Exiting without executing the command.")
            sys.exit(0)
        
        success, output = run_ffmpeg_command(ffmpeg_command)
        if success:
            logging.info("Command executed successfully!")
            logging.debug(f"Command output: {output}")
            sys.exit(0)
        else:
            logging.error("Command failed. Error message:")
            logging.error(output)
            error_message = output
            logging.info("Retrying...\n")
            time.sleep(2 ** attempt)
    
    logging.error("Maximum retries exceeded. Exiting with error.")
    sys.exit(1)

if __name__ == "__main__":
    main()