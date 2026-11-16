# Python Base64 Obfuscator & Runtime Loader

Obfuscation and runtime-loading system designed specifically for complex multi-module Python applications like **Stable Diffusion WebUI (AUTOMATIC1111)**.

Unlike naive obfuscation scripts that break relative imports, crash on missing `__file__` attributes, or disrupt dynamic plugin loaders, this system introduces a custom `sys.meta_path` import machinery that decrypts and executes obfuscated code on-the-fly while maintaining 100% application compatibility.

---

## Project Structure

```text
├── obfuscate_project.py           # Main packaging and obfuscation script
└── modules/
    └── obfuscation_runtime.py     # Runtime MetaPath finder and loader hook

```

---

## How It Works

1. **Obfuscation (`obfuscate_project.py`):**
* Recursively scans target project directories (`modules`, `scripts`, `extensions`, `extensions-builtin`, `repositories`).
* Encodes standard Python source files into a base64 payload format: `__obf_payload__ = b'...'`.
* Automatically creates backups (`.obfuscation_backup`) for safe restoration.
* Patches root entry points (`webui.py`, `launch.py`) into self-unpacking launchers with early runtime bootstrapping.


2. **Runtime Loading (`modules/obfuscation_runtime.py`):**
* Hooks into Python's import system via `importlib.abc.MetaPathFinder`.
* Intercepts project module requests, decodes the base64 payload on-the-fly, and compiles it into clean bytecode.
* Pre-registers modules in `sys.modules` to seamlessly support complex dependency graphs and circular imports.



---

## Installation & Usage

### 1. Place the Files

Ensure `obfuscate_project.py` is in your project root, and `modules/obfuscation_runtime.py` is placed inside the `modules/` directory.

### 2. Obfuscate the Project

Run the obfuscation script pointing to your WebUI root directory:

```bash
python obfuscate_project.py --project-root /path/to/stable-diffusion-webui -v

```

### 3. Restore Original Files (If Needed)

If you need to revert the obfuscation and restore all original source files from backups:

```bash
python obfuscate_project.py --project-root /path/to/stable-diffusion-webui --restore -v

```

---

## Command-Line Arguments (`obfuscate_project.py`)

* `--project-root`: Path to the target project directory (defaults to the script's directory).
* `--dry-run`: Performs a dry run scan and check without modifying any files.
* `-v`, `--verbose`: Enables detailed logging of processed files.
* `--restore`: Restores all project files from `.obfuscation_backup` and cleans up bootstraps.
