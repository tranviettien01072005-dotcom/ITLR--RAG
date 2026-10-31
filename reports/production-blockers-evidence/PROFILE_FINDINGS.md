# Local model performance diagnostic — 2026-10-30

Read-only app diagnostic. No provider/model/threshold/source edits, no cloud keys, no model unload or daemon restart. E5-base768 loaded from cached revision in an isolated Python process against the existing118item/1576chunk staging artifacts. Qwen2.5:3b requests use the existing loopback Ollama daemon. Sharedhost and promptcache prevent cold-model or dedicated-capacity claims.

Current frozen **DEV** queries only. Prepared all12 positive DEVqueries to choose the existing Vietnamese404 question and the longest existing production prompt, Vietnamese contextmanager query dev-vi-5061. No confirmation, holdout or independently frozen evaluation labels used for selection or tuning. All requests used temperature0.3, current full production prompt and max_tokens2000, except minimal smoke64. Async HTTP diagnostic applies an actual45s wall deadline. No prompt/context/output reduction was applied.

| Request | Promptchars | Wallseconds | TTFTseconds | Completion | Tokens / decode tok/s |
|---|---:|---:|---:|---|---|
| warm minimal OK |14|0.349|0.224|stop|2 /15.90|
| warm DEV404 production prompt |5811|6.671|0.228|stop|42 /6.52|
| longestDEV contextmanager prompt |6015|45.046|null|TIMEOUT,0deltas|unknown|
| concurrent1 DEV404 |5811|15.206|8.453|stop|42 /6.22|
| concurrent2 contextmanager |6015|22.623|15.352|stop|44 /6.06|

Both sequential and concurrent successes are **near-complete promptcache hits**:404 prompt_eval1420/cached1419; contextmanager1386/cached1385. This is not evidence that an uncached1420token prompt meets45s. The longest query first timed out with no deltas, then cachehit completed in the subsequent concurrent run. DirectOllama reproduction localizes the45s failure below FastAPI/Express; provider scheduling/prompt evaluation/cache/hardware must be separated from application protocol correctness.

The previous simple OK request's41.57s wall time with0.10s decode is not reproduced consistently: current same smoke0.349s. Shared scheduling/cache state can dominate it. Ollama successful completion metadata leaves~8s unattributed during both concurrent calls; this is consistent with queue/scheduling overhead, not a measured isolated queue timer. After the timeout, subsequent404 still waited~8s before prefilling/decoding: no assumption that closing a client socket immediately cancels a CPU prefill batch.

RAG observed completion3/4=75%, on only2DEVqueries with repeated prompts. Elapsed p50/p95 includingtimeout18.915/41.683s; successful-only TTFT p50/p95 8.453/14.662s. These tiny, cache-dependent samples are diagnostic figures, not release SLO or quality estimates. Three completed answers have valid item/chunk membership. The404 answer states requestedresource absent; contextmanager answer names__enter__/__exit__, consistent with visible expected evidence on a manual technical spotcheck. However, the contextmanager answer cites5061:7, whose suppliedexcerpt discussesclosing/aclosing and lacks__enter__/__exit__; other suppliedchunks0/14/1 containthosemethods. This is one observed unsupported-passagecitation in a technicallycorrectanswer, not humanlabelgroundtruth or an estimatedhallucinationrate. Exactanswer/excerpts/provenance are saved in citation-support-spotcheck.json. Human faithfulness/answerquality remains null. No contextoverflow reproduced in this smallhistoryfree sample (maxobservedprompt1420tokens vs loadedcontext4096; output42–44tokens); history/context limits remain unverified.

E5 processload13.061s. DEV retrieval/preparation72.7–108.3ms. Resource sampling uses /proc CPU-time deltas every~250ms, rather than ps lifetime averages. Runner RSSpeak2445.74MiB; CPUmean367.88%,p95427.06%,max514.80% (100%=one logicalCPU). IsolatedPython E5 processRSSpeak1742.78MiB; Ollamadaemon35.76MiB. Sharedrunner CPU includes any other requests and is not per-request attribution; summing processmaxima is not wholehost peakmemory. Full samples and percentiles are in profile-local.json/profile-summary.json.

Docker freshpreflight is BLOCKED. Socketroot:docker0660 denies this user; rootlesskit/dockerd-rootless helpers and subuid/subgid mapping exist, but newuidmap/newgidmap/slirp4netns/fuseoverlayfs are absent. No globalinstallation/groupchange or daemonstartup attempted. docker-environment.json records exact observations. No Docker/Pg16/Caddy runtime PASS claim.

Artifacts: profile_local.py (repro), profile-local.log, profile-local.json, profile-ollama-tags.json, profile-ollama-ps.json, summarize_profile.py, profile-summary.json, docker-environment.json. Only /tmp/itlr-blockers written. No repo application files changed, no commits/push/activation.


## DEV context-window experiment — rejected for runtime

Two sequential diagnostic conditions keep maxoutput2000, temperature0.3,45s hardwall, samequery, allsourcenames/URLs/IDs and the systeminjectionguard. Different harmless diagnosticnonce prefixes make cache reuse measurable; this is a diagnosticprompt variant, not the exactproductionprompt. No sharedmodel unload.

Fullfive-sources6073chars: firstdelta44.876s, timeout45.003s afteronly'Context', no confirmedcompletion. Extractivewindows2743chars:29.842s,TTFT22.488s,stop54tokens7.35tok/s; terminal762prompttokens/cached9,22.258sprefill (~34.2tokens/s), so unlike warm404this is a substantially uncachedpromptmeasurement.

The shorterinput is NOT accepted: answer omits__enter__, cites5061:7 where itsclaimisnotpresent, and omits[item_id]. Citationmembershipvalidationmissing. The expectedmethodfacts remain in other retainedexactwindows but the modeldidnotuse themcorrectly. This confirms that meeting45sbycuttinginputdoesnotestablishqualitypreservation. No runtimeprompt/context/outputlimitschanged. No threshold/rankingtuning. Fullprompts/excerpts/outputs and technicalspotcheck (not humanlabels) are in context-experiment.json; harnesscontext_experiment.py.

Rootlesskit actualpreflightalsofails beforechildcommand: missingnewuidmap; see rootless-preflight.log. No daemonstarted or globalsettingchanged.
