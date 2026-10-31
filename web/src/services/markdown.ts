import MarkdownIt from "markdown-it";

const md = new MarkdownIt({ html: false, breaks: true, linkify: true });

// Only escaped prose becomes citation links; code and existing links stay literal.
md.core.ruler.after("linkify", "item-citations", state => {
  const ids: ReadonlySet<number> | undefined = state.env.itemIds;
  if (!ids) return;
  for (const block of state.tokens) {
    let linkDepth = 0;
    for (const token of block.children || []) {
      if (token.type === "link_open") linkDepth++;
      else if (token.type === "link_close") linkDepth--;
      else if (token.type === "text" && linkDepth === 0) {
        const escaped = md.utils.escapeHtml(token.content);
        const linked = escaped.replace(/\[item_id:(\d+)\]/g, (label, raw: string) => {
          const id = Number(raw);
          return ids.has(id) ? `<a href="/courses/${id}">item_id:${id}</a>` : label;
        });
        if (linked !== escaped) {
          token.type = "html_inline";
          token.content = linked;
        }
      }
    }
  }
});

export function renderMd(src: string, itemIds?: ReadonlySet<number>): string {
  return md.render(src || "", { itemIds });
}

export function googleRefs(query: string): { label: string; url: string }[] {
  const t = (query || "").trim().slice(0, 120);
  if (!t) return [];
  const g = (q: string) => "https://www.google.com/search?q=" + encodeURIComponent(q);
  return [
    { label: `Tìm "${t}" trên Google`, url: g(t) },
    { label: "Hướng dẫn & lộ trình học", url: g(t + " hướng dẫn lộ trình học") },
    { label: "Tài liệu chính thức (docs)", url: g(t + " tài liệu chính thức documentation") },
  ];
}
