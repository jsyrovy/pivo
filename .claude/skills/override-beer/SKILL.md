---
name: override-beer
description: Create an Untappd override for a beer that can't be matched automatically. Use when the user provides a beer name and an Untappd URL (short or full) and wants it paired via override. Covers the full cycle: resolve URL, find beer key, add override, commit, push, trigger pairing, verify.
compatibility: Requires Python 3.14+, uv, gh CLI, and network access to untappd.com and tap API.
---

# Override beer workflow

When a beer can't be matched by the normal Untappd search (brewery name divergence, collab
names, etc.), add an entry to `untappd_pairing/overrides.json`. This bypasses the matcher
entirely and pairs via direct Untappd page fetch.

## Checklist

- [ ] Resolve short URL to full Untappd URL
- [ ] Find correct beer key from tap API
- [ ] Add entry to `untappd_pairing/overrides.json`
- [ ] Commit and push
- [ ] Trigger `untappd-pairing` workflow
- [ ] Verify override matched in workflow logs
- [ ] Check CI passed

## Procedure

### 1. Resolve the Untappd URL

Short URLs (`https://untp.beer/...`) must be resolved to the full canonical URL:

```sh
uv run --no-dev python -c "
import httpx
r = httpx.get('https://untp.beer/<slug>', follow_redirects=True)
print(r.url)
"
```

### 2. Find the beer key from the live tap API

The beer key format is `source::brewery::name`. Do **not** guess the key from
`pairings.json` unmatched — it may be stale or use a different brewery string.
Query the tap API directly:

```sh
uv run --no-dev python -c "
from untappd_pairing.tap_api import fetch_all_beers
beers = fetch_all_beers()
for b in beers:
    if '<beer_name>' in b.name.lower():
        print(f'{b.source}::{b.brewery}::{b.name}')
"
```

### 3. Add the override

Edit `untappd_pairing/overrides.json` — add one line before the closing `}`:

```json
"<source>::<brewery>::<name>": "<full untappd url>"
```

### 4. Commit and push

Commit only `untappd_pairing/overrides.json`. Do not commit `pairings.json` or
`fixtures.json` — those are side effects of pairing runs.

```sh
git add untappd_pairing/overrides.json
git commit -m "Override <brewery> <beer name>"
git pull --rebase && git push
```

### 5. Trigger the pairing workflow

```sh
gh workflow run untappd-pairing
```

### 6. Verify

Watch the workflow and check logs for the override match:

```sh
gh run watch <run_id> --exit-status
gh run view <run_id> --log | grep -i '<beer_name>'
```

Expected log line: `Override matched <brewery>::<name> -> <untappd_url>`

Also confirm CI passed (`gh run list` — all jobs green).

## Gotchas

- **Beer key comes from tap API, not pairings.json.** Collab beers have combined brewery
  names (e.g. `Sibeeria/Alefarm` not `Sibeeria, Praha`). Always query `fetch_all_beers()`
  for the live key.

- **`select_pending` intentionally returns override beers** when they have no entry in
  `pairings.json` yet — the pairing process needs to run `_pair_via_override` to create
  the record. This is correct behavior, not a bug.

- **Push may need `git pull --rebase` first** — the pairing action auto-commits
  `pairings.json` on each run, so remote is often ahead.

- **Commit message convention**: terse imperative, e.g. `Override Klenot Dragon Gem and
  Haksna BRU-1ng Galaxy`.
