"""Shared cookie auth + profile for all serpiwi.com tools.

Drop-in: `from serpiwi_auth import init_auth; init_auth(app, "ابزار من")`.
One login (cookie scoped to .serpiwi.com) unlocks every subdomain, plus a shared
profile page (change password) and /whoami for the global nav.

Config via env:
  SERPIWI_SECRET, SERPIWI_USER, SERPIWI_PASS_HASH (pbkdf2_sha256:iters:salt:hash),
  SERPIWI_COOKIE_DOMAIN (.serpiwi.com), SERPIWI_COOKIE_SECURE (1/0),
  SERPIWI_CREDS (path to a writable JSON {user,pass_hash}; enables runtime password change).
Auth disables itself when no password is configured (open mode for standalone repos).
"""
import os
import hmac
import json
import hashlib
import secrets
from urllib.parse import urlparse

from flask import session, request, redirect, url_for, render_template_string, Response, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix

_OPEN = {"login", "logout", "static", "healthz"}
CREDS_PATH = os.environ.get("SERPIWI_CREDS", "")


def _hash_pw(pw, iters=200000):
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), iters).hex()
    return "pbkdf2_sha256:%d:%s:%s" % (iters, salt, dk)


def _verify_password(password, stored):
    try:
        scheme, iters, salt, want = stored.split(":", 3)
    except ValueError:
        return False
    if scheme != "pbkdf2_sha256":
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iters)).hex()
    return hmac.compare_digest(dk, want)


def _load_creds():
    if CREDS_PATH and os.path.exists(CREDS_PATH):
        try:
            d = json.load(open(CREDS_PATH))
            return d.get("user", "admin"), d.get("pass_hash", "")
        except Exception:
            pass
    return os.environ.get("SERPIWI_USER", "admin"), os.environ.get("SERPIWI_PASS_HASH", "")


def _save_creds(user, pass_hash):
    if not CREDS_PATH:
        return False
    tmp = CREDS_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"user": user, "pass_hash": pass_hash}, f)
    os.replace(tmp, CREDS_PATH)
    return True


def _safe_next(target):
    if not target:
        return None
    u = urlparse(target)
    return target if (not u.netloc and not u.scheme and target.startswith("/")) else None


def init_auth(app, app_title="Serpiwi"):
    app.secret_key = os.environ.get("SERPIWI_SECRET", "dev-insecure-change-me")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    _, pass_hash0 = _load_creds()
    if not pass_hash0:
        return app  # open mode (standalone repo without configured credentials)

    app.config.update(
        SESSION_COOKIE_NAME="serpiwi_session",
        SESSION_COOKIE_DOMAIN=os.environ.get("SERPIWI_COOKIE_DOMAIN") or None,
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
        if request.path.startswith("/api/") or request.path == "/whoami":
            return Response('{"error":"unauthorized"}', 401, mimetype="application/json")
        return redirect(url_for("login", next=request.full_path.rstrip("?")))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if session.get("authed") and request.method == "GET":
            return redirect(_safe_next(request.args.get("next")) or "/")
        error = ""
        if request.method == "POST":
            user, ph = _load_creds()
            u = (request.form.get("username") or "").strip()
            p = request.form.get("password") or ""
            if u == user and ph and _verify_password(p, ph):
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

    @app.route("/whoami")
    def whoami():
        return jsonify({"authed": bool(session.get("authed")), "user": session.get("user", "")})

    @app.route("/profile", methods=["GET"])
    def profile():
        msg = request.args.get("msg", "")
        ok = request.args.get("ok", "")
        return render_template_string(_PROFILE_HTML, user=session.get("user", ""),
                                      can_change=bool(CREDS_PATH), msg=msg, ok=ok)

    @app.route("/profile/password", methods=["POST"])
    def profile_password():
        user, ph = _load_creds()
        cur = request.form.get("current") or ""
        new = request.form.get("new") or ""
        conf = request.form.get("confirm") or ""
        if not CREDS_PATH:
            return redirect("/profile?msg=" + "تغییر رمز روی این نصب فعال نیست.")
        if not _verify_password(cur, ph):
            return redirect("/profile?msg=" + "رمز فعلی نادرست است.")
        if len(new) < 8:
            return redirect("/profile?msg=" + "رمز جدید باید حداقل ۸ کاراکتر باشد.")
        if new != conf:
            return redirect("/profile?msg=" + "رمز جدید و تکرارش یکسان نیستند.")
        _save_creds(user, _hash_pw(new))
        return redirect("/profile?ok=1&msg=" + "رمز عبور با موفقیت تغییر کرد.")

    return app


_HEAD_THEME = """<script>(function(){try{var m=document.cookie.match(/serpiwi_theme=(\\w+)/);var t=m?m[1]:(localStorage.getItem('serpiwi_theme')||'system');var d=t==='dark'||(t==='system'&&matchMedia('(prefers-color-scheme:dark)').matches);document.documentElement.dataset.theme=d?'dark':'light';}catch(e){}})();</script>"""

_LOGIN_HTML = """<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>ورود · {{ title }}</title>
  <link rel="icon" href="/static/favicon-32x32.png" sizes="32x32"/>
  <link rel="apple-touch-icon" href="/static/favicon-180x180.png"/>
  __HEAD_THEME__
  <link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;500;600;700&display=swap" rel="stylesheet"/>
  <style>
    :root{--ink:#14201f;--muted:#5a6b69;--line:#dde5e3;--surf:#fff;--err:#ba1a1a}
    html[data-theme="dark"]{--ink:#e7ecea;--muted:#9fb0ad;--line:#2b3a38;--surf:#161e1d}
    *{box-sizing:border-box}
    body{margin:0;min-height:100vh;font-family:'Vazirmatn',system-ui,sans-serif;
      background:linear-gradient(125deg,#16a34a,#6d28d9);display:grid;place-items:center;padding:20px}
    .card{width:100%;max-width:380px;background:var(--surf);border-radius:22px;overflow:hidden;
      box-shadow:0 18px 50px rgba(0,0,0,.28)}
    .head{background:#fff;padding:24px;text-align:center}
    .head img{height:40px}
    .body{padding:20px 24px 24px}
    .body h1{font-size:1.05rem;margin:0 0 2px;color:var(--ink);text-align:center}
    .body p.sub{margin:0 0 18px;font-size:.82rem;color:var(--muted);text-align:center}
    label{display:block;font-size:.82rem;font-weight:600;color:var(--ink);margin:0 0 6px}
    .f{margin-bottom:14px}
    input{width:100%;padding:12px 14px;border:1.5px solid var(--line);border-radius:12px;
      font-family:inherit;font-size:1rem;background:transparent;color:var(--ink)}
    input:focus{outline:none;border-color:#16a34a;box-shadow:0 0 0 3px rgba(22,163,74,.18)}
    button{width:100%;margin-top:4px;padding:13px;border:none;border-radius:999px;cursor:pointer;
      font-family:inherit;font-size:1rem;font-weight:700;color:#fff;
      background:linear-gradient(125deg,#16a34a,#6d28d9);box-shadow:0 6px 16px rgba(109,40,217,.25)}
    .err{background:#fdecec;color:var(--err);border:1px solid #f5c2c2;border-radius:10px;
      padding:9px 12px;font-size:.83rem;margin-bottom:14px;text-align:center}
    html[data-theme="dark"] .err{background:#3a1414;border-color:#6b2020;color:#ffb4ab}
    html[data-theme="dark"] .head{background:#0f1614}
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
</html>""".replace("__HEAD_THEME__", _HEAD_THEME)

_PROFILE_HTML = """<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>پروفایل · Serpiwi</title>
  <link rel="icon" href="/static/favicon-32x32.png" sizes="32x32"/>
  __HEAD_THEME__
  <link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;500;600;700&display=swap" rel="stylesheet"/>
  <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,0,0" rel="stylesheet"/>
  <link rel="stylesheet" href="/static/serpiwi-ui.css"/>
  <style>
    body{margin:0;font-family:'Vazirmatn',system-ui,sans-serif;background:var(--sp-bg);color:var(--sp-ink)}
    .wrap{max-width:560px;margin:28px auto 60px;padding:0 16px}
    .pcard{background:var(--sp-surface);border:1px solid var(--sp-line);border-radius:18px;padding:24px;margin-bottom:16px}
    .idrow{display:flex;align-items:center;gap:14px;margin-bottom:6px}
    .big-av{width:58px;height:58px;border-radius:50%;background:linear-gradient(135deg,var(--sp-brand),#6d28d9);
      color:#fff;display:grid;place-items:center;font-size:1.4rem;font-weight:700}
    .idrow b{font-size:1.15rem}.idrow span{font-size:.82rem;color:var(--sp-muted)}
    h2{font-size:1rem;margin:0 0 14px;display:flex;align-items:center;gap:8px}
    h2 .material-symbols-rounded{color:var(--sp-brand);font-size:20px}
    label{display:block;font-size:.82rem;font-weight:600;margin:0 0 6px}
    .f{margin-bottom:14px}
    input{width:100%;box-sizing:border-box;padding:11px 13px;border:1.5px solid var(--sp-line);border-radius:11px;
      font-family:inherit;font-size:.98rem;background:var(--sp-surface-2);color:var(--sp-ink)}
    input:focus{outline:none;border-color:var(--sp-brand);box-shadow:0 0 0 3px var(--sp-brand-soft)}
    .btn{border:none;border-radius:999px;cursor:pointer;font-family:inherit;font-weight:700;font-size:.95rem;
      color:#fff;background:var(--sp-brand);padding:12px 22px}
    .msg{border-radius:11px;padding:11px 14px;font-size:.86rem;margin-bottom:14px}
    .msg.ok{background:var(--sp-brand-soft);color:var(--sp-brand-ink)}
    .msg.no{background:#fdecec;color:#ba1a1a;border:1px solid #f5c2c2}
    html[data-theme="dark"] .msg.no{background:#3a1414;color:#ffb4ab;border-color:#6b2020}
    .hint{font-size:.78rem;color:var(--sp-muted);margin-top:4px}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="pcard">
      <div class="idrow">
        <div class="big-av">{{ (user[0]|upper) if user else 'U' }}</div>
        <div><b>{{ user or 'کاربر' }}</b><br/><span>حساب مدیریت Serpiwi</span></div>
      </div>
    </div>
    <div class="pcard">
      <h2><span class="material-symbols-rounded">lock_reset</span> تغییر رمز عبور</h2>
      {% if msg %}<div class="msg {{ 'ok' if ok else 'no' }}">{{ msg }}</div>{% endif %}
      {% if can_change %}
      <form method="post" action="/profile/password">
        <div class="f"><label>رمز فعلی</label><input name="current" type="password" autocomplete="current-password"/></div>
        <div class="f"><label>رمز جدید</label><input name="new" type="password" autocomplete="new-password"/>
          <div class="hint">حداقل ۸ کاراکتر.</div></div>
        <div class="f"><label>تکرار رمز جدید</label><input name="confirm" type="password" autocomplete="new-password"/></div>
        <button class="btn" type="submit">ذخیره رمز جدید</button>
      </form>
      {% else %}
      <div class="hint">تغییر رمز روی این نصب فعال نیست (فایل اعتبارنامه تنظیم نشده).</div>
      {% endif %}
    </div>
    <div class="pcard">
      <h2><span class="material-symbols-rounded">palette</span> ظاهر</h2>
      <div class="hint">حالت روشن/تیره را از دکمهٔ تم در نوار بالا تغییر دهید؛ انتخاب شما در همهٔ ابزارها ذخیره می‌شود.</div>
    </div>
  </div>
  <script src="/static/serpiwi-shell.js" defer></script>
</body>
</html>""".replace("__HEAD_THEME__", _HEAD_THEME)
