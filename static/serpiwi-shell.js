/* Serpiwi shared shell: global nav, theme toggle, user menu. Loaded by every tool. */
(function () {
  var TOOLS = [
    { k: "home", label: "خانه", icon: "home" },
    { k: "title", label: "امتیاز عنوان", icon: "manage_search" },
    { k: "reranker", label: "ری‌رنک محتوا", icon: "readiness_score" },
    { k: "kwr", label: "کلیدواژه", icon: "key_visualizer" }
  ];
  var keys = ["title", "reranker", "kwr"];
  var host = location.hostname.replace(/^www\./, "");
  var labels = host.split(".");
  var active = "home", base = host;
  if (labels.length > 2 && keys.indexOf(labels[0]) >= 0) { active = labels[0]; base = labels.slice(1).join("."); }
  var href = function (k) { return k === "home" ? ("https://" + base + "/") : ("https://" + k + "." + base + "/"); };

  // ---- theme ----
  function getPref() {
    var m = document.cookie.match(/serpiwi_theme=(\w+)/);
    return m ? m[1] : (localStorage.getItem("serpiwi_theme") || "system");
  }
  function resolve(p) {
    return p === "dark" || (p === "system" && matchMedia("(prefers-color-scheme: dark)").matches) ? "dark" : "light";
  }
  function applyPref(p) {
    document.documentElement.dataset.theme = resolve(p);
    try { localStorage.setItem("serpiwi_theme", p); } catch (e) {}
    document.cookie = "serpiwi_theme=" + p + ";path=/;max-age=31536000;domain=." + base + ";samesite=lax";
    syncThemeUI(p);
  }
  function syncThemeUI(p) {
    var seg = document.getElementById("sp-themeseg");
    if (seg) seg.querySelectorAll("button").forEach(function (b) { b.classList.toggle("on", b.dataset.t === p); });
    var ic = document.getElementById("sp-themeicon");
    if (ic) ic.textContent = resolve(p) === "dark" ? "light_mode" : "dark_mode";
  }
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () {
    if (getPref() === "system") applyPref("system");
  });

  // ---- build nav ----
  function build() {
    if (document.querySelector(".sp-nav")) return;
    document.body.setAttribute("data-sp-shell", "");
    var nav = document.createElement("nav");
    nav.className = "sp-nav";
    var tabs = TOOLS.map(function (t) {
      return '<a class="sp-tab' + (t.k === active ? " active" : "") + '" href="' + href(t.k) + '">' +
        '<span class="material-symbols-rounded">' + t.icon + '</span><span class="lbl">' + t.label + "</span></a>";
    }).join("");
    nav.innerHTML =
      '<div class="sp-nav-in">' +
        '<a class="sp-brand" href="' + href("home") + '"><img src="/static/serpiwi-logo-color.png" alt="Serpiwi"/></a>' +
        '<div class="sp-tabs">' + tabs + "</div>" +
        '<div class="sp-actions">' +
          '<button class="sp-ibtn" id="sp-toggle" title="تغییر تم"><span class="material-symbols-rounded" id="sp-themeicon">dark_mode</span></button>' +
          '<div class="sp-user">' +
            '<button class="sp-avatar" id="sp-av">U</button>' +
            '<div class="sp-menu" id="sp-menu">' +
              '<div class="who"><b id="sp-who">کاربر</b><span>Serpiwi</span></div>' +
              '<a href="' + href("home") + 'profile"><span class="material-symbols-rounded">person</span> پروفایل کاربری</a>' +
              '<div class="sp-seg" id="sp-themeseg">' +
                '<button data-t="system">سیستم</button><button data-t="light">روشن</button><button data-t="dark">تیره</button>' +
              "</div>" +
              '<a class="danger" href="' + href("home") + 'logout"><span class="material-symbols-rounded">logout</span> خروج</a>' +
            "</div>" +
          "</div>" +
        "</div>" +
      "</div>";
    document.body.insertBefore(nav, document.body.firstChild);

    document.getElementById("sp-toggle").addEventListener("click", function () {
      applyPref(resolve(getPref()) === "dark" ? "light" : "dark");
    });
    document.getElementById("sp-themeseg").querySelectorAll("button").forEach(function (b) {
      b.addEventListener("click", function (e) { e.stopPropagation(); applyPref(b.dataset.t); });
    });
    var menu = document.getElementById("sp-menu");
    document.getElementById("sp-av").addEventListener("click", function (e) { e.stopPropagation(); menu.classList.toggle("open"); });
    document.addEventListener("click", function () { menu.classList.remove("open"); });
    menu.addEventListener("click", function (e) { e.stopPropagation(); });

    syncThemeUI(getPref());
    fetch("/whoami").then(function (r) { return r.json(); }).then(function (d) {
      if (d && d.user) {
        document.getElementById("sp-who").textContent = d.user;
        document.getElementById("sp-av").textContent = (d.user[0] || "U").toUpperCase();
      }
    }).catch(function () {});
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", build);
  else build();
})();
