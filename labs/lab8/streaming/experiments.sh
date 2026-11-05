#!/usr/bin/env bash
# Experiments 2 and 4 read one replay of the whole day, next to the baseline; each group has its own
# place in the log, so they do not disturb each other (about 28 minutes). Experiments 1 and 3 replay
# two peak hours each (about 4 minutes each). `experiments.sh hours` runs only those two.
set -euo pipefail
cd "$(dirname "$0")"

PY=../.venv/bin/python
DAY=events-2026-10-15.jsonl
OUT=output
IDLE=30 # a consumer ends the stream after this many silent seconds
mkdir -p "$OUT"

rpk() { docker compose exec -T redpanda rpk "$@"; }

reset_topic() {
  # A group remembers its place in the log; a fresh run must not inherit that from an earlier one.
  for group in baseline grace-zero split control restart failures; do
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

if [ "${1:-all}" != hours ]; then
  note "the whole day: baseline, grace zero, two in one group"
  reset_topic
  consume baseline --group baseline >/dev/null
  consume exp4-grace-zero --group grace-zero --grace 0 >/dev/null
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

  wait "$producer_pid"
  note "the day is replayed"
  sleep $((IDLE + 10))
fi

note "experiment 1: stop one consumer for a minute, next to one that keeps running"
reset_topic
consume exp1-control --group control >/dev/null
restart_pid=$(consume exp1-restart-part1 --group restart)
sleep 3
$PY -u producer.py "$DAY" --between 17:00 19:00 >"$OUT/producer-restart.log" 2>&1 &
producer_pid=$!
sleep 90
kill -TERM "$restart_pid"
sleep 58
rpk group describe restart >"$OUT/exp1-lag-while-stopped.txt"
consume exp1-restart-part2 --group restart >/dev/null
sleep 15
rpk group describe restart >"$OUT/exp1-lag-after-restart.txt"
wait "$producer_pid"
sleep $((IDLE + 10))

note "experiment 3: two peak hours, 30% of the payments made to fail"
reset_topic
consume exp3-failures --group failures >/dev/null
sleep 3
$PY -u producer.py "$DAY" --between 17:00 19:00 --fail-rate 0.3 >"$OUT/producer-failures.log" 2>&1
sleep $((IDLE + 10))

wait
$PY compare.py | tee "$OUT/summary.txt"
note "done"
