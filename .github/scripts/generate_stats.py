"""Generate theme-aware public GitHub statistics using only the Python stdlib."""

import argparse
from collections import Counter
from datetime import datetime, timezone
from html import escape
import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def get_json(path):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-stats"}
    if token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"https://api.github.com/{path}", headers=headers)
    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except (HTTPError, URLError) as error:
            if isinstance(error, HTTPError) and error.code < 500 and error.code != 429:
                raise
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def repositories(owner):
    result = []
    page = 1
    while True:
        batch = get_json(f"users/{owner}/repos?type=owner&per_page=100&page={page}")
        result.extend(repo for repo in batch if not repo["fork"] and not repo["private"])
        if len(batch) < 100:
            return result
        page += 1


def render(repos, dark, date):
    bg, fg, muted, border, accent = (
        ("#0d1117", "#f0f6fc", "#b1bac4", "#30363d", "#79c0ff") if dark else
        ("#ffffff", "#1f2328", "#59636e", "#d1d9e0", "#0969da")
    )
    languages = Counter(repo["language"] for repo in repos if repo["language"])
    rows = sorted(languages.items(), key=lambda item: (-item[1], item[0]))[:5]
    height = 242 + max(1, len(rows)) * 34
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="480" height="{height}" '
           f'viewBox="0 0 480 {height}" role="img" aria-labelledby="title desc">',
           '<title id="title">Public GitHub snapshot</title>',
           '<desc id="desc">Owned public repositories, excluding forks. Languages counted '
           'by repository primary language, not code volume or proficiency.</desc>',
           f'<rect x="0.5" y="0.5" width="479" height="{height - 1}" rx="12" '
           f'fill="{bg}" stroke="{border}"/>',
           '<g font-family="-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif">']

    def text(x, y, value, size=16, color=fg, weight=400):
        svg.append(f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" '
                   f'font-weight="{weight}">{escape(str(value))}</text>')

    text(24, 36, "PUBLIC GITHUB SNAPSHOT", 14, accent, 600)
    text(24, 64, f"Updated {date} UTC", 13, muted)
    text(24, 110, len(repos), 30, fg, 600)
    text(244, 110, sum(repo["stargazers_count"] for repo in repos), 30, fg, 600)
    text(24, 137, "Repositories", 15, muted)
    text(244, 137, "Stars received", 15, muted)
    svg.append(f'<path d="M24 158H456" stroke="{border}"/>')
    text(24, 187, "Primary languages", 16, fg, 600)
    text(24, 210, "Top five · number of repositories", 13, muted)
    if not rows:
        text(24, 242, "No language data available yet", 15, muted)
    for index, (language, count) in enumerate(rows):
        y = 242 + index * 34
        text(24, y, language, 15)
        svg.append(f'<rect x="220" y="{y - 10}" width="180" height="6" rx="3" fill="{border}"/>')
        svg.append(f'<rect x="220" y="{y - 10}" width="{180 * count / len(repos):.2f}" '
                   f'height="6" rx="3" fill="{accent}"/>')
        text(422, y, count, 15, muted)
    svg.append('</g></svg>\n')
    return "\n".join(svg)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", default=os.environ.get("PROFILE_OWNER"))
    parser.add_argument("--output", type=Path, default=Path("dist/assets"))
    args = parser.parse_args()
    if not args.owner or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", args.owner):
        parser.error("a valid GitHub --owner or PROFILE_OWNER is required")
    repos = repositories(args.owner)
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    args.output.mkdir(parents=True, exist_ok=True)
    for theme in ("light", "dark"):
        (args.output / f"stats-{theme}.svg").write_text(render(repos, theme == "dark", date))
    print(f"Generated light/dark statistics for {len(repos)} public non-fork repositories.")


if __name__ == "__main__":
    main()
