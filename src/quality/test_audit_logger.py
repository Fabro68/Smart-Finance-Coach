from datetime import datetime, timezone
import time

from audit_logger import create_run_id, write_audit_log


run_id = create_run_id()
start_time = datetime.now(timezone.utc)

print(f"Starting test audit run: {run_id}")

time.sleep(1)

end_time = datetime.now(timezone.utc)

write_audit_log(
    pipeline_run_id=run_id,
    process_name="test_audit_logger",
    layer="test",
    dataset="test_dataset",
    status="SUCCESS",
    start_time=start_time,
    end_time=end_time,
    records_read=100,
    records_written=100,
    message="Audit logger test completed successfully.",
)

print("Audit log written successfully.")