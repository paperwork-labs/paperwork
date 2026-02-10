from backend.services.market.stage_utils import compute_stage_run_lengths


def test_compute_stage_run_lengths_basic():
    labels = ["1", "1", "2A", "2A", "2A", "3", None, "2"]
    out = compute_stage_run_lengths(labels)

    assert out[0]["current_stage_days"] == 1
    assert out[0]["previous_stage_label"] is None
    assert out[0]["previous_stage_days"] is None

    assert out[1]["current_stage_days"] == 2
    assert out[1]["previous_stage_label"] is None

    assert out[2]["current_stage_days"] == 1
    assert out[2]["previous_stage_label"] == "1"
    assert out[2]["previous_stage_days"] == 2

    assert out[4]["current_stage_days"] == 3
    assert out[4]["previous_stage_label"] == "1"
    assert out[4]["previous_stage_days"] == 2

    assert out[5]["current_stage_days"] == 1
    assert out[5]["previous_stage_label"] == "2A"
    assert out[5]["previous_stage_days"] == 3

    assert out[6]["current_stage_days"] is None
    assert out[6]["previous_stage_label"] is None
    assert out[6]["previous_stage_days"] is None

    assert out[7]["current_stage_days"] == 1
    assert out[7]["previous_stage_label"] is None
