"""Create, verify, and restore complete ORIGIN beta data snapshots.

Backups contain a consistent SQLite snapshot plus every mission artifact. They
never include Compose secrets, which live outside the data directory. Operators
must stop the exclusive worker before creating a backup so mission files do not
change while the archive is being assembled.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import sqlite3
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import BinaryIO
from urllib.parse import quote


FORMAT_VERSION = 1
ARCHIVE_ROOT = "origin-beta-backup"
MANIFEST_NAME = f"{ARCHIVE_ROOT}/manifest.json"
DATABASE_NAME = "origin_web.sqlite3"
MAX_FILES = 100_000
MAX_TOTAL_BYTES = 10 * 1024 * 1024 * 1024
MAX_MANIFEST_BYTES = 2 * 1024 * 1024


class BackupError(RuntimeError):
    pass


def _digest_stream(stream: BinaryIO) -> str:
    digest = hashlib.sha256()
    while chunk := stream.read(1024 * 1024):
        digest.update(chunk)
    return digest.hexdigest()


def _digest_file(path: Path) -> str:
    with path.open("rb") as stream:
        return _digest_stream(stream)


def _integrity_check(path: Path) -> None:
    try:
        connection = sqlite3.connect(f"file:{quote(str(path))}?mode=ro", uri=True)
        result = connection.execute("PRAGMA integrity_check").fetchone()
    except sqlite3.Error as exc:
        raise BackupError(f"SQLite integrity check failed: {exc}") from exc
    finally:
        if "connection" in locals():
            connection.close()
    if not result or result[0] != "ok":
        raise BackupError(f"SQLite integrity check failed: {result!r}")


def _sqlite_snapshot(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise BackupError(f"database is missing: {source}")
    source_connection = None
    destination_connection = None
    try:
        source_connection = sqlite3.connect(
            f"file:{quote(str(source))}?mode=ro", uri=True)
        destination_connection = sqlite3.connect(destination)
        source_connection.backup(destination_connection)
        destination_connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        destination_connection.commit()
    except sqlite3.Error as exc:
        raise BackupError(f"could not snapshot SQLite database: {exc}") from exc
    finally:
        if destination_connection is not None:
            destination_connection.close()
        if source_connection is not None:
            source_connection.close()
    destination.chmod(0o600)
    _integrity_check(destination)


def _regular_mission_files(data_dir: Path) -> list[Path]:
    missions = data_dir / "missions"
    if not missions.exists():
        return []
    files: list[Path] = []
    for path in sorted(missions.rglob("*")):
        if path.is_symlink():
            raise BackupError(f"mission snapshot refuses symbolic link: {path}")
        if path.is_file():
            files.append(path)
        elif not path.is_dir():
            raise BackupError(f"mission snapshot refuses special file: {path}")
        if len(files) > MAX_FILES:
            raise BackupError("mission snapshot exceeds the file-count limit")
    return files


def _tar_info(path: Path, archive_name: str) -> tarfile.TarInfo:
    info = tarfile.TarInfo(archive_name)
    stat = path.stat()
    info.size = stat.st_size
    info.mode = 0o600
    info.mtime = int(stat.st_mtime)
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    return info


def create_backup(data_dir: Path, output: Path) -> dict:
    data_dir = Path(data_dir).resolve()
    output = Path(output).resolve()
    if not data_dir.is_dir():
        raise BackupError(f"data directory is missing: {data_dir}")
    if output == data_dir or data_dir in output.parents:
        raise BackupError("backup output must be outside the live data directory")
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    files = _regular_mission_files(data_dir)
    total = sum(path.stat().st_size for path in files)
    if total > MAX_TOTAL_BYTES:
        raise BackupError("mission snapshot exceeds the total-size limit")

    with tempfile.TemporaryDirectory(prefix="origin-db-", dir=output.parent) as temp_dir:
        database_snapshot = Path(temp_dir) / DATABASE_NAME
        _sqlite_snapshot(data_dir / DATABASE_NAME, database_snapshot)
        sources = [(database_snapshot, DATABASE_NAME)]
        sources.extend((path, path.relative_to(data_dir).as_posix()) for path in files)
        if sum(path.stat().st_size for path, _ in sources) > MAX_TOTAL_BYTES:
            raise BackupError("complete snapshot exceeds the total-size limit")
        entries = []
        for path, relative in sources:
            entries.append({
                "path": relative,
                "size": path.stat().st_size,
                "sha256": _digest_file(path),
            })
        manifest = {
            "format": "origin-beta-backup",
            "format_version": FORMAT_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "research_core": "2.1.2",
            "database": DATABASE_NAME,
            "files": entries,
            "worker_quiescence_required": True,
        }
        encoded_manifest = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
        temporary_output = output.with_name(f".{output.name}.{os.getpid()}.tmp")
        try:
            with tarfile.open(temporary_output, "w:gz", format=tarfile.PAX_FORMAT) as archive:
                for path, relative in sources:
                    with path.open("rb") as stream:
                        archive.addfile(
                            _tar_info(path, f"{ARCHIVE_ROOT}/{relative}"), stream)
                info = tarfile.TarInfo(MANIFEST_NAME)
                info.size = len(encoded_manifest)
                info.mode = 0o600
                info.mtime = int(datetime.now(timezone.utc).timestamp())
                info.uid = info.gid = 0
                archive.addfile(info, io.BytesIO(encoded_manifest))
            temporary_output.chmod(0o600)
            os.replace(temporary_output, output)
        finally:
            temporary_output.unlink(missing_ok=True)
    return manifest


def _safe_entry_path(value: str) -> PurePosixPath:
    if not isinstance(value, str):
        raise BackupError("backup manifest path is not a string")
    path = PurePosixPath(value)
    if (not value or not path.parts or path.is_absolute() or ".." in path.parts or
            path.parts[0] == ARCHIVE_ROOT or value.endswith("/")):
        raise BackupError(f"unsafe manifest path: {value!r}")
    return path


def verify_backup(archive_path: Path) -> dict:
    archive_path = Path(archive_path)
    if not archive_path.is_file():
        raise BackupError(f"backup archive is missing: {archive_path}")
    try:
        archive = tarfile.open(archive_path, "r:gz")
    except (OSError, tarfile.TarError) as exc:
        raise BackupError(f"backup archive is unreadable: {exc}") from exc
    with archive:
        members = archive.getmembers()
        if len(members) > MAX_FILES + 2:
            raise BackupError("backup archive exceeds the member-count limit")
        names = [member.name for member in members]
        if len(names) != len(set(names)):
            raise BackupError("backup archive contains duplicate member names")
        member_map = {member.name: member for member in members}
        manifest_member = member_map.get(MANIFEST_NAME)
        if (manifest_member is None or not manifest_member.isfile() or
                manifest_member.size > MAX_MANIFEST_BYTES):
            raise BackupError("backup archive has no valid manifest")
        stream = archive.extractfile(manifest_member)
        if stream is None:
            raise BackupError("backup manifest could not be read")
        try:
            manifest = json.loads(stream.read(MAX_MANIFEST_BYTES + 1))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BackupError("backup manifest is not valid UTF-8 JSON") from exc
        if (manifest.get("format") != "origin-beta-backup" or
                manifest.get("format_version") != FORMAT_VERSION or
                manifest.get("database") != DATABASE_NAME or
                not isinstance(manifest.get("files"), list)):
            raise BackupError("backup manifest format is unsupported")
        if len(manifest["files"]) > MAX_FILES + 1:
            raise BackupError("backup manifest exceeds the file-count limit")
        expected_names = {MANIFEST_NAME}
        total = 0
        saw_database = False
        for entry in manifest["files"]:
            if not isinstance(entry, dict) or set(entry) != {"path", "size", "sha256"}:
                raise BackupError("backup manifest contains an invalid file entry")
            relative = _safe_entry_path(entry["path"])
            if not isinstance(entry["size"], int) or entry["size"] < 0:
                raise BackupError("backup manifest contains an invalid file size")
            if (not isinstance(entry["sha256"], str) or len(entry["sha256"]) != 64 or
                    any(character not in "0123456789abcdef" for character in entry["sha256"])):
                raise BackupError("backup manifest contains an invalid digest")
            name = f"{ARCHIVE_ROOT}/{relative.as_posix()}"
            if name in expected_names:
                raise BackupError("backup manifest contains a duplicate path")
            expected_names.add(name)
            member = member_map.get(name)
            if member is None or not member.isfile() or member.size != entry["size"]:
                raise BackupError(f"backup member does not match manifest: {relative}")
            total += member.size
            if total > MAX_TOTAL_BYTES:
                raise BackupError("backup archive exceeds the total-size limit")
            content = archive.extractfile(member)
            if content is None or _digest_stream(content) != entry["sha256"]:
                raise BackupError(f"backup member digest mismatch: {relative}")
            saw_database |= relative.as_posix() == DATABASE_NAME
        if set(member_map) != expected_names:
            raise BackupError("backup archive contains unlisted members")
        if not saw_database:
            raise BackupError("backup archive contains no database snapshot")
    return manifest


def restore_backup(archive_path: Path, target: Path) -> dict:
    manifest = verify_backup(archive_path)
    target = Path(target).resolve()
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise BackupError("restore target must be absent or an empty directory")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}-restore-",
                                    dir=target.parent))
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            members = {member.name: member for member in archive.getmembers()}
            for entry in manifest["files"]:
                relative = _safe_entry_path(entry["path"])
                destination = staging.joinpath(*relative.parts)
                destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                source = archive.extractfile(
                    members[f"{ARCHIVE_ROOT}/{relative.as_posix()}"])
                if source is None:
                    raise BackupError(f"could not restore backup member: {relative}")
                temporary = destination.with_name(f".{destination.name}.tmp")
                digest = hashlib.sha256()
                with temporary.open("xb") as output:
                    while chunk := source.read(1024 * 1024):
                        digest.update(chunk)
                        output.write(chunk)
                    output.flush()
                    os.fsync(output.fileno())
                if digest.hexdigest() != entry["sha256"]:
                    raise BackupError(f"backup changed while restoring: {relative}")
                temporary.chmod(0o600)
                os.replace(temporary, destination)
        _integrity_check(staging / DATABASE_NAME)
        staging.chmod(0o700)
        if target.exists():
            # A Docker named-volume mount point cannot itself be replaced. It is
            # safe to populate because the precondition above proved it empty.
            for child in staging.iterdir():
                os.replace(child, target / child.name)
            staging.rmdir()
            target.chmod(0o700)
        else:
            os.replace(staging, target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create", help="create a verified backup archive")
    create.add_argument("--data-dir", type=Path, required=True)
    create.add_argument("--out", type=Path, required=True)
    verify = subparsers.add_parser("verify", help="verify every archived file digest")
    verify.add_argument("--archive", type=Path, required=True)
    restore = subparsers.add_parser("restore", help="restore into an empty directory")
    restore.add_argument("--archive", type=Path, required=True)
    restore.add_argument("--target", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            manifest = create_backup(args.data_dir, args.out)
            print(f"Created backup with {len(manifest['files'])} files: {args.out}")
        elif args.command == "verify":
            manifest = verify_backup(args.archive)
            print(f"Verified backup with {len(manifest['files'])} files: {args.archive}")
        else:
            manifest = restore_backup(args.archive, args.target)
            print(f"Restored backup with {len(manifest['files'])} files: {args.target}")
    except BackupError as exc:
        print(f"BACKUP ERROR: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
