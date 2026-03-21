import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread


class _HealthHandler(BaseHTTPRequestHandler):
    def _platform_name(self):
        if os.getenv("RAILWAY_ENVIRONMENT"):
            return "railway"
        if os.getenv("RENDER"):
            return "render"
        if os.getenv("CF_DEPLOYMENT_TARGET") == "cloudflare-containers" or os.getenv("CLOUDFLARE_DEPLOYMENT_ID"):
            return "cloudflare-containers"
        return "generic"

    def _health_payload(self):
        return {
            "status": "ok",
            "service": "registrar-bot",
            "platform": self._platform_name(),
            "host": self.headers.get("Host", ""),
        }

    def _send_json(self, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path not in {"/", "/healthz", "/readyz"}:
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        payload = self._health_payload()
        if self.path == "/readyz":
            payload["token_configured"] = bool(os.getenv("DISCORD_TOKEN"))

        self._send_json(payload)

    def log_message(self, format, *args):
        return


def run():
    port = int(os.environ.get("PORT", 8080))
    server = ThreadingHTTPServer(("0.0.0.0", port), _HealthHandler)
    server.serve_forever()


def keep_alive():
    thread = Thread(target=run, daemon=True)
    thread.start()
    return thread
