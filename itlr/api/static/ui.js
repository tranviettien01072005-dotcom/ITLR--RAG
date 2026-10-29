
// Restricted Markdown: escape HTML first; allow only emphasis, code and line breaks.
const esc = t => String(t ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const md = t => esc(t).replace(/`([^`\n]+)`/g, '<code>$1</code>').replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>');
const safeUrl = value => {
  try { const u = new URL(value); return ["https:", "http:"].includes(u.protocol) ? u.href : ""; }
  catch (_) { return ""; }
};
const api = (path, body) => fetch(path, {
  method: body ? "POST" : "GET",
  headers: {"Content-Type":"application/json"},
  body: body ? JSON.stringify(body) : undefined,
}).then(r => { if(!r.ok) throw new Error(r.status); return r.json(); });

/* ── Tabs ── */
document.querySelectorAll(".tabs button").forEach(b => b.onclick = () => {
  document.querySelectorAll(".tabs button").forEach(x => x.classList.remove("active"));
  document.querySelectorAll(".panel").forEach(x => x.classList.remove("active"));
  b.classList.add("active");
  document.getElementById(b.dataset.tab).classList.add("active");
  if (b.dataset.tab === "foryou" && !personasLoaded) initPersonas();
  if (b.dataset.tab === "chat" && !chatInited) initChat();
  if (b.dataset.tab === "roadmap" && !roadmapInited) initRoadmap();
});

/* ── Card render (dùng chung cho Tìm kiếm & Dành cho bạn) ── */
function cardNode(it, likeBtn=false) {
  const card = document.createElement("div"); card.className = "card";
  for (const [tag, cls, value] of [["span","badge",it.type],["h4","",it.title],
    ["p","cat",it.category],["p","desc",String(it.description || "").slice(0,140)],
    ["p","meta",`${it.instructor || ""} · ${it.platform || ""}`],
    ["p","score",it.score == null ? "" : `Độ tương đồng: ${it.score}%`]]) {
    const el = document.createElement(tag); el.className = cls; el.textContent = value || ""; card.append(el);
  }
  const url = safeUrl(it.link);
  if (url) { const a = document.createElement("a"); a.href = url; a.textContent = "Xem chi tiết →";
    a.target = "_blank"; a.rel = "noopener noreferrer"; card.append(a); }
  if (likeBtn && Number.isSafeInteger(it.item_id)) {
    const b = document.createElement("button"); b.textContent = "👍 Quan tâm";
    b.addEventListener("click", () => markInterested(it.item_id)); card.append(b);
  }
  return card;
}
function addRecs(log, recs) {
  const d = document.createElement("details"); d.className = "recs";
  const summary = document.createElement("summary"); summary.textContent = `📚 ${recs.length} tài nguyên liên quan`;
  const grid = document.createElement("div"); grid.className = "grid";
  grid.replaceChildren(...recs.slice(0,4).map(it => cardNode(it)));
  d.append(summary, grid); log.append(d);
}

/* ── Tìm kiếm ── */
async function doSearch() {
  const q = document.getElementById("q").value.trim();
  const note = document.getElementById("searchnote");
  const box = document.getElementById("searchresults");
  if (!q) { note.textContent = "Vui lòng nhập từ khóa tìm kiếm."; box.innerHTML=""; return; }
  note.textContent = "Đang tìm...";
  box.innerHTML = "";
  try {
    const data = await api("/api/search", {
      query: q,
      type: document.getElementById("qtype").value || null,
      min_pct: parseInt(document.getElementById("minpct").value),
    });
    note.textContent = data.corrected ? `🔎 Đang tìm theo: ${data.display} (${data.note || ""})` : "";
    if (!data.results.length) {
      box.textContent = `Không có kết quả phù hợp cho "${q}". Thử từ khóa khác / hạ ngưỡng.`;
      return;
    }
    box.replaceChildren(...data.results.slice(0,100).map(it => cardNode(it)));
  } catch(e) { note.textContent = "Lỗi tải kết quả: " + e.message; }
}

/* ── Dành cho bạn ── */
let personasLoaded = false;
let interested = new Set();
async function initPersonas() {
  const sel = document.getElementById("persona");
  try {
    const list = await api("/api/personas");
    sel.replaceChildren(...list.map(p => { const o = document.createElement("option"); o.value = p.uid;
      o.textContent = `Người dùng #${p.uid} · quan tâm ${p.label}`; return o; }));
    personasLoaded = true;
    loadForYou();
  } catch(e) { document.getElementById("fyhint").textContent = "Lỗi tải personas: " + e.message; }
}
function markInterested(id) { interested.add(id); loadForYou(); }
function clearInterested() { interested.clear(); loadForYou(); }
async function loadForYou() {
  const box = document.getElementById("fyresults");
  const hint = document.getElementById("fyhint");
  box.innerHTML = "";
  try {
    const data = await api("/api/for-you", {
      persona: parseInt(document.getElementById("persona").value),
      interested: [...interested],
    });
    hint.textContent = `✨ Gợi ý dành cho bạn — Collaborative Filtering (item-based). Đã chọn ${interested.size} mục "Quan tâm" trong phiên.`;
    box.replaceChildren(...data.recs.map(it => cardNode(it, true)));
  } catch(e) { hint.textContent = "Lỗi tải gợi ý: " + e.message; }
}

/* ── Chatbot ── */
let chatInited = false;
let chatHistory = [];   // [{role, content}]
async function initChat() {
  chatInited = true;
  const log = document.getElementById("chatlog");
  try {
    const s = await api("/api/suggested");
    const chips = s.prompts.map(p => { const b = document.createElement("button"); b.textContent = p; b.addEventListener("click", () => usePrompt(b)); return b; });
    log.innerHTML = `<div class="welcome">
        <h2>IT Learning Assistant</h2>
        <p>Trợ lý học tập CNTT — RAG + Gợi ý cá nhân hóa</p>
        <div class="prompts"></div>
      </div>`;
    log.querySelector(".prompts").replaceChildren(...chips);
  } catch(e) { log.textContent = "Lỗi khởi tạo chatbot: " + e.message; }
}
function usePrompt(btn) { document.getElementById("chatinput").value = btn.textContent; sendChat(); }

function appendMsg(role, html, recs) {
  // Xóa màn hình chào nếu còn
  const wel = document.querySelector("#chatlog .welcome"); if (wel) wel.remove();
  const log = document.getElementById("chatlog");
  const wrap = document.createElement("div");
  wrap.className = "msg " + role;
  wrap.innerHTML = `<div class="avatar">${role==="user"?"🧑":"🤖"}</div><div class="bubble">${html}</div>`;
  log.appendChild(wrap);
  if (recs && recs.length) {
    addRecs(log, recs);
  }
  window.scrollTo(0, document.body.scrollHeight);
}

async function sendChat() {
  const input = document.getElementById("chatinput");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  appendMsg("user", md(text));
  chatHistory.push({role:"user", content:text});

  const log = document.getElementById("chatlog");
  const wel = document.querySelector("#chatlog .welcome"); if (wel) wel.remove();
  const wrap = document.createElement("div");
  wrap.className = "msg assistant";
  // Gợi ý chờ: model chạy nội bộ (Ollama) có thể mất ~30-60s cho câu đầu — báo trước để
  // người dùng không tưởng là treo. Sẽ bị thay bằng nội dung ngay khi token đầu tới.
  wrap.innerHTML = `<div class="avatar">🤖</div><div class="bubble">`
    + `<span class="hint">⏳ Đang soạn câu trả lời… (mô hình chạy nội bộ, có thể mất ~30–60s)</span></div>`;
  log.appendChild(wrap);
  const bubble = wrap.querySelector(".bubble");
  window.scrollTo(0, document.body.scrollHeight);

  let acc = "", recs = [];
  try {
    // STREAMING (SSE): đọc dần thay vì chờ cả câu -> không "treo", vượt timeout proxy 30s.
    const resp = await fetch("/api/chat/stream", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ message: text, history: chatHistory.slice(-21,-1).map(m => ({...m, content: m.content.slice(0,4000)})) }),
    });
    if (!resp.ok || !resp.body) throw new Error(resp.status || "no-stream");
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      buf += decoder.decode(value, {stream:true});
      let idx;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        const line = buf.slice(0, idx).trim(); buf = buf.slice(idx + 2);
        if (!line.startsWith("data:")) continue;
        let obj; try { obj = JSON.parse(line.slice(5).trim()); } catch(_) { continue; }
        if (obj.type === "text") {
          acc += obj.text;
          bubble.innerHTML = md(acc);
          window.scrollTo(0, document.body.scrollHeight);
        } else if (obj.type === "meta" && obj.recommendations) {
          recs = obj.recommendations;
        }
      }
    }
    bubble.innerHTML = md(acc || "Xin lỗi, mình chưa tạo được câu trả lời. Bạn thử gửi lại nhé.");
    if (recs && recs.length) {
      addRecs(log, recs);
    }
    chatHistory.push({role:"assistant", content: acc});
    window.scrollTo(0, document.body.scrollHeight);
  } catch(e) {
    bubble.innerHTML = md("Xin lỗi, có lỗi khi xử lý: " + e.message + ". Bạn thử gửi lại giúp mình nhé.");
  }
}

/* ── Lộ trình (orbital timeline) ── */
let roadmapInited = false;
const ROADMAP = [
  { id:1, title:"Nền tảng máy tính", date:"Giai đoạn 1", level:"Cơ bản", icon:"cpu", energy:100, relatedIds:[2],
    content:"Kiến thức gốc: cách máy tính hoạt động, hệ điều hành, mạng cơ bản, dòng lệnh. Nền móng cho mọi hướng đi CNTT." },
  { id:2, title:"Lập trình", date:"Giai đoạn 2", level:"Cơ bản", icon:"code", energy:85, relatedIds:[1,3],
    content:"Thành thạo một ngôn ngữ (Python/JavaScript), tư duy giải quyết vấn đề, Git và viết code sạch." },
  { id:3, title:"Giải thuật & CTDL", date:"Giai đoạn 3", level:"Trung cấp", icon:"sigma", energy:70, relatedIds:[2,4],
    content:"Cấu trúc dữ liệu, độ phức tạp, các thuật toán cốt lõi — nền tảng để code hiệu quả và qua phỏng vấn." },
  { id:4, title:"Web & Backend", date:"Giai đoạn 4", level:"Trung cấp", icon:"globe", energy:60, relatedIds:[3,5],
    content:"HTTP, REST API, frontend/backend, framework. Xây dựng ứng dụng web hoàn chỉnh." },
  { id:5, title:"Cơ sở dữ liệu", date:"Giai đoạn 5", level:"Trung cấp", icon:"database", energy:50, relatedIds:[4,6],
    content:"SQL/NoSQL, thiết kế schema, tối ưu truy vấn — lưu trữ và quản lý dữ liệu cho ứng dụng thật." },
  { id:6, title:"AI/ML & Triển khai", date:"Giai đoạn 6", level:"Nâng cao", icon:"sparkles", energy:35, relatedIds:[5],
    content:"Machine learning, mô hình hóa, MLOps, đưa sản phẩm lên cloud/CI-CD. Hướng chuyên sâu & thực chiến." }
];
function goAskChat(text) {
  document.querySelector('.tabs button[data-tab="chat"]').click();
  setTimeout(function () {
    const inp = document.getElementById("chatinput");
    inp.value = text;
    sendChat();
  }, 60);
}
function initRoadmap() {
  roadmapInited = true;
  if (!window.initOrbitalTimeline) return;
  initOrbitalTimeline(document.getElementById("orbital"), ROADMAP, {
    onAsk: function (it) { goAskChat("Lộ trình học " + it.title + " từ cơ bản đến nâng cao"); }
  });
}

document.querySelector('[data-action="action-0"]').addEventListener("click", event => { doSearch() });
document.querySelector('[data-action="action-1"]').addEventListener("input", event => { document.getElementById("pctlbl").textContent=event.currentTarget.value });
document.querySelector('[data-action="action-2"]').addEventListener("click", event => { loadForYou() });
document.querySelector('[data-action="action-3"]').addEventListener("click", event => { clearInterested() });
document.querySelector('[data-action="action-4"]').addEventListener("keydown", event => { if(event.key==='Enter')sendChat() });
document.querySelector('[data-action="action-5"]').addEventListener("click", event => { sendChat() });
