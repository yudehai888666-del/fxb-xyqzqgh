import hashlib
import json
import shutil
import sqlite3
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

import click
from flask import current_app

from app.db import close_db


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_tree_files(source, destination):
    source = Path(source)
    if not source.exists():
        return
    for path in source.rglob("*"):
        if path.is_file():
            target = destination / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def create_backup(database, upload_dir, generated_dir, backup_dir):
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    archive_path = backup_dir / f"academic-planning-{timestamp}.tar.gz"

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "academic-planning-backup"
        data_root = root / "data"
        data_root.mkdir(parents=True)

        source_db = sqlite3.connect(Path(database))
        destination_db = sqlite3.connect(data_root / "database.sqlite3")
        try:
            source_db.backup(destination_db)
        finally:
            destination_db.close()
            source_db.close()

        _copy_tree_files(upload_dir, data_root / "uploads")
        _copy_tree_files(generated_dir, data_root / "generated")

        files = {}
        for path in sorted(data_root.rglob("*")):
            if path.is_file():
                relative = path.relative_to(root).as_posix()
                files[relative] = {"sha256": _sha256(path), "size_bytes": path.stat().st_size}
        manifest = {
            "format_version": 1,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "files": files,
        }
        (root / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        with tarfile.open(archive_path, "w:gz") as archive:
            archive.add(root, arcname=root.name)
    return archive_path


def _safe_extract(archive, destination):
    destination = Path(destination).resolve()
    for member in archive.getmembers():
        target = (destination / member.name).resolve()
        if destination != target and destination not in target.parents:
            raise ValueError("备份包包含不安全路径")
    archive.extractall(destination)


def verify_backup(archive_path):
    with tempfile.TemporaryDirectory() as temporary:
        with tarfile.open(archive_path, "r:gz") as archive:
            _safe_extract(archive, temporary)
        root = Path(temporary) / "academic-planning-backup"
        manifest_path = root / "manifest.json"
        if not manifest_path.exists():
            raise ValueError("备份包缺少校验清单")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for relative, expected in manifest.get("files", {}).items():
            path = root / relative
            if not path.is_file() or _sha256(path) != expected["sha256"]:
                raise ValueError(f"备份文件校验失败：{relative}")
        return manifest


def restore_backup(archive_path, database, upload_dir, generated_dir):
    verify_backup(archive_path)
    with tempfile.TemporaryDirectory() as temporary:
        with tarfile.open(archive_path, "r:gz") as archive:
            _safe_extract(archive, temporary)
        data_root = Path(temporary) / "academic-planning-backup" / "data"
        restored_db = data_root / "database.sqlite3"
        if not restored_db.exists():
            raise ValueError("备份包缺少数据库")

        database = Path(database)
        database.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(restored_db, database)
        for source, destination in (
            (data_root / "uploads", Path(upload_dir)),
            (data_root / "generated", Path(generated_dir)),
        ):
            destination.mkdir(parents=True, exist_ok=True)
            if source.exists():
                _copy_tree_files(source, destination)


def register_backup_commands(app):
    @app.cli.command("backup-data")
    def backup_data_command():
        """创建并校验完整数据备份。"""
        path = create_backup(
            current_app.config["DATABASE"],
            current_app.config["UPLOAD_DIR"],
            current_app.config["GENERATED_DIR"],
            current_app.config["BACKUP_DIR"],
        )
        verify_backup(path)
        click.echo(f"备份已创建并校验：{path}")

    @app.cli.command("restore-data")
    @click.argument("archive", type=click.Path(exists=True, path_type=Path))
    @click.option("--yes", is_flag=True, help="确认执行恢复")
    def restore_data_command(archive, yes):
        """校验备份后恢复数据，并先创建恢复前备份。"""
        if not yes:
            raise click.ClickException("恢复会替换当前数据库，请加 --yes 确认")
        safety = create_backup(
            current_app.config["DATABASE"],
            current_app.config["UPLOAD_DIR"],
            current_app.config["GENERATED_DIR"],
            current_app.config["BACKUP_DIR"],
        )
        close_db()
        restore_backup(
            archive,
            current_app.config["DATABASE"],
            current_app.config["UPLOAD_DIR"],
            current_app.config["GENERATED_DIR"],
        )
        click.echo(f"恢复完成；恢复前备份：{safety}")
