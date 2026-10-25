"""Check that the Vite dev server serves the app and proxies the API.

Usage::

    python frontend_check.py
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

FRONTEND = "http://localhost:5173"


def main() -> int:
    results: list[tuple[str, bool, str]] = []

    def check(label: str, ok: bool, detail: str = "") -> None:
        results.append((label, ok, detail))
        print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f" - {detail}" if detail else ""))

    # 1. The dev server serves the HTML shell.
    try:
        with urllib.request.urlopen(f"{FRONTEND}/", timeout=20) as response:
            html = response.read().decode("utf-8")
            check("frontend serves index.html", response.status == 200, f"status={response.status}")
            check(
                "index.html mounts the React root",
                'id="root"' in html and "/src/main.jsx" in html,
            )
    except urllib.error.HTTPError as exc:
        check("frontend serves index.html", False, f"HTTP {exc.code}")
    except Exception as exc:  # noqa: BLE001
        check("frontend serves index.html", False, str(exc))
        return 1

    # 2. The Vite dev server proxies /api to the FastAPI backend.
    try:
        with urllib.request.urlopen(f"{FRONTEND}/api/health", timeout=20) as response:
            payload = json.loads(response.read())
            check(
                "vite proxies /api to the backend",
                response.status == 200 and payload.get("record_count", 0) > 0,
                f"records={payload.get('record_count')}, model_loaded={payload.get('model_loaded')}",
            )
    except urllib.error.HTTPError as exc:
        check("vite proxies /api to the backend", False, f"HTTP {exc.code}")
    except Exception as exc:  # noqa: BLE001
        check("vite proxies /api to the backend", False, str(exc))

    # 3. The JSX modules are transformed and served.
    for module in ("/src/main.jsx", "/src/App.jsx", "/src/pages/PublicDashboard.jsx",
                   "/src/pages/AuthorityDashboard.jsx", "/src/pages/AuthorityLogin.jsx",
                   "/src/components/ProtectedRoute.jsx", "/src/context/AuthContext.jsx",
                   "/src/components/CrowdBadge.jsx", "/src/components/TransitMap.jsx",
                   "/src/components/States.jsx", "/src/components/AnswerCard.jsx",
                   "/src/components/AlternativeCard.jsx", "/src/components/StationPicker.jsx",
                   "/src/components/ModeSwitch.jsx", "/src/components/ChartCard.jsx",
                   "/src/components/StatCard.jsx", "/src/components/DataNotice.jsx",
                   "/src/components/CollapsibleSection.jsx",
                   "/src/lib/format.js", "/src/styles/tokens.css",
                   "/src/api/client.js"):
        try:
            with urllib.request.urlopen(f"{FRONTEND}{module}", timeout=20) as response:
                body = response.read().decode("utf-8", errors="replace")
                check(f"module {module}", response.status == 200 and len(body) > 100)
        except Exception as exc:  # noqa: BLE001
            check(f"module {module}", False, str(exc))

    # 4. The public API stays open, the authority API is protected.
    try:
        with urllib.request.urlopen(f"{FRONTEND}/api/predict/day?route_id=M1", timeout=20) as response:
            payload = json.loads(response.read())
            check(
                "the public prediction endpoint is reachable without a token",
                response.status == 200 and len(payload.get("predictions", [])) == 24,
            )
    except urllib.error.HTTPError as exc:
        check("the public prediction endpoint is reachable without a token", False,
              f"HTTP {exc.code}")
    except Exception as exc:  # noqa: BLE001
        check("the public prediction endpoint is reachable without a token", False, str(exc))

    try:
        with urllib.request.urlopen(f"{FRONTEND}/api/authority/stats", timeout=20) as response:
            check("the authority endpoint requires a token", False,
                  f"the endpoint answered {response.status} without a token")
    except urllib.error.HTTPError as exc:
        check("the authority endpoint requires a token", exc.code == 401, f"HTTP {exc.code}")
    except Exception as exc:  # noqa: BLE001
        check("the authority endpoint requires a token", False, str(exc))

    passed = sum(1 for _, ok, _ in results if ok)
    print("=" * 60)
    print(f"{passed}/{len(results)} frontend checks passed")
    print("=" * 60)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
