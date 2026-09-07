from pathlib import Path

from evals.generator import write_cases

if __name__ == "__main__":
    count = write_cases(Path("evals/cases.jsonl"))
    print(f"Generated {count} synthetic evaluation cases.")
