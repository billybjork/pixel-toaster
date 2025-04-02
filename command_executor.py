import subprocess
import shlex
import time
import logging

class CommandExecutor:
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries

    def run_command(self, command: str) -> tuple[bool, str]:
        """
        Run the given shell command and return (success, output).
        """
        # Inside run_command
        try:
            # Split the command into a list of arguments
            command_list = shlex.split(command)
            # Ensure 'ffmpeg' is the first element if needed, though shlex should handle paths
            if not command_list:
                return False, "Empty command"

            completed_process = subprocess.run(
                command_list, # Pass the list here
                # shell=False, # Default, safer
                capture_output=True,
                text=True,
                check=False # Don't raise exception on non-zero exit code
            )
            if completed_process.returncode == 0:
                return True, completed_process.stdout
            else:
                # Combine stdout and stderr for more context on failure
                error_output = f"Exit Code: {completed_process.returncode}\nStderr: {completed_process.stderr}\nStdout: {completed_process.stdout}"
                return False, error_output.strip()
        except FileNotFoundError:
            return False, f"Error: 'ffmpeg' command not found. Is FFmpeg installed and in your PATH?"
        except Exception as e:
            return False, f"Subprocess execution error: {str(e)}"

    def execute_with_retries(self, command: str, confirm: bool = False, dry_run: bool = False) -> tuple[bool, str]:
        """
        Execute the command with retries and exponential backoff.
        """
        attempt = 0
        error_message = None
        while attempt < self.max_retries:
            attempt += 1
            logging.info(f"--- Attempt #{attempt} ---")
            if confirm:
                user_input = input("Execute this command? (y/N): ").strip().lower()
                if user_input != "y":
                    logging.info("Command execution cancelled by user.")
                    return False, "User cancelled"
            if dry_run:
                logging.info("Dry-run mode enabled. Exiting without executing the command.")
                return True, "Dry-run: command not executed"
            success, output = self.run_command(command)
            if success:
                logging.info("Command executed successfully!")
                return True, output
            else:
                logging.error("Command failed with error:")
                logging.error(output)
                error_message = output
                time.sleep(2 ** attempt)
        return False, error_message