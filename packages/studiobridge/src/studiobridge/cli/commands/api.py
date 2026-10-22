"""Implementation of 'sbridge api' inspection commands."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from studiobridge.manifest.cards import generate_all_cards
from studiobridge.manifest.drift import load_baseline_manifest
from studiobridge.mcp.tools.core import CoreTools


def handle_api(args: argparse.Namespace) -> int:
    """Dispatch 'sbridge api' subcommands: search, describe, list, export."""
    subaction = getattr(args, "api_action", None)
    is_json = getattr(args, "json", False)

    if not subaction:
        print("Usage: sbridge api <search|describe|list|export> [options]", file=sys.stderr)
        return 2

    core = CoreTools()

    # 1. sbridge api search <query>
    if subaction == "search":
        query = getattr(args, "named_query", None) or getattr(args, "query", "")
        module = getattr(args, "module", None)
        limit = int(getattr(args, "limit", 20))
        include_constants = bool(getattr(args, "constants", False))

        res = core.api_search(
            query=query, module=module, limit=limit, include_constants=include_constants
        )
        if is_json:
            print(json.dumps(res.structured_content, indent=2))
        else:
            matches = res.structured_content.get("matches", [])
            total = res.structured_content.get("total", 0)
            print(f"API Search Results ({len(matches)} of {total} shown):")
            print("=" * 80)
            if not matches:
                print("No matching functions or constants found.")
            else:
                for m in matches:
                    mod = m.get("module", "")
                    name = m.get("name", "")
                    sig = m.get("signature", "")
                    mut = " [MUTATING]" if m.get("mutating") else ""
                    print(f"• {mod}.{name}{mut}")
                    print(f"  Signature: {sig}")
                    summary = m.get("summary", "")
                    if summary:
                        print(f"  Summary:   {summary}")
                    print("-" * 80)
        return 0

    # 2. sbridge api describe <fn>
    if subaction == "describe":
        fn_name = getattr(args, "function", None)
        module = getattr(args, "module", None)
        if not fn_name:
            print(
                "Error: Function name is required "
                "(e.g. 'sbridge api describe mixer.setTrackVolume')",
                file=sys.stderr,
            )
            return 2

        try:
            res = core.api_describe(function=fn_name, module=module)
        except ValueError as err:
            if is_json:
                print(json.dumps({"status": "error", "message": str(err)}, indent=2))
            else:
                print(f"Error: {err}", file=sys.stderr)
            return 1

        if is_json:
            print(json.dumps(res.structured_content, indent=2))
        else:
            d = res.structured_content
            print("=" * 80)
            print(f"FL Studio API: {d['module']}.{d['function']}")
            print("=" * 80)
            print(f"Signature:  {d['signature']}")
            print(f"Since API:  v{d['since']}")
            mut_str = "Yes" if d["mutating"] else "No"
            prot_str = "Yes" if d["protected"] else "No"
            print(f"Mutating:   {mut_str} (Protected: {prot_str})")
            print(f"Plane:      {d['plane']} (Undo: {d['undo']})")
            if d.get("summary"):
                print(f"Summary:    {d['summary']}")

            args_list = d.get("args", [])
            if args_list:
                print("\nParameters:")
                for a in args_list:
                    req_str = "optional" if a.get("optional") else "required"
                    def_str = (
                        f", default={a.get('default')}" if a.get("default") is not None else ""
                    )
                    range_str = f", range={a.get('range')}" if a.get("range") else ""
                    print(f"  • {a['name']} ({a['type']}, {req_str}{def_str}{range_str})")
                    if a.get("doc"):
                        print(f"    {a['doc']}")
            print(f"\nReturn:     {d['ret']}")

            quirks = d.get("quirks")
            if quirks:
                print("\nEmpirical Quirks & Tolerances:")
                if quirks.get("tol"):
                    print(f"  Tolerance: ±{quirks['tol']}")
                if quirks.get("notes"):
                    print(f"  Notes:     {quirks['notes']}")

            if d.get("example"):
                print(f"\nExample:\n{d['example']}")
            print("=" * 80)
        return 0

    # 3. sbridge api list [module]
    if subaction == "list":
        target_mod = getattr(args, "module", None)
        manifest = load_baseline_manifest()

        if target_mod:
            target_clean = target_mod.strip().lower()
            matching_mod = next(
                (m for m in manifest.modules.values() if m.name.lower() == target_clean), None
            )
            if not matching_mod:
                if is_json:
                    print(
                        json.dumps(
                            {"status": "error", "message": f"Module '{target_mod}' not found"},
                            indent=2,
                        )
                    )
                else:
                    print(f"Error: Module '{target_mod}' not found in manifest.", file=sys.stderr)
                return 1

            fn_names = sorted(matching_mod.functions.keys())
            const_names = sorted(matching_mod.constants.keys())
            if is_json:
                print(
                    json.dumps(
                        {
                            "module": matching_mod.name,
                            "summary": matching_mod.summary,
                            "function_count": len(fn_names),
                            "functions": fn_names,
                            "constant_count": len(const_names),
                            "constants": const_names,
                        },
                        indent=2,
                    )
                )
            else:
                mod_hdr = (
                    f"Module '{matching_mod.name}' "
                    f"({len(fn_names)} functions, {len(const_names)} constants):"
                )
                print(mod_hdr)
                print("=" * 80)
                print("Functions:")
                for fn in fn_names:
                    print(f"  • {matching_mod.name}.{fn}")
                if const_names:
                    print("\nConstants:")
                    for c in const_names:
                        print(f"  • {matching_mod.name}.{c}")
            return 0

        # List all modules
        mod_list = []
        for mod_name, mod_doc in sorted(manifest.modules.items()):
            mod_list.append(
                {
                    "name": mod_name,
                    "summary": mod_doc.summary,
                    "function_count": len(mod_doc.functions),
                    "constant_count": len(mod_doc.constants),
                }
            )

        if is_json:
            print(json.dumps({"modules": mod_list, "total": len(mod_list)}, indent=2))
        else:
            print(f"FL Studio Scripting Modules ({len(mod_list)} total):")
            print("=" * 80)
            for m in mod_list:
                line_str = (
                    f"• {m['name']:<15} "
                    f"{m['function_count']:>3} functions, {m['constant_count']:>3} constants"
                )
                print(line_str)
                if m.get("summary"):
                    print(f"  {m['summary']}")
            print("=" * 80)
        return 0

    # 4. sbridge api export
    if subaction == "export":
        fmt = getattr(args, "format", "json")
        out_path_str = getattr(args, "out", None)
        manifest = load_baseline_manifest()

        if fmt == "json":
            content = json.dumps(manifest.to_dict(), indent=2)
            if out_path_str:
                p = Path(out_path_str)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8")
                msg = f"Exported manifest JSON to {p}"
            else:
                msg = content
        elif fmt == "md":
            cards = generate_all_cards(manifest, output_dir=out_path_str)
            if out_path_str:
                msg = f"Exported {len(cards)} markdown cards to {out_path_str}"
            else:
                msg = f"Generated {len(cards)} markdown documentation cards."
        elif fmt == "pyi":
            from studiobridge.manifest.codegen import generate_sdk_stubs

            out_dir = Path(out_path_str) if out_path_str else Path.cwd() / "stubs"
            stubs = generate_sdk_stubs(manifest, output_dir=out_dir)
            msg = f"Exported {len(stubs)} Python stubs (.pyi) to {out_dir}"
        else:
            print(
                f"Unsupported export format '{fmt}'. Choose from 'json', 'pyi', 'md'.",
                file=sys.stderr,
            )
            return 2

        if is_json:
            print(json.dumps({"status": "ok", "format": fmt, "message": msg}, indent=2))
        else:
            if out_path_str:
                print(msg)
            else:
                print(msg[:1000] + ("..." if len(msg) > 1000 else ""))
        return 0

    return 2
