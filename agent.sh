#!/usr/bin/env bash
set -euo pipefail

case "${1:-}" in
  run)
    python3 app/run_agent_loop.py
    ;;
  approve)
    python3 app/approve.py
    ;;
  reject)
    python3 app/reject.py
    ;;
  diff)
    python3 app/git_diff.py
    ;;
  test)
    python3 app/run_tests.py
    ;;
  *)
    echo "Usage:"
    echo "  ./agent.sh run"
    echo "  ./agent.sh diff"
    echo "  ./agent.sh test"
    echo "  ./agent.sh approve"
    echo "  ./agent.sh reject"
    exit 1
    ;;
esac
