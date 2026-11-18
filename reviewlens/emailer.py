"""Email the weekly report (stretch goal).

Sends the most recently saved official week (see history.py) with the report in
the body and the enriched CSV attached. If nothing was saved in the last 8 days
it sends a short reminder instead. Each week is emailed only once.

Settings (.env):
    SMTP_HOST, SMTP_PORT (587 STARTTLS / 465 SSL), SMTP_USER, SMTP_PASSWORD,
    SMTP_FROM (default SMTP_USER), REPORT_RECIPIENTS (comma-separated)

Manual run:
    python -m reviewlens.emailer --dry-run      # print what would be sent
    python -m reviewlens.emailer                # send now (skips if already sent)
    python -m reviewlens.emailer --force        # send again
"""
from __future__ import annotations

import argparse
import html
import json
import os
import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from .history import SavedWeek, list_weeks

RECENT_DAYS = 8


@dataclass
class SMTPSettings:
    host: str
    port: int
    user: str
    password: str
    sender: str
    recipients: list[str]

    @classmethod
    def from_env(cls) -> "SMTPSettings":
        recipients = [r.strip() for r in os.getenv("REPORT_RECIPIENTS", "").split(",") if r.strip()]
        user = os.getenv("SMTP_USER", "").strip()
        return cls(
            host=os.getenv("SMTP_HOST", "").strip(),
            port=int(os.getenv("SMTP_PORT", "587") or 587),
            user=user,
            password=os.getenv("SMTP_PASSWORD", ""),
            sender=os.getenv("SMTP_FROM", "").strip() or user,
            recipients=recipients,
        )

    def missing(self) -> list[str]:
        names = {"SMTP_HOST": self.host, "SMTP_USER": self.user, "SMTP_PASSWORD": self.password,
                 "REPORT_RECIPIENTS": self.recipients}
        return [k for k, v in names.items() if not v]


def _saved_at(week: SavedWeek) -> datetime | None:
    try:
        return datetime.fromisoformat(week.meta["saved_at"])
    except (KeyError, ValueError):
        return None


def pick_week(now: datetime | None = None) -> SavedWeek | None:
    """Most recently *saved* week, if it was saved within the last RECENT_DAYS days."""
    now = now or datetime.now(timezone.utc)
    recent = [(w, _saved_at(w)) for w in list_weeks()]
    recent = [(w, t) for w, t in recent if t and now - t <= timedelta(days=RECENT_DAYS)]
    return max(recent, key=lambda wt: wt[1])[0] if recent else None


def _sent_marker(week: SavedWeek):
    return week.path / "emailed.json"


def already_sent(week: SavedWeek) -> bool:
    return _sent_marker(week).exists()


def build_message(week: SavedWeek | None, settings: SMTPSettings, app_url: str = "") -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = settings.sender
    msg["To"] = ", ".join(settings.recipients)
    link = f"\n\nOpen ReviewLens: {app_url}" if app_url else ""
    if week is None:
        msg["Subject"] = "ReviewLens: no weekly report saved this week"
        msg.set_content(
            "No official weekly report was saved in ReviewLens in the last week.\n\n"
            "Upload this week's reviews, check the results and click "
            "'Save as this week's official report' on the Weekly report tab." + link
        )
        return msg

    report = week.report_text()
    meta = week.meta
    msg["Subject"] = f"ReviewLens weekly report | {meta.get('week_start', '?')} to {week.week_end}"
    msg.set_content(report + "\n\nThe full enriched table is attached (opens in Excel)." + link)
    msg.add_alternative(
        "<p>Weekly customer feedback report from ReviewLens.</p>"
        f"<pre style=\"font-family:Consolas,Menlo,monospace;font-size:13px\">{html.escape(report)}</pre>"
        "<p>The full enriched table is attached (opens in Excel).</p>"
        + (f'<p><a href="{html.escape(app_url)}">Open ReviewLens</a></p>' if app_url else ""),
        subtype="html",
    )
    msg.add_attachment(week.enriched_path.read_bytes(), maintype="text", subtype="csv",
                       filename=f"reviews_enriched_{week.week_end}.csv")
    return msg


def send_message(msg: EmailMessage, settings: SMTPSettings) -> None:
    context = ssl.create_default_context()
    if settings.port == 465:
        with smtplib.SMTP_SSL(settings.host, settings.port, context=context, timeout=30) as smtp:
            smtp.login(settings.user, settings.password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(settings.host, settings.port, timeout=30) as smtp:
            smtp.starttls(context=context)
            smtp.login(settings.user, settings.password)
            smtp.send_message(msg)


def send_weekly_report(force: bool = False, dry_run: bool = False) -> str:
    """Send this week's email. Returns a one-line status message."""
    settings = SMTPSettings.from_env()
    week = pick_week()
    if week is not None and already_sent(week) and not force:
        return f"Skipped: report for week ending {week.week_end} was already emailed."
    msg = build_message(week, settings, os.getenv("APP_URL", ""))
    if dry_run:
        return f"DRY RUN - would send '{msg['Subject']}' to {msg['To'] or '(no recipients)'}"
    missing = settings.missing()
    if missing:
        return f"Not sent: missing settings {', '.join(missing)}."
    send_message(msg, settings)
    if week is not None:
        _sent_marker(week).write_text(json.dumps(
            {"sent_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "to": settings.recipients}), encoding="utf-8")
    return f"Sent '{msg['Subject']}' to {len(settings.recipients)} recipient(s)."


def main() -> None:
    parser = argparse.ArgumentParser(description="Email the ReviewLens weekly report.")
    parser.add_argument("--force", action="store_true", help="send even if this week was already emailed")
    parser.add_argument("--dry-run", action="store_true", help="show what would be sent, send nothing")
    args = parser.parse_args()
    print(send_weekly_report(force=args.force, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
