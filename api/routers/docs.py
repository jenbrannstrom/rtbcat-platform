"""Docs Router - Serve manual chapters as in-app documentation.

Reads markdown files from /manual/ (EN) and /manual/zh/ (ZH) and
exposes them via two endpoints: table-of-contents and chapter content.

Chapters are split into public (visible to everyone, for SEO) and
internal (requires authentication). Sensitive data is redacted from
all publicly served content.
"""

import logging
import re
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Docs"])

# Resolve manual directory relative to project root
_MANUAL_DIR = Path(__file__).resolve().parent.parent.parent / "manual"

# Reference slugs get high order numbers so they sort after numbered chapters
_REFERENCE_ORDER = {
    "glossary": 100,
    "faq": 101,
    "api-reference": 102,
    "index": -1,  # excluded from TOC list
}

# ── Visibility ───────────────────────────────────────────────────────
# Public: chapters 0-10, glossary, faq  (media buyer + getting started)
# Internal: chapters 11-17, api-reference (devops, architecture, credentials)

_INTERNAL_SLUGS = {
    "11-architecture",
    "12-deployment",
    "13-health-monitoring",
    "14-database",
    "15-troubleshooting",
    "16-user-admin",
    "17-integrations",
    "api-reference",
}


def _is_internal(slug: str) -> bool:
    return slug in _INTERNAL_SLUGS


# ── Redaction ────────────────────────────────────────────────────────
# Strip sensitive patterns from content served to unauthenticated users.

_REDACT_PATTERNS = [
    # Email addresses (internal)
    (re.compile(r"cat-scan@rtb\.cat"), "canary@example.com"),
    # Specific buyer account IDs
    (re.compile(r"1487810529"), "BUYER_ID"),
    # Environment variable assignments with sensitive values
    (re.compile(
        r'export\s+(CATSCAN_BEARER_TOKEN|CATSCAN_SESSION_COOKIE)="[^"]*"'
    ), r'export \1="<REDACTED>"'),
    # X-Email header trust chain details (must run before generic OAUTH2 pattern)
    (re.compile(
        r"Trusted by the API when `OAUTH2_PROXY_ENABLED=true`\."
        r" Stripped by nginx for external requests\."
    ), "Used internally for authentication."),
    # OAuth2 Proxy internals
    (re.compile(r"OAUTH2_PROXY_ENABLED=true"), "OAUTH2_PROXY_ENABLED=<value>"),
    # Cloud SQL Proxy references
    (re.compile(r"sudo docker ps \| grep cloudsql"), "<check database proxy status>"),
]


def _redact(content: str) -> str:
    """Remove sensitive operational details from markdown content."""
    for pattern, replacement in _REDACT_PATTERNS:
        content = pattern.sub(replacement, content)
    return content


# ── Part groupings ───────────────────────────────────────────────────

_PARTS = {
    range(0, 3): "Getting Started",
    range(3, 11): "Media Buyer Track",
    range(11, 18): "DevOps Track",
}


def _get_part(order: int) -> str:
    if order >= 100:
        return "Reference"
    for r, name in _PARTS.items():
        if order in r:
            return name
    return "Reference"


def _lang_dir(lang: str) -> Path:
    if lang == "zh":
        d = _MANUAL_DIR / "zh"
        if d.is_dir():
            return d
    return _MANUAL_DIR


def _parse_order(filename: str) -> int:
    m = re.match(r"^(\d+)-", filename)
    if m:
        return int(m.group(1))
    return _REFERENCE_ORDER.get(filename.replace(".md", ""), 999)


def _extract_title(content: str) -> str:
    first_line = content.split("\n", 1)[0].strip()
    if first_line.startswith("# "):
        return first_line[2:].strip()
    return first_line


def _extract_audience(content: str) -> Optional[str]:
    lines = content.split("\n", 4)
    if len(lines) >= 3:
        line = lines[2].strip()
        m = re.match(r"^\*(.+)\*$", line)
        if m:
            return m.group(1)
    return None


def _rewrite_md_links(content: str) -> str:
    return re.sub(
        r"\((\d{2}-[a-z0-9-]+)\.md\)",
        r"(/docs/\1)",
        content,
    )


def _rewrite_reference_links(content: str) -> str:
    for slug in ("glossary", "faq", "api-reference", "index"):
        content = content.replace(f"({slug}.md)", f"(/docs/{slug})")
    return content


def _rewrite_image_paths(content: str) -> str:
    """Rewrite relative image paths to the API image endpoint."""
    content = re.sub(
        r"\(\.\./images/([^)]+)\)",
        r"(/api/docs/images/\1)",
        content,
    )
    content = re.sub(
        r"\(images/([^)]+)\)",
        r"(/api/docs/images/\1)",
        content,
    )
    return content


# ── Response models ──────────────────────────────────────────────────

class TocEntry(BaseModel):
    slug: str
    title: str
    audience: Optional[str] = None
    order: int
    part: str
    internal: bool = False


class TocResponse(BaseModel):
    chapters: List[TocEntry]
    lang: str


class ChapterResponse(BaseModel):
    slug: str
    title: str
    content: str
    prev_slug: Optional[str] = None
    next_slug: Optional[str] = None
    lang: str
    internal: bool = False


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("/docs/toc", response_model=TocResponse)
async def get_docs_toc(
    lang: str = Query("en", pattern="^(en|zh)$"),
    internal: bool = Query(False, description="Include internal (DevOps) chapters"),
):
    """Return the table of contents as a sorted chapter list."""
    directory = _lang_dir(lang)
    if not directory.is_dir():
        raise HTTPException(status_code=404, detail="Manual directory not found")

    entries: List[TocEntry] = []
    for md_file in sorted(directory.glob("*.md")):
        slug = md_file.stem
        order = _parse_order(md_file.name)
        if order == -1:
            continue

        is_internal = _is_internal(slug)
        if is_internal and not internal:
            continue

        try:
            text = md_file.read_text(encoding="utf-8")
        except OSError:
            continue

        title = _extract_title(text)
        audience = _extract_audience(text)
        part = _get_part(order)

        entries.append(TocEntry(
            slug=slug,
            title=title,
            audience=audience,
            order=order,
            part=part,
            internal=is_internal,
        ))

    entries.sort(key=lambda e: e.order)
    return TocResponse(chapters=entries, lang=lang)


@router.get("/docs/content/{slug}", response_model=ChapterResponse)
async def get_docs_content(
    slug: str,
    lang: str = Query("en", pattern="^(en|zh)$"),
    internal: bool = Query(False, description="Allow internal chapters"),
):
    """Return the markdown content for a chapter."""
    # Block internal chapters for public requests
    if _is_internal(slug) and not internal:
        raise HTTPException(
            status_code=403,
            detail="This chapter is only available to authenticated users.",
        )

    directory = _lang_dir(lang)
    md_path = directory / f"{slug}.md"

    if not md_path.is_file() and lang != "en":
        directory = _MANUAL_DIR
        md_path = directory / f"{slug}.md"
        lang = "en"

    if not md_path.is_file():
        raise HTTPException(status_code=404, detail=f"Chapter '{slug}' not found")

    try:
        content = md_path.read_text(encoding="utf-8")
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to read chapter: {e}")

    title = _extract_title(content)
    content = _rewrite_md_links(content)
    content = _rewrite_reference_links(content)
    content = _rewrite_image_paths(content)

    # Redact sensitive data for public requests
    if not internal:
        content = _redact(content)

    # Build prev/next from sorted file list (scoped to visibility)
    all_slugs = _get_ordered_slugs(directory, include_internal=internal)
    prev_slug = None
    next_slug = None
    if slug in all_slugs:
        idx = all_slugs.index(slug)
        if idx > 0:
            prev_slug = all_slugs[idx - 1]
        if idx < len(all_slugs) - 1:
            next_slug = all_slugs[idx + 1]

    return ChapterResponse(
        slug=slug,
        title=title,
        content=content,
        prev_slug=prev_slug,
        next_slug=next_slug,
        lang=lang,
        internal=_is_internal(slug),
    )


def _get_ordered_slugs(directory: Path, include_internal: bool = False) -> List[str]:
    slugs = []
    for md_file in sorted(directory.glob("*.md")):
        slug = md_file.stem
        order = _parse_order(md_file.name)
        if order == -1:
            continue
        if _is_internal(slug) and not include_internal:
            continue
        slugs.append(slug)
    slugs.sort(key=lambda s: _parse_order(s + ".md"))
    return slugs


_IMAGES_DIR = _MANUAL_DIR / "images"
_ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}


@router.get("/docs/images/{filename}")
async def get_docs_image(filename: str):
    """Serve an image from manual/images/."""
    path = (_IMAGES_DIR / filename).resolve()
    if not str(path).startswith(str(_IMAGES_DIR.resolve())):
        raise HTTPException(status_code=403, detail="Invalid path")
    if path.suffix.lower() not in _ALLOWED_IMAGE_EXT:
        raise HTTPException(status_code=400, detail="Unsupported file type")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path)
