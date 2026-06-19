from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_REPO = os.environ["GITHUB_REPOSITORY"]
GITHUB_SHA = os.environ["GITHUB_SHA"]
GITHUB_API = os.environ.get("GITHUB_API_URL", "https://api.github.com")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
EVENT_NAME = os.environ["GITHUB_EVENT_NAME"]
EVENT_PATH = os.environ["GITHUB_EVENT_PATH"]


def get_pr_diff(event: dict) -> str:
    pr_url = event["pull_request"]["url"]
    req = urllib.request.Request(
        pr_url,
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3.diff",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.read().decode()
    except urllib.error.HTTPError as e:
        print(f"Failed to fetch PR diff: {e.code} {e.reason}")
        return ""


def get_push_diff(event: dict) -> str:
    before = event.get("before")
    try:
        if not before or before == "0000000000000000000000000000000000000000":
            result = subprocess.run(
                ["git", "diff", "4b825dc642cb6eb9a060e54bf899d153036e3e6e", "HEAD"],
                capture_output=True, text=True, check=True,
            )
        else:
            result = subprocess.run(
                ["git", "diff", f"{before}..HEAD"],
                capture_output=True, text=True, check=True,
            )
    except subprocess.CalledProcessError:
        return ""
    return result.stdout


def get_diff() -> str:
    with open(EVENT_PATH) as f:
        event = json.load(f)

    if EVENT_NAME == "pull_request":
        return get_pr_diff(event)
    elif EVENT_NAME == "push":
        return get_push_diff(event)
    else:
        print(f"Unsupported event: {EVENT_NAME}")
        sys.exit(1)


def review_with_gemini(diff: str, max_diff_chars: int = 50_000) -> str:
    if len(diff) > max_diff_chars:
        diff = diff[:max_diff_chars] + "\n... (diff truncated)"

    prompt = f"""You are a senior Python code reviewer. Review the
following code diff for the Promptune project
(an intelligent AI prompt enhancer).

Check for:
- Bugs, security issues, performance problems
- Whether the code follows project conventions
  (type annotations, single responsibility, SOLID)
- Whether tests are included and meaningful
- Code clarity and maintainability

Score from 1-10. Be concise and actionable.

Diff:
```diff
{diff}
```

Format your review as:

## Quality Score: X/10

### Positive Aspects
- ...

### Issues Found
1. **Severity: high/medium/low** — short title
   - **File**: ...
   - **Issue**: ...
   - **Suggestion**: ...

### Summary
One-line verdict."""

    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
    }).encode()

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return f"Gemini API error: {e.code} {e.reason}\n{e.read().decode()}"

    try:
        return result["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        return f"Unexpected Gemini response:\n{json.dumps(result, indent=2)}"


def post_comment(comment: str) -> None:
    with open(EVENT_PATH) as f:
        event = json.load(f)

    if EVENT_NAME == "pull_request":
        pr_number = event["pull_request"]["number"]
        url = f"{GITHUB_API}/repos/{GITHUB_REPO}/issues/{pr_number}/comments"
    else:
        url = f"{GITHUB_API}/repos/{GITHUB_REPO}/commits/{GITHUB_SHA}/comments"

    data = json.dumps({"body": comment}).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        print(f"Failed to post comment: {e.code} {e.reason}")
        print(e.read().decode())


def main() -> None:
    print("Fetching diff...")
    diff = get_diff()

    if not diff.strip():
        print("No diff found — skipping review.")
        return

    print(f"Diff size: {len(diff)} chars")
    print("Sending to Gemini...")
    review = review_with_gemini(diff)
    print(f"Review ready ({len(review)} chars)")
    print("Posting comment...")
    post_comment(review)
    print("Done — review posted.")


if __name__ == "__main__":
    main()
