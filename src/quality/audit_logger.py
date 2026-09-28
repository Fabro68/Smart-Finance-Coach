from datetime import datetime, timezone
import json
import os
import uuid


AUDIT_LOG_PATH = "/opt/project/data/audit/pipeline_audit.jsonl"

def create_run_id():
    """Genera un identificador unico para cada ejecucion."""
    return str(uuid.uuid4())


def write_audit_log(
    pipeline_run_id,
    process_name,
    layer,
    dataset,
    status,
    start_time,
    end_time,
    records_read=None,
    records_written=None,
    message=None,
):
    """
    Registra una ejecucion del pipeline en formato JSON Lines.
    """

    audit_record = {
        "pipeline_run_id": pipeline_run_id,
        "process_name": process_name,
        "layer": layer,
        "dataset": dataset,
        "status": status,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "records_read": records_read,
        "records_written": records_written,
        "message": message,
        "logged_at": datetime.now(timezone.utc).isoformat(),
    }

    os.makedirs(os.path.dirname(AUDIT_LOG_PATH), exist_ok=True)

    with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as audit_file:
        audit_file.write(json.dumps(audit_record, ensure_ascii=False) + "\n")