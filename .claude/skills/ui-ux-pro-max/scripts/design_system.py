#!/usr/bin/env python3
"""Design System Generator — Aggregates search results and applies reasoning."""

import csv
import json
from datetime import datetime
from pathlib import Path
from core import search, DATA_DIR

REASONING_FILE: str = "ui-reasoning.csv"

SEARCH_CONFIG: dict = {
    "product": {"max_results": 1},
    "style": {"max_results": 3},
    "color": {"max_results": 2},
    "landing": {"max_results": 2},
    "typography": {"max_results": 2},
}

CHECKLIST = [
    "No emojis as icons (use SVG: Heroicons/Lucide)",
    "cursor-pointer on all clickable elements",
    "Hover states with smooth transitions (150-300ms)",
    "Light mode: text contrast 4.5:1 minimum",
    "Focus states visible for keyboard nav",
    "prefers-reduced-motion respected",
    "Responsive: 375px, 768px, 1024px, 1440px",
]

ANTIPATTERNS = [
    ("Emojis as icons", "Use SVG icons (Heroicons, Lucide, Simple Icons)"),
    ("Missing cursor:pointer", "All clickable elements must have cursor:pointer"),
    ("Layout-shifting hovers", "Avoid scale transforms that shift layout"),
    ("Low contrast text", "Maintain 4.5:1 minimum contrast ratio"),
    ("Instant state changes", "Always use transitions (150-300ms)"),
    ("Invisible focus states", "Focus states must be visible for a11y"),
]

DEFAULTS = {
    "pattern": "Hero + Features + CTA",
    "style_priority": ["Minimalism", "Flat Design"],
    "color_mood": "Professional",
    "typography_mood": "Clean",
    "key_effects": "Subtle hover transitions",
    "severity": "MEDIUM",
}


class DesignSystemGenerator:
    """Generates design system recommendations from aggregated searches."""

    def __init__(self):
        self.reasoning_data = self._load_reasoning()

    def _load_reasoning(self) -> list[dict]:
        filepath = DATA_DIR / REASONING_FILE
        if not filepath.exists():
            return []
        with open(filepath, "r", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def _multi_domain_search(self, query: str, style_priority: list = None) -> dict:
        results: dict = {}
        for domain, config in SEARCH_CONFIG.items():
            if domain == "style" and style_priority:
                combined = f"{query} {' '.join(style_priority[:2])}"
                results[domain] = search(combined, domain, config["max_results"])
            else:
                results[domain] = search(query, domain, config["max_results"])
        return results

    def _find_reasoning_rule(self, category: str) -> dict:
        category_lower = category.lower()
        best_rule: dict = {}
        best_score: int = 0

        for rule in self.reasoning_data:
            ui_cat = rule.get("UI_Category", "").lower()
            if ui_cat == category_lower:
                score = 3
            elif ui_cat in category_lower or category_lower in ui_cat:
                score = 2
            else:
                keywords = ui_cat.replace("/", " ").replace("-", " ").split()
                score = 1 if any(kw in category_lower for kw in keywords) else 0

            if score > best_score:
                best_score = score
                best_rule = rule

        return best_rule

    def _apply_reasoning(self, category: str) -> dict:
        rule = self._find_reasoning_rule(category)

        if not rule:
            return {
                "pattern": DEFAULTS["pattern"],
                "style_priority": DEFAULTS["style_priority"],
                "color_mood": DEFAULTS["color_mood"],
                "typography_mood": DEFAULTS["typography_mood"],
                "key_effects": DEFAULTS["key_effects"],
                "anti_patterns": "",
                "decision_rules": {},
                "severity": DEFAULTS["severity"],
            }

        decision_rules: dict = {}
        try:
            decision_rules = json.loads(rule.get("Decision_Rules", "{}"))
        except json.JSONDecodeError:
            pass

        return {
            "pattern": rule.get("Recommended_Pattern", ""),
            "style_priority": [
                s.strip() for s in rule.get("Style_Priority", "").split("+")
            ],
            "color_mood": rule.get("Color_Mood", ""),
            "typography_mood": rule.get("Typography_Mood", ""),
            "key_effects": rule.get("Key_Effects", ""),
            "anti_patterns": rule.get("Anti_Patterns", ""),
            "decision_rules": decision_rules,
            "severity": rule.get("Severity", "MEDIUM"),
        }

    def _select_best_match(self, results: list, priority_keywords: list) -> dict:
        if not results:
            return {}
        if not priority_keywords:
            return results[0]

        for kw in priority_keywords:
            kw_lower = kw.lower().strip()
            for r in results:
                if kw_lower in r.get("Style Category", "").lower():
                    return r

        scored = []
        for r in results:
            text = str(r).lower()
            score = sum(
                10
                if kw.lower().strip() in r.get("Style Category", "").lower()
                else 3
                if kw.lower().strip() in r.get("Keywords", "").lower()
                else 1
                if kw.lower().strip() in text
                else 0
                for kw in priority_keywords
            )
            if score > 0:
                scored.append((score, r))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1] if scored else {}

    def _extract(self, search_result: dict) -> list:
        return search_result.get("results", [])

    def generate(self, query: str, project_name: str = None) -> dict:
        product_results = self._extract(search(query, "product", 1))
        category = (
            product_results[0].get("Product Type", "General")
            if product_results
            else "General"
        )

        reasoning = self._apply_reasoning(category)
        style_priority = reasoning.get("style_priority", [])

        searches = self._multi_domain_search(query, style_priority)
        searches["product"] = (
            search(query, "product", 1)
            if not product_results
            else {"results": product_results}
        )

        best_style = self._select_best_match(
            self._extract(searches.get("style", {})), style_priority
        )
        best_color = self._first(self._extract(searches.get("color", {})))
        best_typo = self._first(self._extract(searches.get("typography", {})))
        best_landing = self._first(self._extract(searches.get("landing", {})))

        effects = best_style.get("Effects & Animation", "") or reasoning.get(
            "key_effects", ""
        )

        return {
            "project_name": project_name or query.upper(),
            "category": category,
            "pattern": {
                "name": best_landing.get("Pattern Name", "")
                or reasoning.get("pattern", DEFAULTS["pattern"]),
                "sections": best_landing.get("Section Order", "Hero > Features > CTA"),
                "cta_placement": best_landing.get(
                    "Primary CTA Placement", "Above fold"
                ),
                "color_strategy": best_landing.get("Color Strategy", ""),
                "conversion": best_landing.get("Conversion Optimization", ""),
            },
            "style": {
                "name": best_style.get("Style Category", "Minimalism"),
                "type": best_style.get("Type", "General"),
                "effects": best_style.get("Effects & Animation", ""),
                "keywords": best_style.get("Keywords", ""),
                "best_for": best_style.get("Best For", ""),
                "performance": best_style.get("Performance", ""),
                "accessibility": best_style.get("Accessibility", ""),
            },
            "colors": {
                "primary": best_color.get("Primary (Hex)", "#2563EB"),
                "secondary": best_color.get("Secondary (Hex)", "#3B82F6"),
                "cta": best_color.get("CTA (Hex)", "#F97316"),
                "background": best_color.get("Background (Hex)", "#F8FAFC"),
                "text": best_color.get("Text (Hex)", "#1E293B"),
                "notes": best_color.get("Notes", ""),
            },
            "typography": {
                "heading": best_typo.get("Heading Font", "Inter"),
                "body": best_typo.get("Body Font", "Inter"),
                "mood": best_typo.get("Mood/Style Keywords", "")
                or reasoning.get("typography_mood", ""),
                "best_for": best_typo.get("Best For", ""),
                "google_fonts_url": best_typo.get("Google Fonts URL", ""),
                "css_import": best_typo.get("CSS Import", ""),
            },
            "key_effects": effects,
            "anti_patterns": reasoning.get("anti_patterns", ""),
            "decision_rules": reasoning.get("decision_rules", {}),
            "severity": reasoning.get("severity", "MEDIUM"),
        }

    @staticmethod
    def _first(items: list) -> dict:
        return items[0] if items else {}


def _wrap_text(text: str, prefix: str, width: int) -> list[str]:
    if not text:
        return []
    words = text.split()
    lines = []
    current = prefix
    for word in words:
        if len(current) + len(word) + 1 <= width - 2:
            current += (" " if current != prefix else "") + word
        else:
            if current != prefix:
                lines.append(current)
            current = prefix + word
    if current != prefix:
        lines.append(current)
    return lines


def _ds(d: dict, *keys: str, default: str = "") -> str:
    """Deep-get from nested dict: _ds(d, 'pattern', 'name') = d['pattern']['name']."""
    node = d
    for k in keys:
        if not isinstance(node, dict):
            return default
        node = node.get(k, default)
    return node if isinstance(node, str) else default


def format_ascii_box(ds: dict) -> str:
    W = 90
    w = W - 1
    L = []

    L.append("+" + "-" * w + "+")
    L.append(
        f"|  TARGET: {ds.get('project_name', 'PROJECT')} - RECOMMENDED DESIGN SYSTEM".ljust(
            W
        )
        + "|"
    )
    L.append("+" + "-" * w + "+")
    L.append("|" + " " * W + "|")

    # Pattern
    for label, val in [
        ("PATTERN", _ds(ds, "pattern", "name")),
        ("Conversion", _ds(ds, "pattern", "conversion")),
        ("CTA", _ds(ds, "pattern", "cta_placement")),
    ]:
        if val:
            prefix = "|  " if label == "PATTERN" else "|     "
            L.append(f"{prefix}{label}: {val}".ljust(W) + "|")
    L.append("|     Sections:".ljust(W) + "|")
    for i, s in enumerate(_ds(ds, "pattern", "sections").split(">")):
        if s.strip():
            L.append(f"|       {i + 1}. {s.strip()}".ljust(W) + "|")
    L.append("|" + " " * W + "|")

    # Style
    L.append(f"|  STYLE: {_ds(ds, 'style', 'name')}".ljust(W) + "|")
    for text in [
        _ds(ds, "style", "keywords") and f"Keywords: {_ds(ds, 'style', 'keywords')}",
        _ds(ds, "style", "best_for") and f"Best For: {_ds(ds, 'style', 'best_for')}",
    ]:
        if text:
            for ln in _wrap_text(text, "|     ", W):
                L.append(ln.ljust(W) + "|")
    perf = _ds(ds, "style", "performance")
    a11y = _ds(ds, "style", "accessibility")
    if perf or a11y:
        L.append(f"|     Performance: {perf} | Accessibility: {a11y}".ljust(W) + "|")
    L.append("|" + " " * W + "|")

    # Colors
    L.append("|  COLORS:".ljust(W) + "|")
    for label, key in [
        ("Primary", "primary"),
        ("Secondary", "secondary"),
        ("CTA", "cta"),
        ("Background", "background"),
        ("Text", "text"),
    ]:
        L.append(f"|     {label + ':':<12} {_ds(ds, 'colors', key)}".ljust(W) + "|")
    if _ds(ds, "colors", "notes"):
        for ln in _wrap_text(f"Notes: {_ds(ds, 'colors', 'notes')}", "|     ", W):
            L.append(ln.ljust(W) + "|")
    L.append("|" + " " * W + "|")

    # Typography
    L.append(
        f"|  TYPOGRAPHY: {_ds(ds, 'typography', 'heading')} / {_ds(ds, 'typography', 'body')}".ljust(
            W
        )
        + "|"
    )
    for text in [
        _ds(ds, "typography", "mood") and f"Mood: {_ds(ds, 'typography', 'mood')}",
        _ds(ds, "typography", "best_for")
        and f"Best For: {_ds(ds, 'typography', 'best_for')}",
    ]:
        if text:
            for ln in _wrap_text(text, "|     ", W):
                L.append(ln.ljust(W) + "|")
    if _ds(ds, "typography", "google_fonts_url"):
        L.append(
            f"|     Google Fonts: {_ds(ds, 'typography', 'google_fonts_url')}".ljust(W)
            + "|"
        )
    if _ds(ds, "typography", "css_import"):
        L.append(
            f"|     CSS Import: {_ds(ds, 'typography', 'css_import')[:70]}...".ljust(W)
            + "|"
        )
    L.append("|" + " " * W + "|")

    # Effects + Antipatterns
    if ds.get("key_effects"):
        L.append("|  KEY EFFECTS:".ljust(W) + "|")
        for ln in _wrap_text(ds["key_effects"], "|     ", W):
            L.append(ln.ljust(W) + "|")
        L.append("|" + " " * W + "|")
    if ds.get("anti_patterns"):
        L.append("|  AVOID (Anti-patterns):".ljust(W) + "|")
        for ln in _wrap_text(ds["anti_patterns"], "|     ", W):
            L.append(ln.ljust(W) + "|")
        L.append("|" + " " * W + "|")

    # Checklist
    L.append("|  PRE-DELIVERY CHECKLIST:".ljust(W) + "|")
    for item in CHECKLIST:
        L.append(f"|     [ ] {item}".ljust(W) + "|")
    L.append("|" + " " * W + "|")
    L.append("+" + "-" * w + "+")
    return "\n".join(L)


def format_markdown(ds: dict) -> str:
    lines = [f"## Design System: {ds.get('project_name', 'PROJECT')}", ""]

    # Pattern
    lines.append("### Pattern")
    lines.append(f"- **Name:** {_ds(ds, 'pattern', 'name')}")
    for label, key in [
        ("Conversion Focus", "conversion"),
        ("CTA Placement", "cta_placement"),
        ("Color Strategy", "color_strategy"),
    ]:
        val = _ds(ds, "pattern", key)
        if val:
            lines.append(f"- **{label}:** {val}")
    lines.append(f"- **Sections:** {_ds(ds, 'pattern', 'sections')}")
    lines.append("")

    # Style
    lines.append("### Style")
    lines.append(f"- **Name:** {_ds(ds, 'style', 'name')}")
    for key in ["keywords", "best_for"]:
        if _ds(ds, "style", key):
            label = key.replace("_", " ").title()
            lines.append(f"- **{label}:** {_ds(ds, 'style', key)}")
    if _ds(ds, "style", "performance") or _ds(ds, "style", "accessibility"):
        lines.append(
            f"- **Performance:** {_ds(ds, 'style', 'performance')} | **Accessibility:** {_ds(ds, 'style', 'accessibility')}"
        )
    lines.append("")

    # Colors
    lines.append("### Colors")
    lines.append("| Role | Hex |")
    lines.append("|------|-----|")
    for key in ["primary", "secondary", "cta", "background", "text"]:
        lines.append(f"| {key.title()} | {_ds(ds, 'colors', key)} |")
    if _ds(ds, "colors", "notes"):
        lines.append(f"\n*Notes: {_ds(ds, 'colors', 'notes')}*")
    lines.append("")

    # Typography
    lines.append("### Typography")
    lines.append(f"- **Heading:** {_ds(ds, 'typography', 'heading')}")
    lines.append(f"- **Body:** {_ds(ds, 'typography', 'body')}")
    for key, label in [("mood", "Mood"), ("best_for", "Best For")]:
        if _ds(ds, "typography", key):
            lines.append(f"- **{label}:** {_ds(ds, 'typography', key)}")
    if _ds(ds, "typography", "google_fonts_url"):
        lines.append(f"- **Google Fonts:** {_ds(ds, 'typography', 'google_fonts_url')}")
    if _ds(ds, "typography", "css_import"):
        lines.append("- **CSS Import:**")
        lines.append("```css")
        lines.append(_ds(ds, "typography", "css_import"))
        lines.append("```")
    lines.append("")

    # Effects + Antipatterns
    if ds.get("key_effects"):
        lines.append("### Key Effects")
        lines.append(ds["key_effects"])
        lines.append("")
    if ds.get("anti_patterns"):
        lines.append("### Avoid (Anti-patterns)")
        lines.append(f"- {ds['anti_patterns'].replace(' + ', chr(10) + '- ')}")
        lines.append("")

    # Checklist
    lines.append("### Pre-Delivery Checklist")
    for item in CHECKLIST:
        lines.append(f"- [ ] {item}")
    lines.append("")
    return "\n".join(lines)


def format_master_md(ds: dict) -> str:
    colors = ds.get("colors", {})
    typography = ds.get("typography", {})
    pattern = ds.get("pattern", {})
    style = ds.get("style", {})
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def section(title: str, body_lines: list[str]) -> list[str]:
        return [f"### {title}", ""] + body_lines + [""]

    lines = [
        "# Design System Master File",
        "",
        "> **LOGIC:** When building a specific page, first check `design-system/pages/[page-name].md`.",
        "> If that file exists, its rules **override** this Master file.",
        "> If not, strictly follow the rules below.",
        "",
        "---",
        "",
        f"**Project:** {ds.get('project_name', 'PROJECT')}",
        f"**Generated:** {timestamp}",
        f"**Category:** {ds.get('category', 'General')}",
        "",
        "---",
        "",
    ]

    # Color Palette
    color_lines = [
        "| Role | Hex | CSS Variable |",
        "|------|-----|--------------|",
        f"| Primary | `{colors.get('primary', '#2563EB')}` | `--color-primary` |",
        f"| Secondary | `{colors.get('secondary', '#3B82F6')}` | `--color-secondary` |",
        f"| CTA/Accent | `{colors.get('cta', '#F97316')}` | `--color-cta` |",
        f"| Background | `{colors.get('background', '#F8FAFC')}` | `--color-background` |",
        f"| Text | `{colors.get('text', '#1E293B')}` | `--color-text` |",
        "",
    ]
    if colors.get("notes"):
        color_lines += [f"**Color Notes:** {colors['notes']}", ""]
    lines += section("Color Palette", color_lines)

    # Typography
    typo_lines = [
        f"- **Heading Font:** {typography.get('heading', 'Inter')}",
        f"- **Body Font:** {typography.get('body', 'Inter')}",
    ]
    if typography.get("mood"):
        typo_lines.append(f"- **Mood:** {typography['mood']}")
    if typography.get("google_fonts_url"):
        typo_lines.append(
            f"- **Google Fonts:** [{typography.get('heading', '')} + {typography.get('body', '')}]({typography['google_fonts_url']})"
        )
    lines += section("Typography", typo_lines)
    if typography.get("css_import"):
        lines += ["**CSS Import:**", "```css", typography["css_import"], "```", ""]

    # Spacing + Shadows (static design tokens)
    for title, rows in [
        (
            "Spacing Variables",
            [
                ("`--space-xs`", "4px / 0.25rem", "Tight gaps"),
                ("`--space-sm`", "8px / 0.5rem", "Icon gaps, inline spacing"),
                ("`--space-md`", "16px / 1rem", "Standard padding"),
                ("`--space-lg`", "24px / 1.5rem", "Section padding"),
                ("`--space-xl`", "32px / 2rem", "Large gaps"),
                ("`--space-2xl`", "48px / 3rem", "Section margins"),
                ("`--space-3xl`", "64px / 4rem", "Hero padding"),
            ],
        ),
        (
            "Shadow Depths",
            [
                ("`--shadow-sm`", "0 1px 2px rgba(0,0,0,0.05)", "Subtle lift"),
                ("`--shadow-md`", "0 4px 6px rgba(0,0,0,0.1)", "Cards, buttons"),
                ("`--shadow-lg`", "0 10px 15px rgba(0,0,0,0.1)", "Modals, dropdowns"),
                (
                    "`--shadow-xl`",
                    "0 20px 25px rgba(0,0,0,0.15)",
                    "Hero images, featured cards",
                ),
            ],
        ),
    ]:
        lines += section(
            title,
            [
                "| Token | Value | Usage |",
                "|-------|-------|-------|",
            ]
            + [f"| {t} | {v} | {u} |" for t, v, u in rows]
            + [""],
        )

    # Component Specs
    lines += ["---", "", "## Component Specs", ""]
    p = colors.get("primary", "#2563EB")
    c = colors.get("cta", "#F97316")
    bg = colors.get("background", "#FFFFFF")

    lines += section(
        "Buttons",
        [
            "```css",
            f"/* Primary Button */",
            ".btn-primary {",
            f"  background: {c};",
            "  color: white;",
            "  padding: 12px 24px;",
            "  border-radius: 8px;",
            "  font-weight: 600;",
            "  transition: all 200ms ease;",
            "  cursor: pointer;",
            "}",
            "",
            ".btn-primary:hover {",
            "  opacity: 0.9;",
            "  transform: translateY(-1px);",
            "}",
            "",
            "/* Secondary Button */",
            ".btn-secondary {",
            "  background: transparent;",
            f"  color: {p};",
            f"  border: 2px solid {p};",
            "  padding: 12px 24px;",
            "  border-radius: 8px;",
            "  font-weight: 600;",
            "  transition: all 200ms ease;",
            "  cursor: pointer;",
            "}",
            "```",
            "",
        ],
    )

    lines += section(
        "Cards",
        [
            "```css",
            ".card {",
            f"  background: {bg};",
            "  border-radius: 12px;",
            "  padding: 24px;",
            "  box-shadow: var(--shadow-md);",
            "  transition: all 200ms ease;",
            "  cursor: pointer;",
            "}",
            "",
            ".card:hover {",
            "  box-shadow: var(--shadow-lg);",
            "  transform: translateY(-2px);",
            "}",
            "```",
            "",
        ],
    )

    lines += section(
        "Inputs",
        [
            "```css",
            ".input {",
            "  padding: 12px 16px;",
            "  border: 1px solid #E2E8F0;",
            "  border-radius: 8px;",
            "  font-size: 16px;",
            "  transition: border-color 200ms ease;",
            "}",
            "",
            ".input:focus {",
            f"  border-color: {p};",
            "  outline: none;",
            f"  box-shadow: 0 0 0 3px {p}20;",
            "}",
            "```",
            "",
        ],
    )

    lines += section(
        "Modals",
        [
            "```css",
            ".modal-overlay {",
            "  background: rgba(0, 0, 0, 0.5);",
            "  backdrop-filter: blur(4px);",
            "}",
            "",
            ".modal {",
            "  background: white;",
            "  border-radius: 16px;",
            "  padding: 32px;",
            "  box-shadow: var(--shadow-xl);",
            "  max-width: 500px;",
            "  width: 90%;",
            "}",
            "```",
            "",
        ],
    )

    # Style + Pattern + Antipatterns + Checklist (condensed)
    lines += [
        "---",
        "",
        "## Style Guidelines",
        "",
        f"**Style:** {style.get('name', 'Minimalism')}",
        "",
    ]
    if style.get("keywords"):
        lines.append(f"**Keywords:** {style['keywords']}")
        lines.append("")
    if style.get("best_for"):
        lines.append(f"**Best For:** {style['best_for']}")
        lines.append("")
    if ds.get("key_effects"):
        lines.append(f"**Key Effects:** {ds['key_effects']}")
        lines.append("")

    lines += [
        "### Page Pattern",
        "",
        f"**Pattern Name:** {pattern.get('name', '')}",
        "",
    ]
    if pattern.get("conversion"):
        lines.append(f"- **Conversion Strategy:** {pattern['conversion']}")
    if pattern.get("cta_placement"):
        lines.append(f"- **CTA Placement:** {pattern['cta_placement']}")
    lines.append(f"- **Section Order:** {pattern.get('sections', '')}", "")

    lines += ["---", "", "## Anti-Patterns (Do NOT Use)", ""]
    if ds.get("anti_patterns"):
        for a in ds["anti_patterns"].split("+"):
            a = a.strip()
            if a:
                lines.append(f"- ❌ {a}")
    lines += ["", "### Additional Forbidden Patterns", ""]
    for name, desc in ANTIPATTERNS:
        lines.append(f"- ❌ **{name}** — {desc}")
    lines.append("")

    lines += [
        "---",
        "",
        "## Pre-Delivery Checklist",
        "",
        "Before delivering any UI code, verify:",
        "",
    ]
    for item in CHECKLIST:
        lines.append(f"- [ ] {item}")
    lines += [
        "- [ ] No content hidden behind fixed navbars",
        "- [ ] No horizontal scroll on mobile",
        "",
    ]
    return "\n".join(lines)


def format_page_override_md(ds: dict, page_name: str, page_query: str = None) -> str:
    overrides = _generate_intelligent_overrides(page_name, page_query, ds)
    project = ds.get("project_name", "PROJECT")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    page_title = page_name.replace("-", " ").replace("_", " ").title()

    lines = [
        f"# {page_title} Page Overrides",
        "",
        f"> **PROJECT:** {project}",
        f"> **Generated:** {timestamp}",
        f"> **Page Type:** {overrides.get('page_type', 'General')}",
        "",
        "> ⚠️ **IMPORTANT:** Rules in this file **override** the Master file (`design-system/MASTER.md`).",
        "> Only deviations from the Master are documented here. For all other rules, refer to the Master.",
        "",
        "---",
        "",
    ]

    for section_name, key in [
        ("Layout Overrides", "layout"),
        ("Spacing Overrides", "spacing"),
        ("Typography Overrides", "typography"),
        ("Color Overrides", "colors"),
    ]:
        lines.append(f"### {section_name}", "")
        items = overrides.get(key, {})
        for k, v in items.items():
            lines.append(f"- **{k}:** {v}")
        if not items:
            lines.append(
                f"- No overrides — use Master {section_name.split()[0].lower()}"
            )
        lines.append("")

    lines.append("### Component Overrides", "")
    for comp in overrides.get("components", []):
        lines.append(f"- {comp}")
    if not overrides.get("components"):
        lines.append("- No overrides — use Master component specs")
    lines.append("")

    lines += ["---", "", "## Page-Specific Components", ""]
    for comp in overrides.get("unique_components", []):
        lines.append(f"- {comp}")
    if not overrides.get("unique_components"):
        lines.append("- No unique components for this page")
    lines.append("")

    lines += ["---", "", "## Recommendations", ""]
    for rec in overrides.get("recommendations", []):
        lines.append(f"- {rec}")
    lines.append("")
    return "\n".join(lines)


def _generate_intelligent_overrides(page_name: str, page_query: str, ds: dict) -> dict:
    combined = f"{page_name.lower()} {(page_query or '').lower()}"

    style_results = search(combined, "style", 1).get("results", [])
    ux_results = search(combined, "ux", 3).get("results", [])
    landing_results = search(combined, "landing", 1).get("results", [])

    layout, spacing, typography, colors, components, recommendations = (
        {},
        {},
        {},
        {},
        [],
        [],
    )

    if style_results:
        s = style_results[0]
        kw = s.get("Keywords", "").lower()
        if any(k in kw for k in ["data", "dense", "dashboard", "grid"]):
            layout["Max Width"] = "1400px or full-width"
            layout["Grid"] = "12-column grid for data flexibility"
            spacing["Content Density"] = "High — optimize for information display"
        elif any(k in kw for k in ["minimal", "simple", "clean", "single"]):
            layout["Max Width"] = "800px (narrow, focused)"
            layout["Layout"] = "Single column, centered"
            spacing["Content Density"] = "Low — focus on clarity"
        else:
            layout["Max Width"] = "1200px (standard)"
            layout["Layout"] = "Full-width sections, centered content"
        if s.get("Effects & Animation"):
            recommendations.append(f"Effects: {s['Effects & Animation']}")

    for ux in ux_results:
        if ux.get("Do"):
            recommendations.append(f"{ux.get('Category', '')}: {ux['Do']}")
        if ux.get("Don't"):
            dont = ux["Don't"]
            components.append(f"Avoid: {dont}")

    if landing_results:
        l = landing_results[0]
        if l.get("Section Order"):
            layout["Sections"] = l["Section Order"]
        if l.get("Primary CTA Placement"):
            recommendations.append(f"CTA Placement: {l['Primary CTA Placement']}")
        if l.get("Color Strategy"):
            colors["Strategy"] = l["Color Strategy"]

    if not layout:
        layout = {"Max Width": "1200px", "Layout": "Responsive grid"}
    if not recommendations:
        recommendations = [
            "Refer to MASTER.md for all design rules",
            "Add specific overrides as needed for this page",
        ]

    return {
        "page_type": _detect_page_type(combined, style_results),
        "layout": layout,
        "spacing": spacing,
        "typography": typography,
        "colors": colors,
        "components": components,
        "unique_components": [],
        "recommendations": recommendations,
    }


_PAGE_PATTERNS = [
    (
        [
            "dashboard",
            "admin",
            "analytics",
            "data",
            "metrics",
            "stats",
            "monitor",
            "overview",
        ],
        "Dashboard / Data View",
    ),
    (
        ["checkout", "payment", "cart", "purchase", "order", "billing"],
        "Checkout / Payment",
    ),
    (["settings", "profile", "account", "preferences", "config"], "Settings / Profile"),
    (
        ["landing", "marketing", "homepage", "hero", "home", "promo"],
        "Landing / Marketing",
    ),
    (["login", "signin", "signup", "register", "auth", "password"], "Authentication"),
    (["pricing", "plans", "subscription", "tiers", "packages"], "Pricing / Plans"),
    (["blog", "article", "post", "news", "content", "story"], "Blog / Article"),
    (["product", "item", "detail", "pdp", "shop", "store"], "Product Detail"),
    (["search", "results", "browse", "filter", "catalog", "list"], "Search Results"),
    (["empty", "404", "error", "not found", "zero"], "Empty State"),
]


def _detect_page_type(context: str, style_results: list) -> str:
    ctx = context.lower()
    for keywords, page_type in _PAGE_PATTERNS:
        if any(kw in ctx for kw in keywords):
            return page_type
    if style_results:
        best_for = style_results[0].get("Best For", "").lower()
        if "dashboard" in best_for or "data" in best_for:
            return "Dashboard / Data View"
        if "landing" in best_for or "marketing" in best_for:
            return "Landing / Marketing"
    return "General"


def generate_design_system(
    query: str,
    project_name: str = None,
    output_format: str = "ascii",
    persist: bool = False,
    page: str = None,
    output_dir: str = None,
) -> str:
    """Main entry point for design system generation."""
    generator = DesignSystemGenerator()
    ds = generator.generate(query, project_name)

    if persist:
        persist_design_system(ds, page, output_dir, query)

    return format_markdown(ds) if output_format == "markdown" else format_ascii_box(ds)


def persist_design_system(
    ds: dict, page: str = None, output_dir: str = None, page_query: str = None
) -> dict:
    """Persist design system to design-system/<project>/ folder."""
    base_dir = Path(output_dir) if output_dir else Path.cwd()
    project_slug = ds.get("project_name", "default").lower().replace(" ", "-")
    ds_dir = base_dir / "design-system" / project_slug
    pages_dir = ds_dir / "pages"

    ds_dir.mkdir(parents=True, exist_ok=True)
    pages_dir.mkdir(parents=True, exist_ok=True)

    master_path = ds_dir / "MASTER.md"
    master_path.write_text(format_master_md(ds), encoding="utf-8")
    created = [str(master_path)]

    if page:
        page_path = pages_dir / f"{page.lower().replace(' ', '-')}.md"
        page_path.write_text(
            format_page_override_md(ds, page, page_query), encoding="utf-8"
        )
        created.append(str(page_path))

    return {
        "status": "success",
        "design_system_dir": str(ds_dir),
        "created_files": created,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate Design System")
    parser.add_argument("query", help="Search query (e.g., 'SaaS dashboard')")
    parser.add_argument(
        "--project-name", "-p", type=str, default=None, help="Project name"
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["ascii", "markdown"],
        default="ascii",
        help="Output format",
    )
    args = parser.parse_args()
    print(generate_design_system(args.query, args.project_name, args.format))
