#!/usr/bin/env python3
"""Minimal Linear label add/remove. Called from linear-status-sync workflow."""
import argparse
import os
import sys

import httpx

ENDPOINT = "https://api.linear.app/graphql"


def gql(client, query, variables=None):
    r = client.post("", json={"query": query, "variables": variables or {}})
    r.raise_for_status()
    body = r.json()
    if "errors" in body:
        raise RuntimeError(f"Linear: {body['errors']}")
    return body["data"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--issue", required=True)
    p.add_argument("--label", required=True)
    p.add_argument("--action", required=True, choices=["add", "remove"])
    args = p.parse_args()

    key = os.environ["LINEAR_API_KEY"]
    with httpx.Client(
        base_url=ENDPOINT,
        headers={"Authorization": key, "Content-Type": "application/json"},
        timeout=30,
    ) as c:
        d = gql(
            c,
            "query Q($id: String!) { issue(id: $id) { id labels { nodes { id name } } } }",
            {"id": args.issue},
        )
        issue = d["issue"]
        if not issue:
            print(f"Issue {args.issue} not found")
            return 0
        existing = {lbl["name"]: lbl["id"] for lbl in issue["labels"]["nodes"]}

        d = gql(c, "query { issueLabels { nodes { id name } } }")
        label_id = next(
            (lbl["id"] for lbl in d["issueLabels"]["nodes"] if lbl["name"] == args.label),
            None,
        )
        if not label_id:
            print(f"Label '{args.label}' not found in workspace")
            return 0

        if args.action == "add":
            if args.label in existing:
                print(f"Label '{args.label}' already on {args.issue}, skip")
                return 0
            new_ids = list(existing.values()) + [label_id]
        else:
            if args.label not in existing:
                print(f"Label '{args.label}' not on {args.issue}, skip")
                return 0
            new_ids = [v for k, v in existing.items() if k != args.label]

        gql(
            c,
            "mutation U($id: String!, $ids: [String!]!) { issueUpdate(id: $id, input: {labelIds: $ids}) { success } }",
            {"id": issue["id"], "ids": new_ids},
        )
        print(f"Label '{args.label}' {args.action}ed on {args.issue}")


if __name__ == "__main__":
    sys.exit(main() or 0)
