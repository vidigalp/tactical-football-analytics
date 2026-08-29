"""Shrinkage estimators, including the correction they exist to get right."""

from __future__ import annotations

import numpy as np
import pytest

from tfa.stats.shrinkage import (
    beta_binomial_prior,
    gamma_poisson_prior,
    shrink_beta_binomial,
    shrink_gamma_poisson,
)

RNG = np.random.default_rng(20260829)


def simulate_beta_binomial(n_teams: int, trials_per_team: int, alpha: float, beta: float):
    """Draw teams from a known Beta prior, then observe finite samples."""
    true_rates = RNG.beta(alpha, beta, size=n_teams)
    trials = np.full(n_teams, trials_per_team, dtype=float)
    successes = RNG.binomial(trials.astype(int), true_rates).astype(float)
    return successes, trials, true_rates


def test_recovers_known_prior():
    successes, trials, _ = simulate_beta_binomial(400, 400, alpha=12.0, beta=60.0)
    prior = beta_binomial_prior(successes, trials)
    assert prior.mean == pytest.approx(12 / 72, abs=0.01)
    # n0 = 72; recovery is noisy but should land in the right region.
    assert 40 < prior.prior_sample_size < 130


def test_sampling_variance_correction_matters():
    """Without the correction the prior is far too wide, so shrinkage collapses.

    This is the regression test for the trap documented in the module and in
    METHODS.md. The uncorrected estimator treats sampling noise as real
    between-team spread.
    """
    alpha, beta = 12.0, 60.0
    successes, trials, _ = simulate_beta_binomial(20, 60, alpha=alpha, beta=beta)

    corrected = beta_binomial_prior(successes, trials)

    # The same moment calculation without subtracting sampling variance.
    mean = successes.sum() / trials.sum()
    rates = successes / trials
    weights = trials / trials.sum()
    observed_var = float(np.sum(weights * (rates - mean) ** 2))
    uncorrected_n0 = mean * (1 - mean) / observed_var - 1.0

    assert corrected.prior_sample_size > uncorrected_n0 * 1.5, (
        "correcting for sampling variance must produce a tighter prior "
        "(larger n0) and therefore stronger shrinkage"
    )


def test_shrinkage_beats_raw_on_squared_error():
    """The entire justification for shrinking, tested directly."""
    successes, trials, true_rates = simulate_beta_binomial(20, 40, alpha=12.0, beta=60.0)
    out = shrink_beta_binomial(successes, trials)

    raw_error = float(np.mean((out["raw"] - true_rates) ** 2))
    shrunk_error = float(np.mean((out["shrunk"] - true_rates) ** 2))
    assert shrunk_error < raw_error


def test_shrinkage_weight_goes_to_one_with_no_data():
    successes = np.array([5.0, 8.0, 2.0, 0.0])
    trials = np.array([40.0, 50.0, 30.0, 0.0])
    out = shrink_beta_binomial(successes, trials)
    assert out["shrinkage_weight"].iloc[-1] == pytest.approx(1.0)
    assert np.isnan(out["raw"].iloc[-1])
    # A team with no data must sit exactly at the league mean.
    prior = beta_binomial_prior(successes, trials)
    assert out["shrunk"].iloc[-1] == pytest.approx(prior.mean)


def test_intervals_contain_the_estimate_and_widen_with_less_data():
    successes = np.array([10.0, 10.0])
    trials = np.array([400.0, 40.0])
    out = shrink_beta_binomial(successes, trials)
    assert (out["lower"] < out["shrunk"]).all()
    assert (out["shrunk"] < out["upper"]).all()
    wide = out["upper"] - out["lower"]
    assert wide.iloc[1] > wide.iloc[0], "less data must give a wider interval"


def test_reliability_identity():
    """r(n) = n/(n+n0), so r = 0.5 exactly at the prior sample size."""
    successes, trials, _ = simulate_beta_binomial(30, 100, alpha=12.0, beta=60.0)
    prior = beta_binomial_prior(successes, trials)
    n0 = prior.prior_sample_size
    assert prior.reliability(n0) == pytest.approx(0.5)
    assert prior.matches_for_reliability(0.5) == pytest.approx(n0)
    assert prior.reliability(0) == pytest.approx(0.0)


def test_gamma_poisson_recovers_and_shrinks():
    true_rates = RNG.gamma(shape=25.0, scale=1.0, size=200)
    exposure = np.full(200, 30.0)
    counts = RNG.poisson(true_rates * exposure).astype(float)

    prior = gamma_poisson_prior(counts, exposure)
    assert prior.mean == pytest.approx(25.0, rel=0.1)

    out = shrink_gamma_poisson(counts, exposure, prior)
    raw_error = float(np.mean((out["raw"] - true_rates) ** 2))
    shrunk_error = float(np.mean((out["shrunk"] - true_rates) ** 2))
    assert shrunk_error < raw_error


def test_prior_requires_at_least_two_units():
    with pytest.raises(ValueError):
        beta_binomial_prior(np.array([3.0]), np.array([10.0]))


def test_flags_when_variance_is_undetectable():
    """Teams drawn from an identical rate must be reported as indistinguishable."""
    trials = np.full(18, 40.0)
    successes = RNG.binomial(40, 0.17, size=18).astype(float)
    prior = beta_binomial_prior(successes, trials)
    assert prior.detectable_variance is False

    out = shrink_beta_binomial(successes, trials, prior)
    # Everything collapses to the pooled mean, but intervals stay finite.
    assert out["shrunk"].std() < 0.01
    assert (out["upper"] > out["lower"]).all()
    assert out["upper"].max() - out["lower"].min() > 0.01


def test_detects_variance_when_it_is_real():
    successes, trials, _ = simulate_beta_binomial(20, 400, alpha=12.0, beta=60.0)
    assert beta_binomial_prior(successes, trials).detectable_variance is True
