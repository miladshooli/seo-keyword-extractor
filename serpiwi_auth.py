"""Shared cookie auth for all serpiwi.com tools.

Drop-in: `from serpiwi_auth import init_auth; init_auth(app, "ابزار من")`.
One login (cookie scoped to .serpiwi.com) unlocks every subdomain.
Config via env: SERPIWI_SECRET, SERPIWI_USER, SERPIWI_PASS_HASH,
SERPIWI_COOKIE_DOMAIN (e.g. .serpiwi.com), SERPIWI_COOKIE_SECURE (1/0).
"""
import os
import hmac
import hashlib
from functools import wraps
from urllib.parse import urlparse

from flask import session, request, redirect, url_for, render_template_string, Response
from werkzeug.middleware.proxy_fix import ProxyFix

_OPEN = {"login", "logout", "static", "healthz"}


def _verify_password(password, stored):
    try:
        scheme, iters, salt, want = stored.split(":", 3)
    except ValueError:
        return False
    if scheme != "pbkdf2_sha256":
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iters)).hex()
    return hmac.compare_digest(dk, want)


def _safe_next(target):
    if not target:
        return None
    u = urlparse(target)
    return target if (not u.netloc and not u.scheme and target.startswith("/")) else None


def init_auth(app, app_title="Serpiwi"):
    app.secret_key = os.environ.get("SERPIWI_SECRET", "dev-insecure-change-me")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    user = os.environ.get("SERPIWI_USER", "admin")
    pass_hash = os.environ.get("SERPIWI_PASS_HASH", "")
    if not pass_hash:
        # No credentials configured -> auth disabled (open). Lets the public repo
        # deploy run un-gated; serpiwi.com sets SERPIWI_PASS_HASH so it stays protected.
        return app
    cookie_domain = os.environ.get("SERPIWI_COOKIE_DOMAIN") or None
    app.config.update(
        SESSION_COOKIE_NAME="serpiwi_session",
        SESSION_COOKIE_DOMAIN=cookie_domain,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("SERPIWI_COOKIE_SECURE", "1") == "1",
        PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 30,
    )

    @app.before_request
    def _guard():
        if request.endpoint in _OPEN or (request.path or "").startswith("/static/"):
            return None
        if session.get("authed"):
            return None
        if request.path.startswith("/api/"):
            return Response('{"error":"unauthorized"}', 401, mimetype="application/json")
        return redirect(url_for("login", next=request.full_path.rstrip("?")))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if session.get("authed") and request.method == "GET":
            return redirect(_safe_next(request.args.get("next")) or "/")
        error = ""
        if request.method == "POST":
            u = (request.form.get("username") or "").strip()
            p = request.form.get("password") or ""
            if u == user and pass_hash and _verify_password(p, pass_hash):
                session.permanent = True
                session["authed"] = True
                session["user"] = u
                return redirect(_safe_next(request.form.get("next")) or "/")
            error = "نام کاربری یا رمز عبور نادرست است."
        nxt = _safe_next(request.args.get("next")) or _safe_next(request.form.get("next")) or "/"
        return render_template_string(_LOGIN_HTML, title=app_title, error=error, nxt=nxt)

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    return app


_LOGIN_HTML = """<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>ورود · {{ title }}</title>
  <link rel="icon" href="/static/favicon-32x32.png" sizes="32x32"/>
  <link rel="apple-touch-icon" href="/static/favicon-180x180.png"/>
  <link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;500;600;700&display=swap" rel="stylesheet"/>
  <style>
    :root{--p:#0e9f6e;--p2:#6d28d9;--ink:#14201f;--muted:#5a6b69;--line:#dde5e3;--surf:#fff;--err:#ba1a1a}
    @media (prefers-color-scheme: dark){:root{--ink:#e7ecea;--muted:#9fb0ad;--line:#2b3a38;--surf:#161e1d}}
    *{box-sizing:border-box}
    body{margin:0;min-height:100vh;font-family:'Vazirmatn',system-ui,sans-serif;
      background:linear-gradient(125deg,#0e9f6e,#6d28d9);display:grid;place-items:center;padding:20px}
    .card{width:100%;max-width:380px;background:var(--surf);border-radius:22px;overflow:hidden;
      box-shadow:0 18px 50px rgba(0,0,0,.28)}
    .head{background:var(--surf);padding:26px 24px 8px;text-align:center}
    .head img{height:40px}
    @media (prefers-color-scheme: dark){.head{background:#fff;border-radius:0 0 16px 16px;margin:10px 10px 0;padding:18px}}
    .body{padding:20px 24px 24px}
    .body h1{font-size:1.05rem;margin:0 0 2px;color:var(--ink);text-align:center}
    .body p.sub{margin:0 0 18px;font-size:.82rem;color:var(--muted);text-align:center}
    label{display:block;font-size:.82rem;font-weight:600;color:var(--ink);margin:0 0 6px}
    .f{margin-bottom:14px}
    input{width:100%;padding:12px 14px;border:1.5px solid var(--line);border-radius:12px;
      font-family:inherit;font-size:1rem;background:transparent;color:var(--ink)}
    input:focus{outline:none;border-color:var(--p);box-shadow:0 0 0 3px rgba(14,159,110,.18)}
    button{width:100%;margin-top:4px;padding:13px;border:none;border-radius:999px;cursor:pointer;
      font-family:inherit;font-size:1rem;font-weight:700;color:#fff;
      background:linear-gradient(125deg,#0e9f6e,#6d28d9);box-shadow:0 6px 16px rgba(109,40,217,.25)}
    button:active{transform:scale(.99)}
    .err{background:#fdecec;color:var(--err);border:1px solid #f5c2c2;border-radius:10px;
      padding:9px 12px;font-size:.83rem;margin-bottom:14px;text-align:center}
    @media (prefers-color-scheme: dark){.err{background:#3a1414;border-color:#6b2020;color:#ffb4ab}}
    .foot{text-align:center;font-size:.72rem;color:var(--muted);padding:0 24px 20px}
  </style>
</head>
<body>
  <div class="card">
    <div class="head"><img src="/static/serpiwi-logo-color.png" alt="serpiwi"/></div>
    <div class="body">
      <h1>{{ title }}</h1>
      <p class="sub">برای ادامه وارد شوید</p>
      {% if error %}<div class="err">{{ error }}</div>{% endif %}
      <form method="post" action="/login">
        <input type="hidden" name="next" value="{{ nxt }}"/>
        <div class="f"><label>نام کاربری</label><input name="username" autocomplete="username" autofocus/></div>
        <div class="f"><label>رمز عبور</label><input name="password" type="password" autocomplete="current-password"/></div>
        <button type="submit">ورود</button>
      </form>
    </div>
    <div class="foot">Serpiwi · مجموعه ابزارهای SEO</div>
  </div>
</body>
</html>"""
