# Adversarial follow-up review

Reviewed the new app.js change and chat-ui.test.ts against prior behavior; no application edits.

## UI result

No new defect found in the changed completion path. The final SSE event is retained without rendering success or changing conversation state. Only after consume() resolves (requiring final, done, clean UTF-8 and EOF) does app.js render final HTML, show completion, set conversation ID, add the sidebar entry and replace browser history. Every exception clears answer.textContent and shows an error/abort status. Incomplete final streams therefore cannot reach the conversation/sidebar mutation block.

Executed `env -u DEEPSEEK_API_KEY -u OPENAI_API_KEY npx vitest run src/services/chat-ui.test.ts --reporter=dot` from web/: **4 tests passed**. Cases cover EOF without done, invalid UTF-8, truncated UTF-8, and valid final+done. The actual app.js and chat-stream.js execute in the test VM.

Test limits: the synthetic stream starts with final and never sends provisional text, so the blank-answer assertion does not itself exercise clearing a nonempty draft. document.querySelector() always returns null, so the sidebar DOM is absent: browser-history assertions guard the same conversation mutation block, but do not directly inspect sidebar contents. Source inspection shows both paths are behind successful consume(). These are narrow evidence limits, not demonstrated runtime regressions.

## Bandit and artifact trust

The newest scan has **73 findings: 0 High, 27 Medium, 46 Low**. Its multiset of `(filename, rule ID, line, severity)` matches reports/final-engineering-evidence/bandit-triage.json exactly: **zero added or removed findings**. Rule counts: B301=22, B311=19, B403=9, B404=6, B603=6, B310=5, B110=4, B112=2. Scanner acceptance remains conditional; this is not a clean-scan claim.

No new exploitable finding established from this comparison. The Python Dockerfile still has no USER declaration and the API compose mount still exposes ./var:/app/var read-write. web/Dockerfile does use USER node. These three deployment files have no current git diff. A party able to replace trusted artifact pickle plus MANIFEST.json can execute code when the API loads the pickle; SHA256 inventory does not authenticate the builder or prevent malicious simultaneous artifact/manifest replacement. Running the API as container root amplifies an existing compromise. This remains an existing conditional filesystem-trust/deployment risk; no remote untrusted request-to-artifact-write path was demonstrated here. deploy/DEPLOY.md:149 already discloses the read-write API mount.

Observed local modes: var and var/artifacts are o:o 0775; diagnostic staging is o:o 0775 and its MANIFEST.json o:o 0664. These are local observations, not deployed-volume ACL proof. No Docker runtime/image verification or exploit execution was performed.

## Source identities

- `web/src/public/app.js`: `267aea7784ee502da96d7ad47e347d84022ffed9505566ecd554395a425d2257`
- `web/src/services/chat-ui.test.ts`: `30937fe9abc9e64871ba88ee5402b1397b2f73868b86cbdd5cb24d23aed7f0db`
- `Dockerfile`: `dec7e21b024fa04fc72d04536604515453f43bb40a39bc544cfa4e48ea364565`
- `docker-compose.yml`: `cfecfa4c69474b5e45410ecef8ddb37fc8be326242ac6ab7653dbc09b2ba6e66`
- `web/Dockerfile`: `050d3d70768d8799530792a44a339c08eb671ae36a7e359e7a22a6a3013af66a`
- `/tmp/itlr-release/bandit.json`: `2af7efff30367312f64420be5d9b9aa7158d3872ce042d4c08fe0e8f8c13fe2d`
- `reports/final-engineering-evidence/bandit-triage.json`: `4db4345b0a13ce13c8765ea773df6173d4371be44cdac462fd62cee7962e955a`

## Final PDF boundary review and updated UI regression

No new defect or security regression found in the one-line PDF fix. The worker now supplies a plain Uint8Array to pdf-parse instead of a Node Buffer. `new Uint8Array(workerData.buffer)` copies exactly the cloned typed-array elements; it does not reinterpret the complete pooled ArrayBuffer or expose bytes outside the uploaded Buffer view. Worker module selection remains the fixed supported-format map and require.resolve result, independent of document bytes. PDF data is still passed as binary data, not as a path/URL or evaluated program.

The existing caller checks remain: authenticated routes, upload size/count limits, PDF signature/EOF and MIME checks via validateUploads. Extraction still uses the existing two-active-operation guard, worker heap settings (128MB old/16MB young), 5s timeout, max100 parsed pages, 100000-character output cap, and worker termination/error handling. Those existing controls were preserved; worker heap settings are not a proof of a total process RSS limit or an OS security sandbox.

The new valid fixture has ASCII content, so string lengths equal byte offsets/stream length. It includes catalog/pages/page/font/content objects, a correctly sized xref table with free object0 plus five objects, matching startxref, and EOF. It exercises the actual parser inside a real Worker; no parser mock is used. pdf-red.log records valid-fixture extraction failing while three rejection tests pass; pdf-green.log records all four passing after the boundary change. The logs reviewed here are worker-level RED/GREEN evidence; the supervising agent's separate real HTTP500→200 observation was not independently repeated in this review.

Independent focused run: `env -u DEEPSEEK_API_KEY -u OPENAI_API_KEY npx vitest run src/services/dataset-extract.test.ts src/services/chat-ui.test.ts --reporter=dot` from web/: **8/8 tests passed**, two files. Invalid PDF warnings were emitted by deliberately corrupt fixtures. No application edits made by this reviewer.

Updated chat-ui.test.ts now sends `text: provisional draft` before final, so the previous nonempty-draft coverage limitation is resolved: all three invalid terminal cases assert the draft is cleared. Sidebar DOM remains absent in the VM; history mutation and the common guarded source block remain the evidence for no conversation update on incomplete streams.

Current source identities (supersede older hashes for these files):
- `web/src/services/dataset-extract.ts`: `848bd5195e6ccc27aa5cf95d653627cbb7ba451224e3ea3d7d5e1a4bece76530`
- `web/src/services/dataset-extract.test.ts`: `ee70c6d7f1b4b4178727ba4e05ad2b89219804c028503c689d11bc6e5ad1b8ce`
- `web/src/services/chat-ui.test.ts`: `6835aba2de088337a779b9aedbe1ef5cc8763d1810f7239930fc67fc19372f4f`
- `web/src/public/app.js`: `267aea7784ee502da96d7ad47e347d84022ffed9505566ecd554395a425d2257`
