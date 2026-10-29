/* GitHub 每日精品 —— 页面逻辑
 * 数据来自 data.js（window.DAILY_DATA），file:// 或局域网访问均可
 * 新增：换一批（本地从候选池重挑，不请求网络）、变现工作流展示、手机适配
 */
(function () {
  "use strict";

  var DATA = window.DAILY_DATA;
  if (!DATA || !DATA.days || !DATA.days.length) {
    document.getElementById("cards").innerHTML =
      '<p class="empty">没有找到数据文件 data.js，请先双击「更新内容.cmd」生成。</p>';
    return;
  }

  var CATS = ["全部", "AI前沿", "AI变现", "工作提效", "量化交易", "学习资源", "Awesome精选"];
  var QUOTA = { "AI前沿": 3, "AI变现": 2, "工作提效": 2, "量化交易": 1, "学习资源": 1, "Awesome精选": 1 };
  var state = { dayIdx: 0, cat: "全部", q: "" };

  var LS = { fav: "gd_fav_v1", learned: "gd_learned_v1", theme: "gd_theme_v1", custom: "gd_custom_v1" };

  function readLS(k, f) { try { var r = localStorage.getItem(k); return r ? JSON.parse(r) : f; } catch (e) { return f; } }
  function writeLS(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }

  /* 用日期+种子做确定性随机（同一批刷新结果可复现） */
  function hashSeed(str) {
    var h = 2166136261;
    for (var i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); }
    return h >>> 0;
  }
  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function shuffle(arr, rng) {
    for (var i = arr.length - 1; i > 0; i--) {
      var j = Math.floor(rng() * (i + 1));
      var t = arr[i]; arr[i] = arr[j]; arr[j] = t;
    }
    return arr;
  }

  /* 客户端从候选池重挑 10 个（与 build_daily.py 同一套配额规则） */
  function pickFromPool(seed) {
    var pool = DATA.pool || [];
    if (!pool.length) return null;
    var rng = mulberry32(hashSeed(seed));
    var byCat = {};
    pool.forEach(function (x) { (byCat[x.cat] = byCat[x.cat] || []).push(x); });
    var picked = [], used = {};
    Object.keys(QUOTA).forEach(function (cat) {
      var members = (byCat[cat] || []).filter(function (x) { return !used[x.fullName]; });
      shuffle(members.slice(), rng).forEach(function () {});
      var curated = members.filter(function (x) { return x.curated; });
      var other = members.filter(function (x) { return !x.curated; });
      var ordered = shuffle(curated, rng).concat(shuffle(other, rng));
      ordered.slice(0, QUOTA[cat]).forEach(function (x) { picked.push(x); used[x.fullName] = 1; });
    });
    if (picked.length < 10) {
      var rest = shuffle(pool.filter(function (x) { return !used[x.fullName]; }), rng);
      rest.slice(0, 10 - picked.length).forEach(function (x) { picked.push(x); used[x.fullName] = 1; });
    }
    picked.sort(function (a, b) { return b.stars - a.stars; });
    return picked.slice(0, 10);
  }

  var favs = readLS(LS.fav, []);
  var learned = readLS(LS.learned, {});
  var custom = readLS(LS.custom, {}); // {"2026-10-29": ["owner/name", ...]}

  function fmtStars(n) { return n >= 1000 ? (n / 1000).toFixed(n >= 10000 ? 0 : 1) + "k" : String(n); }
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function poolByName() {
    var m = {};
    (DATA.pool || []).forEach(function (x) { m[x.fullName] = x; });
    return m;
  }

  /* 当前展示的 10 个：优先用「换一批」保存的自选，否则用当日推荐 */
  function currentItems() {
    var day = DATA.days[state.dayIdx];
    if (state.dayIdx === 0) {
      var names = custom[day.date];
      if (names && names.length) {
        var byName = poolByName();
        var items = names.map(function (n) { return byName[n]; }).filter(Boolean);
        if (items.length) return items;
      }
    }
    return day.items;
  }

  function dayLearned(d) { if (!learned[d.date]) learned[d.date] = {}; return learned[d.date]; }

  /* ---------- 顶栏 ---------- */
  function renderHead() {
    var d = DATA.days[state.dayIdx];
    var it = currentItems();
    document.getElementById("issueLine").textContent =
      d.date + " 星期" + d.weekday + " · 第 " + d.issue + " 期";
    var best = it.reduce(function (a, b) { return a.stars > b.stars ? a : b; });
    document.getElementById("stats").innerHTML =
      "<span><b>" + it.length + "</b>个项目</span>" +
      "<span>最高 <b>★" + fmtStars(best.stars) + "</b></span>" +
      "<span>候选池 <b>" + (DATA.pool ? DATA.pool.length : DATA.totalCandidates) + "</b></span>" +
      "<span>门槛 <b>★" + fmtStars(DATA.starsThreshold) + "+</b></span>";
    document.getElementById("genLine").textContent = "最近更新：" + DATA.generatedAt;
  }

  /* ---------- 日期选择 ---------- */
  function renderDates() {
    var sel = document.getElementById("dateSel");
    sel.innerHTML = "";
    DATA.days.forEach(function (d, i) {
      var opt = document.createElement("option");
      opt.value = i;
      opt.textContent = (i === 0 ? "今日 · " : "") + d.date + "（第" + d.issue + "期）";
      sel.appendChild(opt);
    });
    sel.value = state.dayIdx;
    sel.onchange = function () {
      state.dayIdx = parseInt(sel.value, 10) || 0;
      renderHead(); renderChips(); renderCards(); renderProgress(); renderBanner();
    };
  }

  /* ---------- 分类筛选 ---------- */
  function renderChips() {
    var box = document.getElementById("catChips");
    box.innerHTML = "";
    CATS.forEach(function (c) {
      var b = document.createElement("button");
      b.className = "chip" + (state.cat === c ? " active" : "");
      b.textContent = c;
      b.onclick = function () { state.cat = c; renderChips(); renderCards(); };
      box.appendChild(b);
    });
  }

  /* ---------- 进度 ---------- */
  function renderProgress() {
    var d = DATA.days[state.dayIdx], items = currentItems();
    var done = dayLearned(d);
    var n = items.filter(function (x) { return done[x.fullName]; }).length;
    document.getElementById("progressText").textContent =
      "今日学习进度：" + n + " / " + items.length + (n === items.length ? "  🎉 全部完成！" : "");
    document.getElementById("progressFill").style.width = (items.length ? (n / items.length) * 100 : 0) + "%";
  }

  /* ---------- 换一批提示条 ---------- */
  function renderBanner() {
    var bar = document.getElementById("customBar");
    var today = DATA.days[0].date;
    var isCustom = !!(custom[today] && custom[today].length);
    if (state.dayIdx === 0 && isCustom) {
      bar.innerHTML = '<span>🔀 这是你换过的一批（可点「恢复今日推荐」还原）</span>' +
        '<button class="btn" id="restoreBtn">恢复今日推荐</button>';
      document.getElementById("restoreBtn").onclick = function () {
        delete custom[today];
        writeLS(LS.custom, custom);
        renderHead(); renderCards(); renderProgress(); renderBanner();
      };
      bar.hidden = false;
    } else {
      bar.hidden = true;
    }
  }

  /* ---------- 卡片 ---------- */
  function renderCards() {
    var box = document.getElementById("cards");
    var items = currentItems();
    var done = dayLearned(DATA.days[state.dayIdx]);
    var q = state.q.trim().toLowerCase();

    var filtered = items.filter(function (x) {
      if (state.cat !== "全部" && x.cat !== state.cat) return false;
      if (!q) return true;
      var hay = [x.fullName, x.description, x.money, x.buyer, x.price, (x.tags || []).join(" "), x.cat]
        .join(" ").toLowerCase();
      return hay.indexOf(q) >= 0;
    });

    box.innerHTML = "";
    document.getElementById("empty").hidden = filtered.length > 0;

    filtered.forEach(function (x, i) {
      var fav = favs.indexOf(x.fullName) >= 0;
      var isDone = !!done[x.fullName];
      var card = document.createElement("article");
      card.className = "card" + (isDone ? " done" : "");

      var wf = (x.workflow || []).map(function (s, k) {
        return '<li><b>' + (k + 1) + '.</b> ' + esc(s) + "</li>";
      }).join("");

      card.innerHTML =
        '<div class="cardHead">' +
          '<span class="rank">#' + (i + 1) + "</span>" +
          '<span class="cat cat-' + esc(x.cat) + '">' + esc(x.cat) + "</span>" +
          (x.awesome ? '<span class="awe">★ Awesome</span>' : "") +
          '<span class="stars">★ ' + x.stars.toLocaleString() + "</span>" +
        "</div>" +
        '<h2 class="title"><a href="' + esc(x.url) + '" target="_blank" rel="noopener noreferrer">' +
          esc(x.name) + '</a> <span class="owner">' + esc(x.owner) + "</span></h2>" +
        '<div class="desc">' + esc(x.description || "（无描述）") + "</div>" +
        '<div class="money"><b>💰 变现点：</b>' + esc(x.money) + "</div>" +
        '<div class="infoRow">' +
          (x.buyer && x.buyer !== "—" ? '<span>🎯 卖给：' + esc(x.buyer) + "</span>" : "") +
          (x.price && x.price !== "—" ? '<span>💵 报价：' + esc(x.price) + "</span>" : "") +
          (x.cycle && x.cycle !== "—" ? '<span>⏱ 周期：' + esc(x.cycle) + "</span>" : "") +
        "</div>" +
        (wf ? '<details class="wf"><summary>📋 变现工作流（' + (x.workflow.length) + " 步，点开看详情）</summary><ol>" + wf + "</ol></details>" : "") +
        '<div class="tags">' +
          (x.tags || []).map(function (t) { return '<span class="tag">' + esc(t) + "</span>"; }).join("") +
        "</div>" +
        '<div class="cardFoot">' +
          '<span class="diff b' + x.diff + '">难度 ' + ["", "★ 易上手", "★★ 需基础", "★★★ 硬核"][x.diff] + "</span>" +
          '<label class="check"><input type="checkbox"' + (isDone ? " checked" : "") +
            ' data-learn="' + esc(x.fullName) + '"> 已学</label>' +
          '<button class="btn' + (fav ? " on" : "") + '" data-fav="' + esc(x.fullName) + '">' +
            (fav ? "★ 已藏" : "☆ 收藏") + "</button>" +
          '<a class="btn primary" href="' + esc(x.url) + '" target="_blank" rel="noopener noreferrer">打开 →</a>' +
        "</div>";
      box.appendChild(card);
    });

    box.querySelectorAll("[data-learn]").forEach(function (cb) {
      cb.onchange = function () {
        var name = cb.getAttribute("data-learn");
        var store = dayLearned(DATA.days[state.dayIdx]);
        if (cb.checked) store[name] = true; else delete store[name];
        writeLS(LS.learned, learned);
        renderProgress(); renderCards();
      };
    });

    box.querySelectorAll("[data-fav]").forEach(function (btn) {
      btn.onclick = function () {
        var name = btn.getAttribute("data-fav");
        var idx = favs.indexOf(name);
        if (idx >= 0) { favs.splice(idx, 1); btn.classList.remove("on"); btn.textContent = "☆ 收藏"; }
        else { favs.push(name); btn.classList.add("on"); btn.textContent = "★ 已藏"; }
        writeLS(LS.fav, favs);
        document.getElementById("favCount").textContent = favs.length;
        renderFavPanel();
      };
    });
  }

  /* ---------- 收藏面板 ---------- */
  function renderFavPanel() {
    var all = poolByName();
    DATA.days.forEach(function (d) { d.items.forEach(function (x) { all[x.fullName] = x; }); });
    var list = document.getElementById("favList");
    var mine = favs.map(function (n) { return all[n]; }).filter(Boolean);
    if (!mine.length) {
      list.innerHTML = '<div class="favEmpty">还没有收藏，点卡片上的「☆ 收藏」试试。</div>';
      return;
    }
    list.innerHTML = mine.map(function (x) {
      return '<div class="favItem"><a href="' + esc(x.url) + '" target="_blank" rel="noopener noreferrer">' +
        esc(x.fullName) + '</a><button class="btn" data-unfav="' + esc(x.fullName) + '">移除</button></div>';
    }).join("");
    list.querySelectorAll("[data-unfav]").forEach(function (b) {
      b.onclick = function () {
        var n = b.getAttribute("data-unfav");
        favs = favs.filter(function (v) { return v !== n; });
        writeLS(LS.fav, favs);
        document.getElementById("favCount").textContent = favs.length;
        renderFavPanel(); renderCards();
      };
    });
  }

  /* ---------- 主题 ---------- */
  function applyTheme(t) {
    document.documentElement.classList.toggle("light", t === "light");
    writeLS(LS.theme, t);
  }

  /* ---------- 初始化 ---------- */
  document.getElementById("favCount").textContent = favs.length;
  renderHead(); renderDates(); renderChips(); renderProgress(); renderCards(); renderFavPanel(); renderBanner();

  document.getElementById("search").addEventListener("input", function (e) {
    state.q = e.target.value;
    renderCards();
  });

  /* 换一批：本地从候选池重挑，不联网 */
  document.getElementById("refreshBtn").onclick = function () {
    if (state.dayIdx !== 0) {
      alert("「换一批」只对今日有效，请先切回今日。");
      return;
    }
    var seed = String(Date.now());
    var picks = pickFromPool(seed);
    if (!picks || !picks.length) {
      alert("候选池为空，请先运行「更新内容.cmd」获取数据。");
      return;
    }
    var today = DATA.days[0].date;
    custom[today] = picks.map(function (x) { return x.fullName; });
    writeLS(LS.custom, custom);
    state.cat = "全部"; state.q = "";
    document.getElementById("search").value = "";
    renderChips(); renderCards(); renderProgress(); renderBanner();
  };

  document.getElementById("favBtn").onclick = function () {
    var p = document.getElementById("favPanel");
    p.hidden = !p.hidden;
    if (!p.hidden) renderFavPanel();
  };
  document.getElementById("closeFav").onclick = function () {
    document.getElementById("favPanel").hidden = true;
  };

  document.getElementById("themeBtn").onclick = function () {
    applyTheme(readLS(LS.theme, "dark") === "dark" ? "light" : "dark");
  };
  applyTheme(readLS(LS.theme, "dark"));
})();
