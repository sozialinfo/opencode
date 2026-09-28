#!/usr/bin/env python3
"""Playwright-based visual verification helper.

Subcommands
-----------
capture   Screenshot one or more URLs at several viewport widths and record
          console/page errors, failed requests and horizontal overflow.
compare   Pixel-diff two capture directories and write amplified diff images.
list      Print the devices available for `--device`.

Examples
--------
    python3 visual_verify.py capture \
        --url http://localhost:1313/ --url http://localhost:1313/article/ \
        --out /tmp/opencode/verify --full-page

    python3 visual_verify.py capture \
        --url http://localhost:1313/ --out /tmp/opencode/verify \
        --widths 390,768,1280 --fail-on-error

    python3 visual_verify.py compare \
        --baseline /tmp/opencode/verify-before \
        --current  /tmp/opencode/verify-after \
        --out      /tmp/opencode/verify-diff
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_WIDTHS = [390, 768, 1280]
VIEWPORT_HEIGHT = 900


def slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return value or "home"


def page_name(url: str) -> str:
    parsed = urlparse(url)
    return slug(f"{parsed.netloc}{parsed.path}")


# --------------------------------------------------------------------------- #
# capture
# --------------------------------------------------------------------------- #
def cmd_capture(args: argparse.Namespace) -> int:
    from playwright.sync_api import sync_playwright

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    widths = args.widths
    device = args.device

    results: list[dict] = []
    with sync_playwright() as p:
        browser_type = getattr(p, args.browser)
        browser = browser_type.launch(headless=not args.headed)

        for url in args.url:
            if device:
                contexts_spec = [(slug(device), dict(p.devices[device]))]
            else:
                contexts_spec = [(str(w), {}) for w in widths]

            for label, descriptor in contexts_spec:
                console_errors: list[str] = []
                page_errors: list[str] = []
                failed_requests: list[dict] = []

                ctx_kwargs = dict(descriptor)
                if device:
                    ctx_kwargs["viewport"] = dict(
                        descriptor.get("viewport")
                        or {"width": 1280, "height": VIEWPORT_HEIGHT}
                    )
                else:
                    ctx_kwargs["viewport"] = {"width": int(label), "height": VIEWPORT_HEIGHT}
                    ctx_kwargs.pop("user_agent", None)
                if args.dark:
                    ctx_kwargs["color_scheme"] = "dark"
                if args.reduced_motion:
                    ctx_kwargs["reduced_motion"] = "reduce"

                context = browser.new_context(**ctx_kwargs)
                page = context.new_page()

                page.on(
                    "console",
                    lambda m: console_errors.append(m.text) if m.type == "error" else None,
                )
                page.on("pageerror", lambda e: page_errors.append(str(e)))
                page.on(
                    "requestfailed",
                    lambda r: failed_requests.append(
                        {"url": r.url, "error": (r.failure or "")}
                    ),
                )

                suffix = slug(device) if device else str(label)
                target = out / f"{page_name(url)}-{suffix}.png"
                entry: dict = {
                    "url": url,
                    "name": target.name,
                    "viewport": ctx_kwargs["viewport"],
                    "screenshot": str(target),
                }

                try:
                    response = page.goto(
                        url, wait_until=args.wait_until, timeout=args.timeout * 1000
                    )
                    entry["status"] = response.status if response else None
                    if args.wait_for:
                        page.wait_for_selector(
                            args.wait_for, timeout=args.timeout * 1000
                        )
                    if args.wait_ms:
                        page.wait_for_timeout(args.wait_ms)

                    entry["title"] = page.title()
                    metrics = page.evaluate(
                        "() => { const d = document.documentElement;"
                        " return { scrollWidth: d.scrollWidth, clientWidth: d.clientWidth }; }"
                    )
                    entry["overflow_px"] = max(
                        0, metrics["scrollWidth"] - metrics["clientWidth"]
                    )
                    entry["horizontal_overflow"] = entry["overflow_px"] > 1

                    if args.element:
                        page.locator(args.element).first.screenshot(path=str(target))
                    else:
                        page.screenshot(path=str(target), full_page=args.full_page)
                except Exception as exc:  # noqa: BLE001 - report, do not abort the run
                    entry["error"] = f"{type(exc).__name__}: {exc}"
                finally:
                    context.close()

                entry["console_errors"] = console_errors
                entry["page_errors"] = page_errors
                entry["failed_requests"] = failed_requests
                results.append(entry)
                print(
                    f"[{'ERR' if entry.get('error') else 'ok '}] "
                    f"{entry['name']}  status={entry.get('status')} "
                    f"overflow={entry.get('overflow_px')}px "
                    f"console_errors={len(console_errors)} page_errors={len(page_errors)}",
                    file=sys.stderr,
                )

        browser.close()

    report = {"mode": "capture", "browser": args.browser, "results": results}
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if not args.quiet:
        print(json.dumps(report, indent=2))

    if args.fail_on_error:
        broken = [
            r
            for r in results
            if r.get("error")
            or r.get("console_errors")
            or r.get("page_errors")
            or r.get("failed_requests")
            or r.get("horizontal_overflow")
            or (r.get("status") or 0) >= 400
        ]
        if broken:
            print(f"\n{len(broken)} capture(s) reported problems.", file=sys.stderr)
            return 1
    return 0


# --------------------------------------------------------------------------- #
# compare
# --------------------------------------------------------------------------- #
def cmd_compare(args: argparse.Namespace) -> int:
    from PIL import Image, ImageChops

    baseline = Path(args.baseline)
    current = Path(args.current)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    names = sorted(
        {p.name for p in baseline.glob("*.png")} | {p.name for p in current.glob("*.png")}
    )
    results: list[dict] = []
    failures = 0

    for name in names:
        old_path, new_path = baseline / name, current / name
        entry: dict = {"name": name}

        if not old_path.exists() or not new_path.exists():
            entry["status"] = "missing"
            entry["baseline"] = old_path.exists()
            entry["current"] = new_path.exists()
            failures += 1
            results.append(entry)
            continue

        old = Image.open(old_path).convert("RGB")
        new = Image.open(new_path).convert("RGB")
        if old.size != new.size:
            entry["status"] = "size-mismatch"
            entry["baseline_size"] = list(old.size)
            entry["current_size"] = list(new.size)
            failures += 1
            results.append(entry)
            continue

        diff = ImageChops.difference(old, new)
        box = diff.getbbox()
        total = old.size[0] * old.size[1]
        if box:
            gray = diff.convert("L")
            zero = gray.histogram()[0]
            changed = total - zero
            ratio = changed / total if total else 0.0
            amplified = diff.convert("RGB").point(lambda v: min(255, v * 4))
            diff_path = out / name
            amplified.save(diff_path)
            entry.update(
                status="changed",
                changed_pixels=changed,
                total_pixels=total,
                ratio=round(ratio, 6),
                bbox=list(box),
                diff_image=str(diff_path),
            )
            if ratio > args.max_ratio:
                entry["exceeds_threshold"] = True
                failures += 1
        else:
            entry.update(status="same", changed_pixels=0, ratio=0.0)

        results.append(entry)
        print(
            f"[{entry['status']:>13}] {name}  ratio={entry.get('ratio', 0)}",
            file=sys.stderr,
        )

    report = {
        "mode": "compare",
        "baseline": str(baseline),
        "current": str(current),
        "max_ratio": args.max_ratio,
        "results": results,
    }
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if not args.quiet:
        print(json.dumps(report, indent=2))

    if failures and args.strict:
        print(f"\n{failures} difference(s) at or above threshold.", file=sys.stderr)
        return 1
    return 0


def cmd_list(_args: argparse.Namespace) -> int:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        print("\n".join(sorted(p.devices)))
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    cap = sub.add_parser("capture", help="screenshot URLs and collect page diagnostics")
    cap.add_argument("--url", action="append", required=True, help="URL to capture (repeatable)")
    cap.add_argument("--out", required=True, help="output directory")
    cap.add_argument("--widths", default=",".join(map(str, DEFAULT_WIDTHS)),
                     help=f"comma-separated viewport widths (default: {','.join(map(str, DEFAULT_WIDTHS))})")
    cap.add_argument("--device", help="Playwright device name (see `list`); overrides --widths")
    cap.add_argument("--browser", default="chromium", choices=["chromium", "firefox", "webkit"])
    cap.add_argument("--full-page", action="store_true", help="capture the full scrollable page")
    cap.add_argument("--element", help="CSS selector: screenshot only this element")
    cap.add_argument("--wait-for", help="CSS selector to wait for before screenshotting")
    cap.add_argument("--wait-until", default="networkidle",
                     choices=["load", "domcontentloaded", "networkidle", "commit"])
    cap.add_argument("--wait-ms", type=int, default=0, help="extra settle delay in ms")
    cap.add_argument("--timeout", type=int, default=30, help="per-step timeout in seconds")
    cap.add_argument("--dark", action="store_true", help="prefers-color-scheme: dark")
    cap.add_argument("--reduced-motion", action="store_true", help="prefers-reduced-motion: reduce")
    cap.add_argument("--headed", action="store_true", help="show the browser window")
    cap.add_argument("--quiet", action="store_true", help="suppress the JSON report on stdout")
    cap.add_argument("--fail-on-error", action="store_true",
                     help="exit non-zero on console/page errors, failed requests, overflow or HTTP >= 400")
    cap.set_defaults(func=cmd_capture)

    cmp_ = sub.add_parser("compare", help="pixel-diff two capture directories")
    cmp_.add_argument("--baseline", required=True)
    cmp_.add_argument("--current", required=True)
    cmp_.add_argument("--out", required=True)
    cmp_.add_argument("--max-ratio", type=float, default=0.0,
                      help="tolerated changed-pixel ratio before a file counts as a failure")
    cmp_.add_argument("--strict", action="store_true", help="exit non-zero when differences are found")
    cmp_.add_argument("--quiet", action="store_true")
    cmp_.set_defaults(func=cmd_compare)

    lst = sub.add_parser("list", help="list available Playwright devices")
    lst.set_defaults(func=cmd_list)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "capture":
        args.widths = [int(w) for w in str(args.widths).split(",") if w.strip()]
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
