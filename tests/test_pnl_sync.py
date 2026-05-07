from agentic_trader.worker.pnl_sync import PnlSyncJob


class DummyAlpaca:
    def get_fill_activities(self):
        return []


def test_index_by_order_reads_dict_activity_payload():
    job = PnlSyncJob(DummyAlpaca())
    activities = [
        {"order_id": "abc", "realized_pl": "10.5"},
        {"order_id": "def", "realized_pl": "-2.0"},
        {"order_id": "ghi", "realized_pl": None},
        {"realized_pl": "1.0"},
    ]

    result = job._index_by_order(activities)

    assert result == {"abc": 10.5, "def": -2.0}
