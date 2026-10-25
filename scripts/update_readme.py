#!/usr/bin/env python3
# обновляет цифры и проекты в README профиля
# карточку языков (profile/top-langs.svg) рисует экшен в workflow

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# настройки
USERNAME = os.environ.get("GH_USER", "neodym121")
TOKEN = os.environ.get("GITHUB_TOKEN", "")

MAX_PROJECTS = 10
SKIP_FORKS = False
TIMEZONE = "Europe/Moscow"

README_PATH = Path(__file__).resolve().parent.parent / "README.md"

# бейджи языков у проектов (shields.io)
BADGE_STYLE = "flat-square"
DEFAULT_BADGE_COLOR = "6e7681"
# язык: (цвет как на гитхабе, иконка из simple-icons или None)
LANGUAGE_BADGES = {
    "Rust": ("dea584", "rust"),
    "Python": ("3572a5", "python"),
    "JavaScript": ("f1e05a", "javascript"),
    "TypeScript": ("3178c6", "typescript"),
    "HTML": ("e34c26", "html5"),
    "CSS": ("663399", "css"),
    "Go": ("00add8", "go"),
    "C": ("555555", "c"),
    "C++": ("f34b7d", "cplusplus"),
    "C#": ("178600", None),
    "Java": ("b07219", None),
    "Kotlin": ("a97bff", "kotlin"),
    "Shell": ("89e051", "gnubash"),
    "PowerShell": ("012456", None),
    "Lua": ("000080", "lua"),
    "PHP": ("4f5d95", "php"),
    "Ruby": ("701516", "ruby"),
    "Swift": ("f05138", "swift"),
    "Dart": ("00b4ab", "dart"),
    "Vue": ("41b883", "vuedotjs"),
    "Svelte": ("ff3e00", "svelte"),
    "Slint": ("2379f4", None),
}


# запросы к гитхабу
def api(path):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-readme-updater",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request("https://api.github.com" + path, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp), resp.headers


def get_repos():
    repos, page = [], 1
    while True:
        data, _ = api(f"/users/{USERNAME}/repos?type=owner&per_page=100&page={page}")
        repos += data
        if len(data) < 100:
            return repos
        page += 1


def get_starred_count():
    data, headers = api(f"/users/{USERNAME}/starred?per_page=1")
    match = re.search(r'[?&]page=(\d+)>; rel="last"', headers.get("Link", ""))
    return int(match.group(1)) if match else len(data)


def visible_repos(repos):
    repos = [r for r in repos
             if r["name"].lower() not in (USERNAME.lower(), ".github")
             and not (SKIP_FORKS and r.get("fork"))]
    repos.sort(key=lambda r: r.get("pushed_at") or "", reverse=True)
    return repos


# описание репо
def short(text, limit=90):
    text = " ".join((text or "").split()).split(". ")[0].rstrip(".")
    first = text.split(" ")[0]
    if first[:1].isupper() and first[1:] == first[1:].lower():
        text = text[0].lower() + text[1:]
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",.;:") + "…"


# куски README
def section_stats(repos, starred):
    stars_received = sum(r.get("stargazers_count", 0) for r in repos)
    return "\n".join([
        f"- **{len(repos)}** public repositories",
        f"- **{starred}** starred",
        f"- **{stars_received}** stars received",
    ])


def language_badge(lang):
    color, logo = LANGUAGE_BADGES.get(lang, (DEFAULT_BADGE_COLOR, None))
    # в пути shields «-» и «_» служебные, их удваивают
    text = lang.lower().replace("-", "--").replace("_", "__")
    url = f"https://img.shields.io/badge/{urllib.parse.quote(text, safe='')}-{color}?style={BADGE_STYLE}"
    if logo:
        # shields сам берёт тёмный текст на светлом фоне, иконку красим так же
        r, g, b = (int(color[i:i + 2], 16) for i in (0, 2, 4))
        logo_color = "black" if (r * 299 + g * 587 + b * 114) / 255000 >= 0.69 else "white"
        url += f"&logo={logo}&logoColor={logo_color}"
    return f"![{lang.lower()}]({url})"


def section_projects(repos):
    blocks = []
    for r in repos[:MAX_PROJECTS]:
        line = ""
        if r.get("language"):
            line += language_badge(r["language"]) + " "
        line += f"[**{r['name']}**]({r['html_url']})"
        # убираем «имя - » в начале описания, имя и так рядом
        desc = re.sub(rf"^{re.escape(r['name'])}\s*[-–—:]\s*", "", r.get("description") or "", flags=re.I)
        desc = short(desc)
        if desc:
            line += f" — {desc}"
        blocks.append(line)
    return "\n\n".join(blocks)


def section_updated(now):
    return f"<sub>Last updated {now.strftime('%d.%m.%y %H:%M')}</sub>"

def replace_section(text, name, body):
    pattern = re.compile(rf"(<!-- {name}:start -->\n).*?(\n<!-- {name}:end -->)", re.DOTALL)
    if not pattern.search(text):
        sys.exit(f"В README.md не найдены метки <!-- {name}:start --> и <!-- {name}:end -->")
    return pattern.sub(lambda m: m.group(1) + body + m.group(2), text, count=1)


def now_local():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(TIMEZONE))
    except Exception:
        return datetime.now(timezone.utc)

def update_text(old, repos, starred, now):
    repos = visible_repos(repos)
    new = old
    new = replace_section(new, "stats", section_stats(repos, starred))
    new = replace_section(new, "projects", section_projects(repos))
    if new == old:
        return None
    return replace_section(new, "updated", section_updated(now))


def main():
    repos = visible_repos(get_repos())
    starred = get_starred_count()

    old = README_PATH.read_text(encoding="utf-8")
    new = update_text(old, repos, starred, now_local())
    if new is None:
        print("Без изменений")
        return
    README_PATH.write_text(new, encoding="utf-8", newline="\n")
    print("README.md обновлён")


if __name__ == "__main__":
    main()
