"""Render a contribution streak card (SVG) straight from GitHub's contribution calendar."""
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone

USER = sys.argv[1]
OUT = sys.argv[2]
TOKEN = os.environ["GITHUB_TOKEN"]

QUERY = """
query($login: String!, $from: DateTime, $to: DateTime) {
  user(login: $login) {
    createdAt
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar { weeks { contributionDays { date contributionCount } } }
    }
  }
}
"""


def gql(variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "User-Agent": "streak-card"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.load(resp)
    if "errors" in body:
        sys.exit(f"GraphQL error: {body['errors']}")
    return body["data"]["user"]


def fetch_days():
    now = datetime.now(timezone.utc)
    created = datetime.fromisoformat(gql({"login": USER})["createdAt"].replace("Z", "+00:00"))
    days = {}
    start = created
    while start < now:
        end = min(start + timedelta(days=364), now)
        user = gql({"login": USER, "from": start.isoformat(), "to": end.isoformat()})
        for week in user["contributionsCollection"]["contributionCalendar"]["weeks"]:
            for d in week["contributionDays"]:
                days[d["date"]] = d["contributionCount"]
        start = end + timedelta(days=1)
    return days, created.date()


def streaks(days, today):
    longest = run = 0
    longest_span = None
    run_start = None
    day = min(date.fromisoformat(k) for k in days)
    while day <= today:
        if days.get(day.isoformat(), 0) > 0:
            run_start = run_start or day
            run += 1
            if run > longest:
                longest, longest_span = run, (run_start, day)
        else:
            run, run_start = 0, None
        day += timedelta(days=1)

    # Current streak: still alive if today has no contributions yet but yesterday did.
    cur_end = today if days.get(today.isoformat(), 0) > 0 else today - timedelta(days=1)
    cur, day = 0, cur_end
    while days.get(day.isoformat(), 0) > 0:
        cur += 1
        day -= timedelta(days=1)
    cur_span = (day + timedelta(days=1), cur_end) if cur else None
    return cur, cur_span, longest, longest_span


def fmt(span):
    if not span:
        return "-"
    a, b = span
    f = lambda d: d.strftime("%b %-d")
    return f"{f(a)} - {f(b)}" if a != b else f(a)


def render(total, first, cur, cur_span, longest, longest_span, updated):
    col = [("Total Contributions", f"{total:,}", f"{first.strftime('%b %-d, %Y')} - Present", "#70a5fd"),
           ("Current Streak", str(cur), fmt(cur_span), "#bf91f3"),
           ("Longest Streak", str(longest), fmt(longest_span), "#70a5fd")]
    cells = ""
    for i, (label, big, sub, color) in enumerate(col):
        x = 82 + i * 165
        cells += (f'<text x="{x}" y="62" text-anchor="middle" font-size="28" font-weight="700" fill="{color}">{big}</text>'
                  f'<text x="{x}" y="98" text-anchor="middle" font-size="14" font-weight="600" fill="{color}">{label}</text>'
                  f'<text x="{x}" y="124" text-anchor="middle" font-size="11" fill="#38bdae">{sub}</text>')
        if i:
            cells += f'<line x1="{x - 82}" y1="25" x2="{x - 82}" y2="125" stroke="#3b4261" stroke-width="1"/>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="495" height="165" viewBox="0 0 495 165" '
            f'font-family="Segoe UI, Ubuntu, sans-serif"><rect width="495" height="165" rx="6" fill="#1a1b27"/>'
            f'{cells}<text x="247" y="152" text-anchor="middle" font-size="9" fill="#565f89">updated {updated}</text></svg>')


def main():
    days, first = fetch_days()
    today = datetime.now(timezone.utc).date()
    total = sum(days.values())
    cur, cur_span, longest, longest_span = streaks(days, today)
    svg = render(total, first, cur, cur_span, longest, longest_span, f"{today.isoformat()} UTC")
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w") as f:
        f.write(svg)
    print(f"total={total} current={cur} {fmt(cur_span)} longest={longest} {fmt(longest_span)}")


main()
