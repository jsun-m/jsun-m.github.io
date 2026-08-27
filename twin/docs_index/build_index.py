"""Build the Beam docs BM25 index artifact.

Fetches https://docs.beam.cloud/llms.txt (Mintlify), pulls every page as raw
markdown, chunks by heading, and writes beam_docs_index.json.gz next to this
file. Run offline; the artifact ships with the deploy image.

Usage: python docs_index/build_index.py
"""

import gzip
import json
import re
import sys
from pathlib import Path

import httpx

DOCS_BASE = "https://docs.beam.cloud"
OUT_PATH = Path(__file__).parent / "beam_docs_index.json.gz"

MAX_CHUNK_CHARS = 2400
MIN_CHUNK_CHARS = 80

TOKEN_RE = re.compile(r"[a-z0-9_]+")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def page_urls(client: httpx.Client) -> list[str]:
    r = client.get(f"{DOCS_BASE}/llms.txt")
    r.raise_for_status()
    urls = []
    for m in re.finditer(r"\((https://docs\.beam\.cloud/[^)\s]+)\)", r.text):
        url = m.group(1).split("#")[0].rstrip("/")
        if url not in urls:
            urls.append(url)
    return urls


def split_page(url: str, markdown: str) -> list[dict]:
    """Split a markdown page into heading-scoped chunks."""
    title = url.rsplit("/", 1)[-1]
    m = re.search(r"^#\s+(.+)$", markdown, re.M)
    if m:
        title = m.group(1).strip()

    chunks = []
    heading = title
    buf: list[str] = []

    def flush():
        text = "\n".join(buf).strip()
        buf.clear()
        if len(text) < MIN_CHUNK_CHARS:
            return
        # oversized sections get split on paragraph boundaries
        while text:
            piece, text = text[:MAX_CHUNK_CHARS], text[MAX_CHUNK_CHARS:]
            if text:
                cut = piece.rfind("\n\n")
                if cut > MAX_CHUNK_CHARS // 2:
                    text = piece[cut:] + text
                    piece = piece[:cut]
            chunks.append({"url": url, "title": title, "heading": heading, "text": piece.strip()})

    for line in markdown.splitlines():
        hm = re.match(r"^(#{1,3})\s+(.+)$", line)
        if hm:
            flush()
            heading = hm.group(2).strip()
        else:
            buf.append(line)
    flush()
    return chunks


def main() -> int:
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        urls = page_urls(client)
        print(f"llms.txt: {len(urls)} pages")
        all_chunks: list[dict] = []
        failed = []
        for i, url in enumerate(urls, 1):
            try:
                r = client.get(url + ".md")
                if r.status_code != 200 or "<html" in r.text[:200].lower():
                    r = client.get(url)  # fallback: some pages serve md at the bare path
                r.raise_for_status()
                page_chunks = split_page(url, r.text)
                all_chunks.extend(page_chunks)
                if i % 20 == 0:
                    print(f"  {i}/{len(urls)} pages, {len(all_chunks)} chunks")
            except Exception as e:  # noqa: BLE001 — a few failed pages shouldn't kill the build
                failed.append((url, str(e)))

    for c in all_chunks:
        c["tokens"] = tokenize(f"{c['title']} {c['heading']} {c['text']}")

    payload = {"source": DOCS_BASE, "chunks": all_chunks}
    with gzip.open(OUT_PATH, "wt", encoding="utf-8") as f:
        json.dump(payload, f)

    print(f"wrote {OUT_PATH.name}: {len(all_chunks)} chunks from {len(urls) - len(failed)} pages "
          f"({OUT_PATH.stat().st_size // 1024} KB)")
    for url, err in failed:
        print(f"  FAILED {url}: {err}", file=sys.stderr)
    return 0 if len(all_chunks) >= 100 else 1


if __name__ == "__main__":
    raise SystemExit(main())
