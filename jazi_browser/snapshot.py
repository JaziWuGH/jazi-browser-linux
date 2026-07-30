"""
Page snapshot engine — produces LLM-friendly structured representations of web pages.

Uses DOM-based extraction (querying interactive elements via JavaScript in the page)
rather than the accessibility tree, which requires newer Playwright versions.
"""

import re
from typing import Optional


def _sanitize_text(text, max_len: int = 120) -> str:
    """Clean up text for snapshot output."""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", str(text)).strip()
    if len(text) > max_len:
        text = text[:max_len - 3] + "..."
    return text


async def snapshot(page, compact: bool = True) -> str:
    """Take an LLM-friendly snapshot of the current page.

    Extracts interactive elements (buttons, links, inputs, selects, textareas)
    and assigns each a unique @eN ref ID for later interaction.
    Also maps data-jazi-ref attributes for click/fill targeting.

    Args:
        page: Playwright Page object
        compact: If True, show interactive elements + headings only

    Returns:
        Formatted snapshot text
    """
    url = page.url
    try:
        title = await page.title()
    except Exception:
        title = ""

    # Extract interactive elements with ref IDs
    elements = await _extract_elements(page)

    lines = [f"[Snapshot] URL: {url}"]
    if title:
        lines.append(f"Title: {title}")

    if not elements:
        if not compact:
            # Fall back to full body text
            try:
                body = await page.evaluate(
                    "() => document.body?.innerText?.substring(0, 3000) || ''"
                )
                lines.append(f"\nBody text:\n{body}")
            except Exception:
                lines.append("\n[Empty page]")
        else:
            lines.append("\n[No interactive elements found]")
        return "\n".join(lines)

    # Count by type
    type_counts = {}
    for el in elements:
        t = el.get("tag", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    lines.append(f"\n--- Interactive Elements ({len(elements)} total) ---")

    # Group by role/semantic category
    for el in elements:
        ref = el["ref"]
        tag = el.get("tag", "")
        role = el.get("role", "")
        text = _sanitize_text(el.get("text", ""), 80)
        el_type = el.get("type", "")
        placeholder = el.get("placeholder", "")
        value = el.get("value", "")
        href = el.get("href", "")
        name_attr = el.get("name", "")
        id_attr = el.get("id", "")

        # Format the element description
        desc_parts = []

        if role == "heading":
            level = el.get("heading_level", "")
            desc_parts.append(f"h{level}")

        # Tag-based formatting
        tag_display = tag
        if tag == "input" and el_type:
            tag_display = f"input[{el_type}]"
        elif tag == "select":
            tag_display = "select"
        elif tag == "textarea":
            tag_display = "textarea"

        desc_parts.append(tag_display)

        # Identifying info
        if text:
            desc_parts.append(f'"{text}"')
        if placeholder:
            desc_parts.append(f'placeholder="{placeholder}"')
        if name_attr:
            desc_parts.append(f'name="{name_attr}"')
        if id_attr:
            desc_parts.append(f'id="{id_attr}"')
        if value:
            desc_parts.append(f'value="{_sanitize_text(value, 30)}"')
        if href:
            short_href = href[:80] + ("..." if len(href) > 80 else "")
            desc_parts.append(f'href="{short_href}"')

        lines.append(f"  {ref} | {' | '.join(desc_parts)}")

    # Also extract headings for context
    if compact:
        headings = await _extract_headings(page)
        if headings:
            lines.insert(3, "\n--- Headings ---")
            for h in headings:
                lines.insert(4, f"  {h}")

    return "\n".join(lines)


async def _extract_elements(page) -> list[dict]:
    """Extract all interactive elements from the page with ref IDs.

    Assigns data-jazi-ref attributes for later targeting.
    """
    script = """
    () => {
        const selectors = [
            // Interactive elements
            'button',
            'a[href]',
            'input:not([type="hidden"])',
            'select',
            'textarea',
            // Semantic interactive
            '[role="button"]',
            '[role="link"]',
            '[role="textbox"]',
            '[role="checkbox"]',
            '[role="radio"]',
            '[role="combobox"]',
            '[role="menuitem"]',
            '[role="option"]',
            '[role="tab"]',
            '[role="switch"]',
            '[role="slider"]',
            '[role="spinbutton"]',
            '[role="searchbox"]',
            // Clickable non-standard
            '[onclick]:not(button):not(a)',
            '[tabindex]:not([tabindex="-1"])',
        ];

        const seen = new Set();
        const elements = [];

        for (const sel of selectors) {
            document.querySelectorAll(sel).forEach(el => {
                // Skip hidden elements
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden') return;
                if (el.offsetWidth === 0 && el.offsetHeight === 0) return;

                // Deduplicate
                if (seen.has(el)) return;
                seen.add(el);

                const tag = el.tagName.toLowerCase();
                const ref = '@e' + (elements.length + 1);
                el.setAttribute('data-jazi-ref', ref);

                elements.push({
                    ref: ref,
                    tag: tag,
                    role: el.getAttribute('role') || '',
                    text: (el.textContent || el.getAttribute('aria-label') || el.title || '').trim().substring(0, 80),
                    type: el.getAttribute('type') || '',
                    id: el.id || '',
                    name: el.getAttribute('name') || '',
                    placeholder: el.getAttribute('placeholder') || '',
                    value: el.value || el.getAttribute('value') || '',
                    href: el.getAttribute('href') || '',
                    heading_level: '',
                });
            });
        }

        return elements;
    }
    """
    try:
        elements = await page.evaluate(script)
        return elements or []
    except Exception:
        return []


async def _extract_headings(page) -> list[str]:
    """Extract heading hierarchy for page structure context."""
    script = """
    () => {
        const headings = [];
        for (let i = 1; i <= 4; i++) {
            document.querySelectorAll('h' + i).forEach(h => {
                const text = (h.textContent || '').trim().substring(0, 80);
                if (text) headings.push('#'.repeat(i) + ' ' + text);
            });
        }
        return headings;
    }
    """
    try:
        headings = await page.evaluate(script)
        return headings or []
    except Exception:
        return []


async def get_page_text(page, max_chars: int = 5000) -> str:
    """Extract visible text from the page."""
    try:
        text = await page.evaluate(
            f"() => (document.body?.innerText || '').substring(0, {max_chars})"
        )
        return text
    except Exception:
        return ""
