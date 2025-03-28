#!/usr/bin/env python3

import os
import sys
import json
import subprocess
import openai
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# ---------------------------------------------------------------------
# Updated system prompt that handles ambiguous video filenames
SYSTEM_PROMPT = """\
You are an FFmpeg command generator. 
Output your result in valid JSON, using this exact schema:

{
  "command": "the ffmpeg command"
}

No additional keys. No code blocks. No extra explanation.
Just the JSON as specified.

GENERAL RULES:
1. Output exactly one valid ffmpeg command. 
2. Never use shell loops, piping, semicolons, or other trickery.
3. For multiple image files, you can use:
   - pattern_type glob (e.g., ffmpeg -pattern_type glob -i '*.png' ...)
   - bracket expansions (e.g., ffmpeg -i 'input_%03d.png' ...)
4. For multiple video files, you can use the concat demuxer or any built-in FFmpeg technique (no external files or shell loops).
5. If the user’s request is ambiguous:
   - If they say "all images" or "all .png", assume -pattern_type glob -i '*.png'
   - If they mention a single image but do not specify the exact name, assume -pattern_type glob -i '*.png'
   - If they mention a single video but do not specify the exact name, assume -i '*.mp4'
6. Always start the command with 'ffmpeg'.
7. If you need to guess details, do so conservatively, but never produce an invalid command.
8. Do not return an explanation or anything other than the JSON object described above.

The user wants to execute an FFmpeg command based on their request.
"""

MAX_RETRIES = 3

def generate_ffmpeg_command(user_query, error_message=None):
    """
    Pass the user query + optional error_message to the LLM
    and get back an ffmpeg command in JSON format.
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
    Execute the given command string via subprocess.
    Return (success_boolean, stderr_output).
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
    user_query = " ".join(sys.argv[1:])
    if not user_query.strip():
        print("Usage: toast <your natural language prompt>")
        print("Example: toast convert to gif at 12.5 fps with max file size 5mb")
        sys.exit(1)

    print(f"[toast] Interpreting your request: {user_query}\n")

    attempt = 0
    error_message = None

    while attempt < MAX_RETRIES:
        attempt += 1
        print(f"--- Attempt #{attempt} ---")

        # 1. Generate the FFmpeg command (in JSON format).
        json_string = generate_ffmpeg_command(user_query, error_message)

        # 2. Parse the JSON. If it fails, treat as error.
        try:
            parsed = json.loads(json_string)
            ffmpeg_command = parsed.get("command", "").strip()
        except json.JSONDecodeError as e:
            print("[toast] Error: LLM did not return valid JSON. Full response:\n", json_string)
            error_message = f"JSON parse error: {e}"
            continue

        if not ffmpeg_command or not ffmpeg_command.startswith("ffmpeg"):
            print("[toast] Error: Did not find a valid 'ffmpeg' command. Response:\n", json_string)
            error_message = f"Invalid command: {json_string}"
            continue

        print("[toast] Proposed command:", ffmpeg_command)

        # 3. Run the command
        success, output = run_ffmpeg_command(ffmpeg_command)

        if success:
            print("[toast] Command executed successfully!")
            print(output)
            sys.exit(0)
        else:
            print("[toast] Command failed. Error message:\n", output)
            error_message = output
            print("[toast] Retrying...\n")

    print("[toast] Maximum retries exceeded. Exiting with error.")
    sys.exit(1)

if __name__ == "__main__":
    main()