const { chromium } = require(
  process.env.ITLR_PLAYWRIGHT_MODULE || "playwright",
);
const assert = require("node:assert/strict");
const fs = require("node:fs");
// Explicit fixture only: never point this data-writing check at a real service.
const base = process.env.ITLR_STAGING_URL;
if (
  process.env.ITLR_STAGING_CONFIRM !== "isolated-fixture" ||
  !base ||
  !["127.0.0.1", "[::1]", "localhost"].includes(new URL(base).hostname)
) {
  throw new Error(
    "Require ITLR_STAGING_CONFIRM=isolated-fixture and loopback ITLR_STAGING_URL",
  );
}
if (!process.env.ITLR_STAGING_PDF)
  throw new Error("ITLR_STAGING_PDF must name a valid fixture PDF");
(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.ITLR_CHROMIUM_EXECUTABLE || undefined,
    headless: true,
    args: ["--no-sandbox"],
  });
  try {
    const context = await browser.newContext({
      ignoreHTTPSErrors: process.env.ITLR_STAGING_TLS_INSECURE === "1",
    });
    const page = await context.newPage();
    page.setDefaultTimeout(15000);
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    const email = `browser-${Date.now()}@example.test`,
      password = "LocalFixture!Aa3456";
    await page.goto(base + "/register");
    await page.locator("[name=name]").fill("Isolated Browser Fixture");
    await page.locator("[name=email]").fill(email);
    await page.locator("[name=password]").fill(password);
    await Promise.all([
      page.waitForURL("**/dashboard"),
      page.locator('form[action="/register"] button[type=submit]').click(),
    ]);
    const csrf = async (ctx) =>
      (await ctx.cookies()).find((c) => c.name === "csrf").value;
    let response = await context.request.post(
      base + "/api/learning/diagnostic",
      {
        data: {
          track: "python",
          goal: "Learn isolated Python fixtures",
          answers: [1, 0, 2],
        },
      },
    );
    assert.equal(response.status(), 403);
    await page.goto(base + "/learning");
    await page.locator("#goal").fill("Learn isolated Python fixtures");
    for (const [i, a] of [1, 0, 2].entries())
      await page.locator(`input[name=q${i}][value="${a}"]`).check();
    await Promise.all([
      page.waitForResponse(
        (r) =>
          r.url().endsWith("/api/learning/diagnostic") && r.status() === 200,
      ),
      page.locator("#diagnostic-form button[type=submit]").click(),
    ]);
    await page.waitForSelector(".learning-resource");
    const form = page.locator(".learning-progress-form").first();
    await form.locator("[name=progress]").fill("40");
    await Promise.all([
      page.waitForResponse(
        (r) => r.url().endsWith("/api/learning/progress") && r.status() === 200,
      ),
      form.locator("button[type=submit]").click(),
    ]);
    await page.waitForTimeout(700);
    await page.goto(base + "/learning");
    assert.equal(
      await page
        .locator(".learning-progress-form [name=progress]")
        .first()
        .inputValue(),
      "40",
    );
    await page.goto(base + "/search?q=python");
    assert((await page.content()).includes("Python introduction fixture"));
    await page.goto(base + "/chat");
    await page.locator("#chatinput").fill("Explain fixture Python");
    const streamPromise = page.waitForResponse((r) =>
      r.url().endsWith("/api/chat/stream"),
    );
    await page.locator("#chatform button[type=submit]").click();
    response = await streamPromise;
    assert.equal(
      response.status(),
      200,
      "HTTP " + response.url() + " " + (await response.text()).slice(0, 160),
    );
    const data = await response.text();
    const events = data
      .split(/\r?\n\r?\n/)
      .filter((s) => s.startsWith("data:"))
      .map((s) => JSON.parse(s.slice(5)));
    const final = events.find((e) => e.type === "final");
    assert(final);
    assert(!events.some((e) => e.type === "error"));
    await page.waitForTimeout(500);
    await page.goto(base + "/chat?c=" + final.conversation_id);
    assert((await page.content()).includes("Fixture answer"));
    response = await context.request.post(
      base + "/api/courses/700001/attachments",
      {
        headers: { "x-csrf-token": await csrf(context) },
        multipart: {
          file: {
            name: "forged.pdf",
            mimeType: "application/pdf",
            buffer: Buffer.from("not a PDF"),
          },
        },
      },
    );
    assert.equal(response.status(), 415);
    response = await context.request.post(
      base + "/api/courses/700001/attachments",
      {
        headers: { "x-csrf-token": await csrf(context) },
        multipart: {
          file: {
            name: "invalid.pdf",
            mimeType: "application/pdf",
            buffer: Buffer.from(
              "%PDF-1.4\n1 0 obj<</Type /Catalog>>endobj\n%%EOF",
            ),
          },
        },
      },
    );
    assert.equal(response.status(), 400);
    response = await context.request.post(
      base + "/api/courses/700001/attachments",
      {
        headers: { "x-csrf-token": await csrf(context) },
        multipart: {
          file: {
            name: "fixture.pdf",
            mimeType: "application/pdf",
            buffer: fs.readFileSync(process.env.ITLR_STAGING_PDF),
          },
        },
      },
    );
    assert.equal(
      response.status(),
      200,
      "HTTP " + response.url() + " " + (await response.text()).slice(0, 160),
    );
    assert.equal((await response.json()).pending, true);
    await page.goto(base + "/admin");
    assert(page.url().includes("/admin/login"));
    const anonymous = await browser.newContext({
      ignoreHTTPSErrors: process.env.ITLR_STAGING_TLS_INSECURE === "1",
    });
    response = await anonymous.request.get(base + "/api/conversations");
    assert.equal(response.status(), 401);
    const otherPage = await anonymous.newPage();
    await otherPage.goto(base + "/learning");
    assert(otherPage.url().includes("/login"));
    await otherPage.goto(base + "/register");
    await otherPage.locator("[name=name]").fill("Other Browser Fixture");
    await otherPage
      .locator("[name=email]")
      .fill(`other-${Date.now()}@example.test`);
    await otherPage.locator("[name=password]").fill(password);
    await Promise.all([
      otherPage.waitForURL("**/dashboard"),
      otherPage.locator('form[action="/register"] button[type=submit]').click(),
    ]);
    response = await anonymous.request.post(base + "/api/chat", {
      headers: { "x-csrf-token": await csrf(anonymous) },
      data: { message: "forbidden", conversation_id: final.conversation_id },
    });
    assert.equal(response.status(), 404);
    await page.locator('form[action="/logout"] button').click();
    await page.waitForURL("**/login");
    await page.locator("[name=email]").fill(email);
    await page.locator("[name=password]").fill(password);
    await Promise.all([
      page.waitForURL("**/dashboard"),
      page.locator('form[action="/login"] button[type=submit]').click(),
    ]);
    assert.deepEqual(errors, []);
    const result = {
      scope:
        "Real Chromium -> Express -> isolated PostgreSQL; RAG upstream is explicit HTTP fixture (not neural API/LLM)",
      registration: true,
      login: true,
      csrfReject: true,
      anonymousDenied: true,
      adminDenied: true,
      crossUserChatDenied: true,
      searchFixture: true,
      chatStream: events.map((e) => e.type),
      persistedChat: true,
      progressPersisted: 40,
      forgedUploadRejected: true,
      structurallyInvalidPdfRejected: true,
      validPdfPending: true,
      pageErrors: errors,
    };
    if (process.env.ITLR_STAGING_REPORT)
      fs.writeFileSync(
        process.env.ITLR_STAGING_REPORT,
        JSON.stringify(result, null, 2),
      );
    console.log(JSON.stringify(result));
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e.stack);
  process.exitCode = 1;
});
