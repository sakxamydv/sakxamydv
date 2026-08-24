"""
Fetches GitHub stats for GH_USERNAME and rewrites the block between
<!--START_SECTION:stats--> and <!--END_SECTION:stats--> in README.md.

Requires env vars:
  GH_TOKEN     - a token with `repo` and `read:user` scope
                 (the default GITHUB_TOKEN from Actions works)
  GH_USERNAME  - the GitHub username to report stats for
"""

import os
import re
import sys
import requests

API_URL = "https://api.github.com"
GRAPHQL_URL = "https://api.github.com/graphql"

TOKEN = os.environ["GH_TOKEN"]
USERNAME = os.environ["GH_USERNAME"]

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
}


def get_user_info():
    resp = requests.get(f"{API_URL}/users/{USERNAME}", headers=HEADERS)
    resp.raise_for_status()
    data = resp.json()
    return {
        "followers": data["followers"],
        "public_repos": data["public_repos"],
    }


def get_total_stars():
    stars = 0
    page = 1
    while True:
        resp = requests.get(
            f"{API_URL}/users/{USERNAME}/repos",
            headers=HEADERS,
            params={"per_page": 100, "page": page, "type": "owner"},
        )
        resp.raise_for_status()
        repos = resp.json()
        if not repos:
            break
        stars += sum(r["stargazers_count"] for r in repos)
        page += 1
    return stars


def get_commits_last_year():
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          totalCommitContributions
          restrictedContributionsCount
        }
      }
    }
    """
    resp = requests.post(
        GRAPHQL_URL,
        headers=HEADERS,
        json={"query": query, "variables": {"login": USERNAME}},
    )
    resp.raise_for_status()
    data = resp.json()["data"]["user"]["contributionsCollection"]
    return data["totalCommitContributions"] + data["restrictedContributionsCount"]


def build_stats_block(user_info, stars, commits):
    return (
        f"Repos: .......... {user_info['public_repos']} | "
        f"Stars: ............ {stars}\n"
        f"Followers: ...... {user_info['followers']} | "
        f"Commits (last yr): . {commits}"
    )


def update_readme(stats_block, path="README.md"):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    new_content = re.sub(
        r"(<!--START_SECTION:stats-->)(.*?)(<!--END_SECTION:stats-->)",
        lambda m: f"{m.group(1)}\n{stats_block}\n{m.group(3)}",
        content,
        flags=re.DOTALL,
    )

    if new_content == content:
        print("No changes to README.md")
        return False

    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("README.md updated")
    return True


def main():
    user_info = get_user_info()
    stars = get_total_stars()
    commits = get_commits_last_year()
    stats_block = build_stats_block(user_info, stars, commits)
    update_readme(stats_block)


if __name__ == "__main__":
    try:
        main()
    except requests.HTTPError as e:
        print(f"GitHub API error: {e}", file=sys.stderr)
        sys.exit(1)
