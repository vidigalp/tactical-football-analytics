"""Study 03 follow-up: how much of a club's card count is not about defending?

Wyscout labels every foul with its own vocabulary. Four of those labels
("Protest", "Time lost foul", "Simulation", "Out of game foul") are not
challenges: they are almost always carded, and their pitch coordinate is
wherever the player happened to be standing. Any statistic about *where* a club
fouls has to be able to drop them, and the size of a club's non-play card count
is a claim outside analysts make that this dataset can actually test.

Nothing here is about Portugal. The Portuguese feed carries card counts and no
card reason, so what this file produces for that league is a bound, in the same
sense as the location bound already in the dashboard.

Run: uv run python scripts/card_typology.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "03-the-lever-nobody-pulls"
MIN_FOULS = 200

#: Cards that are not a defensive or play action. The wording of the definition
#: matters more than the list: these are the four labels where the offence is
#: conduct rather than a challenge for the ball.
NON_PLAY = ("Protest", "Time lost foul", "Simulation", "Out of game foul")

#: Neither clearly conduct nor clearly a challenge, so they are reported on
#: their own and counted as play fouls, which is the conservative direction:
#: it makes the non-play share smaller, not larger.
AMBIGUOUS = ("Late card foul", "Violent Foul")


def wilson(k: int, n: int) -> tuple[float, float]:
    z = 1.96
    centre = (k / n + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt((k / n) * (1 - k / n) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return float(max(centre - half, 0)), float(min(centre + half, 1))


def correlation(a: pd.Series, b: pd.Series) -> dict[str, float]:
    r = float(stats.pearsonr(a, b)[0])
    se = 1 / np.sqrt(len(a) - 3)
    z = np.arctanh(r)
    return {"r": r, "lo": float(np.tanh(z - 1.96 * se)),
            "hi": float(np.tanh(z + 1.96 * se)), "r2": r * r}


def main() -> None:
    fouls = pd.read_parquet(ROOT / "data" / "events" / "fouls_bigfive_2017-18.parquet")
    fouls["carded"] = (fouls.card != "none").astype(int)
    fouls["non_play"] = fouls.sub_type.isin(NON_PLAY).astype(int)
    fouls["own_third"] = (fouls.x < 100 / 3).astype(int)
    play = fouls[fouls.non_play == 0]

    by_type = {}
    for name, group in fouls.groupby("sub_type"):
        n, k = int(len(group)), int(group.carded.sum())
        lo, hi = wilson(k, n)
        by_type[name] = {"fouls": n, "cards": k, "rate": k / n, "lo": lo, "hi": hi}

    clubs = fouls.groupby(["league", "team_id"]).agg(
        fouls=("carded", "size"), cards=("carded", "sum"),
        matches=("match_id", "nunique"))
    clubs = clubs[clubs.fouls >= MIN_FOULS]
    # Every non-play foul in the five leagues is carded bar six, so its count is
    # its card count; counting the cards rather than the fouls makes that
    # explicit instead of assuming it.
    clubs["non_play_cards"] = fouls[fouls.non_play == 1].groupby(
        ["league", "team_id"]).carded.sum().reindex(clubs.index).fillna(0)
    clubs["non_play_share"] = clubs.non_play_cards / clubs.cards
    clubs["cards_per_match"] = clubs.cards / clubs.matches
    clubs["non_play_per_match"] = clubs.non_play_cards / clubs.matches
    play_clubs = play.groupby(["league", "team_id"]).agg(
        play_fouls=("carded", "size"), play_cards=("carded", "sum"))
    clubs = clubs.join(play_clubs)
    clubs["play_rate"] = clubs.play_cards / clubs.play_fouls
    clubs["card_rate"] = clubs.cards / clubs.fouls
    own = play.groupby(["league", "team_id"]).own_third.mean().reindex(clubs.index)

    # Is a club's non-play share a trait or the noise of a small count? Split
    # each club's own matches into two halves and correlate the halves. One
    # season cannot answer persistence across seasons; this is what it can
    # answer, and the Spearman-Brown step is the standard correction for
    # measuring a season with half of it.
    fouls["half"] = fouls.groupby(["league", "team_id"]).match_id.transform(
        lambda s: pd.factorize(s)[0] % 2)
    halves = fouls.groupby(["league", "team_id", "half"]).agg(
        cards=("carded", "sum"), non_play=("non_play", "sum"))
    halves["share"] = halves.non_play / halves.cards
    wide = halves.share.unstack("half").reindex(clubs.index).dropna()
    split_half = float(stats.pearsonr(wide[0], wide[1])[0])
    corrected = 2 * split_half / (1 + split_half)

    non_play_share = float(fouls[fouls.non_play == 1].carded.sum() / fouls.carded.sum())
    base = float(fouls.carded.mean())
    play_base = float(play.carded.mean())

    def rate(frame: pd.DataFrame) -> float:
        return float(frame.carded.mean())

    facts = {
        "fouls": int(len(fouls)),
        "cards": int(fouls.carded.sum()),
        "clubs": int(len(clubs)),
        "by_sub_type": by_type,
        "non_play_labels": list(NON_PLAY),
        "ambiguous_labels": list(AMBIGUOUS),
        "non_play_fouls": int(fouls.non_play.sum()),
        "non_play_cards": int(fouls[fouls.non_play == 1].carded.sum()),
        "non_play_share_of_cards": non_play_share,
        "non_play_share_of_fouls": float(fouls.non_play.mean()),

        # Study 03's own numbers with the four conduct labels removed. If these
        # differ from facts.json, the study's gradient was carrying cards that
        # have nothing to do with where a challenge was made.
        "base_rate": base,
        "play_base_rate": play_base,
        "play_own_fifth": rate(play[play.x <= 20]),
        "play_attacking_fifth": rate(play[play.x > 80]),
        "play_own_third": rate(play[play.own_third == 1]),
        "play_middle_third": rate(play[(play.own_third == 0) & (play.x < 200 / 3)]),
        "play_attacking_third": rate(play[play.x >= 200 / 3]),
        "play_location_bound_low": rate(play[play.x > 80]) / play_base,
        "play_location_bound_high": rate(play[play.x <= 20]) / play_base,
        "r_own_third_share_play": correlation(own, clubs.play_rate),

        # The spread between clubs, which is what a claim about one club needs.
        "club_non_play_share_min": float(clubs.non_play_share.min()),
        "club_non_play_share_median": float(clubs.non_play_share.median()),
        "club_non_play_share_max": float(clubs.non_play_share.max()),
        "club_non_play_per_match_min": float(clubs.non_play_per_match.min()),
        "club_non_play_per_match_median": float(clubs.non_play_per_match.median()),
        "club_non_play_per_match_max": float(clubs.non_play_per_match.max()),
        "club_non_play_cards_min": int(clubs.non_play_cards.min()),
        "club_non_play_cards_max": int(clubs.non_play_cards.max()),
        "r_non_play_share_vs_card_rate": correlation(clubs.non_play_share, clubs.card_rate),
        "r_non_play_vs_cards_per_match": correlation(
            clubs.non_play_per_match, clubs.cards_per_match),

        # How much of a club's season a conduct count can move, as a multiplier
        # on expected cards: the same shape as the location bound, so the
        # dashboard can carry it the same way.
        "typology_bound_low": float(1 - clubs.non_play_share.max()
                                    + clubs.non_play_share.min()),
        "typology_bound_high": float(1 + clubs.non_play_share.max()
                                     - clubs.non_play_share.min()),

        # The location bound the dashboard carries, rebuilt. Scaling a club's
        # whole expected count by a fifth's card rate assumes every card moves
        # with the foul's position, and half the cards in the attacking fifth
        # are conduct cards that do not: they stay wherever the club's rate of
        # dissent puts them. So only the play share scales, and the conduct
        # share is carried at one. The result is narrower at both ends than
        # the published bound, which means the published one overstates how far
        # location alone can move a club.
        "attacking_fifth_cards": int(fouls[fouls.x > 80].carded.sum()),
        "attacking_fifth_non_play_cards": int(
            fouls[(fouls.x > 80) & (fouls.non_play == 1)].carded.sum()),
        "own_fifth_cards": int(fouls[fouls.x <= 20].carded.sum()),
        "own_fifth_non_play_cards": int(
            fouls[(fouls.x <= 20) & (fouls.non_play == 1)].carded.sum()),
        "composite_location_bound_low": float(
            (1 - non_play_share) * (rate(play[play.x > 80]) / play_base) + non_play_share),
        "composite_location_bound_high": float(
            (1 - non_play_share) * (rate(play[play.x <= 20]) / play_base) + non_play_share),

        "split_half_r": split_half,
        "split_half_corrected": float(corrected),
        "split_half_clubs": int(len(wide)),
    }
    (REPORT / "typology.json").write_text(json.dumps(facts, indent=2, sort_keys=True) + "\n")
    for key, value in facts.items():
        if isinstance(value, dict) and "r" in value:
            print(f"  {key:<32}{value['r']:+.3f} [{value['lo']:+.3f}, {value['hi']:+.3f}]")
        elif isinstance(value, float):
            print(f"  {key:<32}{value:.4f}")
        elif isinstance(value, (int, str, list)):
            print(f"  {key:<32}{value}")
    print(f"\nwrote {(REPORT / 'typology.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
