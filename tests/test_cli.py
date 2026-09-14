"""Entry point contracts; no assertions about human-readable output."""

from contextlib import ExitStack
from importlib.metadata import EntryPoint
from unittest.mock import patch
import errno
from pathlib import Path
import importlib.util
import io
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

from specroad.cli import main

ROOT = Path(__file__).resolve().parents[1]


def build_distribution(output, source=None):
    spec = importlib.util.spec_from_file_location("specroad_dev_build", ROOT / "tools/build_core.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    return builder.build_core(source or ROOT / "src", output)


def copy_source_fixture(destination: Path, *, source_root: Path | None = None) -> Path:
    """Copy only package bytes; do not inherit host metadata or local src siblings.

    Inspect fresh lstat metadata, not cached DirEntry type hints. In a virtual
    filesystem these may disagree, for example for emulated hardlinks. Actual
    symlinks and special files are still rejected, never followed or ignored.
    Validate and read the package before creating any destination entries.
    """
    source_root = ROOT / "src" if source_root is None else Path(source_root)
    if not stat.S_ISDIR(source_root.lstat().st_mode):
        raise ValueError(f"Source fixture root is not a regular directory: {source_root!s}")
    package = source_root / "specroad"
    payload = {}
    directories = []

    def collect_directory(source: Path, relative: Path) -> None:
        if not stat.S_ISDIR(source.lstat().st_mode):
            raise ValueError(f"Source fixture directory is not regular: {source!s}")
        directories.append(relative)
        # Enumeration supplies names only. Every type decision uses fresh lstat.
        with os.scandir(source) as entries:
            names = sorted(entry.name for entry in entries)
        for name in names:
            source_path = source / name
            target_relative = relative / name
            mode = source_path.lstat().st_mode
            if stat.S_ISLNK(mode):
                raise ValueError(f"Unexpected symlink in source fixture: {source_path!s}")
            if stat.S_ISDIR(mode):
                if name != "__pycache__":
                    collect_directory(source_path, target_relative)
            elif stat.S_ISREG(mode):
                # Explicit reads, no copytree/copyfile/copystat or fast-copy path.
                with source_path.open("rb") as incoming:
                    payload[target_relative] = incoming.read()
            else:
                raise ValueError(f"Unexpected special source fixture entry: {source_path!s}")

    collect_directory(package, Path("specroad"))
    destination = Path(destination)
    destination.mkdir()  # Exclusive: an existing target is never overwritten.
    for relative in directories:
        (destination / relative).mkdir()
    for relative, data in payload.items():
        with (destination / relative).open("xb") as outgoing:
            outgoing.write(data)
    return destination


def files_under(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def run_process(arguments, cwd):
    env = dict(os.environ)
    env["PATH"] = ""
    env.pop("VIRTUAL_ENV", None)
    return subprocess.run(
        [sys.executable, *arguments], cwd=cwd, env=env,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )


class EntryPointTests(unittest.TestCase):
    def test_help_is_an_implemented_no_write_operation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "specroad.json").write_bytes(b'{"existing":true}\n')
            before = files_under(root)
            # Public callable used by the installed console entry point.
            entry = EntryPoint(name="specroad", value="specroad.cli:main", group="console_scripts")
            previous = Path.cwd()
            try:
                os.chdir(root)
                self.assertEqual(entry.load()(["--help"], stdout=io.StringIO()), 0)
            finally:
                os.chdir(previous)
            self.assertEqual(before, files_under(root))

    def test_missing_command_returns_usage_error(self):
        self.assertEqual(main([], stderr=io.StringIO()), 2)

    def test_module_and_zipapp_have_same_exit_and_file_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            module, archive = build_distribution(root / "build")
            project = root / "project"
            project.mkdir()
            (project / "specroad.json").write_bytes(b'{"keep":true}\n')
            distribution_before = files_under(root / "build")
            project_before = files_under(project)
            # -m from the trusted unpacked distribution needs no installation.
            a = run_process(["-E", "-S", "-B", "-m", "specroad", "--help"], module)
            b = run_process(["-I", "-S", "-B", str(archive), "--help"], project)
            c = run_process(["-I", "-S", "-B", str(module), "--help"], project)
            for result in (a, b, c):
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(project_before, files_under(project))
            self.assertEqual(distribution_before, files_under(root / "build"))

    def test_builder_preserves_existing_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "existing"
            output.mkdir()
            (output / "keep").write_bytes(b'keep')
            with self.assertRaises(FileExistsError):
                build_distribution(output)
            self.assertEqual(files_under(output), {"keep": b'keep'})

    def test_builder_rejects_source_symlink_before_publication(self):
        if not hasattr(os, "symlink"):
            self.skipTest("Host cannot create symlinks")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "src"
            copy_source_fixture(source)
            foreign = root / "foreign.py"
            foreign.write_text("raise RuntimeError('must not execute')\n")
            (source / "specroad" / "foreign.py").symlink_to(foreign)
            with self.assertRaises(ValueError):
                build_distribution(root / "build", source)
            self.assertFalse((root / "build").exists())


    def test_portable_build_without_optional_copy_or_metadata_facilities(self):
        # Model the reported EINVAL capability failure, without relying on PRoot.
        # The contract is a complete, runnable distribution with unchanged inputs.
        def unavailable(*args, **kwargs):
            raise OSError(errno.EINVAL, "optional copy/metadata facility unavailable")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            with ExitStack() as stack:
                for name in ("copytree", "copyfile", "copy", "copy2", "copystat", "copymode"):
                    stack.enter_context(patch.object(shutil, name, side_effect=unavailable))
                for name in ("sendfile", "copy_file_range", "listxattr", "getxattr", "setxattr", "utime"):
                    if hasattr(os, name):
                        stack.enter_context(patch.object(os, name, side_effect=unavailable))
                source = copy_source_fixture(root / "source")
                source_before = files_under(source)
                module, archive = build_distribution(root / "build", source)
                self.assertEqual(files_under(source), source_before)
                self.assertEqual(files_under(module / "specroad"), files_under(source / "specroad"))
            for invocation in (module, archive):
                result = run_process(["-I", "-S", "-B", str(invocation), "--help"], project)
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(files_under(project), {})


class EntryPointRobustnessTests(unittest.TestCase):
    def test_bad_input_never_prompts_or_claims_success(self):
        class ForbiddenInput:
            def read(self, *args, **kwargs):
                raise AssertionError("implicit stdin read")
            readline = read
            readlines = read
            def __iter__(self):
                raise AssertionError("implicit stdin iteration")
        original = sys.stdin
        sys.stdin = ForbiddenInput()
        try:
            for arguments in ([], ["--help", "extra"], ["--help", "--bad"],
                              ["--he"], ["change", "apply"], ["validate"], ["init"],
                              ["--format"], ["--format", "json"], ["\x1b[31m"],
                              "--help", [None], 42):
                with self.subTest(arguments=arguments):
                    self.assertEqual(main(arguments, stdout=io.StringIO(), stderr=io.StringIO()), 2)
        finally:
            sys.stdin = original

    def test_argument_list_is_not_modified(self):
        args = ["--help"]
        self.assertEqual(main(args, stdout=io.StringIO()), 0)
        self.assertEqual(args, ["--help"])

    def test_entry_point_uses_current_argv_when_not_supplied(self):
        previous = sys.argv
        try:
            sys.argv = ["specroad", "--help"]
            self.assertEqual(main(stdout=io.StringIO()), 0)
            sys.argv = ["specroad", "unknown"]
            self.assertEqual(main(stderr=io.StringIO()), 2)
        finally:
            sys.argv = previous

    def test_relocated_distributions_do_not_need_original_source(self):
        with tempfile.TemporaryDirectory(prefix="specroad relocation ") as tmp:
            root = Path(tmp)
            source = root / "source"
            copy_source_fixture(source)
            build_distribution(root / "build", source)
            shutil.rmtree(source)
            relocated = root / "verschoben ueberall"
            (root / "build").rename(relocated)
            project = root / "project"
            project.mkdir()
            before = files_under(relocated)
            for command in (str(relocated / "specroad.pyz"), str(relocated / "module")):
                for args, code in ((["--help"], 0), ([], 2), (["change", "apply"], 2)):
                    result = run_process(["-I", "-S", "-B", command, *args], project)
                    self.assertEqual(result.returncode, code, result.stderr)
            self.assertEqual(files_under(project), {})
            self.assertEqual(files_under(relocated), before)

    def test_hostile_cwd_cannot_execute_code_in_isolated_portable_invocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            module, archive = build_distribution(root / "build")
            project = root / "project"
            project.mkdir()
            sentinel = project / "FOREIGN_CODE_EXECUTED"
            poison = "open(" + repr(str(sentinel)) + ", 'w').write('executed')\nraise RuntimeError('foreign module')\n"
            for name in ("argparse", "json", "os", "typing", "rich", "sitecustomize"):
                (project / (name + ".py")).write_text(poison)
            (project / "specroad").mkdir()
            (project / "specroad" / "__init__.py").write_text(poison)
            before = files_under(project)
            for invocation in (archive, module):
                result = run_process(["-I", "-S", "-B", str(invocation), "--help"], project)
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(sentinel.exists())
            self.assertEqual(files_under(project), before)

    def test_missing_builder_output_parameter_has_no_side_effect(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_process(["-I", "-S", "-B", str(ROOT / "tools/build_core.py")], root)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(files_under(root), {})

    def test_incomplete_source_does_not_publish_partial_distribution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "source" / "specroad").mkdir(parents=True)
            with self.assertRaises(ValueError):
                build_distribution(root / "build", root / "source")
            self.assertFalse((root / "build").exists())

    def test_output_inside_source_is_rejected_without_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            copy_source_fixture(source)
            before = files_under(source)
            with self.assertRaises(ValueError):
                build_distribution(source / "build", source)
            self.assertEqual(before, files_under(source))


    def test_source_directory_and_dangling_links_are_rejected(self):
        if not hasattr(os, "symlink"):
            self.skipTest("Host cannot create symlinks")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root / "outside"
            outside.mkdir()
            (outside / "keep.py").write_bytes(b"# original\n")
            original = files_under(outside)
            for kind in ("directory", "dangling"):
                with self.subTest(kind=kind):
                    source = copy_source_fixture(root / (kind + "-source"))
                    target = outside if kind == "directory" else root / "absent.py"
                    (source / "specroad" / "linked.py").symlink_to(
                        target, target_is_directory=kind == "directory")
                    output = root / (kind + "-build")
                    with self.assertRaises(ValueError):
                        build_distribution(output, source)
                    self.assertFalse(output.exists())
            self.assertEqual(files_under(outside), original)

    def test_existing_output_file_and_link_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            existing = root / "existing"
            existing.write_bytes(b"preserve exactly")
            with self.assertRaises(FileExistsError):
                build_distribution(existing)
            self.assertEqual(existing.read_bytes(), b"preserve exactly")
            if hasattr(os, "symlink"):
                link = root / "link"
                link.symlink_to(existing)
                with self.assertRaises(FileExistsError):
                    build_distribution(link)
                self.assertTrue(link.is_symlink())
                self.assertEqual(existing.read_bytes(), b"preserve exactly")

    def test_failed_archive_creation_leaves_no_partial_publication(self):
        import zipapp
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            keep = root / "keep"
            keep.write_bytes(b"preserve exactly")
            with patch.object(zipapp, "create_archive", side_effect=OSError(errno.EIO, "archive write failed")):
                with self.assertRaises(OSError):
                    build_distribution(root / "build")
            self.assertEqual(set(root.iterdir()), {keep})
            self.assertEqual(keep.read_bytes(), b"preserve exactly")


class SourceFixturePortabilityTests(unittest.TestCase):
    """Real copied bytes, isolation and rejection; no rendering expectations."""

    def test_local_src_siblings_are_not_part_of_the_distribution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = copy_source_fixture(root / "source")
            outside = root / "outside"
            outside.mkdir()
            (outside / "keep.py").write_bytes(b"do not package or alter\n")
            metadata = source / "specroad.egg-info"
            metadata.mkdir()
            (metadata / "development-link").symlink_to(outside, target_is_directory=True)
            (source / "unrelated-link").symlink_to(root / "missing")
            before = files_under(source / "specroad")
            copied = copy_source_fixture(root / "copied", source_root=source)
            self.assertEqual({p.name for p in copied.iterdir()}, {"specroad"})
            self.assertEqual(files_under(copied / "specroad"), before)
            module, archive = build_distribution(root / "build", copied)
            self.assertEqual(files_under(module / "specroad"), before)
            result = run_process(["-I", "-S", "-B", str(archive), "--help"], root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((outside / "keep.py").read_bytes(), b"do not package or alter\n")
            self.assertTrue((metadata / "development-link").is_symlink())
            self.assertTrue((source / "unrelated-link").is_symlink())

    def test_cached_symlink_hints_do_not_override_regular_file_metadata(self):
        # Model a virtual filesystem whose enumeration reports emulated links.
        # No real source link is reclassified; lstat remains the host authority.
        real_scandir = os.scandir

        class MisleadingEntry:
            def __init__(self, entry):
                self.name = entry.name
                self.path = entry.path
            def is_symlink(self):
                return True
            def is_file(self, *, follow_symlinks=True):
                return False
            def is_dir(self, *, follow_symlinks=True):
                return False

        class MisleadingScan:
            def __init__(self, path):
                self.scan = real_scandir(path)
            def __enter__(self):
                return iter(MisleadingEntry(entry) for entry in self.scan)
            def __exit__(self, *args):
                self.scan.close()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = copy_source_fixture(root / "source")
            expected = files_under(source / "specroad")
            with patch.object(os, "scandir", side_effect=MisleadingScan):
                copied = copy_source_fixture(root / "copied", source_root=source)
            self.assertEqual(files_under(copied / "specroad"), expected)
            module, archive = build_distribution(root / "build", copied)
            self.assertEqual(files_under(module / "specroad"), expected)
            result = run_process(["-I", "-S", "-B", str(archive), "--help"], root)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_actual_file_directory_and_dangling_links_remain_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root / "outside"
            outside.mkdir()
            keep = outside / "keep.py"
            keep.write_bytes(b"outside must stay unchanged\n")
            for kind, target in (("file", keep), ("directory", outside),
                                 ("dangling", root / "absent.py")):
                with self.subTest(kind=kind):
                    source = copy_source_fixture(root / (kind + "-source"))
                    (source / "specroad" / "foreign.py").symlink_to(
                        target, target_is_directory=kind == "directory")
                    destination = root / (kind + "-copy")
                    with self.assertRaises(ValueError):
                        copy_source_fixture(destination, source_root=source)
                    self.assertFalse(destination.exists())
            self.assertEqual(keep.read_bytes(), b"outside must stay unchanged\n")

    def test_package_root_symlink_is_rejected_before_destination_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good = copy_source_fixture(root / "good")
            source = root / "source"
            source.mkdir()
            (source / "specroad").symlink_to(good / "specroad", target_is_directory=True)
            destination = root / "copy"
            with self.assertRaises(ValueError):
                copy_source_fixture(destination, source_root=source)
            self.assertFalse(destination.exists())

    def test_metadata_failure_is_not_treated_as_permission_to_copy(self):
        original_lstat = Path.lstat
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = copy_source_fixture(root / "source")
            denied = source / "specroad" / "__init__.py"
            original = denied.read_bytes()
            def fail_for_one_file(path, *args, **kwargs):
                if path == denied:
                    raise OSError(errno.EACCES, "cannot inspect test source")
                return original_lstat(path, *args, **kwargs)
            destination = root / "copy"
            with patch.object(Path, "lstat", new=fail_for_one_file):
                with self.assertRaises(OSError):
                    copy_source_fixture(destination, source_root=source)
            self.assertFalse(destination.exists())
            self.assertEqual(denied.read_bytes(), original)

    def test_existing_destination_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "existing"
            destination.mkdir()
            (destination / "keep").write_bytes(b"unchanged")
            with self.assertRaises(FileExistsError):
                copy_source_fixture(destination)
            self.assertEqual(files_under(destination), {"keep": b"unchanged"})
