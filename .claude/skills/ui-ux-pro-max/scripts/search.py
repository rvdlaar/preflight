#!/usr/bin/env python3
"""UI/UX Pro Max Search — CLI entry point for BM25 search and design system generation."""

import argparse
import json
import sys
import io

from core import CSV_CONFIG, AVAILABLE_STACKS, MAX_RESULTS, search, search_stack
from design_system import generate_design_system, persist_design_system

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


def format_output(result: dict) -> str:
    """Format results for token-optimized CLI consumption."""
    if "error" in result:
        return f"Error: {result['error']}"

    header = f"## UI Pro Max {'Stack' if result.get('stack') else ''} Search Results"
    source = result.get("stack") or result.get("domain", "")
    output = [
        f"{header}",
        f"**{'Stack' if result.get('stack') else 'Domain'}:** {source} | **Query:** {result['query']}",
        f"**Source:** {result['file']} | **Found:** {result['count']} results",
        "",
    ]

    for i, row in enumerate(result["results"], 1):
        output.append(f"### Result {i}")
        for key, value in row.items():
            val = str(value)
            if len(val) > 300:
                val = val[:300] + "..."
            output.append(f"- **{key}:** {val}")
        output.append("")

    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(description="UI Pro Max Search")
    parser.add_argument("query", help="Search query")
    parser.add_argument(
        "--domain", "-d", choices=list(CSV_CONFIG.keys()), help="Search domain"
    )
    parser.add_argument(
        "--stack", "-s", choices=AVAILABLE_STACKS, help="Stack-specific search"
    )
    parser.add_argument(
        "--max-results",
        "-n",
        type=int,
        default=MAX_RESULTS,
        help="Max results (default: 3)",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Design system generation
    parser.add_argument(
        "--design-system",
        "-ds",
        action="store_true",
        help="Generate design system recommendation",
    )
    parser.add_argument(
        "--project-name", "-p", type=str, default=None, help="Project name"
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["ascii", "markdown"],
        default="ascii",
        help="Design system output format",
    )
    parser.add_argument(
        "--persist",
        action="store_true",
        help="Save design system to design-system/ folder",
    )
    parser.add_argument(
        "--page", type=str, default=None, help="Create page-specific override file"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory for persisted files",
    )

    args = parser.parse_args()

    if args.design_system:
        result = generate_design_system(
            args.query,
            args.project_name,
            args.format,
            persist=args.persist,
            page=args.page,
            output_dir=args.output_dir,
        )
        print(result)

        if args.persist:
            slug = (
                args.project_name.lower().replace(" ", "-")
                if args.project_name
                else "default"
            )
            print(f"\n{'=' * 60}")
            print(f"✅ Design system persisted to design-system/{slug}/")
            print(f"   📄 design-system/{slug}/MASTER.md (Global Source of Truth)")
            if args.page:
                page_file = args.page.lower().replace(" ", "-")
                print(
                    f"   📄 design-system/{slug}/pages/{page_file}.md (Page Overrides)"
                )
            print(
                f"\n📖 Usage: When building a page, check design-system/{slug}/pages/[page].md first."
            )
            print(
                f"   If exists, its rules override MASTER.md. Otherwise, use MASTER.md."
            )
            print("=" * 60)
    elif args.stack:
        result = search_stack(args.query, args.stack, args.max_results)
        print(
            json.dumps(result, indent=2, ensure_ascii=False)
            if args.json
            else format_output(result)
        )
    else:
        result = search(args.query, args.domain, args.max_results)
        print(
            json.dumps(result, indent=2, ensure_ascii=False)
            if args.json
            else format_output(result)
        )


if __name__ == "__main__":
    main()
