#!/usr/bin/env python3
"""
Advanced Obfuscation Script for Stable Diffusion WebUI (AUTOMATIC1111)
Packs all project Python files into exec(base64.b64decode(...)) wrappers
while ensuring proper runtime bootstrap for root entry points.
"""

import sys
import os
import re
import shutil
import base64
import time
from pathlib import Path

# Все целевые директории проекта
TARGET_DIRS = [
    "modules",
    "scripts",
    "extensions",
    "extensions-builtin"
]
ROOT_FILES = ["webui.py", "launch.py"]

EXCLUDE_PATTERNS = [
    r"^\.obfuscation",
    r"__pycache__",
    r"\.pyc$",
    r"obfuscate_project\.py$",
    r"obfuscation_runtime\.py$",
    r"modules/shared.*",
    r"modules/initialize.*",
    r"modules/cmd_args\.py$",
    r"modules/paths.*",
    r"modules/sd_models_types\.py$"  # Исключаем из обфускации
]

SKIP_DIRS = {
    "__pycache__",
    ".git",
    ".github",
    ".obfuscation_backups",
    ".gitignore",
    "node_modules",
    "venv",
    ".venv",
    ".obfuscation"
}

def should_exclude(fp, project_root):
    rel_path = os.path.relpath(fp, project_root)
    return any(re.search(p, rel_path) for p in EXCLUDE_PATTERNS)

def is_already_obfuscated(fp):
    try:
        with open(fp, 'r', encoding='utf-8') as fh:
            content = fh.read()
            return '__obf_payload__ = ' in content or 'modules.obfuscation_runtime' in content
    except Exception:
        return False

def obfuscate_file(fp, is_root_file=False):
    with open(fp, 'r', encoding='utf-8') as fh:
        src = fh.read()

    orig_size = len(src.encode('utf-8'))

    backup_path = fp + '.obfuscation_backup'
    if not os.path.exists(backup_path):
        shutil.copy2(fp, backup_path)

    if is_root_file:
        bootstrap_code = (
            "import sys, os\n"
            "_root = os.path.dirname(os.path.abspath(__file__))\n"
            "if _root not in sys.path: sys.path.insert(0, _root)\n"
            "try:\n"
            "    import modules.obfuscation_runtime\n"
            "except Exception:\n"
            "    pass\n\n"
        )
        if "modules.obfuscation_runtime" in src:
            wrapped_content = src
        else:
            lines = src.splitlines(keepends=True)
            insert_idx = 0
            for idx, line in enumerate(lines):
                if line.strip().startswith("from __future__") or line.strip().startswith("#"):
                    insert_idx = idx + 1
                else:
                    break
            lines.insert(insert_idx, bootstrap_code)
            wrapped_content = "".join(lines)
    else:
        b64_encoded = base64.b64encode(src.encode('utf-8'))
        wrapped_content = f"__obf_payload__ = {b64_encoded!r}\n"

    with open(fp, 'w', encoding='utf-8') as fh:
        fh.write(wrapped_content)

    return {
        "success": True,
        "original_size": orig_size,
        "wrapped_size": len(wrapped_content.encode('utf-8'))
    }

def collect_files(project_root):
    collected = []
    root_path = Path(project_root).resolve()

    # 1. Сбор из TARGET_DIRS
    for target_dir in TARGET_DIRS:
        dir_path = root_path / target_dir
        if not dir_path.is_dir():
            continue
        for root, dirs, files in os.walk(str(dir_path)):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for file in files:
                if not file.endswith('.py'):
                    continue
                full_path = os.path.join(root, file)

                # Жёсткое исключение файла sd_models_types.py
                if file == "sd_models_types.py":
                    continue

                if should_exclude(full_path, str(root_path)) or is_already_obfuscated(full_path):
                    continue
                collected.append((full_path, False))

    # 2. Сбор корневых файлов (webui.py, launch.py)
    for fn in ROOT_FILES:
        full_path = str(root_path / fn)
        if os.path.isfile(full_path) and not should_exclude(full_path, str(root_path)) and not is_already_obfuscated(full_path):
            collected.append((full_path, True))

    return collected

def obfuscate_project(project_root, dry_run=False, verbose=False):
    project_root = os.path.abspath(project_root)
    files = collect_files(project_root)
    total = len(files)

    if verbose:
        print(f"Найдено файлов для обфускации: {total}")

    if not files:
        print("Нет файлов для обработки.")
        return

    start_time = time.time()
    success_count = 0

    for i, (fp, is_root) in enumerate(files, 1):
        rel_path = os.path.relpath(fp, project_root)
        if verbose:
            print(f"[{i}/{total}] {'[ROOT] ' if is_root else ''}Обработка: {rel_path}")

        if dry_run:
            success_count += 1
            continue

        try:
            res = obfuscate_file(fp, is_root_file=is_root)
            success_count += 1
            if verbose:
                print(f"  -> ОК: {res['original_size']} -> {res['wrapped_size']} байт")
        except Exception as exc:
            print(f"  -> ОШИБКА в {rel_path}: {exc}")

    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print(f"Обфускация завершена! Успешно: {success_count}/{total} за {elapsed:.2f}с")
    print("=" * 60)

def restore_project(project_root, verbose=False):
    project_root = os.path.abspath(project_root)
    restored = 0
    errors = 0

    for root, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for file in files:
            if file.endswith('.obfuscation_backup'):
                backup_path = os.path.join(root, file)
                orig_path = backup_path[:-19]
                try:
                    shutil.copy2(backup_path, orig_path)
                    os.remove(backup_path)
                    restored += 1
                    if verbose:
                        print(f"Восстановлен: {os.path.relpath(orig_path, project_root)}")
                except Exception as exc:
                    errors += 1
                    if verbose:
                        print(f"Ошибка восстановления {orig_path}: {exc}")

    print("=" * 60)
    print(f"Восстановление завершено. Восстановлено: {restored}, Ошибок: {errors}")
    print("=" * 60)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Обфускатор для Stable Diffusion WebUI")
    parser.add_argument('--project-root', default=None, help="Путь к корню SD-WebUI")
    parser.add_argument('--dry-run', action='store_true', help="Тестовый прогон без изменения файлов")
    parser.add_argument('--verbose', '-v', action='store_true', help="Подробный вывод")
    parser.add_argument('--restore', action='store_true', help="Восстановить файлы из бэкапов")
    args = parser.parse_args()

    root = args.project_root if args.project_root else os.path.dirname(os.path.abspath(__file__))
    if not os.path.isdir(root):
        print(f"Ошибка: директория не найдена: {root}")
        sys.exit(1)

    if args.restore:
        restore_project(root, verbose=args.verbose)
    else:
        obfuscate_project(root, dry_run=args.dry_run, verbose=args.verbose)

if __name__ == "__main__":
    main()
