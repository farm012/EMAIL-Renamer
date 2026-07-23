import os
import io
import json
import contextlib
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

from rename_and_convert_emails import process_directory

PORT = 8731

PAGE_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Email Renamer &amp; Converter</title>
<style>
  body { font-family: Segoe UI, Arial, sans-serif; max-width: 720px; margin: 40px auto; color: #222; }
  h1 { font-size: 22px; }
  .step { margin-bottom: 18px; }
  label { font-weight: 600; display: block; margin-bottom: 6px; }
  input[type=text] { width: 100%; padding: 8px; font-size: 14px; box-sizing: border-box; }
  .opts label { font-weight: normal; display: inline-block; margin-right: 16px; }
  button { background: #2d7d46; color: white; border: none; padding: 10px 22px;
           font-size: 15px; font-weight: 600; border-radius: 4px; cursor: pointer; }
  button:disabled { background: #999; cursor: default; }
  #log { background: #111; color: #d8d8d8; font-family: Consolas, monospace; font-size: 13px;
         padding: 12px; border-radius: 4px; white-space: pre-wrap; min-height: 120px;
         max-height: 360px; overflow-y: auto; margin-top: 10px; }
  .hint { color: #666; font-size: 13px; margin-top: 4px; }
</style>
</head>
<body>
  <h1>Email Renamer &amp; Converter</h1>

  <div class="step">
    <label for="folder">Step 1: Paste the folder path containing your .eml / .msg files</label>
    <input type="text" id="folder" placeholder="e.g. C:\\Users\\You\\Documents\\Emails">
    <div class="hint">Tip: In Windows Explorer, click the address bar and copy the path shown there.</div>
  </div>

  <div class="step opts">
    <label>Step 2: What should it do?</label>
    <label><input type="checkbox" id="rename" checked> Rename files</label>
    <label><input type="checkbox" id="convert" checked> Convert to .txt</label>
    <label><input type="checkbox" id="attachments" checked> Extract attachments</label>
  </div>

  <div class="step">
    <button id="runBtn" onclick="run()">Run</button>
  </div>

  <div id="log"></div>

<script>
async function run() {
  const folder = document.getElementById('folder').value.trim();
  const log = document.getElementById('log');
  const btn = document.getElementById('runBtn');
  if (!folder) {
    log.textContent = 'Please paste a folder path first.';
    return;
  }
  btn.disabled = true;
  btn.textContent = 'Working...';
  log.textContent = 'Processing, please wait...';

  const body = {
    folder: folder,
    rename: document.getElementById('rename').checked,
    convert: document.getElementById('convert').checked,
    attachments: document.getElementById('attachments').checked
  };

  try {
    const res = await fetch('/run', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body)
    });
    const data = await res.json();
    log.textContent = data.output || data.error || 'No output.';
  } catch (e) {
    log.textContent = 'Error contacting the local server: ' + e;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Run';
  }
}
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # silence default console logging

    def do_GET(self):
        if self.path == "/":
            self._send_html(PAGE_HTML)
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path != "/run":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json({"error": "Bad request."}, status=400)
            return

        folder = payload.get("folder", "").strip()
        if not folder or not os.path.isdir(folder):
            self._send_json({"error": f"Folder not found: {folder}"})
            return

        buffer = io.StringIO()
        try:
            with contextlib.redirect_stdout(buffer):
                process_directory(
                    folder,
                    do_rename=bool(payload.get("rename", True)),
                    do_convert=bool(payload.get("convert", True)),
                    extract_attachments=bool(payload.get("attachments", True)),
                    write_log=True,
                )
        except Exception as e:
            buffer.write(f"\nERROR: {e}\n")

        self._send_json({"output": buffer.getvalue()})

    def _send_html(self, html):
        encoded = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_json(self, obj, status=200):
        encoded = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def main():
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}/"
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    print(f"Email Renamer running at {url}")
    print("Leave this window open while you use the tool. Close it when you're done.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
