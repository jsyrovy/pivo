---
name: pairing-debug
description: Debug Untappd pairing problems by annotating fixtures and fixing the matcher, query-builder, or overrides. Use when annotating a fixture (wrong_match / should_match / expected_missing / not_on_untappd), tuning untappd_pairing/normalize.py or matcher.py against the fixtures corpus, or adding an override for a brewery name mismatch.
---

# Pairing debug workflow

The project captures each pairing attempt (beer data, queries tried, candidates returned by Untappd, outcome) to
`untappd_pairing/fixtures.json`. Annotations on those fixtures drive both regression tests and matcher tuning. This
skill walks through the debugging cycle.

## Key files

| Path                                            | What's in it                                                                               |
|-------------------------------------------------|--------------------------------------------------------------------------------------------|
| `untappd_pairing/fixtures.json`                 | Captured pairing data, one entry per beer. Source of truth for what queries returned what. |
| `untappd_pairing/fixtures.py`                   | `FixturesStore`, `replay()`, `expected_outcome()`, dataclasses.                            |
| `untappd_pairing/pairings.json`                 | Production pairings + unmatched cooldown state.                                            |
| `untappd_pairing/overrides.json`                | `beer_key → untappd_url` map. Bypasses matcher entirely.                                   |
| `untappd_pairing/normalize.py`                  | `build_search_queries`, `clean_beer_name`, `_DEGREE_RE` etc. Generates the query strings.  |
| `untappd_pairing/matcher.py`                    | `best_match`, `name_overlap`, `brewery_matches`. Picks a candidate from search results.    |
| `tests/untappd_pairing/test_fixtures_replay.py` | Parametrized regression test — replays current matcher against every captured fixture.     |

## Verdict decision tree

Given a fixture entry and the **correct Untappd URL** (provided by the user, in compressed `/b/...` form):

```
Is the correct URL in record.candidates?
├── Yes
│   ├── outcome.matched == correct URL?  → no annotation needed (already correct)
│   ├── outcome.matched is some other URL → verdict = "wrong_match"
│   └── outcome.matched is null          → verdict = "should_match"
└── No
    ├── Correct URL is null (beer not on Untappd)  → verdict = "not_on_untappd"
    └── Correct URL exists on Untappd              → verdict = "expected_missing"
```

The `expected_missing` case usually means the queries built by `normalize.build_search_queries` never asked for the
right thing — Untappd's search didn't surface the right beer because the query was off.

## Fix strategies per verdict

### `wrong_match` or `should_match`

The right candidate IS in `record.candidates`, so the search worked but `matcher.best_match` picked wrong (or rejected
all of them).

- Investigate `matcher.py` — likely `NAME_OVERLAP_WITH_BREWERY`, `NAME_OVERLAP_WITHOUT_BREWERY`, `brewery_matches`
  token-subset check, or the `_sort_key` priorities.
- Add a unit test to `tests/untappd_pairing/test_matcher.py` reproducing the case (build candidates from the fixture,
  call `best_match`, assert expected URL).
- Be careful: lowering thresholds may break OK matches in other fixtures. Run `make test` — the replay test will flag
  regressions across all fixtures.

### `expected_missing`

The right candidate is NOT in any captured query's results. Two paths:

1. **Generic fix**: improve `normalize.build_search_queries` so a new query variant would return the right beer.
    - Example we already did: `_DEGREE_RE` didn't handle `12,5°` decimal form. Fix: extend regex to
      `\d+(?:[.,]\d+)?\s*°`.
    - Always add a unit test to `tests/untappd_pairing/test_normalize.py`.
    - After the fix, re-run `make run-untappd-pairing` to fetch fresh candidates; verify the correct URL now appears.

2. **Override**: when the source brewery name and the Untappd brewery name diverge in a way that no query can bridge.
    - Example we already did: `Kynšperský Zajíc` (source) vs `Kynšperský pivovar` (Untappd) — no normalization can
      recover this.
    - Add an entry to `untappd_pairing/overrides.json`: `"<beer_key>": "<full untappd URL>"`.
    - Overrides bypass `_pair_via_search` and `fixture` capture entirely. The existing `expected_missing` fixture stays
      as a historical record; update its `note` to mention the override resolution.

### `not_on_untappd`

Nothing to do beyond the annotation itself. The fixture serves as a documented "we checked, it's not there" record.

## End-to-end cycle

1. **Pick a fixture to debug.** Either user supplies the `beer_key`, or scan `fixtures.json` for entries where
   `outcome.matched is null` or where you suspect the match is wrong.

2. **Ask the user for the correct URL.** They look it up on Untappd. Accept compressed (`/b/...`) or full URL. Treat
   `null` as "not on Untappd."

3. **Check whether the correct URL is in `record.candidates`, then apply the verdict tree.** Run via Bash:

   ```sh
   uv run --no-dev python -c "
   import json
   from pathlib import Path
   from untappd_pairing.fixtures import compress_url
   data = json.loads(Path('untappd_pairing/fixtures.json').read_text())
   record = data['fixtures']['<beer_key>']
   urls = [c['url'] for c in record['candidates']]
   print('in candidates:', compress_url('<full url>') in urls)
   print('candidates:', urls)
   "
   ```

4. **Write the annotation** into `fixtures.json` under the entry's `annotation` key:

   ```json
   "annotation": {
     "verdict": "<wrong_match|should_match|expected_missing|not_on_untappd>",
     "expected": "/b/...",  // or null for not_on_untappd
     "note": "human-readable explanation"
   }
   ```

5. **Run `make test`.** The replay test will:
    - `wrong_match` / `should_match`: fail until matcher is fixed (expected — you'll fix it next)
    - `expected_missing`: skip (can't replay against captured candidates that don't contain the expected URL)
    - `not_on_untappd`: pass (asserts no match was made)

6. **Apply the fix** per the strategy above (code change in matcher/normalize, or new entry in overrides.json).

7. **Re-run pairing** to capture fresh fixtures with the fixed query/matcher behavior:

   ```sh
   uv run --no-dev run_untappd_pairing.py --notificationless
   ```

   Caveat: if the beer is currently in `pairings.json[unmatched]`, it's in a 7-day cooldown. Force a re-pair by removing
   the entry first:

   ```sh
   uv run --no-dev python -c "
   import json
   from pathlib import Path
   path = Path('untappd_pairing/pairings.json')
   data = json.loads(path.read_text())
   data['unmatched'].pop('<beer_key>', None)
   path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
   "
   ```

   `upstream_error` reasons retry immediately — only the non-transient reasons (`no_candidates_above_threshold`,
   `override_page_parse_failed`) sit in cooldown.

8. **Resolve the annotation.**
    - **Delete** the `annotation` block when the new run matches the expected URL. The fixture then serves as a
      regression test for the fix.
    - **Keep and update the `note`** when the fix used an override. The verdict stays `expected_missing` — the
      underlying query problem is unresolved, just sidestepped.
    - **Redo the verdict tree** when the new run still doesn't match. Fresh candidates may shift the diagnosis.

9. **Verify `make before-commit` is green**, then commit. Conventional commit messages in this repo are terse
   imperative ("Override X", "Match decimal-degree beer names like ...").

## LLM-sourced fixtures (`source: "llm"`)

When the deterministic matcher rejects every candidate but Untappd did return some, an optional LLM fallback
(`untappd_pairing/llm_matcher.py`, OpenRouter free models, only active when `OPENROUTER_API_KEY` is set) adjudicates
the captured candidate pool. An LLM match is recorded in `pairings.json` with `query_used == "<llm>"` and the fixture's
`outcome.source` is set to `"llm"`.

- **Replay skips LLM-sourced fixtures** (`expected_outcome` returns `None` when `source == "llm"` and there's no
  annotation) — the deterministic matcher legitimately can't reproduce them, same as `expected_missing`.
- Treat `source: "llm"` fixtures as a **discoverable list of matcher gaps**: each is a candidate to promote to an
  `overrides.json` entry, or to fix in `matcher.py`/`normalize.py`. Once the matcher catches it deterministically, the
  next run rewrites the fixture with `source` back to `"matcher"`.

## Pitfalls

- **Untappd URL slug aliases**: the same beer ID can appear at two different slugs (e.g. `/b/...maisel-and-friends...`
  vs `/b/...maisel-friends...`). The beer ID at the end is authoritative. If user provides a URL with a different slug
  than what Untappd's search currently returns, prefer the search-returned slug — it's what the matcher will encounter.
  Don't fail on slug mismatch when the trailing ID matches.

- **Overrides don't capture fixtures**. `_pair_via_override` skips `fixtures_store.upsert`. If you add an override, the
  existing fixture (if any) stays unchanged on subsequent runs.

- **Fixture re-capture overwrites trace + outcome but preserves annotation**. So you can fix code, re-run pairing, and
  the annotation will follow the new fixture. Decide whether to keep/update/delete it explicitly.

- **The `fixtures_store.save` happens even in `--local` mode.** Don't rely on `--local` to avoid touching
  `fixtures.json`.

- **`generated_at` updates on every save** — that's expected noise in diffs.

