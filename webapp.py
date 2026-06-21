from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import json
import mimetypes

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, content_type="application/json; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, INDEX.read_bytes(), "text/html; charset=utf-8")
            return
        if self.path == "/api/summary":
            payload = {
                "name": "AutomintNFT",
                "status": "ok",
                "project_count": 1,
                "account_count": 1,
                "features": ["wl", "eligibility", "mint", "pipeline"]
            }
            self._send(200, json.dumps(payload, indent=2))
            return
        self._send(404, json.dumps({"error": "not found"}))

    def log_message(self, format, *args):
        return

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 3000), Handler)
    print("listening on http://0.0.0.0:3000", flush=True)
    server.serve_forever()
