import os
import re
import logging
from typing import List, Optional, Set

# Supported file extensions
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".gif"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".heic"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".aac", ".flac"}

class FileManager:
    def __init__(self, directory: str = "."):
        self.directory = os.path.abspath(directory) # Use absolute path
        if not os.path.isdir(self.directory):
            logging.warning(f"Target directory does not exist: {self.directory}. File listing might be empty.")

    def extract_explicit_filename(self, user_query: str) -> Optional[str]:
        """
        Look for potential filenames with common media extensions in the query.
        This is a simple check and might need refinement based on edge cases.
        It prioritizes filenames with extensions.
        """
        # Regex to find words that look like filenames with known extensions
        # Allows for spaces if quoted, or common filename characters otherwise
        # Handles quoted filenames first
        quoted_pattern = r'["\']([^"\']+\.(?:mp4|mov|mkv|avi|webm|png|jpg|jpeg|bmp|tiff|gif|heic|mp3|wav|aac|flac))["\']'
        quoted_matches = re.findall(quoted_pattern, user_query, re.IGNORECASE)
        if quoted_matches:
            # Check if the extracted filename actually exists
            potential_file = os.path.join(self.directory, quoted_matches[0])
            if os.path.isfile(potential_file):
                 return potential_file # Return full path
            else:
                 # Maybe it was an output filename suggestion? Log it.
                 logging.debug(f"Found quoted potential filename '{quoted_matches[0]}' in query, but it doesn't exist locally.")

        # Then check for unquoted filenames (more restrictive characters)
        unquoted_pattern = r'\b([a-zA-Z0-9_.-]+\.(?:mp4|mov|mkv|avi|webm|png|jpg|jpeg|bmp|tiff|gif|heic|mp3|wav|aac|flac))\b'
        unquoted_matches = re.findall(unquoted_pattern, user_query, re.IGNORECASE)
        if unquoted_matches:
            # Check existence for unquoted matches too
            for fname in unquoted_matches:
                 potential_file = os.path.join(self.directory, fname)
                 if os.path.isfile(potential_file):
                     return potential_file # Return full path
            logging.debug(f"Found unquoted potential filenames {unquoted_matches} in query, but none exist locally.")

        # Basic check: if a token *exactly* matches an existing file (case-insensitive)
        tokens = re.findall(r'\b[\w.-]{3,}\b', user_query) # Find words >= 3 chars
        try:
            local_files = {f.lower(): f for f in os.listdir(self.directory) if os.path.isfile(os.path.join(self.directory, f))}
            for token in tokens:
                if token.lower() in local_files:
                    # Check if it has a media extension before returning
                    _, ext = os.path.splitext(local_files[token.lower()])
                    if ext.lower() in (VIDEO_EXTENSIONS | IMAGE_EXTENSIONS | AUDIO_EXTENSIONS):
                        return os.path.join(self.directory, local_files[token.lower()]) # Return full path
        except FileNotFoundError:
             logging.warning(f"Directory not found when checking tokens: {self.directory}")
        except Exception as e:
             logging.error(f"Error during token matching: {e}")


        return None # No explicit file found and verified

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
                        matches.append(full_path) # Append full path
        except FileNotFoundError:
            logging.warning(f"Directory not found for listing files: {self.directory}")
        except Exception as e:
            logging.error(f"Error listing files in {self.directory}: {e}")
        return matches