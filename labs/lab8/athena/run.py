#!/usr/bin/env python3
"""Run SQL files in Athena; save each result as CSV and its cost and time in results/stats.csv.

    python run.py sql/03_turnover.sql
    python run.py sql/03_turnover.sql --set PAYMENTS=lab8.payments_parquet --tag parquet --times 3

${BUCKET} and every --set NAME=VALUE are substituted into the SQL before it is sent.
"""

import argparse
import csv
import statistics
import sys
import time
from pathlib import Path
from string import Template

import boto3

WORKGROUP = "peach-lab8"
RESULTS = Path(__file__).parent / "results"
PRICE_PER_TB = 5.0  # USD, Athena in us-east-1
MIN_BILLED_BYTES = 10 * 1024**2  # every query is billed for at least 10 MB

athena = boto3.client("athena", region_name="us-east-1")
BUCKET = f"peach-lab8-{boto3.client('sts').get_caller_identity()['Account']}"


def run(sql: str) -> tuple[str, dict]:
    """Start one statement, wait for it, return its id and statistics; raise if it failed."""
    query_id = athena.start_query_execution(QueryString=sql, WorkGroup=WORKGROUP)["QueryExecutionId"]
    while True:
        execution = athena.get_query_execution(QueryExecutionId=query_id)["QueryExecution"]
        state = execution["Status"]["State"]
        if state in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            break
        time.sleep(0.5)
    if state != "SUCCEEDED":
        raise RuntimeError(f"{state}: {execution['Status'].get('StateChangeReason')}\n{sql}")
    return query_id, execution["Statistics"]


def fetch(query_id: str) -> list[list[str]]:
    """All rows of a finished query; the first row is the header."""
    rows = []
    for page in athena.get_paginator("get_query_results").paginate(QueryExecutionId=query_id):
        for row in page["ResultSet"]["Rows"]:
            rows.append([cell.get("VarCharValue", "") for cell in row["Data"]])
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--set", action="append", default=[], metavar="NAME=VALUE")
    parser.add_argument("--tag", default="json", help="label for this run in the file names and stats")
    parser.add_argument("--times", type=int, default=1, help="run N times; the median time is reported")
    parser.add_argument("--show", type=int, default=25, help="rows to print")
    args = parser.parse_args()

    values = {"BUCKET": BUCKET, **dict(item.split("=", 1) for item in args.set)}
    RESULTS.mkdir(exist_ok=True)
    stats_path = RESULTS / "stats.csv"
    new_stats = not stats_path.exists()

    with stats_path.open("a", newline="") as stats_file:
        stats = csv.writer(stats_file)
        if new_stats:
            stats.writerow(["query", "tag", "runs", "median_seconds", "bytes_scanned", "billed_usd", "query_id"])

        for path in args.files:
            sql = Template(path.read_text()).substitute(values)
            seconds, scanned, query_id = [], 0, ""
            for _ in range(args.times):
                query_id, s = run(sql)
                seconds.append(s["EngineExecutionTimeInMillis"] / 1000)
                scanned = s.get("DataScannedInBytes", 0)

            rows = fetch(query_id)
            if rows:
                with (RESULTS / f"{path.stem}.{args.tag}.csv").open("w", newline="") as out:
                    csv.writer(out).writerows(rows)

            billed = max(scanned, MIN_BILLED_BYTES) / 1024**4 * PRICE_PER_TB if scanned else 0
            median = statistics.median(seconds)
            stats.writerow([path.stem, args.tag, args.times, median, scanned, f"{billed:.6f}", query_id])
            stats_file.flush()

            print(f"== {path.stem} [{args.tag}] {median:.2f} s, {scanned / 1024**2:.1f} MB, ${billed:.5f}")
            for row in rows[: args.show + 1]:
                print(" | ".join(row))
            if len(rows) > args.show + 1:
                print(f"... {len(rows) - 1} rows in all")
    return 0


if __name__ == "__main__":
    sys.exit(main())
