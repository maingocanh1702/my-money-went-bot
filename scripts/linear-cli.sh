#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# Linear CLI — Manage Linear issues from your IDE terminal
#
# Usage: ./scripts/linear-cli.sh <command> [options]
#
# Requires: LINEAR_API_KEY in .env (or exported)
#           jq (brew install jq)
#           curl
#
# Setup:
#   1. Go to https://linear.app/settings/api → Create personal API key
#   2. Add LINEAR_API_KEY=lin_api_xxxxx to .env
#   3. Run: ./scripts/linear-cli.sh init  (fetches team/project IDs)
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LINEAR_API="https://api.linear.app/graphql"
CACHE_FILE="$PROJECT_ROOT/.linear-cache.json"

# ── Load env ────────────────────────────────────────────────────────
load_env() {
  if [[ -f "$PROJECT_ROOT/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    . "$PROJECT_ROOT/.env"
    set +a
  fi
  if [[ -z "${LINEAR_API_KEY:-}" ]]; then
    echo "❌ LINEAR_API_KEY not set. Add to .env or export it."
    echo "   Get your key: https://linear.app/settings/api"
    exit 1
  fi
}

# ── GraphQL helper ──────────────────────────────────────────────────
gql() {
  local query="$1"
  local variables="${2:-{}}"
  local response
  response=$(curl -s -X POST "$LINEAR_API" \
    -H "Authorization: $LINEAR_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"query\": $(echo "$query" | jq -Rs .), \"variables\": $variables}")

  # Check for errors
  if echo "$response" | jq -e '.errors' > /dev/null 2>&1; then
    echo "❌ Linear API error:" >&2
    echo "$response" | jq '.errors[0].message' >&2
    return 1
  fi
  echo "$response"
}

# ── Cache helpers ───────────────────────────────────────────────────
cache_get() {
  local key="$1"
  if [[ -f "$CACHE_FILE" ]]; then
    jq -r ".$key // empty" "$CACHE_FILE" 2>/dev/null
  fi
}

cache_set() {
  local key="$1" value="$2"
  if [[ ! -f "$CACHE_FILE" ]]; then
    echo "{}" > "$CACHE_FILE"
  fi
  local tmp
  tmp=$(jq ".$key = \"$value\"" "$CACHE_FILE")
  echo "$tmp" > "$CACHE_FILE"
}

# ── INIT: Fetch team & project IDs ─────────────────────────────────
cmd_init() {
  echo "🔄 Fetching Linear workspace info..."
  local result
  result=$(gql '{
    teams { nodes { id name key } }
    projects { nodes { id name state } }
  }')

  echo ""
  echo "📋 Teams:"
  echo "$result" | jq -r '.data.teams.nodes[] | "  \(.key) — \(.name) (id: \(.id))"'

  local team_id
  team_id=$(echo "$result" | jq -r '.data.teams.nodes[0].id')
  local team_key
  team_key=$(echo "$result" | jq -r '.data.teams.nodes[0].key')
  cache_set "teamId" "$team_id"
  cache_set "teamKey" "$team_key"

  echo ""
  echo "📁 Projects:"
  echo "$result" | jq -r '.data.projects.nodes[] | "  \(.name) — state: \(.state) (id: \(.id))"'

  echo ""
  echo "✅ Cached team: $team_key ($team_id)"
  echo "   Cache file: $CACHE_FILE"
  echo ""
  echo "Add $CACHE_FILE to .gitignore (contains workspace IDs)."
}

# ── CREATE: Create a new issue ──────────────────────────────────────
cmd_create() {
  local title="" project="" priority="" assignee="" label="" parent="" description=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --title|-t)    title="$2"; shift 2 ;;
      --project|-p)  project="$2"; shift 2 ;;
      --priority)    priority="$2"; shift 2 ;;
      --assign|-a)   assignee="$2"; shift 2 ;;
      --label|-l)    label="$2"; shift 2 ;;
      --parent)      parent="$2"; shift 2 ;;
      --desc|-d)     description="$2"; shift 2 ;;
      *)
        if [[ -z "$title" ]]; then
          title="$1"; shift
        else
          echo "Unknown option: $1"; exit 1
        fi
        ;;
    esac
  done

  if [[ -z "$title" ]]; then
    echo "Usage: linear-cli.sh create \"Title\" [--project P2] [--priority high] [--assign email] [--label feature] [--parent MMW-123] [--desc \"description\"]"
    exit 1
  fi

  local team_id
  team_id=$(cache_get "teamId")
  if [[ -z "$team_id" ]]; then
    echo "❌ Run 'linear-cli.sh init' first."
    exit 1
  fi

  # Build input object
  local input="\"teamId\": \"$team_id\", \"title\": $(echo "$title" | jq -Rs .)"

  # Priority mapping: urgent=1, high=2, medium=3, low=4, none=0
  if [[ -n "$priority" ]]; then
    case "${priority,,}" in
      urgent|u|1) input="$input, \"priority\": 1" ;;
      high|h|2)   input="$input, \"priority\": 2" ;;
      medium|m|3) input="$input, \"priority\": 3" ;;
      low|l|4)    input="$input, \"priority\": 4" ;;
      none|0)     input="$input, \"priority\": 0" ;;
    esac
  fi

  # Description
  if [[ -n "$description" ]]; then
    input="$input, \"description\": $(echo "$description" | jq -Rs .)"
  fi

  # Project — search by name prefix
  if [[ -n "$project" ]]; then
    local proj_result
    proj_result=$(gql "{ projects(filter: { name: { startsWith: \"$project\" } }) { nodes { id name } } }")
    local proj_id
    proj_id=$(echo "$proj_result" | jq -r '.data.projects.nodes[0].id // empty')
    if [[ -n "$proj_id" ]]; then
      input="$input, \"projectId\": \"$proj_id\""
    else
      echo "⚠️  Project '$project' not found, creating without project."
    fi
  fi

  # Assignee — search by display name or email
  if [[ -n "$assignee" ]]; then
    local user_result
    user_result=$(gql "{ users { nodes { id name email } } }")
    local user_id
    user_id=$(echo "$user_result" | jq -r ".data.users.nodes[] | select(.name == \"$assignee\" or .email == \"$assignee\") | .id" | head -1)
    if [[ -n "$user_id" ]]; then
      input="$input, \"assigneeId\": \"$user_id\""
    else
      echo "⚠️  User '$assignee' not found, creating unassigned."
    fi
  fi

  # Parent issue — resolve MMW-123 to ID
  if [[ -n "$parent" ]]; then
    local parent_num="${parent#MMW-}"  # strip prefix if present
    local team_key
    team_key=$(cache_get "teamKey")
    local parent_result
    parent_result=$(gql "{ issueSearch(query: \"$team_key-$parent_num\") { nodes { id identifier } } }")
    local parent_id
    parent_id=$(echo "$parent_result" | jq -r '.data.issueSearch.nodes[0].id // empty')
    if [[ -n "$parent_id" ]]; then
      input="$input, \"parentId\": \"$parent_id\""
    else
      echo "⚠️  Parent '$parent' not found, creating without parent."
    fi
  fi

  # Create issue
  local create_result
  create_result=$(gql "mutation { issueCreate(input: { $input }) { success issue { id identifier title url priority state { name } } } }")

  local identifier url issue_title
  identifier=$(echo "$create_result" | jq -r '.data.issueCreate.issue.identifier')
  url=$(echo "$create_result" | jq -r '.data.issueCreate.issue.url')
  issue_title=$(echo "$create_result" | jq -r '.data.issueCreate.issue.title')
  local state_name
  state_name=$(echo "$create_result" | jq -r '.data.issueCreate.issue.state.name')

  echo "✅ Created $identifier: $issue_title"
  echo "   Status: $state_name"
  [[ -n "$project" ]] && echo "   Project: $project"
  echo "   🔗 $url"

  # Add label if specified
  if [[ -n "$label" ]]; then
    local label_result
    label_result=$(gql "{ issueLabels(filter: { name: { eq: \"$label\" } }) { nodes { id name } } }")
    local label_id
    label_id=$(echo "$label_result" | jq -r '.data.issueLabels.nodes[0].id // empty')
    if [[ -n "$label_id" ]]; then
      local issue_id
      issue_id=$(echo "$create_result" | jq -r '.data.issueCreate.issue.id')
      gql "mutation { issueUpdate(id: \"$issue_id\", input: { labelIds: [\"$label_id\"] }) { success } }" > /dev/null
      echo "   Label: $label"
    fi
  fi
}

# ── LIST: List issues ───────────────────────────────────────────────
cmd_list() {
  local filter="all" project="" limit=20

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --status|-s)   filter="$2"; shift 2 ;;
      --project|-p)  project="$2"; shift 2 ;;
      --limit|-n)    limit="$2"; shift 2 ;;
      blocked)       filter="blocked"; shift ;;
      active)        filter="active"; shift ;;
      backlog)       filter="backlog"; shift ;;
      done)          filter="done"; shift ;;
      mine)          filter="mine"; shift ;;
      *)             shift ;;
    esac
  done

  local query_filter=""
  case "$filter" in
    active)   query_filter='filter: { state: { type: { in: ["started", "unstarted"] } } }' ;;
    backlog)  query_filter='filter: { state: { type: { eq: "backlog" } } }' ;;
    done)     query_filter='filter: { state: { type: { eq: "completed" } } }' ;;
    blocked)  query_filter='filter: { labels: { name: { eq: "blocked" } } }' ;;
    mine)     query_filter='filter: { assignee: { isMe: { eq: true } }, state: { type: { nin: ["completed", "canceled"] } } }' ;;
    all)      query_filter="" ;;
  esac

  local team_id
  team_id=$(cache_get "teamId")

  local result
  result=$(gql "{
    team(id: \"$team_id\") {
      issues($query_filter, first: $limit, orderBy: updatedAt) {
        nodes {
          identifier
          title
          priority
          state { name type }
          assignee { name }
          project { name }
          labels { nodes { name } }
        }
      }
    }
  }")

  # Priority icons
  local pri_icons=("—" "🔴" "🟠" "🟡" "🔵")

  echo ""
  echo "📋 Issues ($filter) — showing up to $limit:"
  echo "─────────────────────────────────────────────────────────────"

  echo "$result" | jq -r '.data.team.issues.nodes[] |
    "\(.identifier)\t\(.priority)\t\(.state.name)\t\(.assignee.name // "—")\t\(.project.name // "—")\t\(.title)"' |
  while IFS=$'\t' read -r id pri status assignee proj title; do
    local icon="${pri_icons[$pri]:-—}"
    printf "  %-10s %s %-14s %-12s %-16s %s\n" "$id" "$icon" "$status" "$assignee" "$proj" "$title"
  done

  echo ""
}

# ── VIEW: View issue details ────────────────────────────────────────
cmd_view() {
  local issue_id="${1:-}"
  if [[ -z "$issue_id" ]]; then
    echo "Usage: linear-cli.sh view MMW-123"
    exit 1
  fi

  local team_key
  team_key=$(cache_get "teamKey")
  # Handle both "MMW-123" and "123" formats
  local search_id="$issue_id"
  if [[ ! "$issue_id" =~ ^[A-Z]+-[0-9]+$ ]]; then
    search_id="${team_key}-${issue_id}"
  fi

  local result
  result=$(gql "{
    issueSearch(query: \"$search_id\", first: 1) {
      nodes {
        identifier title description priority
        state { name }
        assignee { name email }
        project { name }
        labels { nodes { name } }
        children { nodes { identifier title state { name } } }
        attachments { nodes { title url } }
        url
        createdAt updatedAt
      }
    }
  }")

  local node
  node=$(echo "$result" | jq '.data.issueSearch.nodes[0]')

  if [[ "$node" == "null" ]]; then
    echo "❌ Issue $issue_id not found."
    exit 1
  fi

  echo ""
  echo "$(echo "$node" | jq -r '.identifier'): $(echo "$node" | jq -r '.title')"
  echo "─────────────────────────────────────────────────────────────"
  echo "  Status:    $(echo "$node" | jq -r '.state.name')"
  echo "  Priority:  $(echo "$node" | jq -r '.priority')"
  echo "  Assignee:  $(echo "$node" | jq -r '.assignee.name // "Unassigned"')"
  echo "  Project:   $(echo "$node" | jq -r '.project.name // "None"')"
  echo "  Labels:    $(echo "$node" | jq -r '[.labels.nodes[].name] | join(", ") // "—"')"
  echo "  Created:   $(echo "$node" | jq -r '.createdAt[:10]')"
  echo "  Updated:   $(echo "$node" | jq -r '.updatedAt[:10]')"
  echo "  🔗 $(echo "$node" | jq -r '.url')"

  # Sub-issues
  local children_count
  children_count=$(echo "$node" | jq '.children.nodes | length')
  if [[ "$children_count" -gt 0 ]]; then
    echo ""
    echo "  Sub-issues ($children_count):"
    echo "$node" | jq -r '.children.nodes[] | "    [\(.state.name)] \(.identifier): \(.title)"'
  fi

  # Description
  local desc
  desc=$(echo "$node" | jq -r '.description // empty')
  if [[ -n "$desc" ]]; then
    echo ""
    echo "  Description:"
    echo "$desc" | sed 's/^/    /'
  fi
  echo ""
}

# ── ASSIGN: Assign issue to user ────────────────────────────────────
cmd_assign() {
  local issue_id="${1:-}" user_name="${2:-}"
  if [[ -z "$issue_id" || -z "$user_name" ]]; then
    echo "Usage: linear-cli.sh assign MMW-123 \"Dev Name\""
    exit 1
  fi

  # Resolve issue
  local team_key
  team_key=$(cache_get "teamKey")
  local search_id="$issue_id"
  [[ ! "$issue_id" =~ ^[A-Z]+-[0-9]+$ ]] && search_id="${team_key}-${issue_id}"

  local issue_result
  issue_result=$(gql "{ issueSearch(query: \"$search_id\", first: 1) { nodes { id identifier } } }")
  local real_id
  real_id=$(echo "$issue_result" | jq -r '.data.issueSearch.nodes[0].id // empty')
  if [[ -z "$real_id" ]]; then
    echo "❌ Issue $issue_id not found."
    exit 1
  fi

  # Resolve user
  local user_result
  user_result=$(gql "{ users { nodes { id name email } } }")
  local user_id
  user_id=$(echo "$user_result" | jq -r ".data.users.nodes[] | select(.name == \"$user_name\" or .email == \"$user_name\") | .id" | head -1)
  if [[ -z "$user_id" ]]; then
    echo "❌ User '$user_name' not found. Available:"
    echo "$user_result" | jq -r '.data.users.nodes[] | "  \(.name) (\(.email))"'
    exit 1
  fi

  gql "mutation { issueUpdate(id: \"$real_id\", input: { assigneeId: \"$user_id\" }) { success issue { identifier assignee { name } } } }" |
    jq -r '"✅ \(.data.issueUpdate.issue.identifier) assigned to \(.data.issueUpdate.issue.assignee.name)"'
}

# ── STATUS: Update issue status ─────────────────────────────────────
cmd_status() {
  local issue_id="${1:-}" new_status="${2:-}"
  if [[ -z "$issue_id" || -z "$new_status" ]]; then
    echo "Usage: linear-cli.sh status MMW-123 \"In Progress\""
    echo "  Statuses: Triage, Backlog, Todo, \"In Progress\", \"In Review\", Done, Canceled"
    exit 1
  fi

  local team_id
  team_id=$(cache_get "teamId")

  # Resolve issue
  local team_key
  team_key=$(cache_get "teamKey")
  local search_id="$issue_id"
  [[ ! "$issue_id" =~ ^[A-Z]+-[0-9]+$ ]] && search_id="${team_key}-${issue_id}"

  local issue_result
  issue_result=$(gql "{ issueSearch(query: \"$search_id\", first: 1) { nodes { id identifier } } }")
  local real_id
  real_id=$(echo "$issue_result" | jq -r '.data.issueSearch.nodes[0].id // empty')
  if [[ -z "$real_id" ]]; then
    echo "❌ Issue $issue_id not found."
    exit 1
  fi

  # Resolve workflow state
  local states_result
  states_result=$(gql "{ workflowStates(filter: { team: { id: { eq: \"$team_id\" } } }) { nodes { id name } } }")
  local state_id
  state_id=$(echo "$states_result" | jq -r ".data.workflowStates.nodes[] | select(.name == \"$new_status\") | .id" | head -1)
  if [[ -z "$state_id" ]]; then
    echo "❌ Status '$new_status' not found. Available:"
    echo "$states_result" | jq -r '.data.workflowStates.nodes[] | "  \(.name)"'
    exit 1
  fi

  gql "mutation { issueUpdate(id: \"$real_id\", input: { stateId: \"$state_id\" }) { success issue { identifier state { name } } } }" |
    jq -r '"✅ \(.data.issueUpdate.issue.identifier) → \(.data.issueUpdate.issue.state.name)"'
}

# ── SEARCH: Search issues ──────────────────────────────────────────
cmd_search() {
  local query="${*:-}"
  if [[ -z "$query" ]]; then
    echo "Usage: linear-cli.sh search \"parser bug\""
    exit 1
  fi

  local result
  result=$(gql "{
    issueSearch(query: $(echo "$query" | jq -Rs .), first: 10) {
      nodes {
        identifier title
        state { name }
        assignee { name }
        project { name }
        url
      }
    }
  }")

  echo ""
  echo "🔍 Search: \"$query\""
  echo "─────────────────────────────────────────────────────────────"
  echo "$result" | jq -r '.data.issueSearch.nodes[] |
    "  \(.identifier)  [\(.state.name)]  \(.title)\n    → \(.assignee.name // "Unassigned") | \(.project.name // "No project")\n    🔗 \(.url)\n"'
}

# ── PROGRESS: Show project progress ────────────────────────────────
cmd_progress() {
  local result
  result=$(gql '{
    projects(filter: { state: { nin: ["canceled"] } }, orderBy: updatedAt) {
      nodes {
        name state progress
        issues { nodes { id } }
        completedIssues: issues(filter: { state: { type: { eq: "completed" } } }) { nodes { id } }
      }
    }
  }')

  echo ""
  echo "📊 Project Progress"
  echo "─────────────────────────────────────────────────────────────"

  echo "$result" | jq -r '.data.projects.nodes[] |
    {
      name: .name,
      state: .state,
      pct: ((.progress // 0) * 100 | floor),
      total: (.issues.nodes | length),
      done: (.completedIssues.nodes | length)
    } |
    "\(.name)\n  \(.state) — \(.done)/\(.total) issues — \(.pct)%\n"'
}

# ── HELP ────────────────────────────────────────────────────────────
cmd_help() {
  cat <<'EOF'
Linear CLI — Manage Linear issues from your IDE

SETUP:
  linear-cli.sh init                          Fetch & cache workspace info

CREATE:
  linear-cli.sh create "Fix parser bug"       Create issue (minimal)
  linear-cli.sh create "Title" \
    --project P2 \                            Assign to project (prefix match)
    --priority high \                         urgent|high|medium|low
    --assign "Dev Name" \                     By name or email
    --label feature \                         Add label
    --parent MMW-123 \                        Create as sub-issue
    --desc "Details here"                     Description

LIST:
  linear-cli.sh list                          All active issues
  linear-cli.sh list active                   In Progress + Todo
  linear-cli.sh list backlog                  Backlog only
  linear-cli.sh list blocked                  Blocked issues
  linear-cli.sh list done                     Completed
  linear-cli.sh list mine                     My assigned issues
  linear-cli.sh list --project P2             Filter by project
  linear-cli.sh list --limit 50              Show more

VIEW:
  linear-cli.sh view MMW-123                  Full issue details + sub-issues

ASSIGN:
  linear-cli.sh assign MMW-123 "Dev Name"     Assign by name or email

STATUS:
  linear-cli.sh status MMW-123 "In Progress"  Update status
  linear-cli.sh status MMW-123 Done           Quick done

SEARCH:
  linear-cli.sh search "parser bug"           Full-text search

PROGRESS:
  linear-cli.sh progress                      All projects progress %

EOF
}

# ── Main dispatch ───────────────────────────────────────────────────
main() {
  load_env

  local cmd="${1:-help}"
  shift || true

  case "$cmd" in
    init)     cmd_init "$@" ;;
    create|c) cmd_create "$@" ;;
    list|ls)  cmd_list "$@" ;;
    view|v)   cmd_view "$@" ;;
    assign|a) cmd_assign "$@" ;;
    status|s) cmd_status "$@" ;;
    search)   cmd_search "$@" ;;
    progress) cmd_progress "$@" ;;
    help|-h|--help) cmd_help ;;
    *)
      echo "Unknown command: $cmd"
      cmd_help
      exit 1
      ;;
  esac
}

main "$@"
