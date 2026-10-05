"use strict";
// 採用マーケティング・インテリジェンス フロントエンド（依存なし・ハッシュルーティング）

const $app = document.getElementById("app");
let META = null;

const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const num = (v, d = 0) => (v === null || v === undefined ? "—" : Number(v).toLocaleString("ja-JP", { maximumFractionDigits: d, minimumFractionDigits: d }));
const pct = (v) => (v === null || v === undefined ? "—" : (v * 100).toFixed(1) + "%");
// 人数非公開（NULL）は 0 と区別して表示する（16章）
const headcount = (v) => (v === null || v === undefined ? '<span class="tag">非公開</span>' : num(v));
const grade = (g) => `<span class="grade grade-${esc(g)}">${esc(g)}</span>`;
const bar = (ratio, main = false) => `<div class="bar${main ? " main" : ""}"><span style="width:${Math.max(0, Math.min(1, ratio || 0)) * 100}%"></span></div>`;
const listed = (v) => (v === null || v === undefined ? '<span class="tag">不明</span>' : v ? '<span class="tag yes">掲載あり</span>' : '<span class="tag">掲載なし</span>');

async function api(path, opts) {
  // ブラウザ版デモ（scripts/build_static_demo.py）では事前計算したデータから応答する
  if (window.RMI_STATIC) return window.RMI_STATIC(path, opts);
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error(`${r.status} ${(await r.json().catch(() => ({}))).detail || r.statusText}`);
  return r.json();
}

function sourcesBlock(sources) {
  if (!sources || !sources.length) return "";
  return `<h2>出典（一次ソース）</h2><div class="table-wrap"><table>
    <tr><th>ID</th><th>情報源</th><th>対象年度</th><th>公開日</th><th>取得日</th><th>信頼度</th><th>URL</th></tr>
    ${sources.map((s) => `<tr><td><code>${esc(s.source_id)}</code></td><td>${esc(s.source_name)}</td><td>${esc(s.target_year ?? "—")}</td>
      <td>${esc(s.published_at ?? "—")}</td><td>${esc(s.retrieved_at ?? "—")}</td><td><span class="tag lvl">${esc(s.reliability ?? "—")}</span></td>
      <td><a href="${esc(s.url)}" target="_blank" rel="noopener">開く ↗</a></td></tr>`).join("")}
  </table></div>`;
}

function setNav(name) {
  document.querySelectorAll("[data-nav]").forEach((a) => a.classList.toggle("active", a.dataset.nav === name));
}

// ------------------------------------------------------------------ 9-1 重点大学・学部ランキング
async function viewRanking(params) {
  setNav("ranking");
  const qs = new URLSearchParams(params);
  const data = await api("/api/ranking?" + qs.toString());
  const f = data.filters;
  const opt = (arr, cur) => `<option value="">すべて</option>` + arr.map((v) => `<option ${v === cur ? "selected" : ""}>${esc(v)}</option>`).join("");
  const tname = esc(META.target.name);
  $app.innerHTML = `
    <h1>重点大学・学部ランキング</h1>
    <p class="muted">どの学生市場を見るべきか。攻略優先度は相対評価（上位20%=A／次30%=B／次30%=C／残り=D）。</p>
    <form class="filters" id="filters">
      <label>地域<select name="region">${opt(META.regions, f.region)}</select></label>
      <label>設置区分<select name="establishment">${opt(["国公立", "国立", "公立", "私立"], f.establishment)}</select></label>
      <label>文理<select name="field">${opt(META.fields, f.field)}</select></label>
      <label>学部名<input name="faculty" value="${esc(f.faculty || "")}" placeholder="例：商学部"></label>
      <label>最小卒業者数<input name="min_graduates" type="number" min="0" step="100" value="${esc(f.min_graduates || "")}"></label>
      <label>競合企業が就職先にある<select name="competitor"><option value="">指定なし</option>
        ${META.competitor_options.map((c) => `<option value="${esc(c.company_id)}" ${c.company_id === f.competitor ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select></label>
      <label>${tname} 就職実績<select name="target_listed">
        <option value="">すべて</option><option value="yes" ${f.target_listed === "yes" ? "selected" : ""}>掲載あり</option>
        <option value="no" ${f.target_listed === "no" ? "selected" : ""}>掲載なし</option></select></label>
      <button type="submit">絞り込む</button><a class="btn ghost" href="#/">クリア</a>
    </form>
    <p class="small muted">${data.rows.length} 件</p>
    <div class="table-wrap"><table>
      <tr><th>#</th><th>大学</th><th>学部</th><th>優先度</th><th class="num">スコア</th><th class="num">Market Fit</th>
        <th class="num">市場規模<br><span class="small muted">卒業者</span></th><th>${tname}</th><th class="num">自社親和性</th>
        <th class="num">競合強度</th><th class="num">未開拓余地</th><th>公開情報<br>信頼度</th><th>推奨アクション</th></tr>
      ${data.rows.map((r) => `<tr class="clickable" data-href="#/faculty/${esc(r.faculty_id)}">
        <td class="num">${r.rank}</td><td style="white-space:nowrap">${esc(r.university)}<div class="small muted">${esc(r.region)}・${esc(r.establishment)}</div></td>
        <td>${esc(r.faculty)}<div class="small muted">${esc(r.field || "")}</div></td>
        <td>${grade(r.grade)}</td><td class="num"><b>${num(r.score, 1)}</b></td><td class="num">${num(r.market_fit, 0)}</td>
        <td class="num">${num(r.graduates)}</td><td>${listed(r.target_listed)}</td>
        <td class="num">${num(r.components.affinity * 100, 0)}</td>
        <td class="num">${r.competition_strength === null ? "—" : num(r.competition_strength, 0)}</td>
        <td class="num">${r.missing.includes("untapped") ? "—" : num(r.components.untapped * 100, 0)}</td>
        <td><span class="tag lvl">${esc(r.disclosure_level)}</span></td>
        <td class="small">${esc(r.recommended_action)}</td></tr>`).join("")}
    </table></div>
    <h2>スコアの考え方</h2>
    <div class="grid g2">
      <div class="card"><h3>攻略優先度（Recruitment Opportunity Score・100点）</h3>
        ${META.weights.opportunity.map((w) => `<div class="barrow"><span>${esc(w.label)}</span>${bar(w.weight / 20)}<span class="v">${w.weight}点</span></div>`).join("")}
        <p class="small muted">欠損した指標は 0 ではなく中立値で補完し、欠損として明示します。</p></div>
      <div class="card"><h3>採用競合スコア（Recruiting Competition Score）</h3>
        ${META.weights.competition.map((w) => `<div class="barrow"><span>${esc(w.label)}</span>${bar(w.weight / 0.3)}<span class="v">${(w.weight * 100).toFixed(0)}%</span></div>`).join("")}
        <p class="small muted">事業競合ではなく「同じ学生市場に出現する企業」を競合とみなします。</p></div>
    </div>`;
  document.getElementById("filters").addEventListener("submit", (e) => {
    e.preventDefault();
    const p = new URLSearchParams();
    for (const [k, v] of new FormData(e.target)) if (v) p.set(k, v);
    location.hash = "#/?" + p.toString();
  });
}

// ------------------------------------------------------------------ 10 大学・学部詳細
async function viewFaculty(fid) {
  setNav("");
  const d = await api(`/api/faculties/${encodeURIComponent(fid)}`);
  const o = d.outcomes[d.outcomes.length - 1] || {};
  const opp = d.opportunity;
  const years = Object.keys(d.industries_by_year);
  const latestInd = years.length ? d.industries_by_year[years[years.length - 1]] : [];
  const maxRatio = Math.max(0.01, ...latestInd.map((r) => r.ratio || 0));
  const prevMap = years.length > 1 ? Object.fromEntries(d.industries_by_year[years[years.length - 2]].map((r) => [r.industry, r.ratio])) : {};
  const t = d.target;
  $app.innerHTML = `
    <div class="crumbs"><a href="#/">重点大学・学部</a> › ${esc(d.label)}</div>
    <div class="strategy-head"><h1>${esc(d.label)}</h1>${grade(opp.grade)}
      <span class="muted">攻略優先度 ${num(opp.score, 1)}点（${opp.rank}位）</span>
      <span class="tag lvl">情報取得レベル ${esc(d.university.disclosure_level)}</span>
      <a class="btn" href="#/strategy/${esc(fid)}">攻略提案を見る →</a></div>
    <div class="flow"><span>市場規模</span>→<span>就職先構成</span>→<span>競合企業</span>→<span>学生価値観</span>→<span>${esc(t.name)}との親和性</span>→<span>課題</span>→<span>攻略方法</span></div>

    <h2>基本情報</h2>
    <div class="grid g4">
      ${kpi("学生数", num(d.faculty.student_count), "名")}
      ${kpi("卒業者数", num(o.graduates), `名（${o.year ?? "—"}年度）`)}
      ${kpi("就職者数", num(o.employed), "名")}
      ${kpi("進学率", o.graduates ? pct(o.further_study / o.graduates) : "—")}
      ${kpi("就職率", o.employment_rate == null ? "—" : o.employment_rate + "%")}
      ${kpi("地域", esc(d.university.region), esc(d.university.establishment))}
    </div>
    ${d.outcomes.length > 1 ? `<h3>過年度推移</h3><div class="table-wrap"><table><tr><th>年度</th><th class="num">卒業者</th><th class="num">就職者</th><th class="num">進学者</th><th class="num">就職率</th><th>出典</th></tr>
      ${d.outcomes.map((r) => `<tr><td>${r.year}</td><td class="num">${num(r.graduates)}</td><td class="num">${num(r.employed)}</td><td class="num">${num(r.further_study)}</td><td class="num">${r.employment_rate ?? "—"}%</td><td class="src"><code>${esc(r.source_id)}</code></td></tr>`).join("")}</table></div>` : ""}

    <div class="grid g2">
      <div>
        <h2>就職先構成：業種${years.length ? `（${years[years.length - 1]}年度）` : ""}</h2>
        ${latestInd.length ? latestInd.map((r) => {
          const p = prevMap[r.industry];
          const dlt = p == null || r.ratio == null ? "" : ((r.ratio - p) * 100).toFixed(1);
          return `<div class="barrow"><span>${esc(r.industry)}</span>${bar(r.ratio / maxRatio, r.industry === META.target.industry)}<span class="v">${pct(r.ratio)}${dlt !== "" ? `<br><span class="small delta ${dlt >= 0 ? "up" : "down"}">${dlt >= 0 ? "+" : ""}${dlt}pt</span>` : ""}</span></div>`;
        }).join("") : `<p class="muted">業種別データは非公開または未取得です。</p>`}
      </div>
      <div>
        <h2>${esc(t.name)}との接点</h2>
        <div class="card">
          <p>就職先への掲載：${listed(t.listed)} ${t.listed ? `人数 ${headcount(t.count)}` : ""}</p>
          ${t.raw_names.length ? `<p class="small muted">原文表記：${t.raw_names.map(esc).join("／")}（分析用IDに統合）</p>` : ""}
          <h3>周辺企業（同業種：${esc(META.target.industry || "")}）</h3>
          ${t.neighbors.length ? `<ul class="tight">${t.neighbors.map((c) => `<li><a href="#/company/${esc(c.company_id)}?faculty=${esc(fid)}">${esc(c.name)}</a> ${headcount(c.count)}</li>`).join("")}</ul>` : `<p class="muted small">掲載なし</p>`}
          <h3>近接業種の構成比</h3>
          ${t.proximity.length ? t.proximity.map((r) => `<div class="barrow"><span>${esc(r.industry)}</span>${bar(r.ratio / maxRatio)}<span class="v">${pct(r.ratio)}</span></div>`).join("") : `<p class="muted small">業種データなし</p>`}
        </div>
      </div>
    </div>

    <h2>主な就職先${d.employment_year ? `（${d.employment_year}年度）` : ""}</h2>
    ${d.companies.length ? `<div class="table-wrap"><table><tr><th>企業</th><th>業界</th><th class="num">人数</th><th>原文表記</th><th>出典</th></tr>
      ${d.companies.map((c) => `<tr class="${c.company_id === t.company_id ? "" : "clickable"}" ${c.company_id === t.company_id ? "" : `data-href="#/company/${esc(c.company_id)}?faculty=${esc(fid)}"`}>
        <td>${c.company_id === t.company_id ? `<b>${esc(c.name)}</b>` : esc(c.name)}</td><td>${esc(c.industry || "")}</td><td class="num">${headcount(c.count)}</td>
        <td class="small muted">${c.raw_names.map(esc).join("／")}</td><td class="src"><code>${esc(c.source_id)}</code></td></tr>`).join("")}
      ${d.unresolved_companies.map((c) => `<tr><td>${esc(c.raw_name)} <span class="tag">未正規化</span></td><td>—</td><td class="num">${headcount(c.count)}</td><td></td><td class="src"><code>${esc(c.source_id)}</code></td></tr>`).join("")}
      </table></div>` : `<p class="muted">学部別の就職先企業は公開されていません（情報取得レベル ${esc(d.university.disclosure_level)}）。</p>`}

    <h2>採用競合企業 TOP10</h2>
    ${competitorTable(d.competitors, fid)}

    <h2>攻略優先度の内訳</h2>
    <div class="card">${META.weights.opportunity.map((w) => {
      const v = opp.components[w.key];
      const miss = opp.missing.includes(w.key);
      return `<div class="barrow"><span>${esc(w.label)}${miss ? ' <span class="tag">欠損</span>' : ""}</span>${bar(v)}<span class="v">${(v * w.weight).toFixed(1)} / ${w.weight}</span></div>`;
    }).join("")}
    <p class="small muted">推奨アクション：${esc(opp.recommended_action)}</p></div>
    ${sourcesBlock(d.sources)}`;
}

function kpi(label, value, unit = "") {
  return `<div class="card kpi"><div class="label">${esc(label)}</div><div class="value">${value}<small>${unit}</small></div></div>`;
}

function competitorTable(rows, fid) {
  if (!rows.length) return `<p class="muted">就職先データが無いため競合を算出できません。</p>`;
  return `<div class="table-wrap"><table>
    <tr><th>#</th><th>企業</th><th>業界</th>${fid ? '<th class="num">学部内人数</th>' : ""}<th class="num">同一市場出現回数<br><span class="small muted">自社掲載学部での同時出現</span></th>
      <th class="num">出現大学数</th><th class="num">ONE CAREER<br>お気に入り</th><th class="num">体験談数<br><span class="small muted">選考/インターン</span></th><th class="num">人気順位</th><th class="num">競合Score</th></tr>
    ${rows.map((c, i) => `<tr class="clickable" data-href="#/company/${esc(c.company_id)}${fid ? `?faculty=${esc(fid)}` : ""}">
      <td class="num">${i + 1}</td><td>${esc(c.name)}</td><td>${esc(c.industry || "")}</td>${fid ? `<td class="num">${headcount(c.count_in_faculty)}</td>` : ""}
      <td class="num">${c.cooccurrence_count}</td><td class="num">${c.university_count}</td><td class="num">${num(c.favorites)}</td>
      <td class="num">${num(c.selection_reviews)} / ${num(c.intern_reviews)}</td><td class="num">${c.popularity_rank ? num(c.popularity_rank) + "位" : "—"}</td>
      <td class="num"><b>${num(c.score, 1)}</b>${bar(c.score / 100, i === 0)}</td></tr>`).join("")}
  </table></div><p class="small muted">体験談数は応募者数ではありません。学生の関心度シグナルとしてのみ使用します。</p>`;
}

// ------------------------------------------------------------------ 11 競合企業詳細
async function viewCompany(cid, params) {
  setNav("");
  const fid = params.get("faculty");
  const d = await api(`/api/companies/${encodeURIComponent(cid)}${fid ? `?faculty_id=${encodeURIComponent(fid)}` : ""}`);
  const c = d.company, comp = d.competition, tname = esc(d.target.name);
  const themes = Object.keys({ ...d.theme_mentions, ...d.target_theme_mentions });
  const maxT = Math.max(1, ...themes.map((t) => Math.max(d.theme_mentions[t] || 0, d.target_theme_mentions[t] || 0)));
  const dist = (obj) => Object.entries(obj).sort((a, b) => b[1] - a[1]).map(([k, v]) => `<span class="tag">${esc(k)} ${v}</span>`).join(" ");
  $app.innerHTML = `
    <div class="crumbs"><a href="#/">重点大学・学部</a>${fid ? ` › <a href="#/faculty/${esc(fid)}">学部詳細</a>` : ""} › ${esc(c.name)}</div>
    <h1>${esc(c.name)}</h1>
    <p class="muted">${esc(c.industry || "")}　｜　なぜ ${tname} と採用市場で競合するのか</p>
    <div class="grid g4">
      ${kpi("競合Score", num(comp.score, 1), fid ? "（この学部）" : "（全体）")}
      ${kpi(`${tname}と重なる学部`, d.overlap_faculties.length, "学部")}
      ${kpi("出現大学数", d.appearance.universities, "大学")}
      ${kpi("出現学部数", d.appearance.faculties, "学部")}
      ${kpi("採用人数（公開値）", num(c.hiring_count), "名")}
      ${kpi("初任給（公開値）", c.starting_salary ? num(c.starting_salary) : "—", c.starting_salary ? "円" : "")}
    </div>
    <div class="grid g2">
      <div><h2>競合シグナルの内訳</h2><div class="card">
        ${comp.breakdown.map((b) => `<div class="barrow"><span>${esc(b.label)}</span>${bar(b.value)}<span class="v">+${b.contribution}</span></div>`).join("")}
        <p class="small muted">値は 0〜1 に正規化。右端は Score への寄与点。</p></div></div>
      <div><h2>出現分布</h2><div class="card">
        <h3>地域</h3><p>${dist(d.appearance.regions) || "—"}</p>
        <h3>文理</h3><p>${dist(d.appearance.fields) || "—"}</p>
        <h3>${tname}と重なる大学</h3><p class="small">${d.overlap_universities.map(esc).join("、") || "—"}</p></div></div>
    </div>

    <h2>${tname} vs ${esc(c.name)}</h2>
    <div class="table-wrap"><table>
      <tr><th style="width:18%">比較項目</th><th style="width:41%">${tname}</th><th>${esc(c.name)}</th></tr>
      ${d.signal_comparison.map((r) => `<tr><td>${esc(r.signal)}</td><td>${fmtSig(r.signal, r.target)}</td><td>${fmtSig(r.signal, r.competitor)}</td></tr>`).join("")}
      ${d.comparison.map((r) => `<tr><td>${esc(r.attribute)}</td><td>${esc(r.target ?? "—")}${r.target_source ? ` <span class="src"><code>${esc(r.target_source)}</code></span>` : ""}</td>
        <td>${esc(r.competitor ?? "—")}${r.competitor_source ? ` <span class="src"><code>${esc(r.competitor_source)}</code></span>` : ""}</td></tr>`).join("")}
    </table></div>

    <h2>体験談のテーマ別言及件数（ONE CAREER 等・本文は保存しない）</h2>
    <div class="card">${themes.map((t) => `<div class="barrow"><span>${esc(t)}</span><div>
      ${bar((d.target_theme_mentions[t] || 0) / maxT, true)}<div style="height:3px"></div>${bar((d.theme_mentions[t] || 0) / maxT)}</div>
      <span class="v small">${num(d.target_theme_mentions[t])}<br>${num(d.theme_mentions[t])}</span></div>`).join("") || "<p class='muted'>データなし</p>"}
      <p class="small muted">上段（濃）＝${tname}／下段＝${esc(c.name)}。件数は言及の多さであり評価の良し悪しではありません。</p></div>

    <h2>${tname}と重なる学部（${d.overlap_faculties.length}）</h2>
    ${d.overlap_faculties.length ? `<div class="table-wrap"><table><tr><th>大学・学部</th><th class="num">${esc(c.name)} 人数</th><th class="num">${tname} 人数</th></tr>
      ${d.overlap_faculties.map((r) => `<tr class="clickable" data-href="#/faculty/${esc(r.faculty_id)}"><td>${esc(r.label)}</td><td class="num">${headcount(r.count)}</td><td class="num">${headcount(r.target_count)}</td></tr>`).join("")}</table></div>` : `<p class="muted">重なる学部はありません。</p>`}
    ${sourcesBlock(d.sources)}`;
}

function fmtSig(label, v) {
  if (v === null || v === undefined) return "—";
  if (label.includes("順位") || label.includes("ランキング")) return num(v) + "位";
  if (label.includes("評価")) return num(v, 2);
  return num(v);
}

// ------------------------------------------------------------------ 12 学生インサイト
async function viewInsights(params) {
  setNav("insights");
  const seg = params.get("segment") || "全体";
  const d = await api(`/api/insights?segment=${encodeURIComponent(seg)}`);
  const metricBlock = (name, rows) => {
    const max = Math.max(1, ...rows.map((r) => r.value || 0));
    return `<div class="card"><h3>${esc(name)}（${d.year}年）</h3>${rows.map((r) => `<div class="barrow"><span>${esc(r.theme)}</span>${bar(r.value / max)}
      <span class="v">${num(r.value, 1)}${esc(r.unit || "")}${r.delta != null ? `<br><span class="small delta ${r.delta >= 0 ? "up" : "down"}">${r.delta >= 0 ? "+" : ""}${r.delta}pt</span>` : ""}</span></div>`).join("")}
      <p class="src">出典：<code>${esc(rows[0]?.source_id || "")}</code>　前年差は ${d.prev_year ?? "—"} 年比</p></div>`;
  };
  const maxM = Math.max(1, ...d.review.flatMap((r) => Object.values(r.mentions).map((v) => v || 0)));
  $app.innerHTML = `
    <h1>学生インサイト</h1>
    <p class="muted">公開調査・体験談メタデータから学生の価値観を整理。値はセグメント全体の一般的傾向で、個別学部の値ではありません。</p>
    <div class="actions">${["全体", "文系", "理系"].map((s) => `<a class="btn ${s === seg ? "" : "ghost"}" href="#/insights?segment=${encodeURIComponent(s)}">${s}</a>`).join("")}</div>
    <div class="grid g2" style="margin-top:12px">${Object.entries(d.metrics).sort(([a], [b]) => (a.startsWith("企業選択") ? -1 : b.startsWith("企業選択") ? 1 : 0)).map(([m, rows]) => metricBlock(m, rows)).join("")}</div>

    <h2>体験談テーマ別の言及件数：${esc(META.target.name)} と主要競合</h2>
    <div class="table-wrap"><table><tr><th>企業</th>${d.review_themes.map((t) => `<th class="num">${esc(t)}</th>`).join("")}</tr>
      ${d.review.map((r, i) => `<tr class="${i ? "clickable" : ""}" ${i ? `data-href="#/company/${esc(r.company_id)}"` : ""}><td>${i ? "" : "<b>"}${esc(r.name)}${i ? "" : "</b>"}</td>
        ${d.review_themes.map((t) => `<td class="num">${num(r.mentions[t])}${bar((r.mentions[t] || 0) / maxM, !i)}</td>`).join("")}</tr>`).join("")}
    </table></div>
    <p class="small muted">個別投稿を学生全体の傾向として一般化しないでください。</p>

    <h2>定性コメントのテーマ分類（AI）</h2>
    <div class="card">
      <p class="small muted">1行に1件。説明会アンケート等の自由記述を貼り付けると、テーマに分類します（本文はサーバーに保存されません）。</p>
      <textarea id="clsIn">全国転勤が気になる
将来どういうキャリアになるかわからない
初任給が他社より低いのが気になる
若手から店長を任されるのは魅力</textarea>
      <div class="actions"><button id="clsBtn">分類する</button></div>
      <div id="clsOut"></div>
    </div>
    ${sourcesBlock(d.sources)}`;
  document.getElementById("clsBtn").onclick = async () => {
    const out = document.getElementById("clsOut");
    out.innerHTML = '<p class="muted">分類中…</p>';
    const texts = document.getElementById("clsIn").value.split("\n").map((s) => s.trim()).filter(Boolean);
    try {
      const r = await api("/api/classify", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ texts }) });
      const counts = {};
      r.results.forEach((x) => x.themes.forEach((t) => (counts[t] = (counts[t] || 0) + 1)));
      out.innerHTML = `<p class="small muted">エンジン：${r.engine === "claude" ? "Claude" : "キーワード辞書（AI 未接続）"}</p>
        <table><tr><th>コメント</th><th>テーマ</th></tr>${r.results.map((x) => `<tr><td>${esc(x.text)}</td><td>${x.themes.map((t) => `<span class="tag yes">${esc(t)}</span>`).join(" ")}</td></tr>`).join("")}</table>
        <h3>テーマ集計</h3>${Object.entries(counts).sort((a, b) => b[1] - a[1]).map(([t, n]) => `<span class="tag">${esc(t)} ${n}</span>`).join(" ")}`;
    } catch (e) { out.innerHTML = `<p>エラー：${esc(e.message)}</p>`; }
  };
}

// ------------------------------------------------------------------ 13 攻略提案
async function viewStrategy(fid, params) {
  setNav("");
  const useAi = params.get("ai") !== "0";
  $app.innerHTML = `<p class="muted">攻略仮説を生成中…（AI 使用時は数十秒かかる場合があります）</p>`;
  const d = await api(`/api/strategy/${encodeURIComponent(fid)}?use_ai=${useAi}`);
  const r = d.result, opp = d.opportunity;
  const list = (arr) => `<ul class="tight">${(arr || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`;
  $app.innerHTML = `
    <div class="crumbs"><a href="#/">重点大学・学部</a> › <a href="#/faculty/${esc(fid)}">${esc(d.label)}</a> › 攻略提案</div>
    <div class="strategy-head"><h1>${esc(d.label)}</h1><span>攻略優先度</span>${grade(opp.grade)}
      <span class="muted">${num(opp.score, 1)}点・${opp.rank}位</span></div>
    <p class="small muted">生成エンジン：${d.engine === "claude" ? `Claude（${esc(d.model)}）` : "ルールベース（AI 未接続または失敗時のフォールバック）"}
      ${d.engine === "claude" ? `｜ <a href="#/strategy/${esc(fid)}?ai=0">ルールベースと比較</a>` : useAi ? "" : `｜ <a href="#/strategy/${esc(fid)}">AI で生成</a>`}</p>
    <div class="callout"><b>${esc(r.priority_comment)}</b><br>${esc(r.market_summary)}</div>
    <div class="grid g2">
      <div class="card"><h3>市場の特徴</h3>${list(r.market_characteristics)}</div>
      <div class="card"><h3>採用競合</h3><p>${esc(r.competitor_view)}</p></div>
      <div class="card"><h3>学生価値観（一般的傾向）</h3><p>${esc(r.student_values)}</p></div>
      <div class="card"><h3>${esc(META.target.name)}との親和性</h3><p>${esc(r.target_affinity)}</p></div>
    </div>
    <h2>課題</h2>${list(r.issues)}
    <h2>推奨訴求（仮説）</h2>${list(r.appeal_hypotheses)}
    <h2>推奨施策</h2>${list(r.actions)}
    <h2>検証方法</h2>${list(r.validation)}
    <h2>根拠</h2>
    <div class="table-wrap"><table><tr><th>主張</th><th>出典</th></tr>
      ${(r.evidence || []).map((e) => `<tr><td class="ev">${esc(e.claim)}</td><td class="ev">${e.source_ids.map((s) => {
        const src = d.context.sources.find((x) => x.source_id === s);
        return src ? `<a href="${esc(src.url)}" target="_blank" rel="noopener"><code>${esc(s)}</code></a>` : `<code>${esc(s)}</code>`;
      }).join(" ")}</td></tr>`).join("")}</table></div>
    <h2>注意事項</h2>${list(r.caveats)}
    <p class="small muted">AI は公開データから仮説を作る役割です。応募人数・併願率・辞退率などの推定は行いません。</p>`;
}

// ------------------------------------------------------------------ データソース
async function viewSources() {
  setNav("sources");
  const d = await api("/api/sources");
  $app.innerHTML = `
    <h1>データソース・品質</h1>
    <p class="muted">すべてのデータは出典（Source_Log）に紐づきます。データ対象年度・公開日・取得日を分離して保持します。</p>
    <h2>情報取得レベル</h2>
    <p>${["A", "B", "C"].map((l) => `<span class="tag lvl">${l}：${d.disclosure_levels[l] || 0} 大学</span>`).join(" ")}
      <span class="small muted">A=学部×企業まで ／ B=学部×業種または一部企業 ／ C=詳細非公開・学内限定</span></p>
    <div class="table-wrap"><table><tr><th>大学</th><th>地域</th><th>設置</th><th>レベル</th></tr>
      ${d.universities.map((u) => `<tr><td>${esc(u.name)}</td><td>${esc(u.region)}</td><td>${esc(u.establishment)}</td><td><span class="tag lvl">${esc(u.disclosure_level)}</span></td></tr>`).join("")}</table></div>
    <h2>未正規化の企業名（企業マスタ・別名辞書への追加候補）</h2>
    ${d.unresolved_company_names.length ? `<ul class="tight">${d.unresolved_company_names.map((u) => `<li>${esc(u.raw_name)} <span class="muted small">${u.rows} 行</span></li>`).join("")}</ul>` : "<p class='muted'>なし</p>"}
    ${sourcesBlock(d.sources)}`;
}

// ------------------------------------------------------------------ 検索
function setupSearch() {
  const input = document.getElementById("searchInput"), box = document.getElementById("searchResults");
  let timer;
  const run = async () => {
    const q = input.value.trim();
    if (!q) { box.hidden = true; return; }
    const res = await api(`/api/search?q=${encodeURIComponent(q)}`);
    box.innerHTML = res.length ? res.map((u) => `<div class="uni"><b>${esc(u.name)}</b><span class="small muted">${esc(u.region)}・${esc(u.establishment)}・レベル${esc(u.disclosure_level)}</span>
      <div class="chips">${u.faculties.map((f) => `<a href="#/faculty/${esc(f.faculty_id)}">${esc(f.faculty)}</a>`).join("")}</div></div>`).join("")
      : `<div class="uni muted">該当なし</div>`;
    box.hidden = false;
  };
  input.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(run, 150); });
  input.addEventListener("focus", run);
  document.getElementById("searchForm").addEventListener("submit", (e) => { e.preventDefault(); run(); });
  document.addEventListener("click", (e) => { if (!e.target.closest(".search")) box.hidden = true; });
  box.addEventListener("click", (e) => { if (e.target.closest("a")) { box.hidden = true; input.value = ""; } });
}

// ------------------------------------------------------------------ router
async function route() {
  const [path, query] = location.hash.replace(/^#/, "").split("?");
  const params = new URLSearchParams(query || "");
  const parts = (path || "/").split("/").filter(Boolean);
  try {
    if (!parts.length) await viewRanking(Object.fromEntries(params));
    else if (parts[0] === "faculty") await viewFaculty(decodeURIComponent(parts[1]));
    else if (parts[0] === "company") await viewCompany(decodeURIComponent(parts[1]), params);
    else if (parts[0] === "insights") await viewInsights(params);
    else if (parts[0] === "strategy") await viewStrategy(decodeURIComponent(parts[1]), params);
    else if (parts[0] === "sources") await viewSources();
    else $app.innerHTML = "<p>ページが見つかりません。</p>";
  } catch (e) {
    $app.innerHTML = `<p>読み込みに失敗しました：${esc(e.message)}</p>`;
  }
  window.scrollTo(0, 0);
}

$app.addEventListener("click", (e) => {
  if (e.target.closest("a")) return;
  const tr = e.target.closest("tr[data-href]");
  if (tr) location.hash = tr.dataset.href;
});

(async function init() {
  META = await api("/api/meta");
  document.getElementById("demoBanner").hidden = !META.demo_data;
  setupSearch();
  window.addEventListener("hashchange", route);
  route();
})();
