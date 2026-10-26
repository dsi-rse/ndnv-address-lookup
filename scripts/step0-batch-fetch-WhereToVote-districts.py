#!/usr/bin/env python3

import argparse
from concurrent.futures import FIRST_COMPLETED, Future, wait
import csv
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd


PARQUET_PATH = Path("public/911-addresses.parquet")
FETCH_SCRIPT = Path("scripts/step0-fetch-WhereToVote-districts.py")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--parquet",
        type=Path,
        default=PARQUET_PATH,
        help="Path to the input parquet file",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Optional random seed for reproducible row order",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Optional number of shuffled rows to process",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="Number of concurrent subprocesses to run",
    )
    parser.add_argument(
        "--previous",
        type=Path,
        help="CSV from a previous run; rows whose original index already appears are skipped",
    )
    return parser.parse_args()


def stringify_result(process: subprocess.CompletedProcess[str]) -> str:
    if process.returncode == 0:
        stdout = process.stdout.strip()
        if not stdout:
            return ""
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            return stdout
        return json.dumps(parsed, separators=(",", ":"), sort_keys=True)

    stderr = process.stderr.strip()
    stdout = process.stdout.strip()
    if stderr and stdout:
        return f"{stderr}\n{stdout}"
    if stderr:
        return stderr
    return stdout


def load_previous_indices(path: Path) -> set[int]:
    completed: set[int] = set()
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if "index" not in (reader.fieldnames or []):
            raise ValueError(f"{path} does not contain an 'index' column")
        for row in reader:
            value = (row.get("index") or "").strip()
            if not value:
                continue
            try:
                completed.add(int(value))
            except ValueError:
                continue
    return completed


def run_lookup(
    python_executable: str,
    fetch_script: Path,
    row_index: object,
    num: object,
    zip_code: object,
    street: object,
) -> list[object]:
    command = [
        python_executable,
        str(fetch_script),
        "--house-number",
        str(num),
        "--zip-code",
        str(zip_code),
        "--street",
        str(street),
    ]
    process = subprocess.run(
        command,
        capture_output=True,
        text=True,
        cwd=fetch_script.parent.parent,
    )
    return [row_index, num, zip_code, street, stringify_result(process)]


def main() -> int:
    args = parse_args()
    if args.parallel < 1:
        raise ValueError("--parallel must be >= 1")

    dataframe = pd.read_parquet(args.parquet)
    shuffled = dataframe.reset_index().sample(frac=1, random_state=args.seed)
    if args.limit is not None:
        shuffled = shuffled.head(args.limit)

    previous_indices: set[int] = set()
    if args.previous is not None:
        previous_indices = load_previous_indices(args.previous)
        if previous_indices:
            shuffled = shuffled[~shuffled["index"].isin(previous_indices)]

    writer = csv.writer(sys.stdout)
    writer.writerow(["index", "num", "zip", "street", "result"])
    sys.stdout.flush()

    fetch_script = FETCH_SCRIPT.resolve()
    python_executable = sys.executable
    pending_rows = list(shuffled.itertuples(index=False))
    in_flight: dict[Future[list[object]], None] = {}

    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=args.parallel) as executor:
        def submit_next(row: object) -> Future[list[object]]:
            return executor.submit(
                run_lookup,
                python_executable,
                fetch_script,
                row.index,
                row.num,
                row.zip,
                row.street,
            )

        row_iter = iter(pending_rows)

        for _ in range(min(args.parallel, len(pending_rows))):
            try:
                in_flight[submit_next(next(row_iter))] = None
            except StopIteration:
                break

        while in_flight:
            done, _ = wait(in_flight.keys(), return_when=FIRST_COMPLETED)
            for future in done:
                del in_flight[future]
                writer.writerow(future.result())
                sys.stdout.flush()
                try:
                    in_flight[submit_next(next(row_iter))] = None
                except StopIteration:
                    pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
