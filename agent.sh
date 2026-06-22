#!/usr/bin/env bash
set -euo pipefail

case "${1:-}" in
  run)
    PYTHONPATH=app python3 app/commands/run.py
    ;;
  once)
    PYTHONPATH=app python3 app/run_agent_once.py
    ;;
  approve)
    PYTHONPATH=app python3 app/commands/approve.py
    ;;
  reject)
    PYTHONPATH=app python3 app/commands/reject.py
    ;;
  diff)
    PYTHONPATH=app python3 app/commands/status.py diff
    ;;
  test)
    PYTHONPATH=app python3 app/adapters/docker.py
    ;;
  *)
    echo "Usage:"
    echo "  ./agent.sh run"
    echo "  ./agent.sh once"
    echo "  ./agent.sh diff"
    echo "  ./agent.sh test"
    echo "  ./agent.sh approve"
    echo "  ./agent.sh reject"
    exit 1
    ;;
esac
