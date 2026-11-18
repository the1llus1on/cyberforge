"""Build CyberForge artifacts from a verified git archive on Windows x64."""

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path
from shutil import copyfile

PYINSTALLER = "6.22.3"
HOOKS = "2026.10"
INNO = "6.7.4"
UV = "0.13.7"
ROOT = "CyberForge"
PACKAGE_ID = "D2751942-1E3B-4CFB-9233-984CC81C62A4"


def run(*args, **options):
    return subprocess.run(args, check=True, **options)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _unpack(source_archive, source, expected_sha):
    with tarfile.open(source_archive) as archive:
        if archive.pax_headers.get("comment") != expected_sha:
            raise ValueError("source archive does not match the expected Git commit")
        archive.extractall(source, filter="data")


def _verify_bundle(root, source):
    files = {path.name.lower() for path in root.rglob("*") if path.is_file()}
    resources = {
        "cyberforge.exe",
        "python312.dll",
        "sqlite3.dll",
        "qtwebengineprocess.exe",
        "qwindows.dll",
        "qt6webenginecore.dll",
        "icudtl.dat",
        "qtwebengine_resources.pak",
        "qtwebengine_resources_100p.pak",
        "qtwebengine_resources_200p.pak",
        "en-us.pak",
        "uk.pak",
        "env.py",
    } | {
        file.name
        for file in (source / "src/cyberforge/persistence/migrations/versions").glob(
            "*.py"
        )
    }
    if missing := resources - files:
        raise ValueError(f"missing onedir resources: {', '.join(sorted(missing))}")
    if any(
        name == "providers.json"
        or name.startswith(".env")
        or name.endswith((".sqlite", ".sqlite3", ".db"))
        for name in files
    ):
        raise ValueError("private data in onedir bundle")


def _write_notices(python, root, distribution_path, source):
    notices = root / "licenses"
    notices.mkdir()
    entries = []
    for package in sorted(
        importlib.metadata.distributions(path=[str(distribution_path)]),
        key=lambda item: item.metadata["Name"].casefold(),
    ):
        name = package.metadata["Name"]
        entries.append(
            {
                "name": name,
                "version": package.version,
                "license": package.metadata.get("License-Expression")
                or package.metadata.get("License")
                or package.metadata.get_all("Classifier", []),
            }
        )
        for file in package.files or ():
            located = Path(package.locate_file(file))
            if not located.is_file() or not re.match(
                r"(?i)(LICEN[CS]E|COPYING|COPYRIGHT|NOTICE|THIRD.PARTY)",
                located.name,
            ):
                continue
            target = notices / name / file
            if target.is_relative_to(notices / name) and ".." not in file.parts:
                target.parent.mkdir(parents=True, exist_ok=True)
                copyfile(located, target)
    installed_base = Path(
        run(
            str(python),
            "-c",
            "import sys; print(sys.base_prefix)",
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    for path in installed_base.glob("LICENSE*"):
        if path.is_file():
            (notices / "CPython").mkdir(exist_ok=True)
            copyfile(path, notices / "CPython" / path.name)
    copyfile(source / "release/windows/THIRD_PARTY.md", root / "THIRD_PARTY.md")
    (notices / "build-environment.json").write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _sign(path, args):
    if args.signtool:
        run(
            str(args.signtool),
            "sign",
            "/sha1",
            args.thumbprint,
            "/fd",
            "SHA256",
            "/tr",
            args.timestamp,
            "/td",
            "SHA256",
            str(path),
        )
        run(str(args.signtool), "verify", "/pa", str(path))


def _smoke(path):
    env = os.environ.copy()
    for name in (
        "PYTHONPATH",
        "PYTHONHOME",
        "VIRTUAL_ENV",
        "QT_QPA_PLATFORM",
        "QML2_IMPORT_PATH",
        "QT_PLUGIN_PATH",
        "QTWEBENGINEPROCESS_PATH",
        "QTWEBENGINE_DISABLE_SANDBOX",
        "QTWEBENGINE_CHROMIUM_FLAGS",
    ):
        env.pop(name, None)
    windows = Path(os.environ["SystemRoot"])
    env["PATH"] = os.pathsep.join((str(windows / "System32"), str(windows)))
    run(str(path), "--smoke-test", cwd=path.parent, env=env, timeout=90)


def _zip_bundle(root, output):
    with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED, compresslevel=3) as archive:
        for file in sorted(root.rglob("*")):
            if file.is_file():
                archive.write(file, Path(ROOT) / file.relative_to(root))


def _tools(args):
    uv_version = run(str(args.uv), "--version", capture_output=True, text=True).stdout
    if not uv_version.startswith(f"uv {UV} "):
        raise ValueError("pinned uv version mismatch")
    return uv_version.strip()


def build(args):
    if sys.platform != "win32" or platform.machine().upper() not in {"AMD64", "X86_64"}:
        raise SystemExit("build requires native Windows x64 Python")
    if sys.version_info[:2] != (3, 12) or sys.maxsize <= 2**32:
        raise SystemExit("build requires CPython 3.12 x64")
    version = sys.getwindowsversion()
    if version.build < 22000 and not args.hosted_ci:
        raise SystemExit("release build requires Windows 11 x64")
    uv_version = _tools(args)
    args.output.mkdir()
    with tempfile.TemporaryDirectory(prefix="cyberforge-build-") as directory:
        work = Path(directory)
        source = work / "source"
        source.mkdir()
        _unpack(args.archive, source, args.sha)
        script = source / "release/windows"
        env = os.environ | {
            "UV_PROJECT_ENVIRONMENT": str(work / "venv"),
            "PYINSTALLER_CONFIG_DIR": str(work / "pyinstaller-cache"),
        }
        for name in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
            env.pop(name, None)
        run(
            str(args.uv),
            "sync",
            "--locked",
            "--no-dev",
            "--group",
            "release",
            "--no-editable",
            "--python",
            sys.executable,
            "--project",
            str(source),
            env=env,
            cwd=source,
        )
        python = work / "venv/Scripts/python.exe"
        result = run(
            str(python),
            "-c",
            "import json, importlib.metadata as m; "
            "print(json.dumps({k:m.version(k) for k in "
            "('CyberForge', 'PySide6', 'PyInstaller', 'pyinstaller-hooks-contrib')}))",
            capture_output=True,
            text=True,
            env=env,
            cwd=source,
        )
        versions = json.loads(result.stdout)
        if (
            versions["PyInstaller"] != PYINSTALLER
            or versions["pyinstaller-hooks-contrib"] != HOOKS
        ):
            raise ValueError("PyInstaller lock mismatch")
        app_version = versions["CyberForge"]
        run(
            str(python),
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(work / "dist"),
            "--workpath",
            str(work / "work"),
            str(script / "cyberforge.spec"),
            env=env,
            cwd=source,
        )
        bundle = work / "dist" / ROOT
        _verify_bundle(bundle, source)
        _write_notices(python, bundle, work / "venv/Lib/site-packages", source)
        _sign(bundle / "CyberForge.exe", args)
        archive = args.output / f"CyberForge-{app_version}-windows-x64.zip"
        _zip_bundle(bundle, archive)
        smoke_dir = work / "Перевірка повного ZIP"
        with zipfile.ZipFile(archive) as packed:
            packed.extractall(smoke_dir)
        _smoke(smoke_dir / ROOT / "CyberForge.exe")
        compiler = subprocess.run(
            [
                str(args.iscc),
                f"/DApplicationVersion={app_version}",
                f"/DBundleDir={bundle}",
                f"/DRevision={args.sha[:12]}",
                f"/DReleaseDir={args.output}",
                str(script / "CyberForge.iss"),
            ],
            cwd=source,
            capture_output=True,
            text=True,
            errors="replace",
        )
        if compiler.returncode:
            raise ValueError((compiler.stdout + compiler.stderr)[-5000:])
        if f"Compiler engine version: Inno Setup {INNO}" not in compiler.stdout:
            raise ValueError("pinned Inno Setup version mismatch")
        installer = args.output / f"CyberForge-{app_version}-windows-x64-setup.exe"
        _sign(installer, args)
        artifacts = [
            {"file": path.name, "bytes": path.stat().st_size, "sha256": digest(path)}
            for path in (archive, installer)
        ]
        manifest = {
            "schema_version": "cyberforge-release-manifest-v1",
            "source_sha": args.sha,
            "source_archive_sha256": digest(args.archive),
            "lockfile_sha256": digest(source / "uv.lock"),
            "application_id": PACKAGE_ID,
            "windows_build": version.build,
            "windows_edition": platform.win32_edition(),
            "architecture": "x64",
            "hosted_ci": args.hosted_ci,
            "python": platform.python_version(),
            "uv": uv_version,
            "dependencies": versions,
            "inno_setup": INNO,
            "mode": "onedir",
            "signatures": "verified" if args.signtool else "unsigned",
            "portable_qt_webengine_smoke": "passed",
            "artifacts": artifacts,
        }
        (args.output / "release-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        (args.output / "SHA256SUMS.txt").write_text(
            "".join(f"{item['sha256']}  {item['file']}\n" for item in artifacts),
            encoding="utf-8",
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("archive", "output", "uv", "iscc"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--hosted-ci", action="store_true")
    parser.add_argument("--signtool", type=Path)
    parser.add_argument("--thumbprint")
    parser.add_argument("--timestamp")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.sha):
        parser.error("--sha must be an exact SHA-1 Git commit")
    for name in ("archive", "output", "uv", "iscc"):
        setattr(args, name, getattr(args, name).resolve())
    if args.signtool and (
        not re.fullmatch(r"[a-fA-F0-9]{40}", args.thumbprint or "")
        or not (args.timestamp or "").startswith("https://")
    ):
        parser.error("signing needs a certificate thumbprint and HTTPS timestamp URL")
    build(args)


if __name__ == "__main__":
    main()
