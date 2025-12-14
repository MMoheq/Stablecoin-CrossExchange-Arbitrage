# ===================================================================
# run_h1_unit_tests.py — Runs pytest for h1_vol tests
# and saves output into results/unit_tests_h1.txt
# ===================================================================

import subprocess
import sys
from pathlib import Path


def main():
    # Project root is the folder that CONTAINS "experiments" and "scripts"
    project_root = Path(__file__).resolve().parent.parent

    # Ensure results/ exists
    results_dir = project_root / "results"
    results_dir.mkdir(exist_ok=True)

    output_file = results_dir / "unit_tests_h1.txt"

    # Command to run tests: use current Python interpreter
    # so we don't depend on "pytest" being on PATH.
    cmd = [
        sys.executable,          # e.g. C:\Users\...\python.exe
        "-m",
        "pytest",
        "scripts/test_h1_vol.py",
        "-q",
    ]

    print("Running pytest for h1_vol...")

    # Run pytest from the project root
    process = subprocess.Popen(
        cmd,
        cwd=project_root,              # <<< important
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    full_output, _ = process.communicate()

    # Write pytest output to file
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(full_output)

    print(f"Done! Exit code {process.returncode}. Output saved to: {output_file}")


if __name__ == "__main__":
    main()
