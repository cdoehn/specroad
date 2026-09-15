"""Build relocatable development distributions using only the standard library.

This is not the release pipeline or a release-compatibility claim. Only trusted
Core sources are packaged; neither project data nor the development environment
is part of a distribution. Existing destinations are never overwritten.
"""

from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import stat
import tempfile
import zipapp


ARCHIVE_MAIN = "from specroad.cli import main\nraise SystemExit(main())\n"


def build_core(source_root: Path, output: Path) -> tuple[Path, Path]:
    """Publish a module tree and Zipapp together under a new output directory."""
    source_root = Path(source_root).resolve()
    package = source_root / "specroad"
    raw_output = Path(output)
    if os.path.lexists(raw_output):
        raise FileExistsError(raw_output)
    output = raw_output.absolute()
    parent = output.parent.resolve(strict=True)
    output = parent / output.name
    if output == source_root or source_root in output.parents:
        raise ValueError("The output must be outside the source tree.")
    if not package.is_dir() or package.is_symlink():
        raise ValueError("A regular specroad package directory is required.")
    payload = {}
    for path in sorted(package.rglob("*")):
        if path.is_symlink():
            raise ValueError("Source symlinks are not packaged.")
        if path.is_dir() or "__pycache__" in path.parts:
            continue
        if path.suffix != ".py":
            continue
        if not stat.S_ISREG(path.stat().st_mode):
            raise ValueError("Only regular source files are packaged.")
        payload[path.relative_to(source_root)] = path.read_bytes()
    if not {Path("specroad/__init__.py"), Path("specroad/__main__.py")} <= payload.keys():
        raise ValueError("The Core package is incomplete.")
    # Content identity excludes its derived record, timestamps and absolute paths.
    # Input modules are data: never import or execute the caller-supplied tree.
    manifest = {path.as_posix(): hashlib.sha256(data).hexdigest()
                for path, data in payload.items() if path != Path("specroad/_build.py")}
    manifest["__main__.py"] = hashlib.sha256(ARCHIVE_MAIN.encode("utf-8")).hexdigest()
    identity_bytes = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    record = {"format_version": 1, "hash_algorithm": "specroad-dev-payload-v1",
              "build_sha256": hashlib.sha256(b"specroad-dev-payload-v1\0" + identity_bytes).hexdigest()}
    payload[Path("specroad/_build.py")] = ("\"\"\"Generated development payload identity; not release evidence.\"\"\"\n"
                                           + "BUILD_METADATA = " + repr(record) + "\n").encode("utf-8")
    stage = Path(tempfile.mkdtemp(prefix=".specroad-build-", dir=parent))
    try:
        module = stage / "module"
        module.mkdir()
        for relative, data in payload.items():
            dest = module / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        (module / "__main__.py").write_text(ARCHIVE_MAIN, encoding="utf-8")
        zipapp.create_archive(module, target=stage / "specroad.pyz", compressed=False)
        # Refuse an output created while this build was in progress.
        if os.path.lexists(output):
            raise FileExistsError(output)
        stage.rename(output)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return output / "module", output / "specroad.pyz"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        build_core(Path(__file__).resolve().parents[1] / "src", args.output)
    except (OSError, ValueError) as error:
        parser.exit(2, "Core build failed: " + str(error) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
