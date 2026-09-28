---
name: visual-verify
description: Visually verify web pages with Playwright. Use when asked to verify UI changes, check responsive layouts, screenshot a page, or audit a site visually. Captures desktop/tablet/mobile screenshots, console and page errors, failed requests and horizontal overflow, and can pixel-diff a run against a baseline.
license: MIT
metadata:
  author: opencode
  version: "1.0"
---

# Visual verification with Playwright

Verify how pages actually render instead of guessing from markup. The helper
captures screenshots at multiple viewport widths and records the page
diagnostics you would otherwise miss (JS errors, failed requests, horizontal
overflow), then can pixel-diff a run against a known-good baseline.

## Helper

```
~/.config/opencode/skills/visual-verify/scripts/visual_verify.py
```

Python Playwright and the browser binaries are already installed
(`python3 -c "from playwright.sync_api import sync_playwright"`). Run the helper
with `python3`; it only needs `playwright` and `Pillow`.

Set a shorthand for the commands below:

```bash
VV=~/.config/opencode/skills/visual-verify/scripts/visual_verify.py
```

## Workflow

1. **Get a URL.** Use the dev/preview server for the change, or a live URL.
   Start a server only if one is not already running. Generic examples:
   ```bash
   hugo server --bind 0.0.0.0 --port 1313          # static sites
   npm run dev                                     # JS apps (check the printed port)
   docker compose up -d                            # containerised previews
   ```
   Wait until the port answers (`curl -sf -o /dev/null http://localhost:1313/`)
   before capturing.

2. **Capture** every page affected by the change, at mobile, tablet and desktop
   widths:
   ```bash
   python3 "$VV" capture \
     --url http://localhost:1313/ \
     --url http://localhost:1313/article/ \
     --out /tmp/opencode/verify/after \
     --widths 390,768,1280 --full-page
   ```
   Add `--wait-for "<css>"` for pages whose content is injected by JS, and
   `--wait-ms 300` to let fonts/animations settle.

3. **Read the report** (also written to `<out>/report.json`). For each capture
   check, in order:
   - `error` — the page failed to load or an action timed out.
   - `status` — anything `>= 400`.
   - `console_errors` / `page_errors` — JS exceptions and console errors.
   - `failed_requests` — missing images, fonts, or API calls (very common when
     a visual regression is really a 404).
   - `horizontal_overflow` / `overflow_px` — content wider than the viewport, a
     frequent responsive bug.

   `--fail-on-error` makes the command exit non-zero if any of the above is
   present, which is handy before reporting success.

4. **Look at the screenshots** yourself. Show the relevant ones to the user (the
   harness `preview` tool renders images; the `Read` tool displays them to you).
   View both the full-page image and, when a specific area matters, re-capture
   just that element:
   ```bash
   python3 "$VV" capture --url http://localhost:1313/ \
     --out /tmp/opencode/verify/element --element ".hero" --widths 1280
   ```

5. **Compare against a baseline** when you need to prove the change only did
   what was intended. Capture the baseline from the pre-change revision (stash,
   checkout, or the deployed URL) into a separate directory with the same widths,
   then:
   ```bash
   python3 "$VV" compare \
     --baseline /tmp/opencode/verify/before \
     --current  /tmp/opencode/verify/after \
     --out      /tmp/opencode/verify/diff \
     --max-ratio 0.001 --strict
   ```
   The command writes an amplified diff image per changed page and a
   `report.json`, and exits non-zero when a page exceeds `--max-ratio`. Open the
   diff images to confirm each changed region is expected.

## Command reference

`capture`
| Flag | Purpose |
| --- | --- |
| `--url URL` | page to capture (repeatable) |
| `--out DIR` | output directory (required) |
| `--widths 390,768,1280` | viewport widths (default) |
| `--device "iPhone 13"` | Playwright device descriptor, overrides `--widths` (`list` shows names) |
| `--browser chromium\|firefox\|webkit` | engine (default chromium) |
| `--full-page` | full scrollable page instead of the viewport |
| `--element CSS` | screenshot only the first match |
| `--wait-for CSS` | wait for a selector before screenshotting |
| `--wait-until load\|domcontentloaded\|networkidle\|commit` | navigation wait (default networkidle) |
| `--wait-ms N` | extra settle delay |
| `--timeout N` | per-step timeout in seconds (default 30) |
| `--dark`, `--reduced-motion` | emulate preferences |
| `--headed` | show the browser window |
| `--quiet` | suppress JSON on stdout (summary still on stderr) |
| `--fail-on-error` | non-zero exit on errors/overflow/HTTP>=400 |

`compare`
| Flag | Purpose |
| --- | --- |
| `--baseline DIR`, `--current DIR` | directories of PNGs to compare |
| `--out DIR` | where diff images and `report.json` go |
| `--max-ratio F` | tolerated changed-pixel ratio before a file fails |
| `--strict` | exit non-zero when differences are found |
| `--quiet` | suppress JSON on stdout |

`list` prints the available `--device` names.

## Gotchas

- **`networkidle` can hang** on pages with polling, websockets or analytics. Fall
  back to `--wait-until load` plus `--wait-for` the element that matters.
- **Diff noise.** Anti-aliasing and font rasterisation vary between machines and
  browsers. Always compare captures from the same machine and browser, and set a
  small `--max-ratio` rather than expecting a zero-pixel difference.
- **Dynamic content** (carousels, clocks, ads, randomised testimonials) will
  always differ. Capture a stable state with `--wait-for`/`--wait-ms`, or treat
  that page's diff as expected.
- **Full-page screenshots** of very long pages are large; prefer element
  captures when only one region changed.
- **Always check `failed_requests`.** A missing font or image often explains an
  unexpected layout shift better than any CSS reasoning.

## Reporting back

Summarise per page and width: what rendered, and any `console_errors`,
`failed_requests` or horizontal overflow. Give the screenshot/diff file paths so
the user can open them. Do not claim success from the exit code alone — the
screenshots are the evidence.
