"""Upozornění e-mailem na novou poptávku z webu (Resend API nebo SMTP). Chyby jen zaloguje."""
import smtplib
from email.message import EmailMessage

import httpx

from .config import (MAIL_FROM, NOTIFY_TO, PUBLIC_URL, RESEND_API_KEY, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT,
                     SMTP_USER)


def enabled() -> bool:
    return bool(NOTIFY_TO and (RESEND_API_KEY or SMTP_HOST))


def _text(q: dict) -> str:
    return (f"Nová poptávka z webu RM Lab\n\n"
            f"Jméno:    {q['name']}\nFirma:    {q['company']}\nKontakt:  {q['contact']}\n"
            f"Potřebuje: {q.get('need') or '-'}\n\n{q.get('message') or ''}\n\n"
            f"Poptávky v CRM: {PUBLIC_URL}/nase-crm/#poptavky\n")


def send_inquiry(q: dict) -> None:
    if not enabled():
        return
    to = [a.strip() for a in NOTIFY_TO.split(",") if a.strip()]
    subject = f"Nová poptávka: {q['company']} ({q['name']})"
    reply_to = q["contact"] if "@" in q["contact"] else None
    try:
        if RESEND_API_KEY:
            payload = {"from": MAIL_FROM, "to": to, "subject": subject, "text": _text(q)}
            if reply_to:
                payload["reply_to"] = reply_to
            r = httpx.post("https://api.resend.com/emails", json=payload, timeout=15,
                           headers={"Authorization": f"Bearer {RESEND_API_KEY}"})
            r.raise_for_status()
        else:
            msg = EmailMessage()
            msg["From"], msg["To"], msg["Subject"] = MAIL_FROM, ", ".join(to), subject
            if reply_to:
                msg["Reply-To"] = reply_to
            msg.set_content(_text(q))
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
                s.starttls()
                if SMTP_USER:
                    s.login(SMTP_USER, SMTP_PASSWORD)
                s.send_message(msg)
        print(f"[rmlab] upozornění na poptávku odesláno ({', '.join(to)})", flush=True)
    except Exception as ex:  # noqa: BLE001
        print(f"[rmlab] upozornění na poptávku se nepodařilo odeslat: {ex}", flush=True)
