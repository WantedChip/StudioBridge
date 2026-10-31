"""Smoke tests for static site distribution integrity and Cloudflare deployment.

Validates Cloudflare Workers deployment configuration, edge headers,
canonical redirect rules, static build output, content types, custom 404 handling,
and live or local HTTP smoke endpoints.
"""

import fnmatch
import http.server
import json
import mimetypes
import os
import re
import threading
import urllib.error
import urllib.request
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SITE_DIR = REPO_ROOT / "site"
DIST_DIR = SITE_DIR / "dist"
PUBLIC_DIR = SITE_DIR / "public"
WRANGLER_FILE = SITE_DIR / "wrangler.jsonc"
HEADERS_FILE = PUBLIC_DIR / "_headers"
REDIRECTS_FILE = PUBLIC_DIR / "_redirects"


def parse_jsonc(text: str) -> dict[str, Any]:
    """Parse JSON with single-line and block comments and trailing commas."""
    without_single_line = re.sub(r"//.*$", "", text, flags=re.MULTILINE)
    without_comments = re.sub(r"/\*.*?\*/", "", without_single_line, flags=re.DOTALL)
    without_trailing_commas = re.sub(r",(\s*[}\]])", r"\1", without_comments)
    return json.loads(without_trailing_commas)  # pyright: ignore[reportAny]


def parse_headers_file(path: Path) -> dict[str, dict[str, str]]:
    """Parse Cloudflare _headers file into a mapping of path patterns to headers."""
    rules: dict[str, dict[str, str]] = {}
    current_pattern: str | None = None

    if not path.exists():
        return rules

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if not raw_line.startswith(" ") and not raw_line.startswith("\t"):
            current_pattern = line
            rules.setdefault(current_pattern, {})
        elif current_pattern is not None and ":" in line:
            name, value = line.split(":", 1)
            rules[current_pattern][name.strip().lower()] = value.strip()

    return rules


def parse_redirects_file(path: Path) -> list[tuple[str, str, int]]:
    """Parse Cloudflare _redirects file into a list of (src, dst, status) tuples."""
    redirects: list[tuple[str, str, int]] = []
    if not path.exists():
        return redirects

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split()
        if len(parts) >= 2:
            src = parts[0]
            dst = parts[1]
            status = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else 302
            redirects.append((src, dst, status))

    return redirects


def path_matches_pattern(pattern: str, path: str) -> bool:
    """Check if a URL path matches a Cloudflare route pattern."""
    if pattern == "/*":
        return True
    return fnmatch.fnmatch(path, pattern)


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """HTTP redirect handler that intercepts redirects instead of following them."""

    def http_error_301(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
    ) -> Any:
        return fp

    def http_error_302(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
    ) -> Any:
        return fp


class LocalEdgeSimHandler(http.server.SimpleHTTPRequestHandler):
    """Local HTTP request handler simulating Cloudflare Workers static asset delivery."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(DIST_DIR), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress test noise
        pass

    def do_GET(self) -> None:  # noqa: N802
        clean_path = self.path.split("?")[0]
        redirect_rules = parse_redirects_file(DIST_DIR / "_redirects")

        for src, dst, status in redirect_rules:
            if src.endswith("/*"):
                prefix = src[:-2]
                if clean_path.startswith(prefix):
                    splat = clean_path[len(prefix) :]
                    target = dst.replace(":splat", splat.lstrip("/"))
                    self.send_response(status)
                    self.send_header("Location", target)
                    self.end_headers()
                    return
            elif clean_path == src:
                self.send_response(status)
                self.send_header("Location", dst)
                self.end_headers()
                return

        super().do_GET()

    def end_headers(self) -> None:
        headers_rules = parse_headers_file(DIST_DIR / "_headers")
        clean_path = self.path.split("?")[0]

        for pattern, headers in headers_rules.items():
            if path_matches_pattern(pattern, clean_path):
                for name, value in headers.items():
                    # Send with title casing
                    self.send_header(name.title(), value)

        super().end_headers()

    def send_error(
        self,
        code: int,
        message: str | None = None,
        explain: str | None = None,
    ) -> None:
        if code == 404:
            custom_404 = DIST_DIR / "404.html"
            if custom_404.exists():
                content = custom_404.read_bytes()
                self.send_response(404)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
        super().send_error(code, message, explain)


@pytest.fixture(scope="module")
def local_server_url() -> Generator[str, None, None]:
    """Spins up a lightweight local HTTP server simulating edge asset delivery."""
    if not (DIST_DIR / "index.html").exists():
        pytest.skip("Static distribution directory not built yet.")

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), LocalEdgeSimHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{port}"
    try:
        yield base_url
    finally:
        server.shutdown()
        server.server_close()


# ==============================================================================
# 1. Wrangler Deployment Configuration Tests
# ==============================================================================


class TestWranglerConfiguration:
    """Validates Cloudflare Workers deployment configuration."""

    def test_wrangler_file_exists(self) -> None:
        """Verify wrangler.jsonc exists in site root."""
        # req: DIST-05
        assert WRANGLER_FILE.exists(), f"Missing configuration: {WRANGLER_FILE}"

    def test_wrangler_config_schema_and_values(self) -> None:
        """Verify configuration parameters conform to edge requirements."""
        # req: DIST-05
        content = WRANGLER_FILE.read_text(encoding="utf-8")
        config = parse_jsonc(content)

        assert config.get("name") == "studiobridge-site"
        assert config.get("compatibility_date") == "2026-10-01"

        flags = config.get("compatibility_flags", [])
        assert isinstance(flags, list)
        assert "nodejs_compat" in flags

        assets = config.get("assets", {})
        assert isinstance(assets, dict)
        assert assets.get("directory") == "./dist"
        assert assets.get("not_found_handling") == "404-page"
        assert assets.get("html_handling") == "auto-trailing-slash"

        build = config.get("build", {})
        assert isinstance(build, dict)
        assert build.get("command") == "npm run build"
        watch_dirs = build.get("watch_dir", [])
        assert isinstance(watch_dirs, list)
        assert "./" in watch_dirs


# ==============================================================================
# 2. Edge Security Headers Tests
# ==============================================================================


class TestSecurityHeaders:
    """Validates edge caching and security headers defined in _headers."""

    def test_headers_file_present(self) -> None:
        """Verify _headers exists in source public directory."""
        # req: WEB-10, req: DIST-05
        assert HEADERS_FILE.exists()

    def test_headers_file_copied_to_dist(self) -> None:
        """Verify _headers is copied into distribution directory during build."""
        # req: WEB-10, req: DIST-05
        dist_headers = DIST_DIR / "_headers"
        assert dist_headers.exists()

    def test_global_security_headers(self) -> None:
        """Verify global route (/*) defines required security headers."""
        # req: WEB-10, req: DIST-05
        rules = parse_headers_file(HEADERS_FILE)
        assert "/*" in rules

        global_headers = rules["/*"]

        # HSTS enforcement
        assert "strict-transport-security" in global_headers
        hsts = global_headers["strict-transport-security"]
        assert "max-age=31536000" in hsts
        assert "includesubdomains" in hsts.lower()

        # MIME sniffing prevention
        assert global_headers.get("x-content-type-options") == "nosniff"

        # Frame denial (clickjacking defense)
        assert global_headers.get("x-frame-options") == "DENY"

        # Referrer policy
        assert global_headers.get("referrer-policy") == "strict-origin-when-cross-origin"

        # Permissions policy
        assert "permissions-policy" in global_headers

        # Content-Security-Policy
        assert "content-security-policy" in global_headers
        csp = global_headers["content-security-policy"]
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "base-uri 'self'" in csp
        assert "form-action 'self'" in csp

        # Edge default caching
        assert "cache-control" in global_headers
        assert "must-revalidate" in global_headers["cache-control"]

    def test_immutable_static_asset_caching(self) -> None:
        """Verify hashed assets have long-lived immutable cache directives."""
        # req: WEB-10, req: DIST-05
        rules = parse_headers_file(HEADERS_FILE)

        assert "/_astro/*" in rules
        astro_cc = rules["/_astro/*"].get("cache-control", "")
        assert "immutable" in astro_cc
        assert "max-age=31536000" in astro_cc

        assert "/fonts/*" in rules
        fonts_cc = rules["/fonts/*"].get("cache-control", "")
        assert "immutable" in fonts_cc
        assert "max-age=31536000" in fonts_cc


# ==============================================================================
# 3. Canonical Redirect Rules Tests
# ==============================================================================


class TestRedirectRules:
    """Validates URL canonicalization and redirect mappings."""

    def test_redirects_file_present(self) -> None:
        """Verify _redirects exists in source public directory."""
        # req: WEB-10
        assert REDIRECTS_FILE.exists()

    def test_redirects_file_copied_to_dist(self) -> None:
        """Verify _redirects is copied into distribution directory during build."""
        # req: WEB-10
        dist_redirects = DIST_DIR / "_redirects"
        assert dist_redirects.exists()

    def test_documentation_canonical_redirects(self) -> None:
        """Verify legacy /documentation paths redirect permanently to /docs/."""
        # req: WEB-08, req: WEB-10
        redirects = parse_redirects_file(REDIRECTS_FILE)
        redirect_dict = {src: (dst, status) for src, dst, status in redirects}

        assert "/documentation" in redirect_dict
        assert redirect_dict["/documentation"] == ("/docs/", 301)

        assert "/documentation/*" in redirect_dict
        assert redirect_dict["/documentation/*"] == ("/docs/:splat", 301)

        assert "/api" in redirect_dict
        assert redirect_dict["/api"] == ("/docs/api/", 301)

        assert "/api/*" in redirect_dict
        assert redirect_dict["/api/*"] == ("/docs/api/:splat", 301)

    def test_community_redirects(self) -> None:
        """Verify community links redirect to canonical repositories and packages."""
        # req: WEB-10
        redirects = parse_redirects_file(REDIRECTS_FILE)
        redirect_dict = {src: (dst, status) for src, dst, status in redirects}

        assert "/github" in redirect_dict
        assert redirect_dict["/github"][0].startswith("https://github.com/")

        assert "/repo" in redirect_dict
        assert redirect_dict["/repo"][0].startswith("https://github.com/")

        assert "/releases" in redirect_dict
        assert "releases" in redirect_dict["/releases"][0]

        assert "/issues" in redirect_dict
        assert "issues" in redirect_dict["/issues"][0]

        assert "/pypi" in redirect_dict
        assert "pypi.org" in redirect_dict["/pypi"][0]

        assert "/npm" in redirect_dict
        assert "npmjs.com" in redirect_dict["/npm"][0]

    def test_all_redirect_status_codes_valid(self) -> None:
        """Verify all redirect rules specify standard HTTP redirect codes."""
        # req: WEB-10
        redirects = parse_redirects_file(REDIRECTS_FILE)
        for src, dst, status in redirects:
            err = f"Invalid status {status} for rule {src} -> {dst}"
            assert status in (301, 302, 307, 308), err


# ==============================================================================
# 4. Static Distribution Integrity Tests
# ==============================================================================


class TestStaticDistributionIntegrity:
    """Validates built static site assets and content types."""

    def test_distribution_directory_exists(self) -> None:
        """Verify site/dist exists after static build."""
        # req: WEB-10, req: DIST-05
        assert DIST_DIR.exists(), f"Distribution directory missing: {DIST_DIR}"
        assert DIST_DIR.is_dir()

    def test_core_distribution_files_exist(self) -> None:
        """Verify required entrypoint files exist and have non-zero size."""
        # req: WEB-08, req: WEB-09, req: WEB-10, req: DIST-05
        required_files = [
            DIST_DIR / "index.html",
            DIST_DIR / "docs" / "index.html",
            DIST_DIR / "compat" / "index.html",
            DIST_DIR / "404.html",
            DIST_DIR / "llms.txt",
            DIST_DIR / "llms-full.txt",
            DIST_DIR / "robots.txt",
            DIST_DIR / "sitemap-index.xml",
            DIST_DIR / "favicon.svg",
            DIST_DIR / "og.png",
            DIST_DIR / "og.svg",
        ]

        for file_path in required_files:
            assert file_path.exists(), f"Required build file missing: {file_path}"
            assert file_path.stat().st_size > 0, f"Build file is empty: {file_path}"

    def test_landing_page_content(self) -> None:
        """Verify landing page HTML contains essential metadata and tokens."""
        # req: WEB-10
        landing_html = (DIST_DIR / "index.html").read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in landing_html or "<!doctype html>" in landing_html
        assert "StudioBridge" in landing_html
        assert '<meta name="viewport"' in landing_html

    def test_docs_page_content(self) -> None:
        """Verify documentation index contains content and search integration."""
        # req: WEB-08
        docs_html = (DIST_DIR / "docs" / "index.html").read_text(encoding="utf-8")
        assert "StudioBridge" in docs_html
        assert "pagefind" in docs_html.lower()

    def test_compat_page_content(self) -> None:
        """Verify compatibility matrix page contains table and capability data."""
        # req: WEB-10
        compat_html = (DIST_DIR / "compat" / "index.html").read_text(encoding="utf-8")
        assert "Capability Matrix" in compat_html or "compatibility" in compat_html.lower()

    def test_custom_404_page_content(self) -> None:
        """Verify 404 error page is customized and styled."""
        # req: WEB-10
        error_html = (DIST_DIR / "404.html").read_text(encoding="utf-8")
        assert "<html" in error_html
        assert "404" in error_html
        assert "StudioBridge" in error_html or "Not Found" in error_html

    def test_llms_txt_content(self) -> None:
        """Verify llms.txt provides concise project overview and documentation links."""
        # req: WEB-09
        llms_content = (DIST_DIR / "llms.txt").read_text(encoding="utf-8")
        assert "# StudioBridge" in llms_content
        assert "/llms-full.txt" in llms_content
        assert "/docs" in llms_content

    def test_robots_txt_content(self) -> None:
        """Verify robots.txt allows crawling and points to sitemap."""
        # req: WEB-09
        robots_content = (DIST_DIR / "robots.txt").read_text(encoding="utf-8")
        assert "User-agent: *" in robots_content
        assert "Sitemap:" in robots_content

    def test_asset_mime_types(self) -> None:
        """Verify standard static file extensions map to appropriate MIME types."""
        # req: WEB-10
        type_checks: list[tuple[str, str]] = [
            ("index.html", "text/html"),
            ("robots.txt", "text/plain"),
            ("llms.txt", "text/plain"),
            ("favicon.svg", "image/svg+xml"),
            ("og.png", "image/png"),
            ("sitemap-index.xml", "application/xml"),
        ]

        for filename, expected_mime in type_checks:
            guessed_type, _ = mimetypes.guess_type(filename)
            if expected_mime == "application/xml" and guessed_type == "text/xml":
                continue
            err = f"MIME mismatch for {filename}: {guessed_type} != {expected_mime}"
            assert guessed_type == expected_mime, err


# ==============================================================================
# 5. Live & Simulated HTTP Endpoint Smoke Tests
# ==============================================================================


class TestHttpEndpointSmoke:
    """Validates HTTP request and response behavior for edge deployment."""

    def _resolve_base_url(self, local_url: str) -> str:
        # Check if live target URL is supplied via environment
        live_url = os.environ.get("SITE_URL", "").rstrip("/")
        if live_url:
            return live_url
        return local_url

    def test_root_landing_page_endpoint(self, local_server_url: str) -> None:
        """Verify GET / returns HTTP 200 with HTML content and security headers."""
        # req: WEB-10, req: DIST-05
        base_url = self._resolve_base_url(local_server_url)
        req = urllib.request.Request(
            f"{base_url}/",
            headers={"User-Agent": "StudioBridge-Deploy-Smoke/1.0"},
        )

        with urllib.request.urlopen(req, timeout=10) as resp:
            assert resp.status == 200
            content_type = resp.headers.get("Content-Type", "")
            assert "text/html" in content_type

            # Header verification
            nosniff = resp.headers.get("X-Content-Type-Options")
            assert nosniff == "nosniff"

            body = resp.read().decode("utf-8")
            assert "StudioBridge" in body

    def test_docs_page_endpoint(self, local_server_url: str) -> None:
        """Verify GET /docs/ returns HTTP 200 with documentation HTML."""
        # req: WEB-08, req: WEB-10
        base_url = self._resolve_base_url(local_server_url)
        req = urllib.request.Request(
            f"{base_url}/docs/",
            headers={"User-Agent": "StudioBridge-Deploy-Smoke/1.0"},
        )

        with urllib.request.urlopen(req, timeout=10) as resp:
            assert resp.status == 200
            content_type = resp.headers.get("Content-Type", "")
            assert "text/html" in content_type

    def test_compat_page_endpoint(self, local_server_url: str) -> None:
        """Verify GET /compat/ returns HTTP 200 with compatibility table."""
        # req: WEB-10
        base_url = self._resolve_base_url(local_server_url)
        req = urllib.request.Request(
            f"{base_url}/compat/",
            headers={"User-Agent": "StudioBridge-Deploy-Smoke/1.0"},
        )

        with urllib.request.urlopen(req, timeout=10) as resp:
            assert resp.status == 200
            content_type = resp.headers.get("Content-Type", "")
            assert "text/html" in content_type

    def test_llms_txt_endpoint(self, local_server_url: str) -> None:
        """Verify GET /llms.txt returns HTTP 200 with text/plain."""
        # req: WEB-09, req: WEB-10
        base_url = self._resolve_base_url(local_server_url)
        req = urllib.request.Request(
            f"{base_url}/llms.txt",
            headers={"User-Agent": "StudioBridge-Deploy-Smoke/1.0"},
        )

        with urllib.request.urlopen(req, timeout=10) as resp:
            assert resp.status == 200
            content_type = resp.headers.get("Content-Type", "")
            assert "text/plain" in content_type
            body = resp.read().decode("utf-8")
            assert "# StudioBridge" in body

    def test_robots_txt_endpoint(self, local_server_url: str) -> None:
        """Verify GET /robots.txt returns HTTP 200 with text/plain."""
        # req: WEB-09, req: WEB-10
        base_url = self._resolve_base_url(local_server_url)
        req = urllib.request.Request(
            f"{base_url}/robots.txt",
            headers={"User-Agent": "StudioBridge-Deploy-Smoke/1.0"},
        )

        with urllib.request.urlopen(req, timeout=10) as resp:
            assert resp.status == 200
            content_type = resp.headers.get("Content-Type", "")
            assert "text/plain" in content_type
            body = resp.read().decode("utf-8")
            assert "User-agent:" in body

    def test_custom_404_error_handling(self, local_server_url: str) -> None:
        """Verify requesting a non-existent URL returns HTTP 404 with custom error page."""
        # req: WEB-10
        base_url = self._resolve_base_url(local_server_url)
        req = urllib.request.Request(
            f"{base_url}/nonexistent-path-for-smoke-test-404",
            headers={"User-Agent": "StudioBridge-Deploy-Smoke/1.0"},
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                # If server returns 200 for 404 (e.g. SPA fallback), assert failure
                pytest.fail(f"Expected HTTP 404 but got HTTP {resp.status}")
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
            error_body = exc.read().decode("utf-8")
            assert "404" in error_body

    def test_canonical_redirect_execution(self, local_server_url: str) -> None:
        """Verify /documentation path issues HTTP 301 redirecting to /docs/."""
        # req: WEB-08, req: WEB-10
        base_url = self._resolve_base_url(local_server_url)
        opener = urllib.request.build_opener(NoRedirectHandler)

        req = urllib.request.Request(
            f"{base_url}/documentation",
            headers={"User-Agent": "StudioBridge-Deploy-Smoke/1.0"},
        )

        try:
            resp = opener.open(req, timeout=10)
            assert resp.status == 301
            location = resp.headers.get("Location")
            assert location in ("/docs/", f"{base_url}/docs/")
        except urllib.error.HTTPError as exc:
            assert exc.code == 301
            location = exc.headers.get("Location")
            assert location in ("/docs/", f"{base_url}/docs/")


# ==============================================================================
# 6. Live Edge Network Tests (Skipped when SITE_URL is not set)
# ==============================================================================


@pytest.mark.skipif(
    not os.environ.get("SITE_URL"),
    reason="SITE_URL not set; skipping external live edge network smoke test",
)
class TestLiveEdgeProductionNetwork:
    """Verifies live production Cloudflare deployment when SITE_URL is supplied."""

    def test_live_production_edge_security_headers(self) -> None:
        """Verify live deployed edge responds with strict security headers."""
        # req: WEB-10, req: DIST-05
        site_url = os.environ["SITE_URL"].rstrip("/")
        req = urllib.request.Request(
            f"{site_url}/",
            headers={"User-Agent": "StudioBridge-Deploy-Smoke/1.0"},
        )

        with urllib.request.urlopen(req, timeout=15) as resp:
            assert resp.status == 200
            headers = resp.headers

            assert headers.get("X-Content-Type-Options") == "nosniff"
            assert headers.get("X-Frame-Options") == "DENY"

            hsts = headers.get("Strict-Transport-Security")
            assert hsts is not None
            assert "max-age=" in hsts

            csp = headers.get("Content-Security-Policy")
            assert csp is not None
            assert "default-src 'self'" in csp

    def test_live_production_core_routes(self) -> None:
        """Verify all critical static routes return HTTP 200 on production domain."""
        # req: WEB-08, req: WEB-09, req: WEB-10
        site_url = os.environ["SITE_URL"].rstrip("/")
        routes = ["/", "/docs/", "/compat/", "/llms.txt", "/robots.txt"]

        for route in routes:
            req = urllib.request.Request(
                f"{site_url}{route}",
                headers={"User-Agent": "StudioBridge-Deploy-Smoke/1.0"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                assert resp.status == 200, f"Route {route} returned HTTP {resp.status}"
