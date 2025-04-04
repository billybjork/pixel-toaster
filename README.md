# toast (pixel-toaster)

Say goodbye to memorizing complex FFmpeg flags, or copying and pasting Ffmpeg commands from ChatGPT! Just tell `toast` what you want to do.

**toast** is a command-line tool that allows you to perform media conversions and manipulations using natural language prompts. It leverages the power of LLMs to translate your requests into FFmpeg commands, executes them, and even attempts to automatically fix errors by feeding them back to the LLM.

## Features

*   **Natural Language Interface:** Describe your media conversion task in plain English (e.g., "convert video.mp4 to a gif", "make all jpgs grayscale", "extract audio from interview.mov").
*   **FFmpeg Powered:** Generates and executes commands for the powerful FFmpeg library.
*   **LLM Integration:** Uses an LLM (currently configured for OpenAI's API) to interpret your request and generate the appropriate command.
*   **Context-Aware:** Provides the LLM with context about your operating system, shell, FFmpeg version, and files in the current directory to generate more accurate commands.
*   **File Detection:** Automatically detects common video, image, and audio files in the current directory to assist with batch processing prompts.
*   **Batch Processing:** Intelligently generates shell loops (e.g., `for file in *.mp4; do ... done`) when your prompt implies operating on multiple files (e.g., "convert all mp4 files...").
*   **Error Handling & Retry:** If an FFmpeg command fails, `toast` captures the error output and asks the LLM to generate a corrected command based on the failure.
*   **Dry Run Mode:** See the command that *would* be executed without actually running it using the `--dry-run` flag.
*   **Explicit File Input:** Specify a particular input file using the `--file` flag.
*   **Configurable API Key:** Securely configure your OpenAI API key via environment variables or `.env` files.

## Prerequisites

1.  **Python 3:** Ensure you have Python 3.8 or newer installed.
2.  **pip:** Python's package installer.
3.  **FFmpeg:** The core media manipulation tool. You **must** have `ffmpeg` installed and accessible in your system's PATH. You can download it from [ffmpeg.org](https://ffmpeg.org/download.html) or install it via your system's package manager (e.g., `brew install ffmpeg` on macOS, `sudo apt update && sudo apt install ffmpeg` on Debian/Ubuntu, `choco install ffmpeg` on Windows with Chocolatey).
4.  **OpenAI API Key:** You need an API key from OpenAI. Get one at [https://platform.openai.com/signup/](https://platform.openai.com/signup/).

## Installation

1.  **Clone the Repository:**
    ```bash
    git clone <your-repo-url> # Replace <your-repo-url> with the actual URL
    cd toast # Or whatever you named the directory containing the 'toast' script
    ```

2.  **Install Python Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Make the Script Executable:**
    ```bash
    chmod +x toast
    ```

4.  **Add to PATH or Create an Alias (Optional, for convenience):**
    *   You can add the script's directory to your system's PATH environment variable. Ensure the directory containing the `toast` script is in your PATH.
    *   Alternatively, create an alias in your shell's configuration file (e.g., `.bashrc`, `.zshrc`):
        ```bash
        # Example for bash/zsh
        alias toast='/path/to/your/toast/toast' # Point to the 'toast' script directly
        # Remember to source your config file after adding the alias: source ~/.bashrc
        ```

## Configuration

`toast` needs your OpenAI API key to function. It searches for the key (`OPENAI_API_KEY`) in the following order:

1.  **Environment Variable:** The most secure method is to set the `OPENAI_API_KEY` environment variable globally in your system or shell profile.
    ```bash
    export OPENAI_API_KEY='your_api_key_here'
    ```

2.  **User Configuration File (`~/.config/toast/.env`):**
    *   Create the directory: `mkdir -p ~/.config/toast`
    *   Create a file named `.env` inside that directory (`~/.config/toast/.env`).
    *   Add your key to the file:
        ```dotenv
        # ~/.config/toast/.env
        OPENAI_API_KEY=your_api_key_here
        ```

3.  **Script Directory File (`.env`):**
    *   Create a file named `.env` in the *same directory as the actual `toast` script* (it resolves symlinks).
    *   Add your key to the file:
        ```dotenv
        # /path/to/your/toast/.env
        OPENAI_API_KEY=your_api_key_here
        ```

**Note:** It's strongly recommended to use either the environment variable or the user configuration file method, rather than placing the key directly next to the script, especially if you might share the code or commit it to version control.

## Usage

Run the script from your terminal, followed by your natural language prompt enclosed in quotes.

**Basic Syntax:**

```bash
./toast "Your natural language prompt here"
# Or, if aliased or in PATH:
toast "Your natural language prompt here"