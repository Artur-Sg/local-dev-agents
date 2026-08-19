#!/usr/bin/env bash
set -euo pipefail

case "${1:-}" in
  run)
    PYTHONPATH=app python3 app/commands/run.py
    ;;
  auto)
    PYTHONPATH=app python3 app/commands/auto.py
    ;;
  kickoff)
    PYTHONPATH=app python3 app/commands/kickoff.py
    ;;
  once)
    PYTHONPATH=app python3 app/commands/once.py
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
  backlog)
    PYTHONPATH=app python3 app/commands/status.py backlog
    ;;
  recover)
    PYTHONPATH=app python3 app/commands/status.py recover
    ;;
  status)
    PYTHONPATH=app python3 app/commands/status.py run latest
    ;;
  run-status)
    PYTHONPATH=app python3 app/commands/status.py run "${2:-latest}"
    ;;
  test)
    PYTHONPATH=app python3 app/commands/test.py
    ;;
  *)
    echo "Usage:"
    echo "  ./agent.sh run"
    echo "  ./agent.sh auto"
    echo "  ./agent.sh kickoff"
    echo "  ./agent.sh once"
    echo "  ./agent.sh diff"
    echo "  ./agent.sh backlog"
    echo "  ./agent.sh recover"
    echo "  ./agent.sh status"
    echo "  ./agent.sh run-status [run_id|latest]"
    echo "  ./agent.sh test"
    echo "  ./agent.sh approve"
    echo "  ./agent.sh reject"
    exit 1
    ;;
esac
