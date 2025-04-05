# pixel-toaster

Say goodbye to memorizing complex FFmpeg flags or copying and pasting commands from ChatGPT! Just tell `pixel-toaster` what you want to do.

**pixel-toaster** is a command-line tool that allows you to perform media conversions and manipulations using natural language prompts. It leverages the power of LLMs to translate your requests into FFmpeg commands, executes them, and even attempts to automatically fix errors by feeding them back to the LLM.

---

## Features

-   **Natural Language Interface:** Describe your media conversion task in plain English (e.g., "convert video.mp4 to a gif", "make all jpgs grayscale", "extract audio from interview.mov").
-   **FFmpeg Powered:** Generates and executes commands for the powerful FFmpeg library.
-   **LLM Integration:** Uses an LLM (defaults to OpenAI's API, configurable) to interpret your request and generate the appropriate command.
-   **Context-Aware:** Provides the LLM with context about your operating system, shell, FFmpeg version, and files in the current directory to generate more accurate commands.
-   **File Detection:** Automatically detects common video, image, and audio files in the current directory to assist with batch processing prompts.
-   **Batch Processing:** Intelligently generates shell loops (e.g., `for file in *.mp4; do ... done`) when your prompt implies operating on multiple files.
-   **Error Handling & Retry:** If an FFmpeg command fails, `pixel-toaster` captures the error output and asks the LLM to generate a corrected command based on the failure.
-   **Managed Configuration:** Guides you through a secure, interactive first-time setup for your API key. Stores configuration (API key, preferred model, logging settings) in a dedicated user configuration file (`~/.config/pixel-toaster/config.json` or XDG standard path).
-   **Dry Run Mode:** See the command that *would* be executed without actually running it using the `--dry-run` flag.
-   **Explicit File Input:** Specify a particular input file using the `--file` flag.
-   **File Logging:** Records logs to `~/.config/pixel-toaster/toast.log` for debugging (configurable).

---

## Prerequisites

### For Users (Running the Binary)

1.  **FFmpeg:** The core media manipulation tool. You **must** have `ffmpeg` installed and accessible in your system's `PATH`. `pixel-toaster` *does not* bundle FFmpeg.
    *   Download: [ffmpeg.org](https://ffmpeg.org/download.html)
    *   macOS: `brew install ffmpeg`
    *   Debian/Ubuntu: `sudo apt update && sudo apt install ffmpeg`
    *   Windows: Download from the official site or use `choco install ffmpeg` / `winget install ffmpeg`. Ensure the `ffmpeg.exe` location is added to your system's PATH environment variable.
2.  **OpenAI API Key:** You need an API key from OpenAI to use the default LLM backend. Get one at [https://platform.openai.com/signup/](https://platform.openai.com/signup/). You will be prompted for this key the first time you run the tool.

### For Developers (Building from Source)

1.  **Python:** Python 3.8 or newer.
2.  **pip:** Python's package installer.
3.  **Git:** For cloning the repository.
4.  **(Optional but Recommended)** `make`: To use the Makefile commands.
5.  **(Optional)** GitHub CLI (`gh`): For using the `make release-gh` command.

---

## Installation (Recommended Method: Binary Release)

The easiest way to install `pixel-toaster` is by downloading the pre-compiled binary for your operating system. This avoids needing Python installed on your system.

1.  **Go to Releases:** Navigate to the [Releases page](https://github.com/billybjork/pixel-toaster/releases) of the `pixel-toaster` repository.
2.  **Download Binary:** Find the latest release and download the appropriate file for your operating system (e.g., `toast-linux`, `toast-macos`, `toast-windows.exe`).
3.  **Make Executable (Linux/macOS):** Open your terminal and make the downloaded file executable:
    ```bash
    chmod +x /path/to/downloaded/toast-binary
    ```
    *(Replace `/path/to/downloaded/toast-binary` with the actual path and filename)*
4.  **Move to PATH (Recommended):** To run `toast` from any directory, move the executable to a directory included in your system's `PATH`. Common locations include:
    *   **Linux/macOS:** `/usr/local/bin`
    *   **Windows:** A dedicated folder (e.g., `C:\bin`) that you manually add to your user or system PATH environment variable.
    ```bash
    # Example for Linux/macOS:
    sudo mv /path/to/downloaded/toast-binary /usr/local/bin/toast

    # Example for Windows (using PowerShell or CMD):
    # Move the .exe file to a directory in your PATH.
    ```
    *(Moving to system directories like `/usr/local/bin` might require `sudo`)*.

---

## Setting up the `toast` Alias (Optional)

If you moved the binary to a directory in your `PATH` (Step 4 above), you can already run it by typing `toast`.

If you placed the binary somewhere else, or prefer an explicit alias, you can add one to your shell's configuration file.

1.  **Locate the `toast` executable** (the file you downloaded or built).
2.  **Edit your shell configuration file:**
    *   **Bash:** Edit `~/.bashrc` or `~/.bash_profile`
    *   **Zsh:** Edit `~/.zshrc`
    *   **Fish:** Edit `~/.config/fish/config.fish`
3.  **Add the alias line:** Replace `/path/to/your/toast_executable` with the *actual full path* to the binary.
    *   Bash/Zsh: `alias toast='/path/to/your/toast_executable'`
    *   Fish: `alias toast='/path/to/your/toast_executable'`
4.  **Apply the changes:**
    *   Bash: `source ~/.bashrc` (or the file you edited)
    *   Zsh: `source ~/.zshrc`
    *   Fish: Changes apply automatically in new terminals, or run `source ~/.config/fish/config.fish`.

Now you can run the tool simply by typing: `toast "your prompt here"`

---

## Configuration (First Run Setup)

`pixel-toaster` handles its own configuration securely.

1.  **First Execution:** The very first time you run `toast` (e.g., `toast "a simple prompt"`), it will detect that it hasn't been configured yet.
2.  **API Key Prompt:** It will securely prompt you to enter your OpenAI API key. The key will *not* be echoed to the terminal.
    ```
    --- Pixel Toaster First-Time Setup ---
    Configuration will be saved to: /Users/your_user/.config/pixel-toaster/config.json
    Please enter your OpenAI API Key (starts with 'sk-'): ****
    ```
3.  **Configuration Saved:** Once you enter a valid key, the script will create the necessary directory (`~/.config/pixel-toaster` by default, respecting `XDG_CONFIG_HOME` if set) and save the configuration.

### The Configuration File (`~/.config/pixel-toaster/config.json`)

Your configuration is stored in a JSON file like this:

```json
{
    "openai_api_key": "sk-...",
    "llm_model": "gpt-4o-mini",
    "log_level": "INFO",
    "log_to_file": true
}

You generally don't need to edit this manually, but you can change the model or logging preferences here.

---

## Usage

Run the tool from your terminal using the toast command (assuming it's in your PATH or you set up an alias), followed by your natural language prompt.

### Basic Syntax

```bash
toast "Your natural language prompt here" [options]
```

### Options
- --dry-run: Show the generated command without executing.
- --file <path>: Specify the input file explicitly.
- -v, --verbose: Enable verbose debug output.

### Examples

- Convert all MP4s to GIFs:
  ```bash
  toast "convert all mp4 files to gifs, make them loop"
  ```

- Extract audio from a specific file:
  ```bash
  toast --file my_video.mov "extract the audio as mp3"
  ```

- Trim a video and see the command without running:
  ```bash
  toast --dry-run --file input.avi "trim to the first 10 seconds"
  ```

- Run with verbose debug logging:
  ```bash
  toast -v "convert input.jpg to webp"
  ```

---

## Log File

For debugging purposes, pixel-toaster writes logs to:

```
~/.config/pixel-toaster/toast.log
```

You can check this file if you encounter unexpected issues. Logging level and log-to-file preferences can be adjusted in the `config.json`.