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