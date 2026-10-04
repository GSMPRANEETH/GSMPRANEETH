"""Refresh from public GitHub data. Check: python3 scripts/refresh-profile.py --check."""

from datetime import datetime
from html import escape
import json
from pathlib import Path
import re
import subprocess
import sys
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OWNER = "GSMPRANEETH"
START, END = "<!-- recent-work:start -->", "<!-- recent-work:end -->"


def recent_repositories(repositories):
    for repo in repositories:
        name = repo["name"]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
            raise ValueError("Unexpected repository name")
        if repo["html_url"] != f"https://github.com/{OWNER}/{name}":
            raise ValueError("Unexpected repository URL")
        if repo.get("pushed_at"):
            datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))
    # Keep daily refreshes within the projects selected for this profile.
    return sorted(
        (repo for repo in repositories if not repo["private"]
         and repo.get("pushed_at") and repo["name"] == "TEAM-5"),
        key=lambda repo: repo["pushed_at"], reverse=True,
    )


def push_date(repo):
    return datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00")).astimezone(
        ZoneInfo("Asia/Kolkata")
    ).strftime("%d %b %Y")


def render_panel(repositories, recent, snapshot):
    rows = []
    for index, repo in enumerate(recent):
        y = 96 + index * 45
        name = repo["name"] if len(repo["name"]) <= 27 else repo["name"][:24] + "..."
        rows.append(f'<text x="284" y="{y}" class="name">{escape(name)}</text>'
                    f'<text x="284" y="{y + 17}" class="meta">{escape(repo.get("language") or "No primary language")} · last pushed {push_date(repo)}</text>')
    if not recent:
        rows.append('<text x="284" y="114" class="name">No public project updates yet.</text>')
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="820" height="150" viewBox="0 0 820 150" role="img" aria-labelledby="title desc">
<title id="title">AuraSync source activity</title>
<desc id="desc">AuraSync public repository: {escape(', '.join(repo['name'] for repo in recent)) or 'not available'}. Snapshot {snapshot}, India time.</desc>
<style>
.mono,.meta{{font-family:ui-monospace,Consolas,monospace}}.name,.count{{font-family:Arial,Helvetica,sans-serif}}.name{{font-size:17px;font-weight:700;fill:#eeeae1}}.meta{{font-size:11px;fill:#b0b0a4}}.dot{{animation:pulse 3s ease-in-out infinite}}@keyframes pulse{{50%{{opacity:.35}}}}@media(prefers-reduced-motion:reduce){{.dot{{animation:none}}}}
</style>
<rect width="820" height="150" rx="14" fill="#151613"/>
<circle cx="32" cy="34" r="4" fill="#ff7547" class="dot"/>
<text x="46" y="38" class="mono" font-size="11" letter-spacing="1.5" fill="#eeeae1">AURASYNC / PUBLIC ACTIVITY</text>
<text x="788" y="38" text-anchor="end" class="meta">{snapshot} IST</text>
<path d="M32 57h756M252 77v46" stroke="#eeeae1" stroke-opacity=".15"/>
<text x="32" y="102" class="name" fill="#ff7547">AuraSync</text>
<text x="32" y="121" class="meta">team project / public source</text>
{''.join(rows)}
</svg>
'''
    ElementTree.fromstring(svg)
    return svg


def update_readme(readme, recent):
    if readme.count(START) != 1 or readme.count(END) != 1 or readme.index(START) > readme.index(END):
        raise ValueError("README must have one ordered recent-work marker pair")
    links = "\n".join(f'- [{repo["name"]}]({repo["html_url"]}) — last pushed {push_date(repo)}'
                      for repo in recent) or "No public project updates yet."
    before, rest = readme.split(START)
    _, after = rest.split(END)
    return before + START + "\n\n" + links + "\n\n" + END + after


def self_check():
    def repo(name, date="2026-09-06T23:30:00Z", **changes):
        return {"name": name, "html_url": f"https://github.com/{OWNER}/{name}",
                "pushed_at": date, "fork": False, "private": False,
                "language": "TypeScript", **changes}

    repositories = [repo("TEAM-5"), repo("capstone2"), repo("extension"),
                    repo("dtihsb", private=True), repo(OWNER)]
    recent = recent_repositories(repositories)
    assert [item["name"] for item in recent] == ["TEAM-5"]
    assert recent_repositories([repo("TEAM-5", fork=True)])
    assert not recent_repositories([repo("TEAM-5", private=True)])
    assert push_date(recent[0]) == "07 Sep 2026", "Use India time at date boundaries"
    xml = render_panel(repositories, recent, "02 Oct 2026")
    assert "TEAM-5" in xml and "AuraSync source activity" in xml
    assert "capstone2" not in xml and "extension" not in xml and "dtihsb" not in xml
    repositories[0]["language"] = 'C<&"'
    ElementTree.fromstring(render_panel(repositories, recent, "02 Oct 2026"))
    original = "Keep this intro\n" + START + "old content" + END + "\nKeep this footer"
    updated = update_readme(original, recent)
    assert updated.startswith("Keep this intro") and updated.endswith("Keep this footer")
    assert "[TEAM-5]" in updated and "old content" not in updated
    assert "No public project updates yet." in render_panel([], [], "02 Oct 2026")
    for bad in ["no markers", END + START, START + START + END]:
        try:
            update_readme(bad, recent)
        except ValueError:
            continue
        raise AssertionError("Invalid markers accepted")
    malicious = repo("safe")
    malicious["html_url"] = "https://example.com/phishing"
    try:
        recent_repositories([malicious])
    except ValueError:
        pass
    else:
        raise AssertionError("Unexpected URL accepted")
    print("Profile check passed: filtering, India dates, XML escaping, empty data and README preservation.")


if __name__ == "__main__":
    if sys.argv[1:] == ["--check"]:
        self_check()
    else:
        result = subprocess.run(["gh", "api", f"users/{OWNER}/repos?per_page=100",
                                 "--paginate", "--jq", ".[]"], check=True, capture_output=True, text=True)
        repositories = [json.loads(line) for line in result.stdout.splitlines()]
        recent = recent_repositories(repositories)
        snapshot = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y")
        svg = render_panel(repositories, recent, snapshot)
        readme = update_readme((ROOT / "README.md").read_text(), recent)
        (ROOT / "assets/activity.svg").write_text(svg)
        (ROOT / "README.md").write_text(readme)
        print(f"Refreshed {len(recent)} project links from {len(repositories)} public repositories.")
