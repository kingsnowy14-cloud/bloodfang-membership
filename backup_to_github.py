#!/usr/bin/env python3
"""Daily, consistent /data backups to private GitHub Releases."""
import datetime as dt
import json
import logging
import os
import shutil
import sqlite3
import tarfile
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

LOG = logging.getLogger("github-backup")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
REPOSITORY = os.getenv("GITHUB_REPOSITORY", "kingsnowy14-cloud/bloodfang-membership")
TOKEN = os.getenv("GITHUB_BACKUP_TOKEN")
DATA_DIR = Path(os.getenv("BACKUP_DATA_DIR", "/data"))
BACKUP_HOUR_UTC = 3
KEEP_RELEASES = 2
API = "https://api.github.com"

def api_request(url, method="GET", payload=None, data=None, content_type="application/json"):
    if not TOKEN:
        raise RuntimeError("GITHUB_BACKUP_TOKEN is not configured")
    headers = {
        "Authorization": "Bearer " + TOKEN,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Railway-Daily-Backup",
    }
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif data is not None:
        body = data
        headers["Content-Type"] = content_type
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=120) as response:
        raw = response.read()
        return json.loads(raw.decode("utf-8")) if raw else None

def make_snapshot(destination):
    if not DATA_DIR.is_dir():
        raise RuntimeError(f"Persistent data directory not found: {DATA_DIR}")
    destination.mkdir(parents=True, exist_ok=True)
    for source in DATA_DIR.rglob("*"):
        if not source.is_file():
            continue
        relative = source.relative_to(DATA_DIR)
        suffix = source.suffix.lower()
        if suffix in (".db", ".sqlite", ".sqlite3"):
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                with sqlite3.connect(str(source), timeout=30) as src:
                    with sqlite3.connect(str(target), timeout=30) as dst:
                        src.backup(dst)
                LOG.info("Consistent SQLite snapshot: %s", relative)
            except sqlite3.DatabaseError:
                LOG.exception("Could not snapshot SQLite database %s", relative)
                raise
        elif not (source.name.endswith(("-wal", "-shm"))):
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

def create_archive():
    temp = tempfile.TemporaryDirectory(prefix="railway-backup-")
    root = Path(temp.name)
    snapshot = root / "data"
    make_snapshot(snapshot)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = root / f"railway-data-backup-{stamp}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(snapshot, arcname="data")
    return temp, archive, archive.name, stamp

def upload_backup():
    temp, archive, filename, stamp = create_archive()
    try:
        release = api_request(
            f"{API}/repos/{REPOSITORY}/releases",
            method="POST",
            payload={
                "tag_name": f"railway-data-backup-{stamp}",
                "name": f"Railway data backup {stamp}",
                "body": "Automatic daily backup of the Railway /data volume. SQLite databases are copied using the SQLite backup API.",
                "draft": False,
                "prerelease": False,
            },
        )
        upload_url = release["upload_url"].split("{", 1)[0]
        upload_url += "?" + urllib.parse.urlencode({"name": filename})
        with open(archive, "rb") as handle:
            api_request(upload_url, method="POST", data=handle.read(), content_type="application/gzip")
        LOG.info("Backup uploaded successfully: %s (%s bytes) to %s", filename, archive.stat().st_size, REPOSITORY)
        prune_old_releases()
    finally:
        temp.cleanup()

def prune_old_releases():
    releases = api_request(f"{API}/repos/{REPOSITORY}/releases?per_page=100") or []
    backups = [r for r in releases if str(r.get("tag_name", "")).startswith("railway-data-backup-")]
    backups.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    for release in backups[KEEP_RELEASES:]:
        api_request(f"{API}/repos/{REPOSITORY}/releases/{release['id']}", method="DELETE")
        LOG.info("Removed older backup release: %s", release.get("tag_name"))

def seconds_until_next_run():
    now = dt.datetime.now(dt.timezone.utc)
    target = now.replace(hour=BACKUP_HOUR_UTC, minute=0, second=0, microsecond=0)
    if target <= now:
        target += dt.timedelta(days=1)
    return max(1, int((target - now).total_seconds()))

def run_scheduler():
    LOG.info("Daily GitHub backup scheduler active for %s; next run at 03:00 UTC", REPOSITORY)
    while True:
        time.sleep(seconds_until_next_run())
        try:
            upload_backup()
        except Exception:
            LOG.exception("Daily GitHub backup failed; it will retry at the next scheduled run")

def start_backup_scheduler():
    thread = threading.Thread(target=run_scheduler, name="github-backup-scheduler", daemon=True)
    thread.start()
    return thread

if __name__ == "__main__":
    run_scheduler()
