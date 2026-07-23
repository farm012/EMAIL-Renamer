#!/usr/bin/env python3
"""
rename_and_convert_emails.py

Renames .eml / .msg files based on their Date / Sender / Subject, and
converts each one to a plain-text (.txt) version.

Usage:
    python rename_and_convert_emails.py "C:/path/to/your/email/folder"

If no path is given, it uses the current directory.

Output naming pattern:
    YYYY MM DD HH MM from <Sender Name> - <Subject>.msg
    YYYY MM DD HH MM from <Sender Name> - <Subject>.txt

Requirements:
    pip install extract-msg
    (the 'email' module used for .eml files is part of the Python standard library)
"""

import sys
import os
import re
import csv
import email
from email import policy
from email.utils import parsedate_to_datetime

try:
    import extract_msg
except ImportError:
    extract_msg = None


OLE2_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # magic bytes for real .msg files


def looks_like_ole2(filepath: str) -> bool:
    """Check the first 8 bytes to see if this is a genuine OLE2 (.msg) file."""
    try:
        with open(filepath, "rb") as f:
            return f.read(8) == OLE2_SIGNATURE
    except OSError:
        return False


# ---------- helpers ----------

def sanitize_filename(name: str, max_len: int = 120) -> str:
    """Remove characters that are illegal in Windows filenames and trim length."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name)
    name = name.strip(" .")
    if len(name) > max_len:
        name = name[:max_len].rstrip()
    return name or "untitled"


def unique_path(path: str) -> str:
    """If path already exists, append (1), (2), ... before the extension."""
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    i = 1
    while os.path.exists(f"{base} ({i}){ext}"):
        i += 1
    return f"{base} ({i}){ext}"


# ---------- .eml handling ----------

def parse_eml(filepath: str):
    with open(filepath, "rb") as f:
        msg = email.message_from_binary_file(f, policy=policy.default)

    sender = msg.get("From", "Unknown Sender")
    subject = msg.get("Subject", "No Subject")
    date_str = msg.get("Date")

    dt = None
    if date_str:
        try:
            dt = parsedate_to_datetime(date_str)
        except (TypeError, ValueError):
            dt = None

    # Get plain-text body (fall back to stripped HTML)
    body = get_eml_body(msg)
    attachments = get_eml_attachments(msg)

    return {
        "sender": clean_display_name(sender),
        "subject": subject.strip() if subject else "No Subject",
        "date": dt,
        "body": body,
        "headers": dict(msg.items()),
        "attachments": attachments,  # list of (filename, bytes)
    }


def get_eml_attachments(msg):
    attachments = []
    if not msg.is_multipart():
        return attachments
    for part in msg.walk():
        disp = part.get_content_disposition()
        if disp == "attachment" or (disp is None and part.get_filename()):
            fname = part.get_filename() or "attachment"
            try:
                payload = part.get_content()
                if isinstance(payload, str):
                    payload = payload.encode("utf-8", "ignore")
            except Exception:
                payload = part.get_payload(decode=True) or b""
            attachments.append((fname, payload))
    return attachments


def get_eml_body(msg) -> str:
    if msg.is_multipart():
        # Prefer text/plain; fall back to text/html stripped of tags
        plain_parts = []
        html_parts = []
        for part in msg.walk():
            ctype = part.get_content_type()
            if part.get_content_disposition() == "attachment":
                continue
            if ctype == "text/plain":
                plain_parts.append(part.get_content())
            elif ctype == "text/html":
                html_parts.append(part.get_content())
        if plain_parts:
            return "\n".join(plain_parts)
        if html_parts:
            return strip_html("\n".join(html_parts))
        return ""
    else:
        ctype = msg.get_content_type()
        content = msg.get_content()
        if ctype == "text/html":
            return strip_html(content)
        return content


def strip_html(html: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_display_name(raw_from: str) -> str:
    """Turn '"John Doe" <john@x.com>' into 'John Doe'."""
    if not raw_from:
        return "Unknown Sender"
    match = re.match(r'^"?([^"<]+?)"?\s*<.*>$', raw_from.strip())
    if match:
        return match.group(1).strip()
    return raw_from.split("<")[0].strip() or raw_from.strip()


# ---------- .msg handling ----------

def parse_msg(filepath: str):
    if not looks_like_ole2(filepath):
        # Not a real Outlook binary .msg -- most likely a text/eml-style file
        # that was mislabeled. Fall back to eml parsing instead of failing.
        return parse_eml(filepath)

    if extract_msg is None:
        raise RuntimeError(
            "The 'extract-msg' package is required to read .msg files. "
            "Install it with: pip install extract-msg"
        )
    m = extract_msg.Message(filepath)
    sender = m.sender or "Unknown Sender"
    subject = m.subject or "No Subject"
    dt = m.date  # extract_msg gives a datetime (or parseable string) already

    if isinstance(dt, str):
        try:
            dt = parsedate_to_datetime(dt)
        except (TypeError, ValueError):
            dt = None

    body = m.body or (strip_html(m.htmlBody.decode("utf-8", "ignore")) if m.htmlBody else "")

    attachments = []
    try:
        for att in m.attachments:
            fname = att.longFilename or att.shortFilename or "attachment"
            data = att.data
            if isinstance(data, (bytes, bytearray)):
                attachments.append((fname, bytes(data)))
    except Exception:
        pass  # attachment extraction is best-effort

    result = {
        "sender": clean_display_name(sender),
        "subject": subject.strip(),
        "date": dt,
        "body": body,
        "headers": {
            "From": sender,
            "To": m.to or "",
            "Cc": m.cc or "",
            "Subject": subject,
            "Date": str(dt) if dt else "",
        },
        "attachments": attachments,
    }
    m.close()
    return result


# ---------- core logic ----------

def build_new_basename(parsed: dict) -> str:
    dt = parsed["date"]
    if dt:
        date_part = dt.strftime("%Y %m %d %H %M")
    else:
        date_part = "0000 00 00 00 00"
    sender = sanitize_filename(parsed["sender"], max_len=60)
    subject = sanitize_filename(parsed["subject"], max_len=80)
    return f"{date_part} from {sender} - {subject}"


def write_txt(parsed: dict, txt_path: str):
    lines = []
    h = parsed["headers"]
    for key in ("From", "To", "Cc", "Subject", "Date"):
        if h.get(key):
            lines.append(f"{key}: {h[key]}")
    lines.append("")
    lines.append(parsed["body"] or "")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def save_attachments(parsed: dict, directory: str, new_base: str):
    attachments = parsed.get("attachments") or []
    if not attachments:
        return 0
    att_dir = os.path.join(directory, new_base + " - attachments")
    os.makedirs(att_dir, exist_ok=True)
    for fname, data in attachments:
        safe_name = sanitize_filename(fname or "attachment", max_len=150)
        out_path = unique_path(os.path.join(att_dir, safe_name))
        with open(out_path, "wb") as f:
            f.write(data)
    return len(attachments)


def process_directory(directory: str, do_rename: bool = True, do_convert: bool = True,
                       extract_attachments: bool = True, write_log: bool = True, log_func=print):
    directory = os.path.abspath(directory)
    files = [f for f in os.listdir(directory) if f.lower().endswith((".eml", ".msg"))]

    if not files:
        log_func(f"No .eml or .msg files found in: {directory}")
        return

    log_func(f"Found {len(files)} email file(s) in {directory}\n")

    log_rows = []

    for fname in sorted(files):
        fpath = os.path.join(directory, fname)
        ext = os.path.splitext(fname)[1].lower()

        try:
            if ext == ".eml":
                parsed = parse_eml(fpath)
            else:
                parsed = parse_msg(fpath)
        except Exception as e:
            log_func(f"  [SKIPPED] {fname}: could not parse ({e})")
            log_rows.append([fname, "", "", "SKIPPED", str(e)])
            continue

        new_base = build_new_basename(parsed)
        note = "OLE2->ok" if ext != ".msg" or looks_like_ole2(fpath) else "fell back to eml parsing"

        # --- rename (or copy-name) the original file ---
        if do_rename:
            new_path = unique_path(os.path.join(directory, new_base + ext))
            os.rename(fpath, new_path)
            log_func(f"  Renamed: {fname}  ->  {os.path.basename(new_path)}")
        else:
            new_path = fpath

        # --- convert to txt ---
        txt_name = ""
        if do_convert:
            txt_path = unique_path(os.path.join(directory, new_base + ".txt"))
            write_txt(parsed, txt_path)
            txt_name = os.path.basename(txt_path)
            log_func(f"  Converted -> {txt_name}")

        # --- attachments ---
        att_count = 0
        if extract_attachments:
            att_count = save_attachments(parsed, directory, new_base)
            if att_count:
                log_func(f"  Extracted {att_count} attachment(s) -> {new_base} - attachments/")

        log_rows.append([
            fname, os.path.basename(new_path), txt_name, "OK", note, att_count
        ])
        log_func()

    if write_log and log_rows:
        log_path = os.path.join(directory, "conversion_log.csv")
        with open(log_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["original_filename", "renamed_to", "txt_file", "status", "notes", "attachments_extracted"])
            writer.writerows(log_rows)
        log_func(f"Summary log written -> conversion_log.csv")

    log_func("Done.")


# ---------- entry point ----------

if __name__ == "__main__":
    target_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    process_directory(target_dir, do_rename=True, do_convert=True)
