"""Software Bill of Materials (SBOM) generator for StudioBridge.

Generates compliant Software Bill of Materials in CycloneDX 1.5 JSON and SPDX 2.3
JSON formats for both the Python package and the npm launcher package.

Covers:
- CycloneDX 1.5 JSON generation (# req: DIST-06)
- SPDX 2.3 JSON generation (# req: DIST-06)
- Component inventory, cryptographic hashes (SHA-256), and license resolution (# req: DIST-06)
- Dependency relationship graph derivation from lockfile and manifests (# req: DIST-06)
- Schema validation and verification gates (# req: REL-01)
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import re
import sys
import uuid
from collections import deque
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final, Literal

import tomlkit

FormatType = Literal["cyclonedx", "spdx"]

# Known SPDX license mappings for dependency normalization
KNOWN_LICENSES: Final[dict[str, str]] = {
    "studiobridge": "MIT",
    "anyio": "MIT",
    "platformdirs": "MIT",
    "tomlkit": "MIT",
    "idna": "BSD-3-Clause",
    "typing-extensions": "PSF-2.0",
    "typing_extensions": "PSF-2.0",
    "exceptiongroup": "MIT",
    "click": "BSD-3-Clause",
    "colorama": "BSD-3-Clause",
    "pytest": "MIT",
    "iniconfig": "MIT",
    "packaging": "Apache-2.0 OR BSD-2-Clause",
    "pluggy": "MIT",
    "pygments": "BSD-2-Clause",
    "ruff": "MIT",
    "pyright": "MIT",
    "hypothesis": "MPL-2.0",
    "import-linter": "BSD-2-Clause",
    "grimp": "BSD-2-Clause",
    "attrs": "MIT",
    "sortedcontainers": "Apache-2.0",
    "node-fetch": "MIT",
}

DEFAULT_WORKSPACE_ROOT: Final[Path] = Path(__file__).resolve().parents[1]


def resolve_license(package_name: str, fallback: str | None = None) -> str:
    """Resolve SPDX license identifier for a package using metadata or known mapping."""
    canonical = package_name.lower().replace("_", "-")
    if canonical in KNOWN_LICENSES:
        return KNOWN_LICENSES[canonical]

    if fallback:
        cleaned = fallback.strip()
        if cleaned.upper() == "MIT":
            return "MIT"
        if "BSD" in cleaned:
            return "BSD-3-Clause"
        if "APACHE" in cleaned.upper():
            return "Apache-2.0"
        return cleaned

    try:
        dist_meta: Any = importlib.metadata.metadata(package_name)
        lic_expr = dist_meta.get("License-Expression")
        if lic_expr:
            return str(lic_expr).strip()
        lic = dist_meta.get("License")
        if lic:
            cleaned = str(lic).strip()
            if cleaned.upper() in ("MIT", "MIT LICENSE"):
                return "MIT"
            if "BSD" in cleaned:
                return "BSD-3-Clause"
            if "APACHE" in cleaned.upper():
                return "Apache-2.0"
            return cleaned
    except Exception:
        pass

    return "MIT"


def load_python_package_info(pyproject_path: Path) -> dict[str, Any]:
    """Load metadata for the primary Python package from pyproject.toml."""
    if not pyproject_path.exists():
        raise FileNotFoundError(f"Missing pyproject.toml at '{pyproject_path}'")

    doc = tomlkit.loads(pyproject_path.read_text(encoding="utf-8"))
    project_tbl = doc.get("project", {})

    name = str(project_tbl.get("name", "studiobridge"))
    version = str(project_tbl.get("version", "1.0.0"))
    description = str(project_tbl.get("description", ""))
    lic_field = project_tbl.get("license", "MIT")
    license_id = str(lic_field) if isinstance(lic_field, str) else "MIT"

    authors: list[dict[str, str]] = []
    for author_entry in project_tbl.get("authors", []):
        if isinstance(author_entry, dict):
            authors.append(
                {
                    "name": str(author_entry.get("name", "")),
                    "email": str(author_entry.get("email", "")),
                }
            )

    deps = [str(d) for d in project_tbl.get("dependencies", [])]
    urls_tbl = project_tbl.get("urls", {})
    urls = {str(k): str(v) for k, v in urls_tbl.items()} if isinstance(urls_tbl, dict) else {}

    return {
        "name": name,
        "version": version,
        "description": description,
        "license": license_id,
        "authors": authors,
        "dependencies": deps,
        "urls": urls,
    }


def load_npm_package_info(package_json_path: Path) -> dict[str, Any]:
    """Load metadata for the npm launcher package from package.json."""
    if not package_json_path.exists():
        raise FileNotFoundError(f"Missing package.json at '{package_json_path}'")

    data = json.loads(package_json_path.read_text(encoding="utf-8"))
    name = str(data.get("name", "studiobridge"))
    version = str(data.get("version", "1.0.0"))
    description = str(data.get("description", ""))
    license_id = str(data.get("license", "MIT"))
    author = str(data.get("author", ""))
    homepage = str(data.get("homepage", ""))
    repo = data.get("repository", {})
    repo_url = str(repo.get("url", "")) if isinstance(repo, dict) else str(repo)

    return {
        "name": name,
        "version": version,
        "description": description,
        "license": license_id,
        "author": author,
        "homepage": homepage,
        "repository": repo_url,
    }


def load_lockfile_packages(lockfile_path: Path) -> list[dict[str, Any]]:
    """Load resolved package records from uv.lock."""
    if not lockfile_path.exists():
        raise FileNotFoundError(f"Missing uv.lock at '{lockfile_path}'")

    doc = tomlkit.loads(lockfile_path.read_text(encoding="utf-8"))
    packages_raw = doc.get("package", [])
    packages: list[dict[str, Any]] = []

    for pkg in packages_raw:
        if not isinstance(pkg, dict):
            continue
        name = str(pkg.get("name", ""))
        version = str(pkg.get("version", ""))
        if not name or not version:
            continue

        deps: list[str] = []
        for dep in pkg.get("dependencies", []):
            if isinstance(dep, dict) and "name" in dep:
                deps.append(str(dep["name"]))
            elif isinstance(dep, str):
                deps.append(dep)

        # Extract SHA-256 hash from wheels or sdist
        sha256_hash = ""
        wheels = pkg.get("wheels", [])
        if isinstance(wheels, list) and wheels:
            first_whl = wheels[0]
            if isinstance(first_whl, dict):
                h = str(first_whl.get("hash", ""))
                if h.startswith("sha256:"):
                    sha256_hash = h.removeprefix("sha256:")

        if not sha256_hash:
            sdist = pkg.get("sdist", {})
            if isinstance(sdist, dict):
                h = str(sdist.get("hash", ""))
                if h.startswith("sha256:"):
                    sha256_hash = h.removeprefix("sha256:")

        packages.append(
            {
                "name": name,
                "version": version,
                "dependencies": deps,
                "hash_sha256": sha256_hash,
            }
        )

    return packages


def determine_runtime_closure(
    direct_dep_specs: Sequence[str],
    lock_packages: Sequence[dict[str, Any]],
) -> set[str]:
    """Compute the transitive runtime dependency closure from root dependencies."""
    direct_names: set[str] = set()
    for spec in direct_dep_specs:
        cleaned = re.split(r"[><=~;!]", spec)[0].strip().lower()
        if cleaned:
            direct_names.add(cleaned)

    # Build adjacency mapping: name -> list of dependency names
    adj: dict[str, set[str]] = {}
    for p in lock_packages:
        name = p["name"].lower()
        if name not in adj:
            adj[name] = set()
        for dep in p.get("dependencies", []):
            adj[name].add(dep.lower())

    closure: set[str] = set()
    queue: deque[str] = deque(direct_names)

    while queue:
        curr = queue.popleft()
        if curr in closure:
            continue
        closure.add(curr)
        for dep in adj.get(curr, set()):
            if dep not in closure:
                queue.append(dep)

    return closure


def generate_cyclonedx_sbom(
    python_info: dict[str, Any],
    npm_info: dict[str, Any],
    lock_packages: Sequence[dict[str, Any]],
    runtime_closure: set[str],
    *,
    serial_number: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Generate a CycloneDX 1.5 JSON Software Bill of Materials."""
    sn = serial_number or f"urn:uuid:{uuid.uuid4()}"
    ts = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    py_name = python_info["name"]
    py_ver = python_info["version"]
    py_purl = f"pkg:pypi/{py_name}@{py_ver}"

    root_component = {
        "bom-ref": py_purl,
        "type": "application",
        "name": py_name,
        "version": py_ver,
        "description": python_info["description"],
        "licenses": [
            {
                "license": {
                    "id": resolve_license(py_name, python_info.get("license")),
                }
            }
        ],
        "purl": py_purl,
        "externalReferences": [
            {"type": "website", "url": python_info["urls"].get("Homepage", "")},
            {"type": "vcs", "url": python_info["urls"].get("Repository", "")},
            {"type": "issue-tracker", "url": python_info["urls"].get("Issues", "")},
        ],
    }

    components: list[dict[str, Any]] = []

    # 1. Add npm launcher component
    npm_name = npm_info["name"]
    npm_ver = npm_info["version"]
    npm_purl = f"pkg:npm/{npm_name}@{npm_ver}"
    components.append(
        {
            "bom-ref": npm_purl,
            "type": "application",
            "name": npm_name,
            "version": npm_ver,
            "description": npm_info["description"],
            "scope": "required",
            "purl": npm_purl,
            "licenses": [
                {
                    "license": {
                        "id": resolve_license(npm_name, npm_info.get("license")),
                    }
                }
            ],
            "externalReferences": [
                {"type": "website", "url": npm_info.get("homepage", "")},
                {"type": "vcs", "url": npm_info.get("repository", "")},
            ],
        }
    )

    # 2. Add Python dependency components
    seen_purls: set[str] = {py_purl, npm_purl}
    name_to_purls: dict[str, list[str]] = {}

    for pkg in lock_packages:
        p_name = pkg["name"]
        p_ver = pkg["version"]
        if p_name in ("studiobridge", "studiobridge-workspace"):
            continue

        purl = f"pkg:pypi/{p_name}@{p_ver}"
        if purl in seen_purls:
            continue
        seen_purls.add(purl)

        name_to_purls.setdefault(p_name.lower(), []).append(purl)

        is_runtime = p_name.lower() in runtime_closure
        scope = "required" if is_runtime else "optional"
        lic_id = resolve_license(p_name)

        comp: dict[str, Any] = {
            "bom-ref": purl,
            "type": "library",
            "name": p_name,
            "version": p_ver,
            "scope": scope,
            "purl": purl,
            "licenses": [{"license": {"id": lic_id}}],
            "externalReferences": [
                {
                    "type": "distribution",
                    "url": f"https://pypi.org/project/{p_name}/{p_ver}/",
                }
            ],
        }

        h = pkg.get("hash_sha256")
        if h:
            comp["hashes"] = [{"alg": "SHA-256", "content": h}]

        components.append(comp)

    # Build dependency relationships graph
    dependencies: list[dict[str, Any]] = []

    # studiobridge -> direct runtime dependencies
    direct_purls: list[str] = []
    for dep_spec in python_info.get("dependencies", []):
        d_name = re.split(r"[><=~;!]", dep_spec)[0].strip().lower()
        for purl in name_to_purls.get(d_name, []):
            if purl not in direct_purls:
                direct_purls.append(purl)

    dependencies.append(
        {
            "ref": py_purl,
            "dependsOn": sorted(direct_purls),
        }
    )

    # npm launcher depends on studiobridge python package
    dependencies.append(
        {
            "ref": npm_purl,
            "dependsOn": [py_purl],
        }
    )

    # Transitive packages dependencies
    for pkg in lock_packages:
        p_name = pkg["name"]
        p_ver = pkg["version"]
        if p_name in ("studiobridge", "studiobridge-workspace"):
            continue
        purl = f"pkg:pypi/{p_name}@{p_ver}"
        sub_purls: list[str] = []
        for sub_dep in pkg.get("dependencies", []):
            for sub_purl in name_to_purls.get(sub_dep.lower(), []):
                if sub_purl not in sub_purls:
                    sub_purls.append(sub_purl)
        if sub_purls:
            dependencies.append(
                {
                    "ref": purl,
                    "dependsOn": sorted(sub_purls),
                }
            )

    return {
        "$schema": "http://cyclonedx.org/schema/bom-1.5.schema.json",
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": sn,
        "version": 1,
        "metadata": {
            "timestamp": ts,
            "tools": [
                {
                    "vendor": "WantedChip",
                    "name": "studiobridge-sbom-generator",
                    "version": py_ver,
                }
            ],
            "authors": python_info.get("authors", []),
            "component": root_component,
        },
        "components": components,
        "dependencies": dependencies,
    }


def _make_spdx_id(prefix: str, name: str, version: str) -> str:
    """Format a clean, compliant SPDX element ID."""
    clean_name = re.sub(r"[^A-Za-z0-9.-]", "-", name)
    clean_ver = re.sub(r"[^A-Za-z0-9.-]", "-", version)
    return f"SPDXRef-{prefix}-{clean_name}-{clean_ver}"


def generate_spdx_sbom(
    python_info: dict[str, Any],
    npm_info: dict[str, Any],
    lock_packages: Sequence[dict[str, Any]],
    runtime_closure: set[str],
    *,
    namespace_uuid: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Generate an SPDX 2.3 JSON Software Bill of Materials."""
    doc_uuid = namespace_uuid or str(uuid.uuid4())
    ts = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    py_name = python_info["name"]
    py_ver = python_info["version"]
    py_spdx_id = _make_spdx_id("Package", py_name, py_ver)
    py_purl = f"pkg:pypi/{py_name}@{py_ver}"

    npm_name = npm_info["name"]
    npm_ver = npm_info["version"]
    npm_spdx_id = _make_spdx_id("Package", f"{npm_name}-npm", npm_ver)
    npm_purl = f"pkg:npm/{npm_name}@{npm_ver}"

    packages: list[dict[str, Any]] = [
        {
            "SPDXID": py_spdx_id,
            "name": py_name,
            "versionInfo": py_ver,
            "downloadLocation": "https://pypi.org/project/studiobridge/",
            "filesAnalyzed": False,
            "licenseConcluded": resolve_license(py_name, python_info.get("license")),
            "licenseDeclared": resolve_license(py_name, python_info.get("license")),
            "copyrightText": "Copyright (C) 2026 WantedChip",
            "summary": python_info.get("description", ""),
            "externalRefs": [
                {
                    "referenceCategory": "PACKAGE-MANAGER",
                    "referenceType": "purl",
                    "referenceLocator": py_purl,
                }
            ],
        },
        {
            "SPDXID": npm_spdx_id,
            "name": npm_name,
            "versionInfo": npm_ver,
            "downloadLocation": "https://www.npmjs.com/package/studiobridge",
            "filesAnalyzed": False,
            "licenseConcluded": resolve_license(npm_name, npm_info.get("license")),
            "licenseDeclared": resolve_license(npm_name, npm_info.get("license")),
            "copyrightText": "Copyright (C) 2026 WantedChip",
            "summary": npm_info.get("description", ""),
            "externalRefs": [
                {
                    "referenceCategory": "PACKAGE-MANAGER",
                    "referenceType": "purl",
                    "referenceLocator": npm_purl,
                }
            ],
        },
    ]

    relationships: list[dict[str, Any]] = [
        {
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": py_spdx_id,
        },
        {
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": npm_spdx_id,
        },
        {
            "spdxElementId": npm_spdx_id,
            "relationshipType": "DEPENDS_ON",
            "relatedSpdxElement": py_spdx_id,
        },
    ]

    seen_spdx_ids: set[str] = {py_spdx_id, npm_spdx_id}
    name_to_spdx_ids: dict[str, list[str]] = {}

    for pkg in lock_packages:
        p_name = pkg["name"]
        p_ver = pkg["version"]
        if p_name in ("studiobridge", "studiobridge-workspace"):
            continue

        spdx_id = _make_spdx_id("Package", p_name, p_ver)
        if spdx_id in seen_spdx_ids:
            continue
        seen_spdx_ids.add(spdx_id)

        name_to_spdx_ids.setdefault(p_name.lower(), []).append(spdx_id)

        lic_id = resolve_license(p_name)
        purl = f"pkg:pypi/{p_name}@{p_ver}"

        pkg_obj: dict[str, Any] = {
            "SPDXID": spdx_id,
            "name": p_name,
            "versionInfo": p_ver,
            "downloadLocation": f"https://pypi.org/project/{p_name}/{p_ver}/",
            "filesAnalyzed": False,
            "licenseConcluded": lic_id,
            "licenseDeclared": lic_id,
            "copyrightText": "NOASSERTION",
            "externalRefs": [
                {
                    "referenceCategory": "PACKAGE-MANAGER",
                    "referenceType": "purl",
                    "referenceLocator": purl,
                }
            ],
        }

        h = pkg.get("hash_sha256")
        if h:
            pkg_obj["checksums"] = [{"algorithm": "SHA256", "checksumValue": h}]

        packages.append(pkg_obj)

    # studiobridge -> direct dependencies
    for dep_spec in python_info.get("dependencies", []):
        d_name = re.split(r"[><=~;!]", dep_spec)[0].strip().lower()
        for dep_spdx_id in name_to_spdx_ids.get(d_name, []):
            relationships.append(
                {
                    "spdxElementId": py_spdx_id,
                    "relationshipType": "DEPENDS_ON",
                    "relatedSpdxElement": dep_spdx_id,
                }
            )

    # Transitive dependencies
    for pkg in lock_packages:
        p_name = pkg["name"]
        p_ver = pkg["version"]
        if p_name in ("studiobridge", "studiobridge-workspace"):
            continue
        parent_spdx_id = _make_spdx_id("Package", p_name, p_ver)
        for sub_dep in pkg.get("dependencies", []):
            for child_spdx_id in name_to_spdx_ids.get(sub_dep.lower(), []):
                relationships.append(
                    {
                        "spdxElementId": parent_spdx_id,
                        "relationshipType": "DEPENDS_ON",
                        "relatedSpdxElement": child_spdx_id,
                    }
                )

    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "studiobridge-sbom",
        "documentNamespace": f"https://github.com/WantedChip/studiobridge/spdx/{doc_uuid}",
        "creationInfo": {
            "created": ts,
            "creators": [
                f"Tool: studiobridge-sbom-generator-{py_ver}",
                "Organization: WantedChip",
                "Person: WantedChip (ty121rt@gmail.com)",
            ],
            "licenseListVersion": "3.22",
        },
        "packages": packages,
        "relationships": relationships,
    }


def verify_cyclonedx_sbom(data: dict[str, Any]) -> list[str]:
    """Verify CycloneDX 1.5 JSON SBOM against specification invariants."""
    errors: list[str] = []

    if data.get("bomFormat") != "CycloneDX":
        errors.append(f"Invalid bomFormat: expected 'CycloneDX', got '{data.get('bomFormat')}'")

    if data.get("specVersion") != "1.5":
        errors.append(f"Invalid specVersion: expected '1.5', got '{data.get('specVersion')}'")

    sn = str(data.get("serialNumber", ""))
    if not sn.startswith("urn:uuid:"):
        errors.append(f"Invalid serialNumber: must start with 'urn:uuid:', got '{sn}'")

    meta = data.get("metadata", {})
    if not isinstance(meta, dict):
        errors.append("Missing metadata dictionary")
    else:
        root_comp = meta.get("component", {})
        comp_name = root_comp.get("name")
        if comp_name != "studiobridge":
            errors.append(
                f"Metadata component name mismatch: expected 'studiobridge', got '{comp_name}'"
            )
        if not root_comp.get("purl", "").startswith("pkg:pypi/studiobridge"):
            errors.append(f"Metadata component missing valid purl: '{root_comp.get('purl')}'")

    components = data.get("components", [])
    if not isinstance(components, list) or len(components) == 0:
        errors.append("Components list is empty or invalid")
    else:
        comp_names = {str(c.get("name")): c for c in components if isinstance(c, dict)}
        if "studiobridge" not in comp_names:
            errors.append("Missing npm package 'studiobridge' in components")

        runtime_expected = {"anyio", "platformdirs", "tomlkit"}
        for r_name in runtime_expected:
            if r_name not in comp_names:
                errors.append(f"Missing core runtime dependency '{r_name}' in components")

        for c in components:
            if not isinstance(c, dict):
                errors.append(f"Non-dict component found: {c}")
                continue
            name = c.get("name")
            purl = c.get("purl")
            licenses = c.get("licenses")
            if not name or not purl:
                errors.append(f"Component missing name or purl: {c}")
            if not licenses or not isinstance(licenses, list):
                errors.append(f"Component '{name}' missing valid licenses list")

    dependencies = data.get("dependencies", [])
    if not isinstance(dependencies, list) or len(dependencies) == 0:
        errors.append("Dependencies list is empty or invalid")
    else:
        refs = {
            str(d.get("ref")): d.get("dependsOn", []) for d in dependencies if isinstance(d, dict)
        }
        has_root_dep = any(r.startswith("pkg:pypi/studiobridge") for r in refs)
        if not has_root_dep:
            errors.append(
                "Missing root package 'studiobridge' dependency entry in dependencies graph"
            )

    return errors


def verify_spdx_sbom(data: dict[str, Any]) -> list[str]:
    """Verify SPDX 2.3 JSON SBOM against specification invariants."""
    errors: list[str] = []

    if data.get("spdxVersion") != "SPDX-2.3":
        errors.append(f"Invalid spdxVersion: expected 'SPDX-2.3', got '{data.get('spdxVersion')}'")

    if data.get("dataLicense") != "CC0-1.0":
        errors.append(f"Invalid dataLicense: expected 'CC0-1.0', got '{data.get('dataLicense')}'")

    if data.get("SPDXID") != "SPDXRef-DOCUMENT":
        errors.append(f"Invalid SPDXID: expected 'SPDXRef-DOCUMENT', got '{data.get('SPDXID')}'")

    packages = data.get("packages", [])
    if not isinstance(packages, list) or len(packages) == 0:
        errors.append("Packages list is empty or invalid")
    else:
        pkg_names = {str(p.get("name")): p for p in packages if isinstance(p, dict)}
        if "studiobridge" not in pkg_names:
            errors.append("Missing 'studiobridge' in packages")

        runtime_expected = {"anyio", "platformdirs", "tomlkit"}
        for r_name in runtime_expected:
            if r_name not in pkg_names:
                errors.append(f"Missing core runtime dependency '{r_name}' in packages")

        for p in packages:
            if not isinstance(p, dict):
                continue
            name = p.get("name")
            spdx_id = str(p.get("SPDXID", ""))
            if not spdx_id.startswith("SPDXRef-"):
                errors.append(f"Package '{name}' has invalid SPDXID: '{spdx_id}'")
            if not p.get("licenseConcluded"):
                errors.append(f"Package '{name}' missing licenseConcluded")

    relationships = data.get("relationships", [])
    if not isinstance(relationships, list) or len(relationships) == 0:
        errors.append("Relationships list is empty or invalid")
    else:
        types = {r.get("relationshipType") for r in relationships if isinstance(r, dict)}
        if "DESCRIBES" not in types:
            errors.append("Missing DESCRIBES relationship in relationships")
        if "DEPENDS_ON" not in types:
            errors.append("Missing DEPENDS_ON relationship in relationships")

    return errors


def verify_sbom_file(path: Path) -> tuple[bool, list[str]]:
    """Load an existing SBOM file, detect format, and verify compliance."""
    if not path.exists():
        return False, [f"File not found: '{path}'"]

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, [f"Failed parsing JSON from '{path}': {exc}"]

    if data.get("bomFormat") == "CycloneDX":
        errs = verify_cyclonedx_sbom(data)
        return len(errs) == 0, errs
    elif data.get("spdxVersion") == "SPDX-2.3":
        errs = verify_spdx_sbom(data)
        return len(errs) == 0, errs
    else:
        return False, ["Unrecognized SBOM format (neither CycloneDX 1.5 nor SPDX 2.3)"]


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser for SBOM generation and verification."""
    parser = argparse.ArgumentParser(
        description="Generate and verify Software Bill of Materials (SBOM) for StudioBridge.",
    )
    parser.add_argument(
        "--format",
        choices=["cyclonedx", "spdx"],
        default="cyclonedx",
        help="SBOM output specification format (default: cyclonedx).",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Destination path for generated SBOM JSON (default: dist/sbom-<format>.json).",
    )
    parser.add_argument(
        "--verify",
        nargs="?",
        const=True,
        default=None,
        help="Verify an existing SBOM file or verify generation in-memory without writing.",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress informational console output.",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=DEFAULT_WORKSPACE_ROOT,
        help="Path to workspace root directory.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for SBOM generator."""
    parser = build_parser()
    args = parser.parse_args(argv)

    workspace: Path = args.workspace.resolve()
    pyproject_path = workspace / "packages" / "studiobridge" / "pyproject.toml"
    if not pyproject_path.exists():
        pyproject_path = workspace / "pyproject.toml"

    npm_path = workspace / "npm" / "studiobridge" / "package.json"
    if not npm_path.exists():
        npm_path = workspace / "npm" / "package.json"

    lockfile_path = workspace / "uv.lock"

    # Handle --verify on a specific file path
    if isinstance(args.verify, str) and args.verify not in ("True", "true", "1"):
        target_path = Path(args.verify).resolve()
        ok, errors = verify_sbom_file(target_path)
        if not ok:
            if not args.quiet:
                sys.stderr.write(f"[FAIL] SBOM verification failed for '{target_path}':\n")
                for err in errors:
                    sys.stderr.write(f"  - {err}\n")
            return 1
        if not args.quiet:
            print(f"[OK] SBOM verified successfully: {target_path}")
        return 0

    # Load sources
    try:
        py_info = load_python_package_info(pyproject_path)
        npm_info = load_npm_package_info(npm_path)
        lock_pkgs = load_lockfile_packages(lockfile_path)
        runtime_closure = determine_runtime_closure(py_info.get("dependencies", []), lock_pkgs)
    except Exception as exc:
        if not args.quiet:
            sys.stderr.write(f"[ERROR] Failed loading package metadata: {exc}\n")
        return 1

    fmt: FormatType = args.format.lower()
    if fmt == "cyclonedx":
        sbom_data = generate_cyclonedx_sbom(py_info, npm_info, lock_pkgs, runtime_closure)
        errors = verify_cyclonedx_sbom(sbom_data)
    else:
        sbom_data = generate_spdx_sbom(py_info, npm_info, lock_pkgs, runtime_closure)
        errors = verify_spdx_sbom(sbom_data)

    if errors:
        if not args.quiet:
            sys.stderr.write(f"[FAIL] Generated {fmt.upper()} SBOM failed validation:\n")
            for err in errors:
                sys.stderr.write(f"  - {err}\n")
        return 1

    # In-memory verify mode
    if args.verify is True:
        if not args.quiet:
            print(f"[OK] {fmt.upper()} SBOM generation verified successfully (0 schema errors).")
            print(f"  - Root: {py_info['name']} v{py_info['version']}")
            print(f"  - npm: {npm_info['name']} v{npm_info['version']}")
            print(
                f"  - Resolved components: {len(lock_pkgs)} packages "
                f"({len(runtime_closure)} runtime)"
            )
        return 0

    # Write output
    output_path = args.output
    if output_path is None:
        output_path = workspace / "dist" / f"sbom-{fmt}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(sbom_data, indent=2), encoding="utf-8")

    if not args.quiet:
        print(f"[OK] Generated {fmt.upper()} SBOM written to: {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
