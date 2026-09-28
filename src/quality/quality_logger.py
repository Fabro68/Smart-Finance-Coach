from datetime import datetime, timezone
import json
import os
import uuid


QUALITY_LOG_PATH = "/opt/project/data/quality/quality_results.jsonl"


def create_quality_run_id():
    """Genera un identificador unico para cada ejecucion de calidad."""
    return str(uuid.uuid4())


def write_quality_result(
    quality_run_id,
    dataset,
    check_name,
    status,
    observed_value=None,
    expected_value=None,
    message=None,
):
    """
    Guarda el resultado de una regla de calidad en formato JSON Lines.
    """

    quality_record = {
        "quality_run_id": quality_run_id,
        "dataset": dataset,
        "check_name": check_name,
        "status": status,
        "observed_value": observed_value,
        "expected_value": expected_value,
        "message": message,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }

    os.makedirs(
        os.path.dirname(QUALITY_LOG_PATH),
        exist_ok=True,
    )

    with open(
        QUALITY_LOG_PATH,
        "a",
        encoding="utf-8",
    ) as quality_file:
        quality_file.write(
            json.dumps(
                quality_record,
                ensure_ascii=False,
            )
            + "\n"
        )