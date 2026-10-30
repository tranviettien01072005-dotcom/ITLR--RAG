(function () {
  "use strict";
  function safeSourceUrl(value) {
    try {
      var url = new URL(value);
      return (url.protocol === "https:" || url.protocol === "http:") && !url.username && !url.password ? url.href : "";
    } catch (_) { return ""; }
  }
  async function consume(response, onEvent) {
    if (!response.ok || !response.body || !(response.headers.get("content-type") || "").includes("text/event-stream")) {
      throw new Error("Không mở được luồng trả lời. Hãy đăng nhập lại hoặc thử lại.");
    }
    var reader = response.body.getReader(), decoder = new TextDecoder("utf-8", { fatal: true }), buffer = "", finalized = false, ended = false;
    try {
      while (true) {
        var chunk = await reader.read();
        if (chunk.done) break;
        buffer += decoder.decode(chunk.value, { stream: true });
        var match;
        while ((match = /\r?\n\r?\n/.exec(buffer))) {
          if (match.index > 1200000) throw new Error("Stream event too large");
          var frame = buffer.slice(0, match.index);
          buffer = buffer.slice(match.index + match[0].length);
          var data = frame.split(/\r?\n/).filter(function (line) { return line.indexOf("data:") === 0; }).map(function (line) { return line.slice(5).trimStart(); }).join("\n");
          if (!data) continue;
          var event = JSON.parse(data);
          if (ended || (finalized && event.type !== "done")) throw new Error("Invalid stream sequence");
          if (event.type === "error") throw new Error(event.error || "Luồng trả lời gặp lỗi.");
          if (event.type === "final") finalized = true;
          if (event.type === "done") {
            if (!finalized) throw new Error("Missing final response");
            ended = true;
          }
          onEvent(event);
        }
        if (buffer.length > 1200000) throw new Error("Phản hồi quá lớn.");
      }
      buffer += decoder.decode();
      if (!finalized || !ended || buffer.trim()) throw new Error("Luồng trả lời bị gián đoạn. Hãy thử lại.");
    } finally {
      await reader.cancel().catch(function () {});
      reader.releaseLock();
    }
  }
  function sourcesInto(target, sources) {
    target.replaceChildren();
    if (!sources || !sources.length) return;
    var heading = document.createElement("h4");
    heading.textContent = "Nguồn đã truy xuất (" + sources.length + ")";
    target.appendChild(heading);
    sources.slice(0, 20).forEach(function (source) {
      if (!Number.isSafeInteger(source.item_id) || source.item_id <= 0) return;
      var card = document.createElement("article"); card.className = "card";
      var title = document.createElement("a");
      title.href = "/courses/" + source.item_id;
      title.textContent = "[item_id:" + source.item_id + "] " + (source.title || "Tài nguyên");
      card.appendChild(title);
      var excerpt = document.createElement("p");
      excerpt.textContent = source.excerpt || source.description || "Chưa có trích đoạn.";
      card.appendChild(excerpt);
      var provenance = document.createElement("p"); provenance.className = "muted small";
      provenance.textContent = (source.evidence_kind === "source_text" ? "Nội dung nguồn" :
        source.evidence_kind === "synthetic" ? "Dữ liệu mô phỏng" : "Nguồn chưa xác minh") +
        " · " + (source.provenance || "unknown");
      card.appendChild(provenance);
      var url = safeSourceUrl(source.url || source.link);
      if (url) {
        var link = document.createElement("a"); link.href = url;
        link.target = "_blank"; link.rel = "noopener noreferrer"; link.textContent = "Mở nguồn gốc ↗";
        card.appendChild(link);
      }
      var save = document.createElement("button"); save.type = "button";
      save.textContent = "Lưu tài nguyên"; save.className = "btn-ghost chat-source-save";
      save.dataset.course = String(source.item_id); card.appendChild(save);
      target.appendChild(card);
    });
  }
  window.ITLRChatStream = { consume: consume, sourcesInto: sourcesInto, safeSourceUrl: safeSourceUrl };
})();
