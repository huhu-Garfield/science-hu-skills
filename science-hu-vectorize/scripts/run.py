#!/usr/bin/env python3
"""Set up the shared local runtime and run this skill's converter."""
from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REQUIREMENTS = HERE / "requirements.txt"
PREVIEW_REQUIREMENTS = HERE / "requirements-preview.txt"
IMPORT_CHECK = "import cssselect2, fontTools, numpy, pathops, PIL, pptx, tinycss2, vtracer; assert hasattr(vtracer, 'convert_image_to_svg_py')"


def usable(python: Path, preview: bool = False) -> bool:
    imports = IMPORT_CHECK + ("; import pypdfium2, resvg_py" if preview else "")
    return python.is_file() and subprocess.run(
        [str(python), "-c", imports],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def python_in(environment: Path) -> Path:
    return environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def runtime(preview: bool = False) -> Path:
    current = Path(sys.executable)
    if usable(current, preview):
        return current

    cache = Path.home() / ".cache" / "science-hu"
    requirements = [REQUIREMENTS, PREVIEW_REQUIREMENTS] if preview else [REQUIREMENTS]
    revision = hashlib.sha256(b"".join(path.read_bytes() for path in requirements)).hexdigest()[:12]
    environment = cache / f"python-{sys.version_info.major}.{sys.version_info.minor}-{platform.machine()}-{revision}"
    python = python_in(environment)
    if usable(python, preview):
        return python

    cache.mkdir(parents=True, exist_ok=True)
    if environment.exists():
        raise RuntimeError(f"The existing runtime is incomplete. Move it aside and retry: {environment}")

    print("Installing science_hu's local conversion dependencies…", file=sys.stderr)
    uv = shutil.which("uv")
    with tempfile.TemporaryDirectory(prefix=".setup-", dir=cache) as temporary:
        staged = Path(temporary) / "runtime"
        interpreter = str(current.resolve())
        create = (
            [uv, "venv", "--quiet", "--python", interpreter, str(staged)]
            if uv else [interpreter, "-m", "venv", str(staged)]
        )
        subprocess.run(create, check=True)
        staged_python = python_in(staged)
        installer = (
            [uv, "pip", "install", "--python", str(staged_python)]
            if uv else [str(staged_python), "-m", "pip", "install", "--disable-pip-version-check"]
        )
        switches = [value for path in requirements for value in ("-r", str(path))]
        subprocess.run([*installer, "--only-binary=:all:", *switches], check=True)
        if not usable(staged_python, preview):
            raise RuntimeError("The installed packages could not be imported.")
        try:
            staged.rename(environment)
        except OSError:
            if not usable(python, preview):
                raise
    return python


def main() -> int:
    if sys.version_info < (3, 10):
        print("science_hu needs Python 3.10 or newer. Python 3.12 is recommended.", file=sys.stderr)
        return 1
    try:
        arguments = sys.argv[1:]
        preview = any(flag in arguments for flag in ("--preview", "--calibrate-fonts", "--setup-preview"))
        desktop_platform = sys.platform in {"darwin", "win32"}
        if arguments == ["--setup-preview"] and not desktop_platform:
            raise RuntimeError("Preview setup requires desktop PowerPoint on macOS or Windows.")
        try:
            python = runtime(preview and desktop_platform)
        except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
            if not preview or arguments == ["--setup-preview"]:
                raise
            print(f"Optional preview dependencies unavailable: {error}", file=sys.stderr)
            python = runtime()
        if arguments in (["--setup"], ["--setup-preview"]):
            print(f"science_hu is ready: {python}")
            return 0
        return subprocess.call([str(python), str(HERE / "convert.py"), *sys.argv[1:]])
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"science_hu setup failed: {error}", file=sys.stderr)
        print("Use Python 3.12 with venv support and allow package downloads for first-time setup.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
