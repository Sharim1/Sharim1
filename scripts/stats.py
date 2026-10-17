"""Render GitHub stats and top-languages cards (SVG) straight from the GraphQL API."""
import json
import os
import sys
import urllib.request
from html import escape

USER = sys.argv[1]
OUT_DIR = sys.argv[2]
TOKEN = os.environ["GITHUB_TOKEN"]

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    repositoriesContributedTo(first: 1, contributionTypes: [COMMIT, PULL_REQUEST, ISSUE, REPOSITORY]) { totalCount }
    contributionsCollection { contributionCalendar { totalContributions } }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""

STYLE = ('font-family="Segoe UI, Ubuntu, sans-serif"')
BG, TITLE, TEXT, ICON = "#1a1b27", "#70a5fd", "#a9b1d6", "#bf91f3"


def gql():
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "User-Agent": "stats-card"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.load(resp)
    if "errors" in body:
        sys.exit(f"GraphQL error: {body['errors']}")
    return body["data"]["user"]


def card(width, height, title, inner):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" {STYLE}><rect width="{width}" height="{height}" rx="6" fill="{BG}"/>'
            f'<text x="25" y="35" font-size="18" font-weight="600" fill="{TITLE}">{escape(title)}</text>{inner}</svg>')


def stats_card(u):
    repos = u["repositories"]["nodes"]
    rows = [
        ("Total Stars", sum(r["stargazerCount"] for r in repos)),
        ("Contributions (last year)", u["contributionsCollection"]["contributionCalendar"]["totalContributions"]),
        ("Total PRs", u["pullRequests"]["totalCount"]),
        ("Total Issues", u["issues"]["totalCount"]),
        ("Contributed to", u["repositoriesContributedTo"]["totalCount"]),
        ("Followers", u["followers"]["totalCount"]),
    ]
    inner = ""
    for i, (label, value) in enumerate(rows):
        y = 70 + i * 25
        inner += (f'<circle cx="32" cy="{y - 4}" r="4" fill="{ICON}"/>'
                  f'<text x="48" y="{y}" font-size="14" font-weight="600" fill="{TEXT}">{label}:</text>'
                  f'<text x="260" y="{y}" font-size="14" font-weight="700" fill="{TEXT}">{value:,}</text>')
    return card(300, 70 + len(rows) * 25 + 5, f"{USER}'s GitHub Stats", inner)


def langs_card(u):
    totals, colors = {}, {}
    for repo in u["repositories"]["nodes"]:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            totals[name] = totals.get(name, 0) + edge["size"]
            colors[name] = edge["node"]["color"] or "#8b949e"
    top = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:6]
    whole = sum(size for _, size in top) or 1

    bar, x = "", 25.0
    for name, size in top:
        w = 250 * size / whole
        bar += f'<rect x="{x:.1f}" y="52" width="{w:.1f}" height="8" fill="{colors[name]}"/>'
        x += w
    inner = f'<clipPath id="c"><rect x="25" y="52" width="250" height="8" rx="4"/></clipPath><g clip-path="url(#c)">{bar}</g>'
    for i, (name, size) in enumerate(top):
        cx, cy = 25 + (i % 2) * 130, 85 + (i // 2) * 24
        inner += (f'<circle cx="{cx + 5}" cy="{cy - 4}" r="5" fill="{colors[name]}"/>'
                  f'<text x="{cx + 16}" y="{cy}" font-size="12" fill="{TEXT}">{escape(name)} {100 * size / whole:.1f}%</text>')
    return card(300, 85 + ((len(top) + 1) // 2) * 24 + 10, "Top Languages", inner)


def main():
    u = gql()
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, svg in (("stats.svg", stats_card(u)), ("langs.svg", langs_card(u))):
        with open(os.path.join(OUT_DIR, name), "w") as f:
            f.write(svg)
    print("stats + langs written")


main()
