"""Run separately: only this process receives SMTP credentials."""
import os
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

from .common import iso, read_json, timestamp, write_json


def select_alerts(report, status, state, now):
    if not status or not status.get("ok") or not report or not report.get("fee_confirmed"):
        return []
    max_age = report["thresholds"]["max_source_age_hours"]
    if (now - timestamp(report["source_updated_at"])).total_seconds() > max_age * 3600:
        return []
    result = []
    for item in report["items"]:
        if item["status"] != "opportunity" or item["id"] not in report["candidate_ids"]:
            continue
        old = state.get(item["id"])
        if old and item["at"] <= old["at"]:
            continue
        if not old or abs(item["price"] / old["price"] - 1) >= .05 or abs(item["net_margin_pct"] - old["margin"]) >= 2:
            result.append(item)
    return result


def notify(root, env=None, smtp_factory=smtplib.SMTP_SSL, now=None):
    env = os.environ if env is None else env
    now = now or datetime.now(timezone.utc)
    report = read_json(root / "site/data/report.json")
    status = read_json(root / "site/data/status.json")
    state_path = root / "state/alerts.json"
    state = read_json(state_path, {})
    alerts = select_alerts(report, status, state, now)
    if not alerts:
        print("No new eligible alerts.")
        return True
    names = ("SMTP_USER", "SMTP_APP_PASSWORD", "ALERT_EMAIL")
    if not all(env.get(name) for name in names):
        print("Email not configured; report remains available.")
        return True
    try:
        # One configured recipient, no values accepted from the public site.
        if any("\n" in env[k] or "\r" in env[k] for k in ("SMTP_USER", "ALERT_EMAIL")) or any(c in env["ALERT_EMAIL"] for c in ",;"):
            raise ValueError("Invalid recipient")
        message = EmailMessage()
        message["Subject"] = f"DFTrader: {len(alerts)} cơ hội cần xem xét"
        message["From"] = env["SMTP_USER"]
        message["To"] = env["ALERT_EMAIL"]
        lines = ["Tín hiệu thị trường tham khảo, chưa xác minh tốc độ bán.\n"]
        for item in alerts:
            lines.append(f"{item['name']}: giá {item['price']:,}, mục tiêu {item['target']:,}, biên sau phí {item['net_margin_pct']:.1f}%\n{item['url']}\n")
        lines.append(report["notice"])
        message.set_content("\n".join(lines))
        with smtp_factory("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=30) as smtp:
            smtp.login(env["SMTP_USER"], env["SMTP_APP_PASSWORD"])
            smtp.send_message(message, to_addrs=[env["ALERT_EMAIL"]])
        for item in alerts:
            state[item["id"]] = {"at": item["at"], "price": item["price"], "margin": item["net_margin_pct"], "sent_at": iso(now)}
        # Only public market identifiers and deduplication metadata are persisted.
        write_json(state_path, state)
        print(f"Delivered {len(alerts)} alerts.")
        return True
    except Exception:
        print("Email delivery failed; deduplication state unchanged. Report remains available.")
        return False


if __name__ == "__main__":
    # Non-zero SMTP failure must not prevent report deployment.
    raise SystemExit(0 if notify(Path(__file__).resolve().parents[1]) else 1)
