"""Team-season discipline aggregates and their shrunken estimates.

Provenance of the metrics here:

* ``fouls_per_match`` — INDUSTRY. A plain count rate, universally reported.
* ``cards_per_match`` — INDUSTRY. As above.
* ``cards_per_foul`` — LITERATURE, with care. Phatak et al. (2021) use the
  reciprocal (fouls per yellow card) across five leagues as an indicator of
  fouling incentive. It is *not* a named, validated metric with an agreed
  definition, and it must never be pooled across leagues: the same paper reports
  Simpson's paradox on it, where the pooled trend differs in direction from the
  within-league trends.

Known confounders, restated wherever these are published: referee assignment
(observable in England and Scotland only), foul location and severity (never
observable from this source), match state, opponent quality, and the fact that
the yellow-card count includes cards for dissent, time-wasting and bench
offences while the denominator counts fouls alone.
"""

from __future__ import annotations

import pandas as pd

from tfa.stats.shrinkage import shrink_beta_binomial, shrink_gamma_poisson


def team_season(matches: pd.DataFrame) -> pd.DataFrame:
    """Aggregate match rows into one row per team per league-season."""
    from tfa.ingest.matches import to_team_match

    tm = to_team_match(matches)
    grouped = tm.groupby(["Div", "country", "season", "team"], as_index=False).agg(
        matches=("fouls", "size"),
        fouls=("fouls", "sum"),
        yellows=("yellows", "sum"),
        reds=("reds", "sum"),
        opp_fouls=("opp_fouls", "sum"),
        opp_yellows=("opp_yellows", "sum"),
        strength_diff=("strength_diff", "mean"),
    )
    grouped["cards"] = grouped["yellows"] + grouped["reds"]
    return grouped


def with_shrinkage(team_seasons: pd.DataFrame) -> pd.DataFrame:
    """Add shrunken estimates and intervals, fitted **within each league-season**.

    Pooling the prior across leagues would import the very confound Phatak et al.
    warn about, and pooling across seasons would import the era trend — league
    discipline has moved a long way since 2000. So each league-season gets its
    own prior, which is also the only pool in which the teams genuinely face a
    common refereeing regime.
    """
    out = []
    for (_div, _season), group in team_seasons.groupby(["Div", "season"], sort=False):
        group = group.reset_index(drop=True)

        from tfa.stats.shrinkage import beta_binomial_prior, gamma_poisson_prior

        foul_prior = gamma_poisson_prior(group["fouls"], group["matches"])
        card_prior = gamma_poisson_prior(group["cards"], group["matches"])
        rate_prior = beta_binomial_prior(group["yellows"], group["fouls"])

        fouls = shrink_gamma_poisson(group["fouls"], group["matches"], foul_prior)
        cards = shrink_gamma_poisson(group["cards"], group["matches"], card_prior)
        rate = shrink_beta_binomial(group["yellows"], group["fouls"], rate_prior)

        # Whether the league's teams are separable at all at this sample size.
        group["fouls_detectable"] = foul_prior.detectable_variance
        group["cards_detectable"] = card_prior.detectable_variance
        group["cards_per_foul_detectable"] = rate_prior.detectable_variance
        group["cards_per_foul_n0"] = rate_prior.prior_sample_size

        group["fouls_per_match"] = fouls["raw"]
        group["fouls_per_match_shrunk"] = fouls["shrunk"]
        group["fouls_per_match_lo"] = fouls["lower"]
        group["fouls_per_match_hi"] = fouls["upper"]

        group["cards_per_match"] = cards["raw"]
        group["cards_per_match_shrunk"] = cards["shrunk"]
        group["cards_per_match_lo"] = cards["lower"]
        group["cards_per_match_hi"] = cards["upper"]

        group["cards_per_foul"] = rate["raw"]
        group["cards_per_foul_shrunk"] = rate["shrunk"]
        group["cards_per_foul_lo"] = rate["lower"]
        group["cards_per_foul_hi"] = rate["upper"]
        group["cards_per_foul_weight"] = rate["shrinkage_weight"]
        group["cards_per_foul_reliability"] = rate["reliability"]

        # The reciprocal is the form the literature and the public use, but it is
        # never modelled directly: E[F/C] != 1/E[C/F], and it is undefined for a
        # team with no cards. Derived from the shrunken rate instead.
        group["fouls_per_card"] = 1.0 / group["cards_per_foul"]
        group["fouls_per_card_shrunk"] = 1.0 / group["cards_per_foul_shrunk"]
        group["fouls_per_card_lo"] = 1.0 / group["cards_per_foul_hi"]
        group["fouls_per_card_hi"] = 1.0 / group["cards_per_foul_lo"]

        out.append(group)

    return pd.concat(out, ignore_index=True)
