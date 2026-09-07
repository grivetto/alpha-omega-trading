from denaro.domain.adaptive_vol_grid import AdaptiveVolGrid, GridConfig
from denaro.domain.grid import GridDecision


def test_adaptive_vol_grid_implements_node_policy_contract():
    policy = AdaptiveVolGrid(
        GridConfig(
            symbol="SOL/EUR",
            capital=13.5,
            levels=3,
            min_vol_ratio=0.000001,
            fee_rate=0.001,
        ),
        min_amount=0.0001,
    )
    for price in (100.0, 100.5, 99.8, 100.3):
        policy.on_price(price)

    decision = policy.decide(
        price=100.0,
        open_buys={},
        open_sells={},
        cash=13.5,
        capital_config=13.5,
        free_balance=13.5,
        now=1_000.0,
    )

    assert isinstance(decision, GridDecision)
    assert len(decision.to_place) <= 3
    assert all(level.amount >= 0.0001 for level in decision.to_place)
    assert policy.sell_target(100.0) > 100.0


def test_adaptive_vol_grid_does_not_duplicate_open_levels():
    policy = AdaptiveVolGrid(GridConfig(capital=12.0, levels=3, min_vol_ratio=0.000001))
    for price in (100.0, 101.0, 100.0):
        policy.on_price(price)

    decision = policy.decide(
        price=100.0,
        open_buys={"existing": {"price": 99.0, "amount": 0.04, "level": 0, "timestamp": 999.0}},
        open_sells={},
        cash=8.0,
        capital_config=12.0,
        free_balance=8.0,
        now=1_000.0,
    )

    assert len(decision.to_place) <= 2
