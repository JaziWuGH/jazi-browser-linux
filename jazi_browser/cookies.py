"""
Cookie import/export — migrate browser login state across machines.

Export: dumps cookies from a Space (or default) to a portable JSON file.
Import: loads cookies from JSON into a Space, preserving login sessions.

Cross-platform flow:
  Windows Chrome → Export JSON (via browser extension or manual) 
  → Copy file to Linux → jazi cookies import <file>
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


async def export_cookies(context, output_path: Optional[Path] = None) -> Path:
    """Export all cookies from a BrowserContext to a JSON file.

    Args:
        context: Playwright BrowserContext
        output_path: Optional file path. Defaults to ~/jazi-cookies-<timestamp>.json

    Returns:
        Path to the exported file
    """

    # Collect cookies from all pages in the space
    all_cookies = []
    seen = set()

    for page in context.pages:
        try:
            cookies = await page.context.cookies()
            for c in cookies:
                key = f"{c['name']}@{c['domain']}"
                if key not in seen:
                    seen.add(key)
                    all_cookies.append({
                        "name": c["name"],
                        "value": c["value"],
                        "domain": c["domain"],
                        "path": c.get("path", "/"),
                        "expires": c.get("expires", -1),
                        "httpOnly": c.get("httpOnly", False),
                        "secure": c.get("secure", False),
                        "sameSite": c.get("sameSite", "Lax"),
                    })
        except Exception as e:
            logger.warning(f"Could not read cookies from page: {e}")

    if not output_path:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_path = Path.home() / f"jazi-cookies-{ts}.json"

    output = {
        "version": 1,
        "exported_at": datetime.now().isoformat(),
        "source": "jazi-browser",
        "count": len(all_cookies),
        "cookies": all_cookies,
    }

    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    logger.info(f"Exported {len(all_cookies)} cookies to {output_path}")

    return output_path


async def import_cookies(context, input_path: Path, clear_existing: bool = False):
    """Import cookies from a JSON file into a BrowserContext.

    Supports:
    - Jazi Browser export format (version 1)
    - Playwright storageState format
    - Simple array of cookie objects

    Args:
        context: Playwright BrowserContext
        input_path: Path to JSON file
        clear_existing: If True, clear existing cookies before import

    Returns:
        dict with import statistics
    """
    from .space import SpaceManager

    if not input_path.exists():
        raise FileNotFoundError(f"Cookie file not found: {input_path}")

    data = json.loads(input_path.read_text())

    # Detect format and extract cookies
    cookies = _extract_cookies(data)

    if not cookies:
        return {"imported": 0, "skipped": 0, "errors": ["No cookies found in file"]}

    # Clear existing cookies if requested
    if clear_existing:
        try:
            await context.clear_cookies()
        except Exception as e:
            logger.warning(f"Could not clear cookies: {e}")

    # Import cookies
    imported = 0
    skipped = 0
    errors = []

    for c in cookies:
        try:
            cookie_params = {
                "name": c["name"],
                "value": c["value"],
                "domain": c.get("domain", ""),
                "path": c.get("path", "/"),
            }

            # Optional fields
            if "url" in c and c["url"]:
                cookie_params["url"] = c["url"]
            if "expires" in c and c["expires"] and c["expires"] > 0:
                cookie_params["expires"] = c["expires"]
            if "httpOnly" in c:
                cookie_params["httpOnly"] = c["httpOnly"]
            if "secure" in c:
                cookie_params["secure"] = c["secure"]
            if "sameSite" in c:
                cookie_params["sameSite"] = c["sameSite"]

            await context.add_cookies([cookie_params])
            imported += 1
        except Exception as e:
            error_msg = f"{c.get('name', '?')}@{c.get('domain', '?')}: {e}"
            errors.append(error_msg)
            skipped += 1
            logger.debug(f"Cookie import skipped: {error_msg}")

    result = {
        "imported": imported,
        "skipped": skipped,
        "total_in_file": len(cookies),
    }
    if errors:
        result["errors"] = errors[:10]  # First 10 errors only

    logger.info(f"Cookie import complete: {imported} imported, {skipped} skipped")
    return result


def _extract_cookies(data) -> list:
    """Extract cookie list from various JSON formats.

    Supports:
    1. Jazi format: {"version": 1, "cookies": [...]}
    2. Playwright storageState: {"cookies": [...]}
    3. Raw array: [...]
    4. EditThisCookie format: [{"name": ..., "value": ..., ...}]
    """
    if isinstance(data, list):
        # Raw array (EditThisCookie style)
        return data

    if isinstance(data, dict):
        # Jazi or Playwright format
        if "cookies" in data:
            return data["cookies"]

        # Maybe it's a single cookie object? Wrap it.
        if "name" in data and "value" in data:
            return [data]

    return []


def inspect_cookies(input_path: Path) -> dict:
    """Preview a cookie file without importing.

    Returns a summary: domain counts, top domains, total count.
    """
    if not input_path.exists():
        return {"error": f"File not found: {input_path}"}

    data = json.loads(input_path.read_text())
    cookies = _extract_cookies(data)

    if not cookies:
        return {"error": "No cookies found in file", "total": 0}

    # Count by domain
    domains = {}
    for c in cookies:
        domain = c.get("domain", "(unknown)")
        domains[domain] = domains.get(domain, 0) + 1

    # Sort by count
    top_domains = sorted(domains.items(), key=lambda x: x[1], reverse=True)[:20]

    return {
        "total": len(cookies),
        "unique_domains": len(domains),
        "top_domains": [{"domain": d, "cookies": n} for d, n in top_domains],
        "exported_at": data.get("exported_at", "unknown") if isinstance(data, dict) else "unknown",
    }
