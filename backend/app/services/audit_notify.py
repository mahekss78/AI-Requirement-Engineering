"""
app/services/audit_notify.py
=============================
Audit Logging and Notification Services for the AREA platform.

Responsibilities (PDS Vol 2 §9.3.4 & §14.3.4):
1. Writes immutable audit log entries to the database on state transitions,
   BA edits, clarification actions, Jira syncs, and version rollbacks.
2. Dispatches in-app role notifications to the DB queue.
3. Attempts SMTP email dispatch when configured; falls back gracefully to in-app queue.
4. Protects security by guaranteeing credentials and secrets are NEVER logged.
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.models.models import AuditLog, Notification

logger = logging.getLogger(__name__)


class AuditService:
    """
    Manages immutable audit logging for governance and traceability.
    """

    @staticmethod
    def log_event(
        db: Session,
        requirement_id: UUID,
        actor_role: str,
        action_type: str,
        prev_state: Optional[str] = None,
        new_state: Optional[str] = None,
        change_diff: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """
        Write an immutable audit log entry.
        """
        # Ensure no sensitive keys exist in change_diff
        safe_diff = None
        if change_diff:
            safe_diff = {
                k: v for k, v in change_diff.items()
                if k not in ("password", "password_hash", "token", "secret", "api_key")
            }

        log_entry = AuditLog(
            requirement_id=requirement_id,
            actor_role=actor_role or "SYSTEM",
            action_type=action_type,
            prev_state=prev_state,
            new_state=new_state,
            change_diff=safe_diff,
        )
        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)
        logger.info(
            f"AuditLog created [ID: {log_entry.id}] | req={requirement_id} | "
            f"actor={actor_role} | action={action_type}"
        )
        return log_entry


class NotificationService:
    """
    Manages in-app role notification queues and SMTP email fallbacks.
    """

    @staticmethod
    def dispatch_notification(
        db: Session,
        recipient_role: str,
        message: str,
        notification_type: str = "INFO",
        requirement_id: Optional[UUID] = None,
    ) -> Notification:
        """
        Create an in-app notification row and attempt SMTP email delivery if configured.
        """
        notif = Notification(
            recipient_role=recipient_role,
            message=message,
            notification_type=notification_type,
            requirement_id=requirement_id,
            is_read=False,
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)
        logger.info(f"Notification queued for role '{recipient_role}': {message[:60]}...")

        # Optional SMTP fallback (PDS Vol 2 §14.3.4)
        if settings.is_smtp_configured:
            NotificationService._try_send_email(recipient_role, message)

        return notif

    @staticmethod
    def _try_send_email(recipient_role: str, message: str) -> bool:
        """Helper to send SMTP email with graceful error handling."""
        try:
            msg = MIMEText(message)
            msg["Subject"] = f"AREA Notification for {recipient_role}"
            msg["From"] = settings.SMTP_USER
            msg["To"] = settings.SMTP_USER  # Default recipient in MVP

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=5) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)
            logger.info(f"SMTP email sent for role '{recipient_role}'")
            return True
        except Exception as exc:
            # Graceful degradation per PDS Vol 2 §14.3.4
            logger.warning(f"SMTP email dispatch failed (in-app notification preserved): {exc}")
            return False

    @staticmethod
    def get_unread_notifications(db: Session, recipient_role: str) -> List[Notification]:
        """Fetch unread notifications for a specific role."""
        return (
            db.query(Notification)
            .filter(
                Notification.recipient_role == recipient_role,
                Notification.is_read == False,  # noqa: E712
            )
            .order_by(Notification.created_at.desc())
            .all()
        )

    @staticmethod
    def mark_as_read(db: Session, notification_id: UUID) -> Optional[Notification]:
        """Mark a notification as read."""
        notif = db.query(Notification).filter(Notification.id == notification_id).first()
        if notif:
            notif.is_read = True
            db.commit()
            db.refresh(notif)
        return notif


audit_service = AuditService()
notification_service = NotificationService()
