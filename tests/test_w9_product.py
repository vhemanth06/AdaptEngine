from adaptengine.core.config import DEFAULT_CONFIG
from adaptengine.core.profiles import PRODUCT_PROFILE, load_profile, product_config
from adaptengine.learner.state import mastered_by

def test_product_config_values():
    c = product_config()
    assert (c.theta, c.k_responses, c.horizon_aware_mastery) == (0.95, 1, False)
    assert (c.selection_scope, c.concept_cap, c.n_max, c.diag_budget_min, c.diag_budget_per_concept) == ("goal_search", 4, 25, 12, 1.0)
    assert c.consolidation and c.verification_probe and c.feasibility_warning
    assert c.diagnostic_scope == "goal_path"
    assert c.class_params == load_profile("fitted_S1").class_params and PRODUCT_PROFILE == "fitted_S1"

def test_product_rules_on_any_profile():
    c = product_config("w7_default")
    assert c.theta == 0.95 and c.class_params == DEFAULT_CONFIG.class_params

def test_mastery_is_theta_after_one_answer():
    c = product_config("w7_default")
    assert mastered_by(0.95, 1, 1, c) and not mastered_by(0.94, 9, 9, c)
    assert not mastered_by(0.99, 0, 0, c)  # an inferred estimate alone never masters

def test_defaults_untouched():
    assert (DEFAULT_CONFIG.theta, DEFAULT_CONFIG.k_responses, DEFAULT_CONFIG.selection_scope) == (0.85, 2, "concept_sweep")
