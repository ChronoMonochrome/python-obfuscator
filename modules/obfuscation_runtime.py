"""
Robust Obfuscation Runtime Loader for Stable Diffusion WebUI
Filters imports to process ONLY project packages.
"""

import sys
import os
import importlib.abc
import importlib.util
import base64

PAYLOAD_MARKER = "__obf_payload__"
_MODULES_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_MODULES_DIR)

# Явно добавляем стандартные репозитории Stable Diffusion в sys.path в правильном порядке
_REPO_PATHS = [
    os.path.join(_PROJECT_ROOT, "repositories", "stable-diffusion-stability-ai"),
    os.path.join(_PROJECT_ROOT, "repositories", "taming-transformers"),
    os.path.join(_PROJECT_ROOT, "repositories", "k-diffusion"),
    os.path.join(_PROJECT_ROOT, "repositories", "CodeFormer"),
    os.path.join(_PROJECT_ROOT, "repositories", "BLIP"),
]

for p in _REPO_PATHS:
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)

TARGET_PREFIXES = ("modules", "scripts", "extensions", "extensions-builtin")

class ObfuscationFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname == "modules.obfuscation_runtime":
            return None

        # Жёсткий фильтр: если это не модуль проекта, отдаем стандартному загрузчику Python (json, torch, python stdlib и т.д.)
        top_name = fullname.split(".")[0]
        if top_name not in TARGET_PREFIXES:
            return None

        fp = self._locate(fullname, path)
        if fp:
            return importlib.util.spec_from_file_location(
                fullname, fp,
                loader=ObfuscationLoader(fp),
                submodule_search_locations=[os.path.dirname(fp)] if fp.endswith("__init__.py") else None
            )
        return None

    def _locate(self, fullname, path):
        parts = fullname.split(".")
        mod_name = parts[-1]
        search_paths = list(sys.path) + ([_PROJECT_ROOT] if _PROJECT_ROOT not in sys.path else [])
        if path:
            search_paths = list(path) + search_paths

        rel_path = os.path.join(*parts)
        for base_path in search_paths:
            if not base_path or not os.path.isdir(base_path):
                continue
            for candidate in [
                os.path.join(base_path, rel_path + ".py"),
                os.path.join(base_path, rel_path, "__init__.py"),
                os.path.join(base_path, mod_name + ".py"),
                os.path.join(base_path, mod_name, "__init__.py")
            ]:
                if os.path.isfile(candidate):
                    return os.path.abspath(candidate)
        return None

class ObfuscationLoader(importlib.abc.Loader):
    def __init__(self, wrapper_path):
        self._wrapper_path = os.path.abspath(wrapper_path)

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        try:
            with open(self._wrapper_path, "r", encoding="utf-8") as f:
                content = f.read()

            if PAYLOAD_MARKER in content or "__obf_payload__" in content:
                ns = {}
                exec(content, ns)
                payload = ns.get("__obf_payload__")
                if payload:
                    source_code = base64.b64decode(payload).decode("utf-8")
                else:
                    source_code = content
            else:
                source_code = content

            module.__file__ = self._wrapper_path
            module.__loader__ = self
            module.__package__ = module.__name__.rsplit(".", 1)[0] if "." in module.__name__ else ""
            if os.path.basename(self._wrapper_path) == "__init__.py":
                module.__path__ = [os.path.dirname(self._wrapper_path)]
            module.__cached__ = None

            # Предрегистрация модуля в sys.modules для поддержки циклических импортов
            sys.modules[module.__name__] = module

            code_obj = compile(source_code, self._wrapper_path, 'exec')
            exec(code_obj, module.__dict__)

        except Exception as e:
            sys.modules.pop(module.__name__, None)
            raise ImportError(f"Ошибка загрузки модуля {module.__name__} ({self._wrapper_path}): {e}")

_finder = ObfuscationFinder()

def install():
    if _finder not in sys.meta_path:
        if _PROJECT_ROOT not in sys.path:
            sys.path.insert(0, _PROJECT_ROOT)
        sys.meta_path.insert(0, _finder)

install()
