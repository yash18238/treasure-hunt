/* game.js - browser side of Treasure Hunt: draws the board and talks to the Flask API. */
(function () {
  "use strict";

  // ---------- SVG icons (viewBox 24x24) ----------
  const svg = (inner) => '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">' + inner + "</svg>";
  const ICON = {
    player: svg('<ellipse cx="12" cy="21" rx="6" ry="1.6" fill="rgba(0,0,0,.25)"/>' +
      '<path d="M6 19c0-4 2.5-6 6-6s6 2 6 6z" fill="#2563eb"/>' +
      '<circle cx="12" cy="9.5" r="4.2" fill="#f2c496"/>' +
      '<path d="M5.5 8.5c1-4 3.2-5.5 6.5-5.5s5.5 1.5 6.5 5.5c-4-1.5-9-1.5-13 0z" fill="#b91c1c"/>' +
      '<rect x="4.5" y="7.8" width="15" height="1.8" rx=".9" fill="#7f1d1d"/>' +
      '<circle cx="10.500" cy="10.500" r=".8" fill="#222"/><circle cx="13.500" cy="10.500" r=".8" fill="#222"/>'),
    rock: svg('<path d="M3 19l3-9 5-4 6 2 4 7-3 4z" fill="#7b8594"/><path d="M6 10l5-4 6 2-5 3z" fill="#a2acbb"/>' +
      '<path d="M12 11l5-3 4 7-3 4-6 0z" fill="#5d6675"/>'),
    tree: svg('<rect x="10.600" y="12" width="2.800" height="9" rx="1" fill="#7a4a21"/>' +
      '<circle cx="12" cy="8" r="6" fill="#16a34a"/><circle cx="8.500" cy="10" r="3.500" fill="#22c55e"/>' +
      '<circle cx="15.5" cy="9.500" r="3.500" fill="#15803d"/>'),
    coin: svg('<circle cx="12" cy="12" r="8.500" fill="#d99a14"/><circle cx="12" cy="12" r="7" fill="#fbbf24"/>' +
      '<circle cx="12" cy="12" r="4.800" fill="none" stroke="#d99a14" stroke-width="1.400"/>' +
      '<path d="M12 8.500v7M10 10.200h3.200a1.200 1.200 0 010 2.400H10.800a1.200 1.200 0 000 2.400H14" fill="none" stroke="#b7790a" stroke-width="1" />'),
    scroll: svg('<rect x="5" y="5" width="14" height="14" rx="2" fill="#f5e6b8"/>' +
      '<rect x="3.500" y="3.800" width="17" height="3.200" rx="1.600" fill="#c9a050"/>' +
      '<rect x="3.500" y="17" width="17" height="3.200" rx="1.600" fill="#c9a050"/>' +
      '<path d="M8 10h8M8 12.500h8M8 15h5" stroke="#8a6a2c" stroke-width="1.200" stroke-linecap="round"/>'),
    key: svg('<circle cx="8" cy="8" r="4.5" fill="#fbbf24" stroke="#b7790a" stroke-width="1.200"/>' +
      '<circle cx="8" cy="8" r="1.700" fill="#8a6a2c"/>' +
      '<path d="M11.200 11.200L20 20" stroke="#b7790a" stroke-width="3.600" stroke-linecap="round"/>' +
      '<path d="M11.200 11.200L20 20" stroke="#fbbf24" stroke-width="2" stroke-linecap="round"/>' +
      '<path d="M16 16l2.200-2.200M18.500 18.500l2-2" stroke="#fbbf24" stroke-width="2" stroke-linecap="round"/>'),
    chest: svg('<rect x="3" y="9" width="18" height="11" rx="1.8" fill="#8b4a1f"/>' +
      '<path d="M3 10.500C3 6.5 7 4.5 12 4.5s9 2 9 6z" fill="#a85b27"/>' +
      '<rect x="3" y="10" width="18" height="2.200" fill="#fbbf24"/>' +
      '<rect x="10" y="10.500" width="4" height="5.5" rx="1" fill="#fbbf24" stroke="#b7790a"/>' +
      '<circle cx="12" cy="13" r=".9" fill="#5b3412"/>'),
    trap: svg('<ellipse cx="12" cy="13" rx="8.500" ry="5.5" fill="#4a2f1b"/><ellipse cx="12" cy="12.500" rx="6.5" ry="3.800" fill="#2e1c0f"/>' +
      '<path d="M9 9.500l6 6M15 9.500l-6 6" stroke="#ef4444" stroke-width="1.8" stroke-linecap="round"/>'),
  };
  const TILE_ICON = { "#": null, C: ICON.coin, S: ICON.scroll, K: ICON.key, X: ICON.chest, T: ICON.trap };

  // ---------- helpers ----------
  const $ = (id) => document.getElementById(id);
  let S = null;                 // latest game state from the server
  let busy = false;
  let diff = "medium";
  let hintDir = null;

  async function api(path, body) {
    const opts = body === undefined ? {} :
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
    const res = await fetch(path, opts);
    if (!res.ok) throw new Error("request failed");
    return res.json();
  }

  function showScreen(name) {
    $("startScreen").classList.toggle("hidden", name !== "start");
    $("gameScreen").classList.toggle("hidden", name !== "game");
    $("topInfo").textContent = name === "game" ? "Difficulty: " + cap(S.difficulty) : "";
  }
  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

  function renderLeaderboard(list, el) {
    el.innerHTML = "";
    if (!list || !list.length) {
      el.innerHTML = '<li class="empty">No scores yet - be the first!</li>';
      return;
    }
    list.forEach((e) => {
      const li = document.createElement("li");
      li.innerHTML = '<span class="n">' + esc(e.name) + ' <small>' + e.difficulty + " &middot; L" + e.level +
        '</small></span><b>' + e.score + "</b>";
      el.appendChild(li);
    });
  }
  const esc = (t) => String(t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  // ---------- board drawing ----------
  function drawBoard(events) {
    const n = S.size;
    const cell = Math.max(30, Math.min(54, Math.floor((Math.min(window.innerWidth - 80, 600) - 30) / (n + 1))));
    const board = $("board");
    board.style.setProperty("--cell", cell + "px");
    board.style.gridTemplateColumns = "20px repeat(" + n + "," + cell + "px)";
    board.style.gridAutoRows = cell + "px";
    board.innerHTML = "";

    const blank = document.createElement("div");
    board.appendChild(blank);
    for (let c = 0; c < n; c++) board.appendChild(label(S.col_labels[c]));

    const [pr, pc] = S.pos;
    const evTypes = (events || []).map((e) => e.type);
    for (let r = 0; r < n; r++) {
      board.appendChild(label(r + 1));
      for (let c = 0; c < n; c++) {
        const ch = S.tiles[r][c];
        const d = document.createElement("div");
        d.className = "cell";
        if (ch === "?") {
          d.classList.add("fog");
        } else {
          d.classList.add("floor");
          if ((r + c) % 2) d.classList.add("alt");
          const near = Math.max(Math.abs(r - pr), Math.abs(c - pc)) <= S.vision;
          if (!near) d.classList.add("dim");
          if (ch === "#") d.innerHTML = (r * 7 + c * 3) % 3 === 0 ? ICON.tree : ICON.rock;
          else if (TILE_ICON[ch]) d.innerHTML = TILE_ICON[ch];
        }
        if (r === pr && c === pc) {
          d.classList.add("me");
          d.innerHTML = ICON.player;
          if (evTypes.some((t) => ["coin", "scroll", "key", "chest"].includes(t))) d.classList.add("pop");
          if (evTypes.includes("trap")) d.classList.add("trapflash");
        }
        if (hintDir) {
          const dr = { up: -1, down: 1, left: 0, right: 0 }[hintDir];
          const dc = { up: 0, down: 0, left: -1, right: 1 }[hintDir];
          if (r === pr + dr && c === pc + dc) d.classList.add("hintcell");
        }
        board.appendChild(d);
      }
    }
  }
  function label(text) {
    const d = document.createElement("div");
    d.className = "lab";
    d.textContent = text;
    return d;
  }

  // ---------- HUD ----------
  function renderHud(events) {
    $("lvlLabel").textContent = "LEVEL " + S.level + " / " + S.max_level;
    $("playerLabel").textContent = S.name;
    $("scoreVal").textContent = S.score;
    $("movesVal").textContent = S.moves_left;
    const pct = Math.max(0, (S.moves_left / S.moves_total) * 100);
    const bar = $("movesBar");
    bar.style.width = pct + "%";
    bar.classList.toggle("low", pct < 25);
    $("keyVal").textContent = S.has_key ? "Collected" : "Missing";
    $("keyChip").classList.toggle("has", S.has_key);
    $("coinVal").textContent = S.coins + " / " + S.coins_total;
    $("hotLabel").textContent = S.hot.label;
    $("meterMark").style.left = "calc(" + S.hot.percent + "% - 3px)";
    const list = $("clueList");
    list.innerHTML = "";
    if (!S.clues.length) {
      list.innerHTML = '<li class="none">No clues yet. Look for scroll icons on the island.</li>';
    } else {
      S.clues.forEach((c) => { const li = document.createElement("li"); li.textContent = c; list.appendChild(li); });
    }
    if (events && events.length) {
      const t = $("toast");
      t.textContent = events[events.length - 1].text;
      t.className = "toast " + events[events.length - 1].type;
    }
  }

  function render(events) {
    drawBoard(events);
    renderHud(events);
    if (events && events.some((e) => e.type === "blocked" || e.type === "locked")) {
      const b = $("board");
      b.classList.remove("shake"); void b.offsetWidth; b.classList.add("shake");
    }
    if (S.status !== "playing") setTimeout(showModal, 650);
  }

  // ---------- modal ----------
  function showModal() {
    const m = $("modal");
    const title = $("modalTitle"), text = $("modalText"), prim = $("modalPrimary");
    $("modalIcon").innerHTML = S.status === "lost" ? ICON.trap : ICON.chest;
    const stats = [["SCORE", S.score], ["LEVEL", S.level + "/" + S.max_level], ["STEPS", S.steps]];
    $("modalStats").innerHTML = stats.map((s) => "<div><b>" + s[1] + "</b><span>" + s[0] + "</span></div>").join("");
    $("modalLbWrap").classList.add("hidden");
    if (S.status === "level_complete") {
      title.textContent = "Level " + S.level + " complete!";
      text.textContent = "You opened the chest with " + S.moves_left + " moves to spare. Bonus: +" + S.bonus + " points.";
      prim.textContent = "Next level";
      prim.onclick = async () => { hide(); S = await api("/api/next", {}); hintDir = null; render(); setToast("A new island appears from the mist..."); };
    } else if (S.status === "won") {
      title.textContent = "Legendary treasure hunter!";
      text.textContent = "You conquered all " + S.max_level + " islands" + (S.rank ? " and ranked #" + S.rank + " on the leaderboard" : "") + ".";
      prim.textContent = "Play again";
      prim.onclick = () => { hide(); startGame(); };
      renderLeaderboard(S.leaderboard, $("modalLb")); $("modalLbWrap").classList.remove("hidden");
    } else {
      title.textContent = "Out of moves!";
      text.textContent = "The tide came in before you found the treasure on level " + S.level + ".";
      prim.textContent = "Try again";
      prim.onclick = () => { hide(); startGame(); };
      renderLeaderboard(S.leaderboard, $("modalLb")); $("modalLbWrap").classList.remove("hidden");
    }
    m.classList.remove("hidden");
  }
  const hide = () => $("modal").classList.add("hidden");
  function setToast(t) { const e = $("toast"); e.textContent = t; e.className = "toast"; }

  // ---------- actions ----------
  async function startGame() {
    const name = $("nameInput").value.trim();
    S = await api("/api/new", { name, difficulty: diff });
    hintDir = null;
    showScreen("game");
    setToast("Find the golden key, then open the chest. Good luck, " + S.name + "!");
    render();
  }

  async function move(dir) {
    if (busy || !S || S.status !== "playing") return;
    busy = true;
    try {
      hintDir = null;
      S = await api("/api/move", { dir });
      render(S.events);
    } finally { busy = false; }
  }

  async function hint() {
    if (busy || !S || S.status !== "playing") return;
    busy = true;
    try {
      S = await api("/api/hint", {});
      const h = S.events.find((e) => e.type === "hint");
      hintDir = h ? h.dir : null;
      render(S.events);
    } finally { busy = false; }
  }

  async function toMenu() {
    hide();
    showScreen("start");
    renderLeaderboard(await api("/api/leaderboard"), $("startLb"));
  }

  // ---------- wiring ----------
  const KEYS = { ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right",
                 w: "up", s: "down", a: "left", d: "right", W: "up", S: "down", A: "left", D: "right" };
  document.addEventListener("keydown", (e) => {
    if (document.activeElement === $("nameInput")) {
      if (e.key === "Enter") startGame();
      return;
    }
    if ($("gameScreen").classList.contains("hidden")) return;
    if (KEYS[e.key]) { e.preventDefault(); move(KEYS[e.key]); }
    else if (e.key === "h" || e.key === "H") hint();
  });
  document.querySelectorAll("#dpad button").forEach((b) => b.addEventListener("click", () => move(b.dataset.dir)));
  document.querySelectorAll(".diff").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll(".diff").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    diff = b.dataset.d;
  }));
  $("startBtn").addEventListener("click", startGame);
  $("hintBtn").addEventListener("click", hint);
  $("menuBtn").addEventListener("click", toMenu);
  $("modalSecondary").addEventListener("click", toMenu);
  window.addEventListener("resize", () => { if (S && !$("gameScreen").classList.contains("hidden")) drawBoard(); });

  // legend + hero icons
  $("heroIcon").innerHTML = ICON.chest;
  $("keyIcon").innerHTML = ICON.key;
  $("coinIcon").innerHTML = ICON.coin;
  $("legend").innerHTML = [["player", "You"], ["coin", "Coin +10"], ["scroll", "Clue +5"], ["key", "Key +20"],
    ["chest", "Chest"], ["rock", "Boulder"], ["trap", "Mud trap"]]
    .map((x) => "<div>" + ICON[x[0]] + "<span>" + x[1] + "</span></div>").join("");
  toMenu();
})();
