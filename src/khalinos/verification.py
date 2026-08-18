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

MAX_JOURNEYS = 12
MAX_STEPS_PER_JOURNEY = 80
MAX_WAIT_MS = 12_000
MAX_TOTAL_WAIT_MS = 30_000
ASSERTION_ACTIONS = {
    "assert_text",
    "assert_count",
    "assert_attribute",
    "assert_class",
    "assert_state",
}
ATTRIBUTE_NAME = re.compile(r"^[A-Za-z_:][-A-Za-z0-9_:.]{0,79}$")
CLASS_NAME = re.compile(r"^[A-Za-z_][-A-Za-z0-9_]{0,79}$")


def _chromium_executable() -> str | None:
    configured = os.environ.get("KHALINOS_CHROMIUM_PATH")
    if configured:
        return configured
    if os.name != "nt":
        return None
    candidates = [
        Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
    ]
    return str(next((path for path in candidates if path.is_file()), "")) or None


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


def _compare_count(actual: int, operator: str, expected: int) -> bool:
    comparisons = {
        "eq": actual == expected,
        "gt": actual > expected,
        "gte": actual >= expected,
        "lt": actual < expected,
        "lte": actual <= expected,
    }
    if operator not in comparisons:
        raise ValueError(f"unsupported count operator: {operator}")
    return comparisons[operator]


def _assertion_summary(page, action: str, value: object) -> str:
    if action == "assert_text":
        if not isinstance(value, str) or not value.strip():
            raise ValueError("assert_text requires visible text")
        locator = page.get_by_text(value, exact=False).first
        locator.wait_for(state="visible")
        observed = (locator.text_content() or "").strip()
        return f"assert_text expected={value!r} observed={observed!r}"
    if not isinstance(value, dict):
        raise ValueError(f"{action} requires an object")
    selector = value.get("selector")
    if not isinstance(selector, str) or not selector.strip() or len(selector) > 500:
        raise ValueError(f"{action} requires a bounded CSS selector")
    locator = page.locator(selector)
    if action == "assert_count":
        if set(value) != {"selector", "operator", "value"}:
            raise ValueError("assert_count requires selector, operator, and value")
        expected = value["value"]
        if not isinstance(expected, int) or isinstance(expected, bool) or not 0 <= expected <= 10_000:
            raise ValueError("assert_count value must be an integer from 0 to 10000")
        actual = locator.count()
        operator = value["operator"]
        if not isinstance(operator, str) or not _compare_count(actual, operator, expected):
            raise AssertionError(f"count {actual} does not satisfy {operator} {expected} for {selector}")
        return f"assert_count selector={selector!r} observed={actual} {operator} {expected}"
    if action == "assert_attribute":
        if set(value) != {"selector", "name", "operator", "value"}:
            raise ValueError("assert_attribute requires selector, name, operator, and value")
        name = value["name"]
        expected = value["value"]
        operator = value["operator"]
        if not isinstance(name, str) or not ATTRIBUTE_NAME.fullmatch(name):
            raise ValueError("assert_attribute has an invalid attribute name")
        if not isinstance(expected, str) or len(expected) > 500:
            raise ValueError("assert_attribute value must be bounded text")
        if operator not in {"eq", "contains", "not_equals"}:
            raise ValueError(f"unsupported attribute operator: {operator}")
        locator.first.wait_for(state="attached")
        actual = locator.first.get_attribute(name)
        passed = (
            actual == expected if operator == "eq"
            else expected in (actual or "") if operator == "contains"
            else actual != expected
        )
        if not passed:
            raise AssertionError(f"attribute {name}={actual!r} does not satisfy {operator} {expected!r}")
        return f"assert_attribute selector={selector!r} {name} observed={actual!r} {operator} {expected!r}"
    if action == "assert_class":
        if set(value) != {"selector", "includes", "excludes"}:
            raise ValueError("assert_class requires selector, includes, and excludes")
        includes = value["includes"]
        excludes = value["excludes"]
        if not isinstance(includes, list) or not isinstance(excludes, list) or not includes:
            raise ValueError("assert_class requires at least one included class")
        if len(includes) + len(excludes) > 20 or not all(
            isinstance(item, str) and CLASS_NAME.fullmatch(item) for item in [*includes, *excludes]
        ):
            raise ValueError("assert_class contains an invalid class name")
        locator.first.wait_for(state="attached")
        actual = set((locator.first.get_attribute("class") or "").split())
        if not set(includes).issubset(actual) or set(excludes).intersection(actual):
            raise AssertionError(
                f"classes {sorted(actual)!r} do not include {includes!r} and exclude {excludes!r}"
            )
        return f"assert_class selector={selector!r} observed={sorted(actual)!r}"
    if action == "assert_state":
        if set(value) != {"selector", "state"}:
            raise ValueError("assert_state requires selector and state")
        state = value["state"]
        checks = {
            "visible": locator.first.is_visible,
            "hidden": locator.first.is_hidden,
            "enabled": locator.first.is_enabled,
            "disabled": locator.first.is_disabled,
            "checked": locator.first.is_checked,
            "unchecked": lambda: not locator.first.is_checked(),
        }
        if state not in checks:
            raise ValueError(f"unsupported element state: {state}")
        observed = checks[state]()
        if not observed:
            raise AssertionError(f"selector {selector!r} is not {state}")
        return f"assert_state selector={selector!r} observed={state}"
    raise ValueError(f"unsupported assertion action: {action}")


def verify_bundle(
    bundle: ArtifactBundle,
    root: Path,
    evidence_dir: Path,
    required_criteria: list[str] | None = None,
) -> DeterministicEvidence:
    files = bundle.file_map()
    checks: dict[str, bool] = {
        "exact_authorized_files": set(files) == {"index.html", "styles.css", "app.js", "journey.json", "README.md"},
        "bounded_size": sum(len(value.encode("utf-8")) for value in files.values()) <= 150_000,
        "no_external_network_or_dynamic_code": not any(pattern.search(value) for value in files.values() for pattern in FORBIDDEN),
        "html_document": "<!doctype html" in files["index.html"].casefold(),
        "local_assets_linked": bool(re.search(r"href=[\"']styles\.css[\"']", files["index.html"], re.IGNORECASE))
        and bool(re.search(r"src=[\"']app\.js[\"']", files["index.html"], re.IGNORECASE)),
        "accessible_controls": "<button" in files["index.html"].casefold() and ("aria-" in files["index.html"].casefold() or "<label" in files["index.html"].casefold()),
        "responsive_layout": False,
        "no_placeholders": not re.search(r"\b(TODO|FIXME|lorem ipsum)\b", "\n".join(files.values()), re.IGNORECASE),
    }
    issues = [name for name, passed in checks.items() if not passed and name != "responsive_layout"]
    screenshot_names: list[str] = []
    required = list(required_criteria or [])
    criterion_evidence: dict[str, list[str]] = {criterion: [] for criterion in required}
    try:
        journey = json.loads(files["journey.json"])
        if not isinstance(journey, dict) or set(journey) != {"journeys"}:
            raise ValueError('journey.json must use exactly the wrapper {"journeys":[...]}')
        journeys = journey.get("journeys", [])
        if not isinstance(journeys, list) or not journeys:
            raise ValueError("journey.json must contain at least one journey")
        if len(journeys) > MAX_JOURNEYS:
            raise ValueError(f"journey.json may contain at most {MAX_JOURNEYS} journeys")
        total_wait_ms = 0
        evidence_dir.mkdir(parents=True, exist_ok=True)
        with local_server(root) as url, sync_playwright() as playwright:
            executable = _chromium_executable()
            browser = playwright.chromium.launch(
                headless=True,
                executable_path=executable or None,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = browser.new_context(viewport={"width": 1280, "height": 720})
            console_errors: list[str] = []
            responsive_journeys: list[bool] = []
            for index, entry in enumerate(journeys, start=1):
                if not isinstance(entry, dict) or not set(entry).issubset({"name", "criterion", "random_seed", "steps"}):
                    raise ValueError("each journey may contain only name, criterion, random_seed, and steps")
                name_value = entry.get("name")
                if not isinstance(name_value, str) or not name_value.strip() or len(name_value) > 120:
                    raise ValueError("each journey requires a bounded name")
                claimed = entry.get("criterion")
                if required and (not isinstance(claimed, str) or claimed not in required):
                    raise ValueError("each active-Quest journey criterion must exactly match one active criterion")
                if not required and claimed is not None:
                    raise ValueError("visual-foundation journeys cannot claim an inactive Quest criterion")
                steps = entry.get("steps", [])
                if not isinstance(steps, list) or not steps or len(steps) > MAX_STEPS_PER_JOURNEY:
                    raise ValueError(f"each journey requires 1..{MAX_STEPS_PER_JOURNEY} steps")
                seed = entry.get("random_seed")
                if seed is not None and (
                    not isinstance(seed, int) or isinstance(seed, bool) or not 0 <= seed <= 4_294_967_295
                ):
                    raise ValueError("random_seed must be a uint32 integer")
                page = context.new_page()
                page.route("**/*", lambda route: route.continue_() if route.request.url.startswith("http://127.0.0.1:") else route.abort())
                page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
                if seed is not None:
                    page.add_init_script(
                        f"let __khalinosState={seed}>>>0; Math.random=()=>{{__khalinosState=(1664525*__khalinosState+1013904223)>>>0; return __khalinosState/4294967296;}};"
                    )
                page.goto(url, wait_until="networkidle")
                assertion_summaries: list[str] = []
                for step in steps:
                    if not isinstance(step, dict) or len(step) != 1:
                        raise ValueError("each journey step must contain exactly one typed action")
                    action, value = next(iter(step.items()))
                    if action == "click":
                        if not isinstance(value, str) or not value.strip() or len(value) > 500:
                            raise ValueError("click requires a bounded CSS selector")
                        page.locator(value).click()
                    elif action == "right_click":
                        if not isinstance(value, str) or not value.strip() or len(value) > 500:
                            raise ValueError("right_click requires a bounded CSS selector")
                        page.locator(value).click(button="right")
                    elif action == "press":
                        if not isinstance(value, str) or not value.strip() or len(value) > 80:
                            raise ValueError("press requires a bounded keyboard key")
                        page.keyboard.press(value)
                    elif action == "wait_ms":
                        if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= MAX_WAIT_MS:
                            raise ValueError(f"wait_ms must be an integer from 1 to {MAX_WAIT_MS}")
                        total_wait_ms += value
                        if total_wait_ms > MAX_TOTAL_WAIT_MS:
                            raise ValueError(f"journeys may wait at most {MAX_TOTAL_WAIT_MS} ms in total")
                        page.wait_for_timeout(value)
                    elif action in ASSERTION_ACTIONS:
                        assertion_summaries.append(_assertion_summary(page, action, value))
                    else:
                        raise ValueError(f"unsupported journey step: {step}")
                if claimed is not None and not assertion_summaries:
                    raise ValueError(f"journey {name_value!r} claims criteria without a runtime assertion")
                if claimed is not None:
                    criterion_evidence[claimed].extend(
                        f"journey={name_value!r}; seed={seed!r}; {summary}" for summary in assertion_summaries
                    )
                page.set_viewport_size({"width": 320, "height": 720})
                responsive_journeys.append(bool(page.evaluate("""() => {
                    const tolerance = 1;
                    const visible = [...document.querySelectorAll('body > *, button, input, select, textarea')]
                      .filter((element) => {
                        const style = getComputedStyle(element);
                        const rect = element.getBoundingClientRect();
                        return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
                      });
                    const contained = visible.every((element) => {
                      const rect = element.getBoundingClientRect();
                      return rect.left >= -tolerance && rect.right <= window.innerWidth + tolerance;
                    });
                    return contained && document.documentElement.scrollWidth <= window.innerWidth + tolerance;
                }""")))
                page.set_viewport_size({"width": 1280, "height": 720})
                name = f"journey-{index:02d}.png"
                page.screenshot(path=str(evidence_dir / name), full_page=True)
                screenshot_names.append(name)
                page.close()
            browser.close()
        missing = [criterion for criterion, evidence in criterion_evidence.items() if not evidence]
        if missing:
            raise ValueError("acceptance criteria without direct runtime assertion evidence: " + " | ".join(missing))
        checks["browser_journeys"] = True
        checks["criterion_runtime_coverage"] = not missing
        checks["console_clean"] = not console_errors
        checks["responsive_layout"] = bool(responsive_journeys) and all(responsive_journeys)
        if not checks["responsive_layout"]:
            issues.append("responsive_layout: visible content overflows a 320px viewport")
        if console_errors:
            issues.append("console_clean: " + " | ".join(console_errors[:3]))
    except Exception as exc:
        checks["browser_journeys"] = False
        if required:
            checks["criterion_runtime_coverage"] = False
        issues.append(f"browser_journeys: {type(exc).__name__}: {exc}"[:1000])
    return DeterministicEvidence(
        passed=all(checks.values()),
        checks=checks,
        issues=issues,
        screenshot_names=screenshot_names,
        criterion_evidence=criterion_evidence,
    )
