"""Gmail tools registered with the AI tool registry."""

import base64
import email as email_lib
from email.mime.text import MIMEText

from secretary.agent.registry import tool
from secretary.auth.google import get_gmail_service


@tool
def list_emails(max_results: int = 10, query: str = "") -> str:
    """List recent emails from Gmail inbox.

    Args:
        max_results: Maximum number of emails to return. Default is 10.
        query: Gmail search query, e.g. 'is:unread', 'from:boss@company.com', 'subject:meeting'.
    """
    service = get_gmail_service()
    list_result = (
        service.users()
        .messages()
        .list(userId="me", maxResults=max_results, q=query or "in:inbox")
        .execute()
    )

    messages = list_result.get("messages", [])
    if not messages:
        return "No emails found."

    lines = []
    for msg_meta in messages:
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=msg_meta["id"], format="metadata",
                 metadataHeaders=["From", "Subject", "Date"])
            .execute()
        )
        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        subject = headers.get("Subject", "(no subject)")
        sender  = headers.get("From", "unknown")
        date    = headers.get("Date", "")
        snippet = msg.get("snippet", "")[:80]
        lines.append(f"[{msg_meta['id']}] {date[:16]}  From: {sender}\n  Subject: {subject}\n  {snippet}…")

    return "\n\n".join(lines)


@tool
def read_email(email_id: str) -> str:
    """Read the full body of a specific email by its ID.

    Args:
        email_id: The Gmail message ID (shown in list_emails output).
    """
    service = get_gmail_service()
    msg = service.users().messages().get(userId="me", id=email_id, format="full").execute()

    headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
    subject = headers.get("Subject", "(no subject)")
    sender  = headers.get("From", "unknown")
    date    = headers.get("Date", "")

    body = _extract_body(msg["payload"])

    return f"From: {sender}\nDate: {date}\nSubject: {subject}\n\n{body}"


@tool
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email via Gmail.

    Args:
        to: Recipient email address, e.g. 'alice@example.com'.
        subject: Email subject line.
        body: Plain-text email body.
    """
    # Strip newlines from header fields to prevent email header injection
    to = to.replace("\r", "").replace("\n", "").strip()
    subject = subject.replace("\r", "").replace("\n", " ").strip()

    service = get_gmail_service()
    mime_msg = MIMEText(body)
    mime_msg["to"] = to
    mime_msg["subject"] = subject

    raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode()
    result = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return f"Email sent to {to!r} (message ID: {result['id']})."


def _extract_body(payload: dict) -> str:
    """Recursively pull plain-text body from a Gmail message payload."""
    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data")

    if mime_type == "text/plain" and body_data:
        return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")

    for part in payload.get("parts", []):
        result = _extract_body(part)
        if result:
            return result

    return "(no readable body)"
