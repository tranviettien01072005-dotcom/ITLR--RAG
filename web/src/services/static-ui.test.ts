import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import vm from "node:vm";
import { expect, it } from "vitest";
class Element {
  textContent = "";
  children: Element[] = [];
  className = "";
  href = "";
  append(...elements: Element[]) { this.children.push(...elements); }
  addEventListener() {}
  set innerHTML(_value: string) { throw new Error("Untrusted markup reached HTML sink"); }
}
function ui() {
  const context = vm.createContext({ URL, document: {
    querySelectorAll: () => [], querySelector: () => new Element(),
    getElementById: () => new Element(), createElement: () => new Element(),
  } });
  vm.runInContext(readFileSync(resolve("../itlr/api/static/ui.js"), "utf8"), context);
  return (code: string) => vm.runInContext(code, context);
}
it("escapes model HTML and preserves a restricted Markdown subset", () => {
  const run = ui();
  expect(run('md("<img src=x onerror=alert(1)> **safe**")')).toBe("&lt;img src=x onerror=alert(1)&gt; <strong>safe</strong>");
});
it("blocks executable and protocol-relative catalog URLs", () => {
  const run = ui();
  for (const url of ["javascript:alert(1)", "data:text/html,<script>alert(1)</script>", "//evil.test"]) {
    expect(run(`safeUrl(${JSON.stringify(url)})`)).toBe("");
  }
  expect(run('safeUrl("https://example.org/doc")')).toBe("https://example.org/doc");
});
it("renders malicious catalog fields as text without an HTML sink", () => {
  const card = ui()('cardNode({title: "<img onerror=alert(1)>", link:"javascript:alert(1)"})');
  expect(card.children[1].textContent).toBe("<img onerror=alert(1)>");
  expect(card.children.some((node: Element) => node.href)).toBe(false);
});
