
# pixel-toaster

Say goodbye to memorizing complex FFmpeg flags or copying and pasting commands from ChatGPT! Just tell `pixel-toaster` what you want to do.

**pixel-toaster** is a command-line tool that allows you to perform media conversions and manipulations using natural language prompts. It leverages the power of LLMs to translate your requests into FFmpeg commands, executes them, and even attempts to automatically fix errors by feeding them back to the LLM.

---

## Features

- **Natural Language Interface:** Describe your media conversion task in plain English (e.g., "convert video.mp4 to a gif", "make all jpgs grayscale", "extract audio from interview.mov").
- **FFmpeg Powered:** Generates and executes commands for the powerful FFmpeg library.
- **LLM Integration:** Uses an LLM (defaults to OpenAI's API, configurable) to interpret your request and generate the appropriate command.
- **Context-Aware:** Provides the LLM with context about your operating system, shell, FFmpeg version, and files in the current directory to generate more accurate commands.
- **File Detection:** Automatically detects common video, image, and audio files in the current directory to assist with batch processing prompts.
- **Batch Processing:** Intelligently generates shell loops (e.g., `for file in *.mp4; do ... done`) when your prompt implies operating on multiple files.
- **Error Handling & Retry:** If an FFmpeg command fails, `pixel-toaster` captures the error output and asks the LLM to generate a corrected command based on the failure.
- **Managed Configuration:** Guides you through a secure, interactive first-time setup for your API key. Stores configuration (API key, preferred model, logging settings) in a dedicated user configuration file (`~/.config/pixel-toaster/config.json`).
- **Dry Run Mode:** See the command that *would* be executed without actually running it using the `--dry-run` flag.
- **Explicit File Input:** Specify a particular input file using the `--file` flag.
- **File Logging:** Records logs to `~/.config/pixel-toaster/toast.log` for debugging (configurable).

---

## Prerequisites

1. **Python 3:** Ensure you have Python 3.8 or newer installed.
2. **pip:** Python's package installer.
3. **FFmpeg:** The core media manipulation tool. You **must** have `ffmpeg` installed and accessible in your system's PATH. You can download it from [ffmpeg.org](https://ffmpeg.org/download.html) or install it via your system's package manager:
   - macOS: `brew install ffmpeg`
   - Debian/Ubuntu: `sudo apt update && sudo apt install ffmpeg`
   - Windows: `choco install ffmpeg`
4. **OpenAI API Key:** You need an API key from OpenAI to use the default LLM backend. Get one at [https://platform.openai.com/signup/](https://platform.openai.com/signup/). You will be prompted for this key the first time you run the tool.

---

## Installation

### 1. Clone the Repository

```bash
git clone <your-repo-url> # Replace <your-repo-url> with the actual URL
cd pixel-toaster
```

### 2. Install Python Dependencies

Make sure you have a `requirements.txt` file or install the necessary packages manually:

```bash
# If you have requirements.txt:
pip install -r requirements.txt

# Or, install key dependencies manually:
pip install openai
```

> Note: The core application now primarily relies on `openai`.

### 3. (Optional) Add Alias for Convenience

To run the tool from anywhere without typing `python path/to/main.py`, you can create an alias in your shell configuration file:

```bash
# Example for bash/zsh (replace path)
alias toast='python /path/to/your/pixel-toaster/main.py'

# Remember to source your config file:
source ~/.zshrc
```

---

## Configuration (First Run Setup)

`pixel-toaster` handles its own configuration securely. The old method of searching for `.env` files is **no longer used**.

1. **First Execution:** The very first time you run `pixel-toaster` (e.g., `python main.py "your prompt"`), it will detect that it hasn't been configured yet.
2. **API Key Prompt:** It will securely prompt you to enter your OpenAI API key. The key will *not* be echoed to the terminal.

```
--- Pixel Toaster First-Time Setup ---
Configuration will be saved to: /Users/your_user/.config/pixel-toaster/config.json
Please enter your OpenAI API Key (starts with 'sk-'): ****
```

3. **Configuration Saved:** Once you enter a valid key, the script will create the necessary directory and save the configuration.

### The Configuration File (`~/.config/pixel-toaster/config.json`)

Your configuration is stored in a JSON file like this:

```json
{
    "openai_api_key": "sk-...",
    "llm_model": "gpt-4o-mini",
    "log_level": "INFO",
    "log_to_file": true
}
```

You generally don't need to edit this manually, but you can change the model or logging preferences here.

---

## Usage

Run the script from your terminal using `python main.py` (or your alias), followed by your natural language prompt.

### Basic Syntax

```bash
python main.py "Your natural language prompt here"
```

### Examples

- Convert all MP4s to GIFs:
  ```bash
  python main.py "convert all mp4 files to gifs, make them loop"
  ```

- Extract audio from a specific file:
  ```bash
  python main.py --file my_video.mov "extract the audio as mp3"
  ```

- Trim a video and see the command without running:
  ```bash
  python main.py --dry-run --file input.avi "trim to the first 10 seconds"
  ```

- Run with verbose debug logging:
  ```bash
  python main.py -v "convert input.jpg to webp"
  ```

---

## Log File

For debugging purposes, pixel-toaster writes logs to:

```
~/.config/pixel-toaster/toast.log
```

You can check this file if you encounter unexpected issues. Logging level and log-to-file preferences can be adjusted in the `config.json`.