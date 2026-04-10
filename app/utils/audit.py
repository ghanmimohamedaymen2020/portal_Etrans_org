"""Audit applicatif: journalise les evenements utilisateur/admin en JSONL."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import current_app, request


def log_user_event(
    event_type: str,
    actor_username: str,
    actor_role: str,
    status: str = "SUCCESS",
    details: dict[str, Any] | None = None,
) -> None:
    """Ecrit un evenement d'audit dans logs/user_audit.log au format JSON line.

    Cette fonction est best-effort: aucune exception ne doit remonter au flux principal.
    """
    try:
        logs_dir = Path(current_app.root_path).parent / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        file_path = logs_dir / "user_audit.log"

        payload: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": (event_type or "unknown").strip().lower(),
            "actor_username": (actor_username or "anonymous").strip(),
            "actor_role": (actor_role or "guest").strip(),
            "status": (status or "SUCCESS").strip().upper(),
            "path": request.path,
            "method": request.method,
            "ip": request.headers.get("X-Forwarded-For", request.remote_addr),
            "user_agent": (request.user_agent.string or "")[:240],
            "details": details or {},
        }

        with file_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        # Ne jamais casser le parcours utilisateur pour une erreur de journalisation.
        return
