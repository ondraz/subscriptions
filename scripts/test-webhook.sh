#!/usr/bin/env bash
set -euo pipefail

URL="${WEBHOOK_URL:-https://hermes.tail24ec7.ts.net/webhooks/github-pr-review}"
SECRET="${GITHUB_WEBHOOK_SECRET:?set GITHUB_WEBHOOK_SECRET first}"
DELIVERY="$(uuidgen)"

PAYLOAD=$(cat <<'JSON'
{
  "action": "opened",
  "number": 8,
  "pull_request": {
    "id": 2000000008,
    "node_id": "PR_kwDOTEST8",
    "number": 8,
    "state": "open",
    "locked": false,
    "title": "Test PR for webhook",
    "body": "Simulated PR for local webhook testing.",
    "html_url": "https://github.com/ondraz/tidemill/pull/8",
    "url": "https://api.github.com/repos/ondraz/tidemill/pulls/8",
    "diff_url": "https://github.com/ondraz/tidemill/pull/8.diff",
    "patch_url": "https://github.com/ondraz/tidemill/pull/8.patch",
    "issue_url": "https://api.github.com/repos/ondraz/tidemill/issues/8",
    "created_at": "2026-05-09T10:00:00Z",
    "updated_at": "2026-05-09T10:00:00Z",
    "closed_at": null,
    "merged_at": null,
    "merge_commit_sha": null,
    "draft": false,
    "merged": false,
    "mergeable": null,
    "mergeable_state": "unknown",
    "user": {
      "login": "ondraz",
      "id": 12345,
      "node_id": "U_kgDOTEST",
      "type": "User",
      "site_admin": false,
      "html_url": "https://github.com/ondraz"
    },
    "head": {
      "label": "ondraz:feature/test-webhook",
      "ref": "feature/test-webhook",
      "sha": "deadbeefcafebabe1234567890abcdef12345678",
      "repo": { "id": 999, "name": "tidemill", "full_name": "ondraz/tidemill" }
    },
    "base": {
      "label": "ondraz:main",
      "ref": "main",
      "sha": "1111111111111111111111111111111111111111",
      "repo": { "id": 999, "name": "tidemill", "full_name": "ondraz/tidemill" }
    },
    "assignees": [],
    "requested_reviewers": [],
    "labels": [],
    "additions": 42,
    "deletions": 7,
    "changed_files": 3,
    "commits": 1
  },
  "repository": {
    "id": 999,
    "node_id": "R_kgDOTEST",
    "name": "tidemill",
    "full_name": "ondraz/tidemill",
    "private": false,
    "html_url": "https://github.com/ondraz/tidemill",
    "default_branch": "main",
    "owner": {
      "login": "ondraz",
      "id": 12345,
      "type": "User",
      "html_url": "https://github.com/ondraz"
    }
  },
  "sender": {
    "login": "test-reviewer",
    "id": 99999,
    "type": "User",
    "html_url": "https://github.com/test-reviewer"
  }
}
JSON
)

SIG="sha256=$(printf '%s' "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" -hex | awk '{print $2}')"

curl -i -X POST "$URL" \
  -H "Content-Type: application/json" \
  -H "User-Agent: GitHub-Hookshot/test" \
  -H "X-GitHub-Event: pull_request" \
  -H "X-GitHub-Delivery: $DELIVERY" \
  -H "X-GitHub-Hook-ID: 1234567" \
  -H "X-GitHub-Hook-Installation-Target-Type: repository" \
  -H "X-GitHub-Hook-Installation-Target-ID: 999" \
  -H "X-Hub-Signature-256: $SIG" \
  --data "$PAYLOAD"
