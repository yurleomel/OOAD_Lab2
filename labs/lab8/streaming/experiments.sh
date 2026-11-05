#!/usr/bin/env bash
# All four experiments. One replay of the day is read at once by several consumer groups: each group
# has its own place in the log, so they do not disturb each other. That takes about 28 minutes, and
# experiment 3 replays two peak hours afterwards, about 5 minutes more.
set -euo pipefail
cd "$(dirname "$0")"

PY=../.venv/bin/python
DAY=events-2026-10-15.jsonl
OUT=output
IDLE=30 # a consumer ends the stream after this many silent seconds
mkdir -p "$OUT"
rm -f "$OUT"/*.log "$OUT"/*.txt

rpk() { docker compose exec -T redpanda rpk "$@"; }

reset_topic() {
  # A group remembers its place in the log; a fresh run must not inherit that from an earlier one.
  for group in baseline grace-zero restart split failures; do
    rpk group delete "$group" >/dev/null 2>&1 || true
  done
  rpk topic delete payments >/dev/null 2>&1 || true
  rpk topic create payments --partitions 3 --replicas 1 >/dev/null
}

consume() { # log-name, then the consumer's arguments; prints the process id
  local name=$1
  shift
  $PY -u consumer.py --idle-exit "$IDLE" "$@" >"$OUT/$name.log" 2>&1 &
  echo $!
}

note() { echo "$(date +%H:%M:%S) $*"; }

note "the whole day: baseline, grace zero, restart, two in one group"
reset_topic
consume baseline --group baseline >/dev/null
consume exp4-grace-zero --group grace-zero --grace 0 >/dev/null
restart_pid=$(consume exp1-restart-part1 --group restart)
consume exp2-consumer-a --group split >/dev/null

sleep 3
$PY -u producer.py "$DAY" >"$OUT/producer-day.log" 2>&1 &
producer_pid=$!

# Experiment 2: a second consumer joins while the first holds all three partitions.
sleep 30
rpk group describe split >"$OUT/exp2-group-one-consumer.txt"
consume exp2-consumer-b --group split >/dev/null
sleep 30
rpk group describe split >"$OUT/exp2-group-two-consumers.txt"
note "two consumers share the partitions"

# Experiment 1: stop at 5 minutes, start again a minute later.
sleep 240
kill -TERM "$restart_pid"
note "the restart consumer is stopped"
sleep 58
rpk group describe restart >"$OUT/exp1-lag-while-stopped.txt"
consume exp1-restart-part2 --group restart >/dev/null
note "the restart consumer is started again"
sleep 15
rpk group describe restart >"$OUT/exp1-lag-after-restart.txt"

wait "$producer_pid"
note "the day is replayed"
sleep $((IDLE + 10))
rpk topic describe payments --print-partitions >"$OUT/topic-after-day.txt"

note "experiment 3: two peak hours, 30% of the payments made to fail"
reset_topic
consume exp3-failures --group failures >/dev/null
sleep 3
$PY -u producer.py "$DAY" --between 17:00 19:00 --fail-rate 0.3 >"$OUT/producer-failures.log" 2>&1
sleep $((IDLE + 10))

wait
$PY compare.py | tee "$OUT/summary.txt"
note "done"
