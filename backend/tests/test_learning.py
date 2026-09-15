from compoundx.learning import fingerprint, review_similar_lessons


class FakeConn:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, query, params):
        class Result:
            def __init__(self, rows):
                self._rows = rows

            def fetchall(self):
                return self._rows

        return Result(self.rows)


def test_fingerprint_is_stable():
    context = {"symbol": "BTC/USDT", "side": "LONG", "regime": "TREND", "timeframe": "1h", "setup": "breakout", "volume_confirmed": True, "trend_confirmed": True}
    assert fingerprint(context) == fingerprint(dict(context))


def test_learning_reduces_score_after_repeated_failures():
    rows = [("00000000-0000-0000-0000-000000000001", False, "weak_volume", "require_volume_confirmation", 0.9, {})] * 5
    result = review_similar_lessons(FakeConn(rows), {"symbol": "BTC/USDT", "side": "LONG", "regime": "TREND", "timeframe": "1h", "setup": "breakout", "volume_confirmed": False, "trend_confirmed": True})
    assert result["losses"] == 5
    assert result["adjustment"] == -2
    assert result["decision"] == "REDUCE"


def test_learning_does_not_change_when_history_is_insufficient():
    rows = [("00000000-0000-0000-0000-000000000001", False, "x", "y", 0.9, {})] * 2
    result = review_similar_lessons(FakeConn(rows), {"symbol": "BTC/USDT", "side": "LONG", "regime": "TREND", "timeframe": "1h", "setup": "breakout"})
    assert result["adjustment"] == 0
    assert result["decision"] == "UNCHANGED"
