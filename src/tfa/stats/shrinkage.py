"""Empirical-Bayes shrinkage for team rates.

Two conjugate families cover everything this project measures:

* **Beta-binomial** for a rate conditioned on the team's own denominator, such as
  cards per foul.
* **Gamma-Poisson** for a count against an exposure, such as fouls per match.

Both estimate the prior from the league itself, so a team with little data is
pulled toward its league's mean rather than judged on its own noise. The
shrinkage weight ``B = n₀ / (n₀ + n)`` goes to 1 as ``n`` goes to 0, which means
an early-season estimate collapses to the league mean automatically. That
self-silencing behaviour is the main defence against publishing noise, and it
costs nothing.

A useful identity falls out for free: reliability is ``r(n) = n / (n + n₀)``, so
**the prior sample size is the stabilisation point**. A metric whose ``n₀`` is 40
matches cannot be trusted after six, and the model says so without needing a
separate reliability study.

.. warning::
   The method-of-moments prior must subtract sampling variance from observed
   variance. Skipping that step is the classic error: it inflates the estimated
   between-team spread, weakens shrinkage, and manufactures exactly the outliers
   this module exists to suppress. See :func:`beta_binomial_prior` and the
   regression test in ``tests/test_shrinkage.py``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

EPSILON = 1e-9


@dataclass(frozen=True)
class BetaBinomialPrior:
    """Prior for a rate, fitted across a league."""

    alpha: float
    beta: float
    detectable_variance: bool = True
    """False when observed spread is fully explained by sampling noise.

    Not a failure. It is the estimator reporting that at this sample size the
    units are statistically indistinguishable, and every estimate will collapse
    onto the pooled mean. Anything published from such a fit must say so rather
    than presenting a ranking of identical numbers.
    """

    @property
    def mean(self) -> float:
        return self.alpha / (self.alpha + self.beta)

    @property
    def prior_sample_size(self) -> float:
        """``n₀ = α + β`` — also the metric's stabilisation point."""
        return self.alpha + self.beta

    def reliability(self, n: float | np.ndarray) -> float | np.ndarray:
        """Fraction of observed variance that is signal at sample size *n*."""
        return n / (n + self.prior_sample_size)

    def matches_for_reliability(self, target: float = 0.7) -> float:
        """Trials needed to reach a given reliability. ``r=0.5`` is exactly ``n₀``."""
        return self.prior_sample_size * target / (1.0 - target)


@dataclass(frozen=True)
class GammaPoissonPrior:
    """Prior for a count rate against exposure."""

    shape: float
    rate: float
    detectable_variance: bool = True
    """False when observed spread is fully explained by sampling noise."""

    @property
    def mean(self) -> float:
        return self.shape / self.rate

    @property
    def prior_exposure(self) -> float:
        """Exposure at which the estimate is half data, half prior."""
        return self.rate

    def reliability(self, exposure: float | np.ndarray) -> float | np.ndarray:
        return exposure / (exposure + self.rate)


def beta_binomial_prior(successes: np.ndarray, trials: np.ndarray) -> BetaBinomialPrior:
    """Fit a Beta prior by moments, correcting for sampling variance.

    The observed spread of team rates contains two components: genuine
    between-team variation, and the sampling noise of estimating each team's rate
    from a finite denominator. Only the first belongs in the prior.

    Subtracting the mean sampling variance is what separates them. Omitting it is
    the failure this module warns about, and its effect is not subtle: with six
    matches per team it can more than double the apparent between-team spread.
    """
    successes = np.asarray(successes, dtype=float)
    trials = np.asarray(trials, dtype=float)

    keep = trials > 0
    successes, trials = successes[keep], trials[keep]
    if len(trials) < 2:
        raise ValueError("need at least two units with data to fit a prior")

    # Pooled mean, weighted by denominator: a team with more fouls should count
    # for more when estimating the league's card rate.
    mean = successes.sum() / trials.sum()

    rates = successes / trials
    weights = trials / trials.sum()
    observed_var = float(np.sum(weights * (rates - mean) ** 2))

    # Expected variance if every team shared the same true rate.
    sampling_var = float(np.mean(mean * (1.0 - mean) / trials))

    detectable = observed_var > sampling_var
    # Floor the between-unit variance at a small fraction of sampling variance
    # rather than at an arbitrary epsilon. This keeps the prior finite and the
    # posterior intervals meaningful while still shrinking almost completely,
    # and it avoids a 1/epsilon blow-up that silently produces identical
    # estimates with implausibly tight intervals.
    true_var = observed_var - sampling_var if detectable else 0.05 * sampling_var

    # Method of moments for a Beta: n₀ = mean(1-mean)/var - 1.
    total = max(mean * (1.0 - mean) / max(true_var, EPSILON) - 1.0, EPSILON)

    return BetaBinomialPrior(
        alpha=mean * total, beta=(1.0 - mean) * total, detectable_variance=detectable
    )


def gamma_poisson_prior(counts: np.ndarray, exposure: np.ndarray) -> GammaPoissonPrior:
    """Fit a Gamma prior by moments, correcting for sampling variance."""
    counts = np.asarray(counts, dtype=float)
    exposure = np.asarray(exposure, dtype=float)

    keep = exposure > 0
    counts, exposure = counts[keep], exposure[keep]
    if len(exposure) < 2:
        raise ValueError("need at least two units with data to fit a prior")

    mean = counts.sum() / exposure.sum()

    rates = counts / exposure
    weights = exposure / exposure.sum()
    observed_var = float(np.sum(weights * (rates - mean) ** 2))
    sampling_var = float(np.mean(mean / exposure))

    detectable = observed_var > sampling_var
    true_var = observed_var - sampling_var if detectable else 0.05 * sampling_var

    # Gamma moments: mean = shape/rate, var = shape/rate².
    rate = mean / max(true_var, EPSILON)
    return GammaPoissonPrior(
        shape=mean * rate, rate=rate, detectable_variance=detectable
    )


def shrink_beta_binomial(
    successes: np.ndarray,
    trials: np.ndarray,
    prior: BetaBinomialPrior | None = None,
    *,
    credible: float = 0.95,
) -> pd.DataFrame:
    """Posterior mean, interval, shrinkage weight and reliability per unit."""
    successes = np.asarray(successes, dtype=float)
    trials = np.asarray(trials, dtype=float)
    prior = prior or beta_binomial_prior(successes, trials)

    post_a = prior.alpha + successes
    post_b = prior.beta + (trials - successes)

    tail = (1.0 - credible) / 2.0
    with np.errstate(invalid="ignore", divide="ignore"):
        raw = np.where(trials > 0, successes / np.maximum(trials, EPSILON), np.nan)

    return pd.DataFrame(
        {
            "raw": raw,
            "shrunk": post_a / (post_a + post_b),
            "lower": stats.beta.ppf(tail, post_a, post_b),
            "upper": stats.beta.ppf(1.0 - tail, post_a, post_b),
            "trials": trials,
            "shrinkage_weight": prior.prior_sample_size
            / (prior.prior_sample_size + trials),
            "reliability": prior.reliability(trials),
        }
    )


def shrink_gamma_poisson(
    counts: np.ndarray,
    exposure: np.ndarray,
    prior: GammaPoissonPrior | None = None,
    *,
    credible: float = 0.95,
) -> pd.DataFrame:
    """Posterior mean, interval, shrinkage weight and reliability per unit."""
    counts = np.asarray(counts, dtype=float)
    exposure = np.asarray(exposure, dtype=float)
    prior = prior or gamma_poisson_prior(counts, exposure)

    post_shape = prior.shape + counts
    post_rate = prior.rate + exposure

    tail = (1.0 - credible) / 2.0
    with np.errstate(invalid="ignore", divide="ignore"):
        raw = np.where(exposure > 0, counts / np.maximum(exposure, EPSILON), np.nan)

    return pd.DataFrame(
        {
            "raw": raw,
            "shrunk": post_shape / post_rate,
            "lower": stats.gamma.ppf(tail, post_shape, scale=1.0 / post_rate),
            "upper": stats.gamma.ppf(1.0 - tail, post_shape, scale=1.0 / post_rate),
            "exposure": exposure,
            "shrinkage_weight": prior.rate / (prior.rate + exposure),
            "reliability": prior.reliability(exposure),
        }
    )


def historical_prior(
    history_successes: np.ndarray,
    history_trials: np.ndarray,
    *,
    family: str = "beta",
) -> BetaBinomialPrior | GammaPoissonPrior:
    """Fit a prior on completed seasons, for use on an in-progress one.

    Fitting the prior on the season being judged is circular and, early on,
    nearly uninformative: three matches per team cannot reveal how much teams
    genuinely differ. The estimate of between-team spread is then itself noise,
    and it is the quantity that decides how hard to shrink.

    Completed seasons answer it directly, and the gain is **accuracy rather than
    direction**. Simulated with a true prior sample size of 72, a fit on 18 teams
    with 40 trials each has an interquartile range of roughly 54 to 320; a fit on
    many completed seasons lands between 68 and 79. The thin fit can understate
    or overstate how much teams differ by several fold, and there is no way to
    tell which from the thin data alone.

    Portugal 2026-27 happened to land low — 99 fouls of prior weight against
    1,213 from completed seasons — which under-shrank an extreme team from 5.9
    to 7.8 fouls per yellow. It could as easily have landed high and over-shrunk
    a real signal.

    What history knows about how much teams differ does not stop being true
    because a new season started.
    """
    if family == "beta":
        return beta_binomial_prior(history_successes, history_trials)
    if family == "gamma":
        return gamma_poisson_prior(history_successes, history_trials)
    raise ValueError(f"unknown family {family!r}")
