import json
import re
import shlex
import logging
import openai
from dotenv import load_dotenv
from compression_utils import extract_target_file_size, needs_compression

class CommandGenerator:
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
    
    def __init__(self, max_retries: int = 3, temperature: float = 0.0):
        load_dotenv()
        self.max_retries = max_retries
        self.temperature = temperature

    def clean_json_response(self, response_str: str) -> str:
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

    def generate_command(self, user_query: str, error_message: str = None) -> str:
        # Check if the query has a file size constraint or general compression request.
        target_size = extract_target_file_size(user_query)
        if target_size:
            # Append instruction with the exact target size in bytes.
            user_query += f"\nEnsure the output file is no larger than {target_size} bytes."
        elif needs_compression(user_query):
            # Otherwise, simply require the output to be compressed.
            user_query += "\nEnsure that the output file is compressed (i.e., smaller than the input file)."

        if error_message:
            user_query += f"\nThe previous command failed with this error:\n{error_message}\nTry another approach."
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_query}
            ],
            temperature=self.temperature
        )
        return response.choices[0].message.content

    def fix_command_quotes(self, command: str) -> str:
        pattern = r'(-vf\s+)(["\'])(.*?)\2'
        match = re.search(pattern, command)
        if match:
            prefix = match.group(1)
            filters = match.group(3)
            filters_fixed = re.sub(
                r'scale\s*=\s*min\(([^)]+)\)',
                lambda m: "scale='min({})'".format(m.group(1)),
                filters,
                flags=re.IGNORECASE
            )
            filters_fixed = filters_fixed.replace('"', '')
            new_vf = prefix + '"' + filters_fixed + '"'
            command = re.sub(pattern, new_vf, command, count=1)
        return command

    def replace_placeholder_with_file(self, command: str, actual_file: str) -> str:
        import shlex
        try:
            tokens = shlex.split(command)
        except Exception:
            tokens = command.split()
        # Look for the "-i" flag and replace the following token with the actual file.
        for idx, token in enumerate(tokens):
            if token.lower() == "-i" and idx + 1 < len(tokens):
                tokens[idx + 1] = actual_file
                break
        try:
            new_command = shlex.join(tokens)
        except AttributeError:
            new_command = ' '.join(shlex.quote(token) for token in tokens)
        return new_command

    def update_output_filename(self, command: str, input_file: str) -> str:
        import os
        from file_manager import IMAGE_EXTENSIONS  # use the defined image extensions
        try:
            tokens = shlex.split(command)
        except Exception:
            tokens = command.split()
        if len(tokens) < 3:
            return command
        output_token = tokens[-1]
        _, out_ext = os.path.splitext(output_token)
        _, in_ext = os.path.splitext(input_file)
        # Force the output extension to match the input if it's an image.
        if in_ext.lower() in IMAGE_EXTENSIONS:
            out_ext = in_ext
        base, _ = os.path.splitext(os.path.basename(input_file))
        new_output = f"{base}_toasted{out_ext}"
        tokens[-1] = new_output
        try:
            new_command = shlex.join(tokens)
        except AttributeError:
            new_command = ' '.join(shlex.quote(token) for token in tokens)
        return new_command