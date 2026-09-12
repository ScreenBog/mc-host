const api = "";
let token = localStorage.getItem("shnpp_token") || "";
let me = null;
let serverCache = {};
let searchAbort = null;
let searchTimer = null;
let lockLoader = true;

const $ = (id) => document.getElementById(id);

function headers(body) {
  const h = { Accept: "application/json" };
  if (token) h.Authorization = "Bearer " + token;
  if (body && !(body instanceof FormData)) h["Content-Type"] = "application/json";
  return h;
}
async function j(path, opt = {}) {
  const r = await fetch(api + path, { ...opt, headers: { ...headers(opt.body), ...(opt.headers || {}) } });
  const t = await r.text();
  if (!r.ok) throw new Error(t || r.statusText);
  return t ? JSON.parse(t) : null;
}
function go(path) {
  history.pushState({}, "", path);
  render();
}
window.addEventListener("popstate", render);
function toast(msg) {
  let n = document.querySelector(".toast");
  if (!n) {
    n = document.createElement("div");
    n.className = "toast";
    document.body.appendChild(n);
  }
  n.textContent = msg;
  n.style.display = "block";
  setTimeout(() => (n.style.display = "none"), 2200);
}
function copy(text) {
  navigator.clipboard.writeText(text);
  toast("Скопировано");
}
function statusDot(st) {
  const cls = st === "RUNNING" ? "on" : st === "SLEEPING" || st === "STOPPED" ? "sleep" : "off";
  return `<span class="dot ${cls}"></span>${st}`;
}
function isPluginCore(type) {
  return ["PAPER", "PURPUR", "SPIGOT"].includes(type);
}
function hasAddons(type) {
  return type && type !== "VANILLA" && type !== "SNAPSHOT" && type !== "BEDROCK";
}
function addonLabel(type) {
  return isPluginCore(type) ? "Плагины" : "Моды";
}

async function boot() {
  const q = new URLSearchParams(location.search);
  if (q.get("token")) {
    try {
      const d = await j("/api/v1/auth/callback?token=" + encodeURIComponent(q.get("token")));
      token = d.access_token;
      localStorage.setItem("shnpp_token", token);
      history.replaceState({}, "", "/");
    } catch (e) {
      document.body.innerHTML = `<div class="body err">${e.message}</div>`;
      return;
    }
  }
  if (token) {
    try {
      me = await j("/api/v1/me");
    } catch {
      token = "";
      localStorage.removeItem("shnpp_token");
    }
  }
  render();
}

function parseRoute() {
  const p = location.pathname.replace(/\/+$/, "") || "/";
  const parts = p.split("/").filter(Boolean);
  if (p === "/" || p === "") return { name: "home" };
  if (parts[0] === "create") return { name: "create" };
  if (parts[0] === "admin") return { name: "admin" };
  if (parts[0] === "servers" && parts[1]) {
    const id = parts[1];
    const rest = parts.slice(2);
    if (!rest.length) return { name: "overview", id };
    if (rest[0] === "addons" && rest[1] === "add") return { name: "addons-add", id };
    if (rest[0] === "files") return { name: "files", id, filePath: rest.slice(1).join("/") };
    return { name: rest[0], id };
  }
  return { name: "home" };
}

async function loadServer(id) {
  if (!serverCache[id]) serverCache[id] = await j("/api/v1/servers/" + id);
  return serverCache[id];
}
function invalidateServer(id) {
  delete serverCache[id];
}

function shell(sidebar, top, body, mobile) {
  document.getElementById("app").innerHTML = `
    <aside class="sidebar">${sidebar}</aside>
    <div class="main">
      <div class="top">${top}</div>
      <div class="body">${body}</div>
      <nav class="mobile-nav">${mobile || ""}</nav>
    </div>`;
}

function globalSidebar(active) {
  return `<div class="brand" onclick="go('/')">SHNPP</div>
    <a class="${active === "home" ? "on" : ""}" href="/" onclick="event.preventDefault();go('/')">Серверы</a>
    <a class="${active === "create" ? "on" : ""}" href="/create" onclick="event.preventDefault();go('/create')">Создать</a>
    ${me && me.is_admin ? `<a class="${active === "admin" ? "on" : ""}" href="/admin" onclick="event.preventDefault();go('/admin')">Админ</a>` : ""}
    <div style="flex:1"></div>
    <div class="muted" style="padding:10px">${me ? "@" + (me.username || me.telegram_id) : "вход из бота"}</div>`;
}

function serverNav(s, active) {
  const id = s.id;
  const addons = hasAddons(s.server_type);
  const items = [
    ["overview", "Обзор", `/${id}`],
    ["console", "Консоль", `/${id}/console`],
    ["options", "Настройки", `/${id}/options`],
    addons ? ["addons", addonLabel(s.server_type), `/${id}/addons`] : null,
    ["files", "Файлы", `/${id}/files`],
    ["world", "Мир", `/${id}/world`],
    ["backups", "Бэкапы", `/${id}/backups`],
    ["access", "Доступ", `/${id}/access`],
  ].filter(Boolean);
  const links = items
    .map(
      ([key, label, href]) =>
        `<a class="${active === key || (active === "addons-add" && key === "addons") ? "on" : ""}" href="/servers${href}" onclick="event.preventDefault();go('/servers${href}')">${label}</a>`
    )
    .join("");
  return `<div class="brand" onclick="go('/')">SHNPP</div>
    <a href="/" onclick="event.preventDefault();go('/')">← Серверы</a>
    ${links}`;
}

function serverHeader(s) {
  return `<div>
      ${statusDot(s.status)}
      <b>${s.name}</b>
      <span class="muted"> · ${s.subdomain}</span>
      ${s.restart_required ? `<span class="badge">нужен рестарт</span>` : ""}
    </div>
    <div class="row">
      <button onclick="pwr('${s.id}','start')">Старт</button>
      <button class="ghost" onclick="pwr('${s.id}','stop')">Стоп</button>
      <button class="ghost" onclick="pwr('${s.id}','restart')">Рестарт</button>
    </div>
    <div class="row" style="width:100%">
      <code>${s.address || ""}</code>
      <button class="ghost" onclick="copy('${s.address || ""}')">копировать</button>
      <code>${s.ip_address || ""}</code>
      <button class="ghost" onclick="copy('${s.ip_address || ""}')">IP</button>
    </div>`;
}

function mobileBar(id) {
  return `<a href="/servers/${id}">Обзор</a>
    <a href="/servers/${id}/console" onclick="event.preventDefault();go('/servers/${id}/console')">Консоль</a>
    <a href="/servers/${id}/addons" onclick="event.preventDefault();go('/servers/${id}/addons')">Моды</a>
    <a href="/servers/${id}/files" onclick="event.preventDefault();go('/servers/${id}/files')">Файлы</a>
    <a href="/servers/${id}/options" onclick="event.preventDefault();go('/servers/${id}/options')">Ещё</a>`;
}

async function pwr(id, action) {
  await j("/api/v1/servers/" + id + "/power", { method: "POST", body: JSON.stringify({ action }) });
  invalidateServer(id);
  render();
}

async function render() {
  const r = parseRoute();
  if (!token && r.name !== "home") {
    shell(globalSidebar("home"), "", `<div class="empty">Откройте бота → Панель модов</div>`);
    return;
  }
  try {
    if (r.name === "home") return viewHome();
    if (r.name === "create") return viewCreate();
    if (r.name === "admin") return viewAdmin();
    const s = await loadServer(r.id);
    if (r.name === "overview") return viewOverview(s);
    if (r.name === "console") return viewConsole(s);
    if (r.name === "options") return viewOptions(s);
    if (r.name === "addons") return viewAddons(s);
    if (r.name === "addons-add") return viewAddonsAdd(s);
    if (r.name === "files") return viewFiles(s, r.filePath || "");
    if (r.name === "world") return viewWorld(s);
    if (r.name === "backups") return viewBackups(s);
    if (r.name === "access") return viewAccess(s);
    return viewOverview(s);
  } catch (e) {
    shell(globalSidebar("home"), "", `<div class="err">${e.message}</div>`);
  }
}

async function viewHome() {
  if (!token) {
    shell(
      globalSidebar("home"),
      "SHNPP",
      `<div class="empty">Войдите через Telegram-бота → Панель модов.<br>Без лендинга, сразу к серверам.</div>`
    );
    return;
  }
  const servers = await j("/api/v1/servers");
  const rows = servers.length
    ? `<div class="list">${servers
        .map(
          (s) => `<div class="item" onclick="go('/servers/${s.id}')" style="cursor:pointer">
        <div>${statusDot(s.status)} <b>${s.name}</b><div class="muted">${s.server_type} ${s.game_version}</div></div>
        <code>${s.address || ""}</code>
        <span class="muted">${s.subdomain}</span>
      </div>`
        )
        .join("")}</div>`
    : `<div class="empty">Серверов нет. <button onclick="go('/create')">Создать</button></div>`;
  shell(globalSidebar("home"), `<b>Серверы</b> <button onclick="go('/create')">Создать</button>`, rows);
}

let wiz = { step: 1, edition: "JAVA", software: "", version: "" };
async function viewCreate() {
  let body = "";
  if (wiz.step === 1) {
    body = `<h2>Издание</h2><div class="row">
      <button onclick="wiz.edition='JAVA';wiz.step=2;viewCreate()">Java</button>
      <button class="ghost" onclick="wiz.edition='BEDROCK';wiz.step=2;viewCreate()">Bedrock</button></div>`;
  } else if (wiz.step === 2) {
    const list = await j("/api/v1/software?edition=" + wiz.edition);
    body = `<h2>Ядро</h2><div class="cards">${list
      .map(
        (s) => `<div class="card" onclick="wiz.software='${s.id}';wiz.step=3;viewCreate()" style="cursor:pointer">
        <b>${s.name}</b>${s.recommended ? " · рекомендуем" : ""}<div class="hint">${s.blurb}</div></div>`
      )
      .join("")}</div><button class="ghost" onclick="wiz.step=1;viewCreate()">Назад</button>`;
  } else if (wiz.step === 3) {
    const v = await j("/api/v1/software/" + wiz.software + "/versions");
    const g = v.groups || {};
    const blk = (t, a) =>
      a && a.length
        ? `<h3>${t}</h3><div class="row">${a
            .map((x) => `<button class="ghost" onclick="wiz.version='${x}';wiz.step=4;viewCreate()">${x}</button>`)
            .join("")}</div>`
        : "";
    body = `<h2>Версия · ${wiz.software}</h2>${blk("Свежие", g.fresh)}${blk("LTS", g.lts)}${blk("Архив", g.archive)}
      <button class="ghost" onclick="wiz.step=2;viewCreate()">Назад</button>`;
  } else {
    body = `<h2>Имя и поддомен</h2>
      <div class="row"><input id="nm" placeholder="Название"><input id="sub" placeholder="поддомен"></div>
      <div class="row">
        <select id="gm"><option>survival</option><option>creative</option></select>
        <select id="df"><option>normal</option><option>easy</option><option>hard</option><option>peaceful</option></select>
        <input id="slots" type="number" value="10" min="1" max="40" style="width:80px">
      </div>
      <p class="muted" id="submsg"></p>
      <div class="row"><button class="ghost" onclick="wiz.step=3;viewCreate()">Назад</button><button onclick="createSrv()">Создать</button></div>
      <p class="err" id="cerr"></p>`;
  }
  shell(globalSidebar("create"), `<b>Создать сервер</b> · шаг ${wiz.step}/4`, body);
  const sub = $("sub");
  if (sub)
    sub.addEventListener("input", async (ev) => {
      const s = ev.target.value.toLowerCase();
      if (s.length < 2) return;
      const d = await j("/api/v1/subdomain-available?subdomain=" + encodeURIComponent(s));
      $("submsg").textContent = d.available ? "свободно" : "занято";
    });
}
async function createSrv() {
  $("cerr").textContent = "Создаём…";
  try {
    const s = await j("/api/v1/servers", {
      method: "POST",
      body: JSON.stringify({
        name: $("nm").value,
        subdomain: $("sub").value.toLowerCase(),
        server_type: wiz.software,
        game_version: wiz.version,
        edition: wiz.edition,
        gamemode: $("gm").value,
        difficulty: $("df").value,
        max_players: Number($("slots").value),
        plan_id: "starter",
        online_mode: false,
      }),
    });
    wiz = { step: 1, edition: "JAVA", software: "", version: "" };
    go("/servers/" + s.id);
  } catch (e) {
    $("cerr").textContent = e.message;
  }
}

async function viewOverview(s) {
  let log = "";
  try {
    log = (await j("/api/v1/servers/" + s.id + "/console?lines=8")).lines || "";
  } catch {}
  const body = `${s.status === "SLEEPING" || s.status === "STOPPED" ? `<div class="empty">Сервер спит — нажми Старт</div>` : ""}
    <p class="muted">${s.server_type} ${s.game_version} · онлайн ${s.players_online || 0}</p>
    ${!hasAddons(s.server_type) ? `<p class="muted">На Vanilla нет модов. Смените ядро при создании нового сервера.</p>` : ""}
    <h3>Последние строки лога</h3><pre>${escapeHtml(log)}</pre>`;
  shell(serverNav(s, "overview"), serverHeader(s), body, mobileBar(s.id));
}

async function viewConsole(s) {
  shell(
    serverNav(s, "console"),
    serverHeader(s),
    `<pre id="cons"></pre><div class="row"><input id="cmd" placeholder="say hello" style="flex:1"><button onclick="sendCmd('${s.id}')">Отправить</button></div>`,
    mobileBar(s.id)
  );
  loadCons(s.id);
}
async function loadCons(id) {
  try {
    const d = await j("/api/v1/servers/" + id + "/console?lines=80");
    if ($("cons")) $("cons").textContent = d.lines || "";
  } catch {}
}
async function sendCmd(id) {
  await j("/api/v1/servers/" + id + "/console", { method: "POST", body: JSON.stringify({ command: $("cmd").value }) });
  $("cmd").value = "";
  loadCons(id);
}

function optRow(key, control, hint) {
  return `<div class="opt"><label>${key}</label><div>${control}</div><div class="hint">${hint}</div></div>`;
}
async function viewOptions(s) {
  const st = await j("/api/v1/servers/" + s.id + "/settings");
  const num = (k, v) => `<input data-k="${k}" type="number" value="${v ?? ""}">`;
  const sel = (k, v, opts) =>
    `<select data-k="${k}">${opts.map((o) => `<option ${o === v ? "selected" : ""}>${o}</option>`).join("")}</select>`;
  const chk = (k, v) => `<input data-k="${k}" type="checkbox" ${v ? "checked" : ""}>`;
  const txt = (k, v) => `<input data-k="${k}" value="${(v ?? "").toString().replaceAll('"', "&quot;")}">`;
  const body = `
    <details class="acc" open><summary>Игра</summary><div class="inner">
      ${optRow("Слоты", num("max_players", st.max_players), "Сколько игроков может зайти сразу.")}
      ${optRow("Режим", sel("gamemode", st.gamemode, ["survival", "creative", "adventure", "spectator"]), "Режим по умолчанию для новых игроков.")}
      ${optRow("Сложность", sel("difficulty", st.difficulty, ["peaceful", "easy", "normal", "hard"]), "Урон мобов и голод.")}
      ${optRow("PvP", chk("pvp", st.pvp), "Можно ли бить других игроков.")}
      ${optRow("Whitelist", chk("whitelist", st.whitelist), "Только из белого списка.")}
      ${optRow("Command blocks", chk("command_blocks", st.command_blocks), "Командные блоки в мире.")}
    </div></details>
    <details class="acc"><summary>Мир</summary><div class="inner">
      ${optRow("Nether", chk("nether", st.nether), "Адский мир.")}
      ${optRow("Животные", chk("spawn_animals", st.spawn_animals), "Коровы, овцы и т.д.")}
      ${optRow("Монстры", chk("spawn_monsters", st.spawn_monsters), "Зомби, криперы.")}
      ${optRow("Spawn protection", num("spawn_protection", st.spawn_protection ?? 0), "Радиус защиты спавна в блоках.")}
    </div></details>
    <details class="acc"><summary>Производительность</summary><div class="inner">
      ${optRow("View distance", num("view_distance", st.view_distance), "Дальность прорисовки чанков.")}
      ${optRow("Simulation distance", num("simulation_distance", st.simulation_distance), "Где тикают сущности.")}
      ${optRow("Max tick", num("max_tick_time", st.max_tick_time ?? 60000), "Лимит тика watchdog, мс.")}
    </div></details>
    <details class="acc"><summary>Сеть</summary><div class="inner">
      ${optRow("MOTD", txt("motd", st.motd), "Текст в списке серверов.")}
      ${optRow("Online-mode", chk("online_mode", st.online_mode), "Проверка лицензии Mojang.")}
      ${optRow("Resource pack", txt("resource_pack", st.resource_pack), "URL пака, который качает клиент.")}
    </div></details>
    <details class="acc"><summary>Иконка</summary><div class="inner">
      <p class="hint">PNG 64×64 — server-icon.png</p>
      <input type="file" accept="image/png" onchange="upIcon('${s.id}', this)">
    </div></details>
    <p><a href="/servers/${s.id}/files" onclick="event.preventDefault();go('/servers/${s.id}/files?open=server.properties')">Открыть server.properties в Файлах</a></p>
    <div class="sticky-save"><button onclick="saveOpts('${s.id}')">Сохранить</button></div>`;
  shell(serverNav(s, "options"), serverHeader(s), body, mobileBar(s.id));
}
async function saveOpts(id) {
  const patch = {};
  document.querySelectorAll("[data-k]").forEach((n) => {
    patch[n.dataset.k] = n.type === "checkbox" ? n.checked : n.type === "number" ? Number(n.value) : n.value;
  });
  await j("/api/v1/servers/" + id + "/settings", { method: "PUT", body: JSON.stringify(patch) });
  invalidateServer(id);
  toast("Сохранено. Рестарт, чтобы применить.");
  render();
}
async function upIcon(id, input) {
  if (!input.files[0]) return;
  const fd = new FormData();
  fd.append("file", input.files[0]);
  await fetch(api + "/api/v1/servers/" + id + "/icon", { method: "POST", headers: { Authorization: "Bearer " + token }, body: fd });
  toast("Иконка загружена");
}

async function viewAddons(s) {
  const mods = await j("/api/v1/servers/" + s.id + "/mods");
  const off = mods.filter((m) => !m.enabled).length;
  const body = `<div class="row"><span>${mods.length} ${addonLabel(s.server_type).toLowerCase()} · ${off} выкл</span>
      <button onclick="go('/servers/${s.id}/addons/add')">Найти</button></div>
    ${
      mods.length
        ? `<div class="list">${mods
            .map(
              (m) => `<div class="item">
          <div><b>${m.name}</b><div class="muted">${m.source} · ${m.addon_type || "mod"}</div></div>
          <span>${m.enabled ? "вкл" : "выкл"}</span>
          <span>
            <button class="ghost" onclick="togMod('${s.id}',${m.id})">${m.enabled ? "Выкл" : "Вкл"}</button>
            <button class="ghost" onclick="delMod('${s.id}',${m.id})">Удалить</button>
          </span></div>`
            )
            .join("")}</div>`
        : `<div class="empty">Ничего не установлено.<br><button onclick="go('/servers/${s.id}/addons/add')">Найти моды</button></div>`
    }`;
  shell(serverNav(s, "addons"), serverHeader(s), body, mobileBar(s.id));
}
async function togMod(id, mid) {
  await j("/api/v1/servers/" + id + "/mods/" + mid + "/toggle", { method: "POST" });
  invalidateServer(id);
  render();
}
async function delMod(id, mid) {
  await j("/api/v1/servers/" + id + "/mods/" + mid, { method: "DELETE" });
  render();
}

async function viewAddonsAdd(s) {
  let loader = s.server_type.toLowerCase();
  if (["purpur", "spigot"].includes(loader)) loader = "paper";
  const ptype = isPluginCore(s.server_type) ? "plugin" : "mod";
  const body = `<div class="row">
      <input id="q" placeholder="lithium, viaversion…" style="flex:1">
      <select id="src"><option value="modrinth">Modrinth</option><option value="curseforge">CurseForge</option><option value="both">оба</option></select>
      <select id="pt"><option value="${ptype}">${ptype}</option><option value="mod">мод</option><option value="plugin">плагин</option><option value="modpack">пак</option></select>
      <label class="muted"><input type="checkbox" id="lock" checked> версия ${s.game_version} / ${loader}</label>
    </div>
    <div id="hits" class="cards" style="margin-top:12px"></div>
    <div id="more"></div>
    <div id="jobs"></div>`;
  shell(serverNav(s, "addons"), serverHeader(s), body, mobileBar(s.id));
  $("q").addEventListener("input", () => debounceSearch(s, loader));
  $("src").addEventListener("change", () => debounceSearch(s, loader));
  $("pt").addEventListener("change", () => debounceSearch(s, loader));
  pollJobs(s.id);
}
function debounceSearch(s, loader) {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => runSearch(s, loader, 0), 300);
}
async function runSearch(s, loader, offset) {
  const q = $("q").value.trim();
  if (q.length < 2) {
    $("hits").innerHTML = "";
    return;
  }
  if (searchAbort) searchAbort.abort();
  searchAbort = new AbortController();
  $("hits").innerHTML = `<div class="card muted">поиск…</div>`;
  const src = $("src").value;
  const pt = $("pt").value;
  const ver = $("lock") && $("lock").checked ? s.game_version : s.game_version;
  try {
    const hits = await j(
      `/api/v1/mods/search?query=${encodeURIComponent(q)}&loader=${loader}&game_version=${encodeURIComponent(ver)}&source=${src}&project_type=${pt}&offset=${offset}&limit=20`,
      { signal: searchAbort.signal }
    );
    if (!hits.length) {
      $("hits").innerHTML = `<div class="empty">моды не найдены</div>`;
      return;
    }
    $("hits").innerHTML = hits
      .map((h) => {
        const blocked = h.distribution_blocked;
        return `<div class="card ${blocked ? "disabled" : ""}">
        ${h.icon_url ? `<img class="icon" loading="lazy" src="${h.icon_url}" alt="">` : `<div class="ph"></div>`}
        <b>${escapeHtml(h.name)}</b>
        <div class="hint">${escapeHtml((h.description || "").slice(0, 90))}</div>
        <div class="muted">${h.source} · ${(h.downloads || 0).toLocaleString()}</div>
        ${blocked ? `<div class="err">ручная загрузка</div>` : `<button onclick='openHit(${JSON.stringify(h).replaceAll("'", "&#39;")}, "${s.id}")'>Установить</button>`}
      </div>`;
      })
      .join("");
  } catch (e) {
    if (e.name === "AbortError") return;
    $("hits").innerHTML = `<div class="err">${e.message}</div>`;
  }
}
function openHit(h, id) {
  const d = document.createElement("div");
  d.className = "drawer";
  d.innerHTML = `<button class="ghost" onclick="this.parentNode.remove()">закрыть</button>
    <h2>${escapeHtml(h.name)}</h2>
    <p class="hint">${escapeHtml(h.description || "")}</p>
    <p class="muted">${h.source} · ${h.external_id}</p>
    <label class="muted"><input type="checkbox" id="deps" checked> поставить зависимости</label>
    <p><button onclick='startInstall("${id}","${h.source}","${h.external_id}","${escapeHtml(h.name)}")'>Установить</button></p>`;
  document.body.appendChild(d);
}
async function startInstall(id, source, ext, name) {
  document.querySelector(".drawer")?.remove();
  const with_deps = true;
  const job = await j("/api/v1/servers/" + id + "/addons/install", {
    method: "POST",
    body: JSON.stringify({ source, external_id: ext, name, with_deps }),
  });
  toast("В очереди");
  watchJob(id, job.job_id);
}
async function watchJob(id, jobId) {
  const box = $("jobs") || document.querySelector(".body");
  let node = document.getElementById("job-" + jobId);
  if (!node) {
    node = document.createElement("div");
    node.id = "job-" + jobId;
    node.className = "card";
    box.prepend(node);
  }
  const tick = async () => {
    const job = await j(`/api/v1/servers/${id}/addons/jobs/${jobId}`);
    const pct = job.bytes_total ? Math.round((100 * job.bytes_done) / job.bytes_total) : 0;
    node.innerHTML = `<b>${job.filename || job.name || "файл"}</b> · ${job.state}
      ${job.state === "downloading" ? `<div class="bar"><i style="width:${pct}%"></i></div><span class="muted">${pct}% · ${(job.bytes_done / 1e6).toFixed(1)} / ${(job.bytes_total / 1e6).toFixed(1)} МБ</span>` : ""}
      ${job.error ? `<div class="err">${escapeHtml(job.error)}</div>` : ""}`;
    if (["done", "error", "manual"].includes(job.state)) {
      if (job.state === "done") toast("Готово");
      invalidateServer(id);
      return;
    }
    setTimeout(tick, 400);
  };
  tick();
}
async function pollJobs(id) {
  try {
    const jobs = await j("/api/v1/servers/" + id + "/addons/jobs");
    jobs.filter((j) => !["done", "error", "manual"].includes(j.state)).forEach((j) => watchJob(id, j.job_id));
  } catch {}
}

async function viewFiles(s, path) {
  const q = new URLSearchParams(location.search);
  if (q.get("open")) path = q.get("open");
  const data = await j("/api/v1/servers/" + s.id + "/files?path=" + encodeURIComponent(path || ""));
  const crumbs =
    `<a href="#" onclick="event.preventDefault();go('/servers/${s.id}/files')">корень</a>` +
    data.crumbs.map((c) => ` / <a href="#" onclick="event.preventDefault();go('/servers/${s.id}/files/${c.path}')">${c.name}</a>`).join("");
  const tree = ["world", "mods", "plugins", "config", "logs"]
    .map((n) => `<button onclick="go('/servers/${s.id}/files/${n}')">${n}</button>`)
    .join("");
  const rows = data.entries
    .map((e) => {
      const badge = (e.path.startsWith("mods/") || e.path.startsWith("plugins/")) && e.name.endsWith(".jar") ? `<span class="badge">Моды</span>` : "";
      const open = e.dir
        ? `go('/servers/${s.id}/files/${e.path}')`
        : e.text
          ? `openFile('${s.id}','${e.path}')`
          : `dlFile('${s.id}','${e.path}')`;
      return `<div class="item">
        <div onclick="${open}" style="cursor:pointer">${e.dir ? "📁" : "📄"} ${e.name} ${badge}</div>
        <span class="muted">${e.dir ? "" : (e.size / 1024).toFixed(1) + " КБ"}</span>
        <span class="muted">${e.mtime.slice(0, 16).replace("T", " ")}</span>
      </div>`;
    })
    .join("");
  const body = `<div class="row crumbs">${crumbs}</div>
    <div style="display:grid;grid-template-columns:160px 1fr;gap:12px">
      <div class="tree card">${tree}</div>
      <div>
        <div class="row"><input type="file" id="up" multiple>
          <button class="ghost" onclick="mkdir('${s.id}','${path || ""}')">папка</button></div>
        <div class="bar" id="upbar" style="display:none"><i></i></div>
        <div class="list">${rows || `<div class="empty">пусто</div>`}</div>
      </div>
    </div>
    <div id="editor"></div>`;
  shell(serverNav(s, "files"), serverHeader(s), body, mobileBar(s.id));
  const up = $("up");
  if (up)
    up.addEventListener("change", () => uploadFiles(s.id, path || "", up.files));
  document.querySelector(".body").addEventListener("dragover", (e) => e.preventDefault());
  document.querySelector(".body").addEventListener("drop", (e) => {
    e.preventDefault();
    uploadFiles(s.id, path || "", e.dataTransfer.files);
  });
}
async function openFile(id, path) {
  const d = await j("/api/v1/servers/" + id + "/files/content?path=" + encodeURIComponent(path));
  $("editor").innerHTML = `<h3 class="mono">${path}</h3>
    <textarea class="editor" id="ed" style="width:100%;min-height:280px">${escapeHtml(d.content)}</textarea>
    <div class="sticky-save"><button onclick="saveFile('${id}','${path}')">Сохранить</button></div>`;
}
async function saveFile(id, path) {
  await j("/api/v1/servers/" + id + "/files/content?path=" + encodeURIComponent(path), {
    method: "PUT",
    body: JSON.stringify({ content: $("ed").value }),
  });
  toast("Файл сохранён");
}
function dlFile(id, path) {
  fetch(api + "/api/v1/servers/" + id + "/files/download?path=" + encodeURIComponent(path), {
    headers: { Authorization: "Bearer " + token },
  })
    .then((r) => r.blob())
    .then((b) => {
      const a = document.createElement("a");
      a.href = URL.createObjectURL(b);
      a.download = path.split("/").pop();
      a.click();
    });
}
function uploadFiles(id, path, files) {
  [...files].forEach((file) => {
    const xhr = new XMLHttpRequest();
    const bar = $("upbar");
    if (bar) bar.style.display = "block";
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && bar) bar.querySelector("i").style.width = Math.round((100 * e.loaded) / e.total) + "%";
    };
    xhr.onload = () => {
      toast(file.name + " загружен");
      go("/servers/" + id + "/files/" + path);
    };
    xhr.open("POST", api + "/api/v1/servers/" + id + "/files/upload?path=" + encodeURIComponent(path));
    xhr.setRequestHeader("Authorization", "Bearer " + token);
    const fd = new FormData();
    fd.append("file", file);
    xhr.send(fd);
  });
}
async function mkdir(id, path) {
  const name = prompt("Имя папки");
  if (!name) return;
  await j("/api/v1/servers/" + id + "/files/mkdir", {
    method: "POST",
    body: JSON.stringify({ path: path ? path + "/" + name : name }),
  });
  go("/servers/" + id + "/files/" + (path || ""));
}

async function viewWorld(s) {
  shell(
    serverNav(s, "world"),
    serverHeader(s),
    `<div class="row"><button onclick="dlWorld('${s.id}')">Скачать мир</button></div>
     <p class="muted">Залить zip замены мира</p>
     <input type="file" accept=".zip" onchange="upWorld('${s.id}', this)">`,
    mobileBar(s.id)
  );
}
async function dlWorld(id) {
  const r = await fetch(api + "/api/v1/servers/" + id + "/world", { headers: { Authorization: "Bearer " + token } });
  const b = await r.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(b);
  a.download = "world.zip";
  a.click();
}
async function upWorld(id, input) {
  if (!input.files[0]) return;
  const fd = new FormData();
  fd.append("file", input.files[0]);
  await fetch(api + "/api/v1/servers/" + id + "/world", { method: "POST", headers: { Authorization: "Bearer " + token }, body: fd });
  toast("Мир залит, сервер остановлен");
}

async function viewBackups(s) {
  const rows = await j("/api/v1/servers/" + s.id + "/backups");
  const gdrive = await j("/api/v1/servers/" + s.id + "/gdrive");
  const body = `${rows
    .map(
      (b) => `<div class="item"><span>${b.kind} · ${(b.size_bytes / 1e6).toFixed(1)} МБ · ${b.created_at}</span>
      <button class="ghost" onclick="restore('${s.id}',${b.id})">восстановить</button></div>`
    )
    .join("") || `<div class="empty">Бэкапов нет</div>`}
    <button onclick="mkBackup('${s.id}')">Создать сейчас</button>
    <div class="card"><b>Google Drive</b><p class="hint">${gdrive.todo}</p><button class="ghost" disabled>Подключить Google Drive</button></div>`;
  shell(serverNav(s, "backups"), serverHeader(s), body, mobileBar(s.id));
}
async function mkBackup(id) {
  await j("/api/v1/servers/" + id + "/backups", { method: "POST" });
  render();
}
async function restore(id, bid) {
  if (!confirm("Восстановить? Сервер остановится.")) return;
  await j("/api/v1/servers/" + id + "/backups/" + bid + "/restore", { method: "POST" });
  toast("Восстановлено");
}

async function viewAccess(s) {
  const acl = await j("/api/v1/servers/" + s.id + "/acl");
  const body = `${acl.map((a) => `<div>${a.username || a.telegram_id} · ${a.role}</div>`).join("")}
    <div class="row"><input id="tg" placeholder="telegram_id"><select id="role"><option>OPERATOR</option><option>START_CONSOLE</option><option>BACKUPS</option></select>
    <button onclick="addAcl('${s.id}')">Добавить</button></div>
    <p class="hint">Operator может будить спящий сервер.</p>`;
  shell(serverNav(s, "access"), serverHeader(s), body, mobileBar(s.id));
}
async function addAcl(id) {
  await j("/api/v1/servers/" + id + "/acl", {
    method: "POST",
    body: JSON.stringify({ telegram_id: Number($("tg").value), role: $("role").value }),
  });
  render();
}

async function viewAdmin() {
  if (!me || !me.is_admin) {
    shell(globalSidebar("admin"), "Админ", `<div class="empty">Нет доступа</div>`);
    return;
  }
  const ov = await j("/api/v1/admin/overview");
  const users = await j("/api/v1/admin/users");
  const servers = await j("/api/v1/admin/servers");
  const audit = await j("/api/v1/admin/audit");
  shell(
    globalSidebar("admin"),
    "<b>Админ</b>",
    `<div class="card"><pre>${escapeHtml(JSON.stringify(ov.servers, null, 2))}</pre></div>
     <div class="list">${users
       .map(
         (u) => `<div class="item"><span>${u.telegram_id} @${u.username || "—"} ${u.is_banned ? "БАН" : ""}</span>
       <button class="ghost" onclick="ban(${u.telegram_id},${!u.is_banned})">${u.is_banned ? "разбан" : "бан"}</button></div>`
       )
       .join("")}</div>
     <div class="list">${servers
       .map(
         (s) => `<div class="item"><span>${s.subdomain} · ${s.status}</span>
       <span><button class="ghost" onclick="adp('${s.id}','start')">старт</button>
       <button class="ghost" onclick="adp('${s.id}','stop')">стоп</button></span></div>`
       )
       .join("")}</div>
     <pre>${audit
       .slice(0, 30)
       .map((a) => a.created_at + " " + a.action)
       .join("\n")}</pre>`
  );
}
async function ban(tg, banned) {
  await j("/api/v1/admin/users/" + tg + "/ban", { method: "POST", body: JSON.stringify({ banned }) });
  render();
}
async function adp(id, a) {
  await j("/api/v1/admin/servers/" + id + "/power?action=" + a, { method: "POST" });
  render();
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

boot();
