"""Expected yellow cards for a team-match.

The obvious model — ``expected = league_rate x fouls`` — is wrong, and wrong in a
direction that matters. Cards are not proportional to fouls. Fitting
``cards = a + b x fouls`` per league-season gives an intercept worth 13% to 47%
of mean yellows, and observed yellows per foul falls monotonically from 0.195 at six
fouls to 0.127 at eighteen.

The intercept is not noise. It is the cards that have nothing to do with a team's
recorded foul count: dissent, delaying the restart, entering the field of play,
celebration, simulation, plus whatever the source feed does or does not count as
a foul. In Greece and Italy that is nearly half of all cards.

Forcing the line through the origin therefore inflates every low-foul team and
deflates every high-foul team, with no behaviour involved. Dominant clubs foul
less than average, so a proportional model flatters precisely the clubs most
likely to be the subject of a finding. This module exists because that error was
shipped here first and caught later.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class CardModel:
    """Affine card expectation for one league-season: ``a + b * fouls``."""

    intercept: float
    slope: float
    league: str
    season: str

    def expected(self, fouls: np.ndarray) -> np.ndarray:
        return self.intercept + self.slope * np.asarray(fouls, dtype=float)

    @property
    def intercept_share(self) -> float:
        """Fraction of a typical team's cards unexplained by its foul count."""
        typical = self.intercept + self.slope * 13.0
        return self.intercept / typical if typical > 0 else float("nan")


def fit(frame: pd.DataFrame, *, cards: str = "yellows") -> dict[tuple[str, str], CardModel]:
    """Fit one affine model per league-season.

    Per league-season rather than pooled, because both the intercept and the
    slope vary a lot between competitions and eras, and pooling them would
    reintroduce the bias this module removes.
    """
    models: dict[tuple[str, str], CardModel] = {}
    for (league, season), group in frame.groupby(["league", "season"], sort=False):
        if len(group) < 50:
            continue
        slope, intercept = np.polyfit(group["fouls"], group[cards], 1)
        # A negative intercept is not physically meaningful and would give
        # negative expectations at low foul counts; fall back to proportional.
        if intercept < 0:
            slope = group[cards].sum() / group["fouls"].sum()
            intercept = 0.0
        models[(league, season)] = CardModel(
            intercept=float(intercept), slope=float(slope),
            league=str(league), season=str(season),
        )
    return models


def attach(frame: pd.DataFrame, *, cards: str = "yellows") -> pd.DataFrame:
    """Add ``exp_cards``: the affine, league-season expectation."""
    models = fit(frame, cards=cards)
    out = frame.copy()
    expected = np.full(len(out), np.nan)
    for i, (league, season, fouls) in enumerate(
        zip(out["league"], out["season"], out["fouls"], strict=True)
    ):
        model = models.get((league, season))
        if model is not None:
            expected[i] = model.intercept + model.slope * fouls
    out["exp_cards"] = expected
    return out
