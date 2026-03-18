import os
from threading import Thread

from flask import Flask, jsonify, request
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)


def _platform_name():
    if os.getenv("RAILWAY_ENVIRONMENT"):
        return "railway"
    if os.getenv("RENDER"):
        return "render"
    return "generic"


def _health_payload():
    return {
        "status": "ok",
        "service": "registrar-bot",
        "platform": _platform_name(),
        "host": request.host,
    }


@app.get("/")
def home():
    response = jsonify(_health_payload())
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/healthz")
def healthz():
    response = jsonify(_health_payload())
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/readyz")
def readyz():
    response = jsonify(
        {
            **_health_payload(),
            "token_configured": bool(os.getenv("DISCORD_TOKEN")),
        }
    )
    response.headers["Cache-Control"] = "no-store"
    return response


def run():
    port = int(os.environ.get("PORT", 8080))

    try:
        from waitress import serve

        serve(app, host="0.0.0.0", port=port)
    except Exception:
        app.run(host="0.0.0.0", port=port, use_reloader=False)


def keep_alive():
    thread = Thread(target=run, daemon=True)
    thread.start()
    return thread
