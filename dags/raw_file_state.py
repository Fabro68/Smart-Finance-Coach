from pathlib import Path
import hashlib
import json


RAW_DIR = Path("/opt/project/data/raw")
STATE_FILE = Path("/opt/airflow/logs/raw_file_state.json")

EXPECTED_FILES = [
    "users.csv",
    "aug_personal_transactions_with_UserId.csv",
    "Loan_default.csv",
    "MEXCPALTT01IXNBM.csv",
    "IRSTCI01MXM156N.csv",
    "DEXMXUS.csv",
]


def calculate_md5(file_path: Path) -> str:
    md5 = hashlib.md5()

    with file_path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            md5.update(chunk)

    return md5.hexdigest()


def get_current_state() -> dict:
    state = {}

    for file_name in EXPECTED_FILES:
        file_path = RAW_DIR / file_name

        if not file_path.exists():
            state[file_name] = {
                "exists": False,
                "size": None,
                "md5": None,
            }
            continue

        state[file_name] = {
            "exists": True,
            "size": file_path.stat().st_size,
            "md5": calculate_md5(file_path),
        }

    return state


def load_previous_state() -> dict:
    if not STATE_FILE.exists():
        return {}

    with STATE_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    with STATE_FILE.open("w", encoding="utf-8") as file:
        json.dump(state, file, indent=2)


def detect_changes() -> list[str]:
    current_state = get_current_state()
    previous_state = load_previous_state()

    changed_files = []

    for file_name, current_info in current_state.items():
        previous_info = previous_state.get(file_name)

        if previous_info != current_info:
            changed_files.append(file_name)

    return changed_files