"""The affine card expectation, and the bias it exists to remove."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tfa.stats.expectation import attach, fit


def synthetic(n: int = 4000, intercept: float = 0.9, slope: float = 0.10) -> pd.DataFrame:
    rng = np.random.default_rng(11)
    fouls = rng.integers(4, 24, size=n)
    cards = rng.poisson(intercept + slope * fouls)
    return pd.DataFrame({"league": "X", "season": "2024", "fouls": fouls, "yellows": cards})


def test_recovers_a_known_affine_relationship():
    model = fit(synthetic())[("X", "2024")]
    assert model.intercept == pytest.approx(0.9, abs=0.15)
    assert model.slope == pytest.approx(0.10, abs=0.02)


def test_proportional_model_biases_low_foul_teams_upward():
    """The bug this module fixes, demonstrated on data with no team effects.

    Every team here has the identical card process. A proportional model still
    ranks the low-foul teams as though they were booked unusually often.
    """
    frame = synthetic(6000)
    rng = np.random.default_rng(3)
    frame["team"] = rng.choice(["low", "high"], size=len(frame))
    # 'low' fouls less; behaviour is otherwise identical.
    frame.loc[frame.team == "low", "fouls"] = rng.integers(
        4, 12, size=int((frame.team == "low").sum())
    )
    frame["yellows"] = rng.poisson(0.9 + 0.10 * frame["fouls"])

    rate = frame["yellows"].sum() / frame["fouls"].sum()
    proportional = frame.groupby("team").apply(
        lambda g: g.yellows.sum() / (rate * g.fouls.sum()), include_groups=False
    )
    affine = attach(frame).groupby("team").apply(
        lambda g: g.yellows.sum() / g.exp_cards.sum(), include_groups=False
    )

    # Proportional invents a gap between identical teams; affine does not.
    assert proportional["low"] - proportional["high"] > 0.10
    assert abs(affine["low"] - affine["high"]) < 0.04


def test_negative_intercept_falls_back_to_proportional():
    frame = pd.DataFrame({
        "league": "X", "season": "2024",
        "fouls": list(range(5, 25)) * 5,
        "yellows": [0.2 * f for f in list(range(5, 25))] * 5,
    })
    model = fit(frame)[("X", "2024")]
    assert model.intercept >= 0.0


def test_intercept_share_is_reported():
    model = fit(synthetic())[("X", "2024")]
    assert 0.2 < model.intercept_share < 0.6
