# pixel-toaster

Say goodbye to memorizing complex FFmpeg flags or copying and pasting commands from ChatGPT! Just tell `toast` what you want to do.

**pixel-toaster** is a command-line tool that performs media conversions and manipulations using natural language prompts. It leverages the power of LLMs to translate your requests into FFmpeg commands, executes them, and even attempts to automatically fix errors by feeding them back to the LLM.

---

## Features

- **Natural Language Interface** – Describe your media conversion task in plain English (e.g., "convert video.mp4 to a gif", "make all jpgs grayscale", "extract audio from interview.mov").
- **FFmpeg Powered** – Generates and executes commands for the powerful FFmpeg library.
- **LLM Integration** – Uses an LLM (defaults to OpenAI's API, configurable) to interpret your request and generate the appropriate command.
- **Context-Aware** – Provides the LLM with context about your OS, shell, FFmpeg version, and files in the current directory for better results.
- **File Detection** – Automatically detects common video, image, and audio files to help with batch processing.
- **Batch Processing** – Generates shell loops (e.g., `for file in *.mp4; do ... done`) when your prompt implies multiple files.
- **Error Handling & Retry** – If an FFmpeg command fails, `toast` captures the error and asks the LLM to correct it.
- **Managed Configuration** – Interactive setup for your API key; stored in `~/.config/pixel-toaster/config.json` (or XDG-compliant path).
- **Dry Run Mode** – Use `--dry-run` to preview commands without running them.
- **Explicit File Input** – Use `--file` to specify a particular input file.
- **File Logging** – Logs are written to `~/.config/pixel-toaster/toast.log` (configurable).

---

## Prerequisites

### For Users (Running the Binary)

1. **FFmpeg** – You **must** have `ffmpeg` installed and accessible in your `PATH`.
   - Download: [ffmpeg.org](https://ffmpeg.org/download.html)
   - macOS: `brew install ffmpeg`
   - Debian/Ubuntu: `sudo apt update && sudo apt install ffmpeg`
   - Windows: Use the official site or install via `choco install ffmpeg` or `winget install ffmpeg`, and add to `PATH`.

2. **OpenAI API Key** – Get one at [https://platform.openai.com/signup/](https://platform.openai.com/signup/). You’ll be prompted for this on first run.

### For Developers (Building from Source)

- Python 3.8+
- `pip`
- `git`
- (Optional) `make` for using Makefile commands
- (Optional) GitHub CLI (`gh`) for `make release-gh`

---

## Installation (Recommended: Binary Release)

Download the pre-compiled binary for your OS to avoid needing Python.

1. Go to the [Releases page](https://github.com/billybjork/pixel-toaster/releases).
2. Download the appropriate binary (e.g., `toast-linux`, `toast-macos`, `toast-windows.exe`).
3. Make it executable:

   ```bash
   chmod +x /path/to/downloaded/toast-binary
   ```

4. Move it to your `PATH`:

   ```bash
   # macOS/Linux
   sudo mv /path/to/downloaded/toast-binary /usr/local/bin/toast
   ```

   ```powershell
   # Windows
   # Move toast-windows.exe to a folder in your PATH manually
   ```

---

## Setting up the `toast` Alias (Optional)

If the binary is not in your `PATH`, you can create an alias:

1. Locate your `toast` executable.
2. Edit your shell config file:
   - **Bash**: `~/.bashrc` or `~/.bash_profile`
   - **Zsh**: `~/.zshrc`
   - **Fish**: `~/.config/fish/config.fish`
3. Add this line (replace the path):

   ```bash
   alias toast='/full/path/to/toast'
   ```

4. Reload your shell config:

   ```bash
   source ~/.bashrc  # or ~/.zshrc, etc.
   ```

---

## macOS Security Note

You might see a warning the first time you run `toast`. To allow it:

1. Control-click the `toast` binary in Finder.
2. Click **Open** in the dialog.
3. Alternatively, go to **System Settings > Privacy & Security** and click "Open Anyway".

You only need to do this once per version.

You will also need to make the command executable:
```bash
   chmod +x /usr/local/bin/toast
```

---

## Configuration (First Run)

On first run, `pixel-toaster` will prompt you to set up:

```text
--- Pixel Toaster First-Time Setup ---
Configuration will be saved to: ~/.config/pixel-toaster/config.json
Please enter your OpenAI API Key (starts with 'sk-'): ****
```

It will save the config to `~/.config/pixel-toaster/config.json` (or XDG-compliant path).

### Configuration File Example

```json
{
    "openai_api_key": "sk-...",
    "llm_model": "gpt-4o-mini",
    "log_level": "INFO",
    "log_to_file": true
}
```

---

## Usage

Run the tool using natural language prompts:

```bash
toast "Your natural language prompt here" [options]
```

### Options

- `--dry-run` – Show command without executing.
- `--file <path>` – Explicitly specify input file.
- `-v`, `--verbose` – Enable debug output.

### Examples

Convert all MP4s to GIFs:

```bash
toast "convert all mp4 files to gifs, make them loop"
```

Extract audio from a file:

```bash
toast --file my_video.mov "extract the audio as mp3"
```

Trim a video with dry run:

```bash
toast --dry-run --file input.avi "trim to the first 10 seconds"
```

Verbose conversion:

```bash
toast -v "convert input.jpg to webp"
```

---

## Log File

Logs are stored at:

```
~/.config/pixel-toaster/toast.log
```

You can inspect this file for errors or unexpected behavior. Adjust logging preferences in your config file.

---