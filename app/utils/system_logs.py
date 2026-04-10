"""Lecture et agrégation des logs système et d'audit utilisateur."""
from __future__ import annotations

import json
import re
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any


def _logs_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "logs"


def _is_noise_log_file(file_path: Path) -> bool:
    """Ignore les logs techniques externes non applicatifs (ex: MCP)."""
    name = (file_path.name or "").lower()
    return name.startswith("mcp-server-")


def _is_noise_log_line(text: str) -> bool:
    """Ignore les messages connus sans impact applicatif."""
    line = (text or "").lower()
    noise_markers = [
        "could not read package.json from project root",
        "couldn't find project name in package json",
    ]
    return any(marker in line for marker in noise_markers)


def _to_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.min
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return datetime.min


def _read_audit_events(limit: int = 300) -> list[dict[str, Any]]:
    file_path = _logs_dir() / "user_audit.log"
    if not file_path.exists() or not file_path.is_file():
        return []

    events: list[dict[str, Any]] = []
    try:
        with file_path.open("r", encoding="utf-8", errors="ignore") as handle:
            lines = deque(handle, maxlen=limit)
    except OSError:
        return []

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue

        role = str(evt.get("actor_role") or "guest").strip()
        username = str(evt.get("actor_username") or "anonymous").strip()
        event_type = str(evt.get("event_type") or "event").strip()
        status = str(evt.get("status") or "SUCCESS").strip().upper()
        timestamp = str(evt.get("timestamp") or "")
        details = evt.get("details") or {}
        if not isinstance(details, dict):
            details = {"raw": str(details)}

        events.append({
            "timestamp": timestamp,
            "actor_role": role,
            "actor_username": username,
            "event_type": event_type,
            "status": status,
            "path": str(evt.get("path") or ""),
            "method": str(evt.get("method") or ""),
            "details": details,
            "summary": f"[{status}] {role}:{username} - {event_type}",
        })

    events.sort(key=lambda item: _to_datetime(item.get("timestamp")), reverse=True)
    return events


def _read_system_error_lines(limit_per_file: int = 300) -> list[dict[str, Any]]:
    logs_dir = _logs_dir()
    if not logs_dir.exists() or not logs_dir.is_dir():
        return []

    level_pattern = re.compile(r"\b(ERROR|WARNING|WARN|CRITICAL)\b", re.IGNORECASE)
    log_files = sorted(
        [p for p in logs_dir.iterdir() if p.is_file() and p.suffix.lower() in {".log", ".txt"}],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    items: list[dict[str, Any]] = []
    for file_path in log_files[:4]:
        if file_path.name == "user_audit.log":
            continue
        if _is_noise_log_file(file_path):
            continue
        try:
            with file_path.open("r", encoding="utf-8", errors="ignore") as handle:
                last_lines = deque(handle, maxlen=limit_per_file)
        except OSError:
            continue

        for line in last_lines:
            text = line.strip()
            if not text:
                continue
            if _is_noise_log_line(text):
                continue
            m = level_pattern.search(text)
            if not m:
                continue
            level = m.group(1).upper()
            level = "WARNING" if level == "WARN" else level
            items.append({
                "level": level,
                "file": file_path.name,
                "message": text[:300],
            })

    return items


def collect_system_logs_details() -> dict[str, Any]:
    """Résumé compact pour la carte dashboard."""
    logs_dir = _logs_dir()
    if not logs_dir.exists() or not logs_dir.is_dir():
        return {
            "total_files": 0,
            "lines_scanned": 0,
            "errors": 0,
            "warnings": 0,
            "last_message": "Aucun fichier de log",
            "last_level": "INFO",
            "last_file": None,
            "last_modified": None,
            "admin_events": 0,
            "user_events": 0,
            "total_events": 0,
        }

    log_files = sorted(
        [p for p in logs_dir.iterdir() if p.is_file() and p.suffix.lower() in {".log", ".txt"}],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    total_errors = 0
    total_warnings = 0
    total_lines = 0
    latest_message = "Aucune entrée de log"
    latest_level = "INFO"
    latest_file = None
    latest_mtime = None

    scanned_files = [p for p in log_files if not _is_noise_log_file(p)][:3]
    for index, file_path in enumerate(scanned_files):
        try:
            with file_path.open("r", encoding="utf-8", errors="ignore") as handle:
                last_lines = deque(handle, maxlen=250)
        except OSError:
            continue

        lines = [
            line.strip()
            for line in last_lines
            if line and line.strip() and not _is_noise_log_line(line)
        ]
        total_lines += len(lines)
        joined = "\n".join(lines)

        total_errors += len(re.findall(r"\b(ERROR|CRITICAL)\b", joined, re.IGNORECASE))
        total_warnings += len(re.findall(r"\b(WARNING|WARN)\b", joined, re.IGNORECASE))

        if index == 0:
            latest_file = file_path.name
            latest_mtime = datetime.utcfromtimestamp(file_path.stat().st_mtime).isoformat() + "Z"
            if lines:
                latest_raw = lines[-1]
                latest_message = latest_raw[:200]
                match = re.search(r"\b(ERROR|WARNING|WARN|INFO|DEBUG|CRITICAL)\b", latest_raw, re.IGNORECASE)
                if match:
                    level_token = match.group(1).upper()
                    latest_level = "WARNING" if level_token == "WARN" else level_token

    audit_events = _read_audit_events(limit=400)
    admin_events = sum(1 for event in audit_events if event.get("actor_role", "").strip().lower() == "admin")
    user_events = max(len(audit_events) - admin_events, 0)

    if audit_events:
        latest_message = audit_events[0]["summary"]
        latest_file = "user_audit.log"
        latest_level = "INFO"

    return {
        "total_files": len([p for p in log_files if not _is_noise_log_file(p)]),
        "lines_scanned": total_lines,
        "errors": total_errors,
        "warnings": total_warnings,
        "last_message": latest_message,
        "last_level": latest_level,
        "last_file": latest_file,
        "last_modified": latest_mtime,
        "admin_events": admin_events,
        "user_events": user_events,
        "total_events": len(audit_events),
    }


def get_system_logs_page_data(audit_limit: int = 200, system_limit: int = 120) -> dict[str, Any]:
    """Données complètes pour la page de détail des logs."""
    audit_events = _read_audit_events(limit=audit_limit)
    system_items = _read_system_error_lines(limit_per_file=300)

    summary = collect_system_logs_details()
    return {
        "summary": summary,
        "audit_events": audit_events[:audit_limit],
        "system_events": system_items[:system_limit],
    }
