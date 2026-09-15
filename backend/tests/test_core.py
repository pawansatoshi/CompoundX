from compoundx.access_codes import code_hash, generate_code
from compoundx.compounding import compound_next_day
from compoundx.risk import validate_trade


def test_access_code_format_and_hash():
    code = generate_code()
    assert len(code.split("-")) == 4
    assert code_hash(code) == code_hash(code.lower())


def test_daily_compounding_uses_realized_net_pnl():
    assert compound_next_day(100, 4, fees=0.5, slippage=0.5) == 103


def test_risk_blocks_daily_loss_limit():
    d = validate_trade(equity=100, daily_pnl=-0.02, drawdown=0,
                       open_positions=0, entry=100, stop=99, signal_score=9)
    assert not d.allowed
    assert "daily loss" in d.reason
