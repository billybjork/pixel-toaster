import os
import re
import logging
from typing import List, Optional, Set

# Supported file extensions
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".gif"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".heic"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".aac", ".flac"}

# Combine all extensions into one set for unified regex generation
ALL_EXTENSIONS = VIDEO_EXTENSIONS | IMAGE_EXTENSIONS | AUDIO_EXTENSIONS

# Generate a regex pattern from the supported extensions (removing the dot)
ext_pattern = '|'.join(re.escape(ext.lstrip('.')) for ext in ALL_EXTENSIONS)

class FileManager:
    def __init__(self, directory: str = "."):
        self.directory = os.path.abspath(directory)  # Use absolute path
        if not os.path.isdir(self.directory):
            logging.warning(f"Target directory does not exist: {self.directory}. File listing might be empty.")

    def extract_explicit_filename(self, user_query: str) -> Optional[str]:
        """
        Look for potential filenames with common media extensions in the query.
        This is a simple check and might need refinement based on edge cases.
        It prioritizes filenames with extensions.
        """
        # Regex to find quoted filenames (e.g., "filename.mp4")
        quoted_pattern = rf'["\']([^"\']+\.({ext_pattern}))["\']'
        quoted_matches = re.findall(quoted_pattern, user_query, re.IGNORECASE)
        if quoted_matches:
            # re.findall returns a list of tuples (filename, extension)
            potential_filename = quoted_matches[0][0]
            potential_file = os.path.join(self.directory, potential_filename)
            if os.path.isfile(potential_file):
                return potential_file  # Return full path
            else:
                logging.debug(f"Found quoted potential filename '{potential_filename}' in query, but it doesn't exist locally.")

        # Regex to find unquoted filenames (more restrictive characters)
        unquoted_pattern = rf'\b([a-zA-Z0-9_.-]+\.({ext_pattern}))\b'
        unquoted_matches = re.findall(unquoted_pattern, user_query, re.IGNORECASE)
        if unquoted_matches:
            for match in unquoted_matches:
                fname = match[0]  # The full filename
                potential_file = os.path.join(self.directory, fname)
                if os.path.isfile(potential_file):
                    return potential_file  # Return full path
            logging.debug(f"Found unquoted potential filenames {[match[0] for match in unquoted_matches]} in query, but none exist locally.")

        # Basic check: if a token *exactly* matches an existing file (case-insensitive)
        tokens = re.findall(r'\b[\w.-]{3,}\b', user_query)  # Find words >= 3 chars
        try:
            local_files = {f.lower(): f for f in os.listdir(self.directory) if os.path.isfile(os.path.join(self.directory, f))}
            for token in tokens:
                if token.lower() in local_files:
                    _, ext = os.path.splitext(local_files[token.lower()])
                    if ext.lower() in ALL_EXTENSIONS:
                        return os.path.join(self.directory, local_files[token.lower()])  # Return full path
        except FileNotFoundError:
            logging.warning(f"Directory not found when checking tokens: {self.directory}")
        except Exception as e:
            logging.error(f"Error during token matching: {e}")

        return None  # No explicit file found and verified

    def list_files(self, exts: Set[str]) -> List[str]:
        """
        List files in the directory that match any of the extensions.
        Returns a list of full paths.
        """
        matches = []
        try:
            for f in os.listdir(self.directory):
                full_path = os.path.join(self.directory, f)
                if os.path.isfile(full_path):
                    _, ext = os.path.splitext(f)
                    if ext.lower() in exts:
                        matches.append(full_path)  # Append full path
        except FileNotFoundError:
            logging.warning(f"Directory not found for listing files: {self.directory}")
        except Exception as e:
            logging.error(f"Error listing files in {self.directory}: {e}")
        return matches