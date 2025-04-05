import os
import platform
import shutil
import subprocess
import logging as log
import sys
from typing import Tuple, Optional
from pathlib import Path

VERBOSE = False  # Global verbose flag for conditional traceback logging

# --- Paths (Consider moving USER_CONFIG_DIR here if used often by utils) ---
# USER_HOME = Path.home()
# USER_CONFIG_DIR = USER_HOME / ".config" / "toast" # Standard XDG base dir location

# --- Art ---
def print_art():
    """Prints the Toast ASCII art."""
    art = r"""
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣄⠀⠀⠀⢀⡀⠀⠀⠀⣀⡀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢰⣟⠁⠀⠀⣴⡏⠁⠀⠀⣾⡋⠁⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⠿⠄⠀⠈⠻⠷⠀⠀⠈⢹⣷⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣤⣤⣤⣤⣤⣤⣤⣤⣤⣀⠀⠠⣤⣀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠰⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠀⣹⣿⡿⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⠛⠛⠀⠛⠛⠛⠛⠉⠛⠛⠛⠀⠐⠛⠛⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⣠⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣦⠀⠀⠀
⠀⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀
⠀⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀
⠀⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠿⠛⠛⠿⣿⡇⠀⠀
⠀⠀⠀⠀⠀⠀⠸⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠿⠏⢠⣾⣿⣦⠘⠇⠀⠀
⠀⠀⢀⣤⡀⠀⢰⣶⣶⣶⣶⣶⣶⣶⣶⣶⣶⣶⣶⣶⣶⣶⣆⠘⢿⣿⠟⢠⡆⠀⠀
⠀⠀⠘⠛⠛⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣤⣤⣶⣿⡇⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⢠⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⣄⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠘⠛⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⠛⠀⠀⠀⠀⠀⠀
"""
    print(art)

# --- System Info Gathering ---
def get_ffmpeg_executable() -> str:
    """Finds the ffmpeg executable path using shutil.which."""
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path is None:
        raise FileNotFoundError("ffmpeg executable not found in system PATH.")
    return ffmpeg_path

def get_ffmpeg_version(ffmpeg_exe: str) -> str:
    """Gets the first line of the ffmpeg version output."""
    try:
        # Run ffmpeg -version
        result = subprocess.run(
            [ffmpeg_exe, "-version"],
            capture_output=True,
            text=True,
            check=False,  # Don't raise exception on non-zero exit (might output version to stderr)
            timeout=5     # Prevent hanging
        )
        # FFmpeg might print version to stdout or stderr
        output = result.stdout if "ffmpeg version" in result.stdout.lower() else result.stderr
        # Extract the first line if output exists
        if output and output.splitlines():
            first_line = output.splitlines()[0].strip()
            # Return the first line if it looks like a version string
            if "version" in first_line.lower():
                return first_line
            else:
                # Fallback to returning the whole output if first line isn't version
                log.warning(f"Could not parse version from first line: '{first_line}'. Returning full output.")
                return output.strip()
        else:
            return "Could not determine version (no output)."
    except FileNotFoundError:
        log.warning(f"ffmpeg executable '{ffmpeg_exe}' not found during version check.", exc_info=VERBOSE)
        return "Unknown (executable not found)"
    except subprocess.TimeoutExpired:
        log.warning("ffmpeg -version command timed out.", exc_info=VERBOSE)
        return "Unknown (timeout)"
    except Exception as e:
        log.warning(f"Could not get ffmpeg version using '{ffmpeg_exe}': {e}", exc_info=VERBOSE)
        return "Unknown (error)"

def get_os_info() -> Tuple[str, str]:
    """Gets the OS type and detailed OS information string."""
    os_type = platform.system()
    os_release = platform.release()
    os_machine = platform.machine()
    os_info_str = f"{os_type} {os_release} {os_machine}".strip()
    return os_type, os_info_str

def get_default_shell() -> Optional[str]:
    """Tries to determine the default user shell."""
    shell = os.getenv("SHELL")
    if shell:
        return shell

    # Basic platform specific fallbacks
    os_type = platform.system()
    if os_type == "Windows":
        return os.getenv("COMSPEC", "cmd.exe")
    elif os_type in ["Linux", "Darwin"]:  # macOS is Darwin
        # Check common shells in standard locations
        if shutil.which('bash'):
            return shutil.which('bash')
        if shutil.which('zsh'):  # Add zsh check
            return shutil.which('zsh')
        if shutil.which('sh'):
            return shutil.which('sh')
    return None  # Could not determine

# --- Error Printing ---
def eprint(*args, **kwargs):
    """Prints messages to stderr."""
    print(*args, file=sys.stderr, **kwargs)