from __future__ import annotations

from oh_my_exam.ai_usage import AiUsageRecord, AiUsageStore


def test_ai_usage_ledger_aggregates_booked_costs(tmp_path) -> None:
    store = AiUsageStore(tmp_path / "application.sqlite3")
    store.record(AiUsageRecord("deepseek", "deepseek-chat", 1200, 300, 2450, "answer"))
    store.record(AiUsageRecord("deepseek", "deepseek-chat", 800, 200, 1550, "answer"))

    bill = store.monthly_bill()

    assert bill["calls"] == 2
    assert bill["input_tokens"] == 2000
    assert bill["output_tokens"] == 500
    assert bill["cost_microusd"] == 4000
    assert bill["items"] == [{
        "provider": "deepseek",
        "model": "deepseek-chat",
        "calls": 2,
        "input_tokens": 2000,
        "output_tokens": 500,
        "cost_microusd": 4000,
    }]
