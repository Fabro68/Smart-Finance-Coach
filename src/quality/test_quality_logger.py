from quality_logger import (
    create_quality_run_id,
    write_quality_result,
)


quality_run_id = create_quality_run_id()

write_quality_result(
    quality_run_id=quality_run_id,
    dataset="test_dataset",
    check_name="test_check",
    status="PASS",
    observed_value="100",
    expected_value="100",
    message="Quality logger test completed successfully.",
)

print("Quality logger test completed.")
print(f"quality_run_id: {quality_run_id}")