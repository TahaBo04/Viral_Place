"""Encrypted public-schema backup and an isolated, local-only restore drill."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile

from dotenv import dotenv_values
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import parse_dsn


def private_directory(path):
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or path.stat().st_mode & 0o077:
        raise RuntimeError("Backup directories must be private (mode 700), without symlinks.")


def connection_environment(url):
    settings = parse_dsn(url)
    if settings.get("sslmode") not in ("require", "verify-ca", "verify-full"):
        raise RuntimeError("Remote backups require an SSL-enabled database URL.")
    env = {key: value for key, value in os.environ.items() if not key.startswith("PG")}
    for key, variable in (("host", "PGHOST"), ("port", "PGPORT"), ("dbname", "PGDATABASE"), ("user", "PGUSER"), ("password", "PGPASSWORD"), ("sslmode", "PGSSLMODE"), ("channel_binding", "PGCHANNELBINDING")):
        if key in settings:
            env[variable] = settings[key]
    env["PGCONNECT_TIMEOUT"] = "15"
    env["PGAPPNAME"] = "briefvora-backup"
    return env


def counts(connection):
    with connection.cursor() as cursor:
        cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename")
        tables = [row[0] for row in cursor.fetchall()]
        result = {}
        for table in tables:
            cursor.execute(sql.SQL("SELECT count(*) FROM {}.{}").format(sql.Identifier("public"), sql.Identifier(table)))
            result[table] = cursor.fetchone()[0]
        return result


def checked(command, **kwargs):
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180, **kwargs)
    if result.returncode:
        raise RuntimeError(f"{Path(command[0]).name} failed. No credentials or database contents were logged.")
    return result.stdout


def pipe_commands(source, destination, source_env, destination_env):
    # Dump contents travel through pipes, never an unencrypted archive on disk.
    with tempfile.TemporaryFile() as errors:
        with subprocess.Popen(source, stdout=subprocess.PIPE, stderr=errors, env=source_env) as producer:
            try:
                result = subprocess.run(destination, stdin=producer.stdout, stdout=subprocess.DEVNULL, stderr=errors, env=destination_env, timeout=300)
                producer.stdout.close()
                source_code = producer.wait(timeout=30)
                if result.returncode or source_code:
                    raise RuntimeError("Backup/restore pipeline failed; sensitive output suppressed.")
            finally:
                if producer.poll() is None:
                    producer.kill()
                    producer.wait()


def backup(args, gpg):
    values = dotenv_values(args.env_file)
    url = os.environ.get("DATABASE_URL") or values.get("DATABASE_URL_UNPOOLED") or values.get("POSTGRES_URL_NON_POOLING") or values.get("DATABASE_URL")
    if not url:
        raise RuntimeError("An existing PostgreSQL DATABASE_URL is required.")
    env = connection_environment(url)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target = args.output / f"briefvora-{stamp}.dump.gpg"
    partial = target.with_suffix(".partial")
    try:
        with psycopg2.connect(url, connect_timeout=15, application_name="briefvora-backup") as connection:
            connection.set_session(isolation_level="REPEATABLE READ", readonly=True)
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_export_snapshot()")
                snapshot = cursor.fetchone()[0]
            table_counts = counts(connection)
            command = [str(args.pg_bin / "pg_dump"), "--format=custom", "--schema=public", "--no-owner", "--no-privileges", "--lock-wait-timeout=15s", "--snapshot=" + snapshot]
            pipe_commands(command, gpg + ["--cipher-algo", "AES256", "--symmetric", "--output", str(partial)], env, os.environ.copy())
        partial.rename(target)
    finally:
        partial.unlink(missing_ok=True)
    manifest = {"created_at": stamp, "schema": "public", "tables": table_counts, "sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "restore_verified": False}
    target.with_suffix(".json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Encrypted backup created: {target}")
    return target, manifest


def restore_drill(args, archive, manifest, gpg):
    if hashlib.sha256(archive.read_bytes()).hexdigest() != manifest["sha256"]:
        raise RuntimeError("The encrypted archive does not match its recorded checksum.")
    # No caller-supplied restore URL: the only destination is a disposable Unix socket.
    env = {key: value for key, value in os.environ.items() if not key.startswith("PG")}
    with tempfile.TemporaryDirectory(prefix="briefvora-restore-") as directory:
        data = Path(directory) / "data"
        command = lambda name: str(args.pg_bin / name)
        checked([command("initdb"), "-D", str(data), "-U", "restore", "-A", "trust", "--no-locale", "--encoding=UTF8"], env=env)
        started = False
        try:
            checked([command("pg_ctl"), "-D", str(data), "-l", str(Path(directory) / "postgres.log"), "-o", f"-c listen_addresses='' -k {directory}", "-w", "start"], env=env)
            started = True
            local_env = {**env, "PGHOST": directory, "PGDATABASE": "postgres", "PGUSER": "restore", "PGSSLMODE": "disable"}
            pipe_commands(gpg + ["--decrypt", str(archive)], [command("pg_restore"), "--clean", "--if-exists", "--no-owner", "--no-privileges", "--exit-on-error", "--single-transaction", "--dbname=postgres"], env, local_env)
            with psycopg2.connect(host=directory, dbname="postgres", user="restore") as connection:
                restored = counts(connection)
            if restored != manifest["tables"]:
                raise RuntimeError("Restored table counts do not match the exported snapshot.")
            manifest["restore_verified"] = True
            manifest["restore_verified_at"] = datetime.now(timezone.utc).isoformat()
            archive.with_suffix(".json").write_text(json.dumps(manifest, indent=2) + "\n")
            print(f"Restore verified: {len(restored)} tables; all row counts match. No production writes.")
        finally:
            if started:
                checked([command("pg_ctl"), "-D", str(data), "-m", "immediate", "-w", "stop"], env=env)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env.local"))
    parser.add_argument("--pg-bin", type=Path, default=Path(os.environ.get("PG_BIN", "/usr/lib/postgresql/17/bin")))
    parser.add_argument("--output", type=Path, default=Path.home() / ".local/share/briefvora/backups")
    parser.add_argument("--key-file", type=Path, default=Path.home() / ".config/briefvora/backup.key")
    parser.add_argument("--restore-drill", action="store_true")
    parser.add_argument("--archive", type=Path, help="Only restore-test an existing encrypted backup; never connect to production.")
    args = parser.parse_args()
    if args.archive and not args.restore_drill:
        parser.error("--archive requires --restore-drill")
    os.umask(0o077)
    private_directory(args.output)
    private_directory(args.key_file.parent)
    if not args.key_file.exists():
        if args.archive:
            raise RuntimeError("The original encryption key is required to restore.")
        with args.key_file.open("x") as handle:
            handle.write(secrets.token_urlsafe(48) + "\n")
    if args.key_file.is_symlink() or args.key_file.stat().st_mode & 0o077:
        raise RuntimeError("The backup key must be private (mode 600), without symlinks.")
    if not shutil.which("gpg"):
        raise RuntimeError("Install GnuPG before creating backups.")
    with tempfile.TemporaryDirectory(prefix="briefvora-gpg-") as gnupg:
        gpg = ["gpg", "--homedir", gnupg, "--batch", "--yes", "--no-symkey-cache", "--pinentry-mode", "loopback", "--passphrase-file", str(args.key_file)]
        if args.archive:
            archive = args.archive
            manifest = json.loads(archive.with_suffix(".json").read_text())
        else:
            archive, manifest = backup(args, gpg)
        if args.restore_drill:
            restore_drill(args, archive, manifest, gpg)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        print(str(error))
        raise SystemExit(1) from None
    except Exception as error:
        print(f"Backup operation failed ({type(error).__name__}). Sensitive details suppressed; verify configuration and tool versions.")
        raise SystemExit(1) from None
