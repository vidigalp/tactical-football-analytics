"""Does a one-season booking index predict anything, and does shrinking it help?

Split out of build_discipline_story.py when the reliability question became its
own study. It was section nine of seventeen inside a report about one club,
which is the wrong place for the strongest statistics in the repository: study
03 opens by citing this result, so the dependency was real and invisible.

Run: uv run python scripts/index_reliability.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from tfa.competitions import is_completed, season_start_year
from tfa.metrics.discipline import team_season
from tfa.snapshot import read_manifest
from tfa.stats.shrinkage import beta_binomial_prior, shrink_beta_binomial
from tfa.viz import discipline_story as story
from tfa.viz import theme

ROOT = Path(__file__).resolve().parents[1]
REPORT = "04-how-much-of-an-index-is-real"

#: Matches a club-season needs before its raw ratio is worth scoring at all.
MIN_MATCHES = 30


def main() -> None:
    theme.apply()
    directory = sorted((ROOT / "data" / "snapshots").glob("*-W*"))[-1]
    entries = [e for e in read_manifest(directory) if e.source == "football-data"]
    matches = pd.concat(
        [pd.read_parquet(directory / e.parquet_path) for e in entries],
        ignore_index=True,
    )
    # Retrospective: an out-of-sample test cannot use a season that has not
    # finished as its "next season".
    matches = matches[matches["season"].map(is_completed)]

    seasons = team_season(matches)
    seasons["yr"] = seasons.season.map(season_start_year)
    seasons = seasons[seasons.matches >= MIN_MATCHES]

    parts = []
    for _, group in seasons.groupby(["Div", "season"]):
        group = group.reset_index(drop=True)
        prior = beta_binomial_prior(group.yellows, group.fouls)
        estimate = shrink_beta_binomial(group.yellows, group.fouls, prior)
        group["raw"] = estimate["raw"].to_numpy()
        group["shrunk"] = estimate["shrunk"].to_numpy()
        group["league_mean"] = prior.mean
        parts.append(group)
    seasons = pd.concat(parts, ignore_index=True)

    # Each club-season paired with the same club's next season in the same
    # division. This is the out-of-sample test: predict a season you have not
    # looked at, from one you have.
    following = seasons[["Div", "team", "yr", "yellows", "fouls"]].copy()
    following["yr"] -= 1
    following = following.rename(columns={"yellows": "y_next", "fouls": "f_next"})
    pairs = seasons.merge(following, on=["Div", "team", "yr"])
    pairs["actual"] = pairs.y_next / pairs.f_next

    def rmse(prediction: pd.Series) -> float:
        return float(np.sqrt(np.mean((prediction - pairs.actual) ** 2)))

    scores = {
        "raw ratio": rmse(pairs["raw"]),
        "shrunken estimate": rmse(pairs["shrunk"]),
        "ignore the club,\nuse the league mean": rmse(pairs.league_mean),
    }

    out = ROOT / "reports" / REPORT / "figures"
    written = story.shrinkage_validation(
        scores, out / "fig2-shrinkage-validation",
        n_pairs=len(pairs), snapshot=directory.name)
    for path in written:
        print("wrote", path.relative_to(ROOT))

    facts = {
        "snapshot": directory.name,
        "pairs": int(len(pairs)),
        "min_matches": MIN_MATCHES,
        "rmse": {name.replace("\n", " "): value for name, value in scores.items()},
        "shrunk_beats_raw": 1 - scores["shrunken estimate"] / scores["raw ratio"],
        "league_mean_beats_raw": (
            1 - scores["ignore the club,\nuse the league mean"] / scores["raw ratio"]
        ),
    }
    sidecar = ROOT / "reports" / REPORT / "shrinkage.json"
    sidecar.write_text(json.dumps(facts, indent=2, sort_keys=True) + "\n")
    print(f"wrote {sidecar.relative_to(ROOT)}")
    print(f"\n{len(pairs):,} consecutive club-season pairs")
    for name, value in scores.items():
        print(f"  {name.replace(chr(10), ' '):34} rmse {value:.5f}")
    print(f"  shrinking beats the raw ratio by "
          f"{100 * facts['shrunk_beats_raw']:.0f}%; ignoring the club beats it by "
          f"{100 * facts['league_mean_beats_raw']:.0f}%")


if __name__ == "__main__":
    main()
