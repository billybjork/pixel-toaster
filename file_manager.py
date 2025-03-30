import os
import re
import shlex
import logging
from typing import List, Optional, Tuple, Union

# Supported file extensions
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".aac", ".flac"}

class FileManager:
    def __init__(self, directory: str = "."):
        self.directory = directory

    def extract_explicit_filename(self, user_query: str) -> Optional[str]:
        """
        Look for a token in the query that looks like a filename.
        """
        pattern = r'\b(?=[A-Za-z0-9_-]*[A-Za-z])[A-Za-z0-9_-]+\.(?:mp4|mov|mkv|avi|webm|png|jpg|jpeg|bmp|tiff|gif)\b'
        matches = re.findall(pattern, user_query, re.IGNORECASE)
        return matches[0] if matches else None

    def fuzzy_match_filename(self, user_query: str, ext_set: set = None) -> Optional[str]:
        """
        Try to fuzzy-match a file from the query.
        It extracts tokens (with at least 8 characters) from the query and checks if any file's base name
        (ignoring extension) contains one of those tokens.
        """
        tokens = re.findall(r'\b[\w-]{8,}\b', user_query)
        logging.debug(f"Fuzzy matching tokens: {tokens}")
        candidate_files = []
        if ext_set is None:
            ext_set = VIDEO_EXTENSIONS | IMAGE_EXTENSIONS | AUDIO_EXTENSIONS
        for f in os.listdir(self.directory):
            full_path = os.path.join(self.directory, f)
            if os.path.isfile(full_path):
                base, ext = os.path.splitext(f)
                if ext.lower() in ext_set:
                    for token in tokens:
                        if token.lower() in base.lower():
                            candidate_files.append(f)
                            break
        if len(candidate_files) == 1:
            return candidate_files[0]
        elif len(candidate_files) > 1:
            logging.info("Multiple fuzzy matches found: " + ", ".join(candidate_files))
            # For now, return the first one; later you might want to ask the user to disambiguate.
            return candidate_files[0]
        return None

    def list_files(self, exts: set) -> List[str]:
        """
        List files in the directory that match any of the extensions.
        """
        matches = []
        for f in os.listdir(self.directory):
            full_path = os.path.join(self.directory, f)
            if os.path.isfile(full_path):
                _, ext = os.path.splitext(f)
                if ext.lower() in exts:
                    matches.append(f)
        return matches

    def detect_single_file(self, exts: set) -> Optional[str]:
        """
        Return the filename if exactly one file with matching extension exists.
        """
        files = self.list_files(exts)
        return files[0] if len(files) == 1 else None

    def analyze_prompt_for_filetype(
        self, user_query: str
    ) -> Tuple[Optional[set], Optional[Union[str, List[str]]]]:
        """
        Return a tuple: (set_of_extensions, explicit_filename_or_none).
        """
        explicit = self.extract_explicit_filename(user_query)
        if explicit:
            return (None, explicit)
        lower_query = user_query.lower()
        # Check for video and audio keywords first.
        if "video" in lower_query or re.search(r'\b(mp4|mov|mkv|avi|webm)\b', lower_query):
            return (VIDEO_EXTENSIONS, None)
        # Look for explicit "png file" pattern first.
        if re.search(r'\bpng file\b', lower_query):
            return ({".png"}, None)
        # Then look for explicit "jpg file" or "jpeg file" pattern.
        if re.search(r'\b(jpg|jpeg) file\b', lower_query):
            return ({".jpg", ".jpeg"}, None)
        if "audio" in lower_query or re.search(r'\b(mp3|wav|aac|flac)\b', lower_query):
            return (AUDIO_EXTENSIONS, None)
        if "gif" in lower_query:
            return (VIDEO_EXTENSIONS, None)
        # Fallback for generic images if words "image", "png", or "jpg" appear.
        if "image" in lower_query or "png" in lower_query or "jpg" in lower_query:
            return (IMAGE_EXTENSIONS, None)
        return (None, None)

    def create_filelist_for_concat(
        self, file_list: List[str], filelist_filename: str = "filelist.txt"
    ) -> Optional[str]:
        """
        Create a temporary file list for ffmpeg concat.
        """
        try:
            with open(filelist_filename, "w") as f:
                for filename in file_list:
                    f.write(f"file {shlex.quote(filename)}\n")
            logging.info(f"Created temporary file list: {filelist_filename}")
            return filelist_filename
        except Exception as e:
            logging.error(f"Error creating file list: {e}")
            return None