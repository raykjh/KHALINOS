"""Deterministic, network-isolated browser verification for generated micro-apps."""

from __future__ import annotations

import json
import os
import re
import socket
import threading
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

from khalinos.models import ArtifactBundle, DeterministicEvidence


FORBIDDEN = (
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"\bfetch\s*\(", re.IGNORECASE),
    re.compile(r"\bWebSocket\s*\(", re.IGNORECASE),
    re.compile(r"\beval\s*\(", re.IGNORECASE),
    re.compile(r"data:[^;]+;base64", re.IGNORECASE),
)


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *args: object) -> None:
        del args


@contextmanager
def local_server(root: Path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    handler = partial(QuietHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/index.html"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def materialize(bundle: ArtifactBundle, root: Path) -> None:
    root.mkdir(parents=True, exist_ok=False)
    for item in bundle.files:
        target = root / item.path
        target.write_text(item.content.replace("\r\n", "\n"), encoding="utf-8", newline="\n")


def verify_bundle(bundle: ArtifactBundle, root: Path, evidence_dir: Path) -> DeterministicEvidence:
    files = bundle.file_map()
    checks: dict[str, bool] = {
        "exact_authorized_files": set(files) == {"index.html", "styles.css", "app.js", "journey.json", "README.md"},
        "bounded_size": sum(len(value.encode("utf-8")) for value in files.values()) <= 150_000,
        "no_external_network_or_dynamic_code": not any(pattern.search(value) for value in files.values() for pattern in FORBIDDEN),
        "html_document": "<!doctype html" in files["index.html"].casefold(),
        "accessible_controls": "<button" in files["index.html"].casefold() and ("aria-" in files["index.html"].casefold() or "<label" in files["index.html"].casefold()),
        "responsive_css": "@media" in files["styles.css"],
        "no_placeholders": not re.search(r"\b(TODO|FIXME|lorem ipsum)\b", "\n".join(files.values()), re.IGNORECASE),
    }
    issues = [name for name, passed in checks.items() if not passed]
    screenshot_names: list[str] = []
    try:
        journey = json.loads(files["journey.json"])
        journeys = journey.get("journeys", [])
        if not isinstance(journeys, list) or not journeys:
            raise ValueError("journey.json must contain at least one journey")
        evidence_dir.mkdir(parents=True, exist_ok=True)
        with local_server(root) as url, sync_playwright() as playwright:
            executable = os.environ.get("KHALINOS_CHROMIUM_PATH")
            browser = playwright.chromium.launch(
                headless=True,
                executable_path=executable or None,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = browser.new_context(viewport={"width": 1280, "height": 720})
            page = context.new_page()
            page.route("**/*", lambda route: route.continue_() if route.request.url.startswith("http://127.0.0.1:") else route.abort())
            console_errors: list[str] = []
            page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
            for index, entry in enumerate(journeys, start=1):
                page.goto(url, wait_until="networkidle")
                for step in entry.get("steps", []):
                    if set(step) == {"click"}:
                        page.locator(step["click"]).click()
                    elif set(step) == {"press"}:
                        page.keyboard.press(step["press"])
                    elif set(step) == {"assert_text"}:
                        page.get_by_text(step["assert_text"], exact=False).first.wait_for(state="visible")
                    else:
                        raise ValueError(f"unsupported journey step: {step}")
                name = f"journey-{index:02d}.png"
                page.screenshot(path=str(evidence_dir / name), full_page=True)
                screenshot_names.append(name)
            browser.close()
        checks["browser_journeys"] = True
        checks["console_clean"] = not console_errors
        if console_errors:
            issues.append("console_clean: " + " | ".join(console_errors[:3]))
    except Exception as exc:
        checks["browser_journeys"] = False
        issues.append(f"browser_journeys: {type(exc).__name__}: {exc}"[:1000])
    return DeterministicEvidence(
        passed=all(checks.values()),
        checks=checks,
        issues=issues,
        screenshot_names=screenshot_names,
    )

