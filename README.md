# Email Renamer & Converter

Renames `.eml` / `.msg` email files based on their Date, Sender, and Subject,
and converts each one to a plain-text `.txt` file. Also extracts attachments
and writes a CSV summary log.

Turns this:
```
meeting.msg
meeting (2).msg
meeting (3).msg
```
into this:
```
2024 03 09 16 08 from John Doe - meeting.msg
2024 03 09 16 08 from John Doe - meeting.txt
2024 03 09 16 45 from Jane Doe - RE meeting.msg
2024 03 09 16 45 from Jane Doe - RE meeting.txt
```

## Two ways to use it

### 1. Browser UI (recommended for non-technical users)

```bash
pip install extract-msg
python email_renamer_web.py
```

This opens a local page in your default browser. Paste in a folder path,
tick a few checkboxes, and click Run. No command line knowledge needed
after the initial setup, and no GUI toolkit dependencies (no Tkinter, no
Tcl/Tk install issues).

### 2. Command line

```bash
pip install extract-msg
python rename_and_convert_emails.py "/path/to/your/email/folder"
```

## What it does

- Parses `.eml` files using Python's built-in `email` module
- Parses `.msg` files using [`extract-msg`](https://github.com/TeamMsgExtractor/msg-extractor)
- Auto-detects mislabeled `.msg` files (files that are actually plain-text
  `.eml`-style content saved with a `.msg` extension) and falls back to
  parsing them as text instead of failing
- Renames files to: `YYYY MM DD HH MM from <Sender> - <Subject>.ext`
- Converts each email to a matching `.txt` file with headers + body
- Extracts attachments into a `<name> - attachments/` subfolder per email
- Writes `conversion_log.csv` summarizing what happened to every file

## Packaging as a standalone .exe (optional)

If the end user shouldn't need Python installed at all:

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "EmailRenamer" email_renamer_web.py
```

The result is in `dist/EmailRenamer.exe` — a single file with no
dependencies to install.

## Requirements

- Python 3.8+
- [`extract-msg`](https://pypi.org/project/extract-msg/) for `.msg` support
  (not needed if you're only processing `.eml` files)

## License

MIT
