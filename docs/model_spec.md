# Model Specification

## Bayesian Knowledge Tracing (BKT)
- P0 = 0.20
- guess(d) = 0.30 * (1 - d)
- slip(d) = 0.05 + 0.25 * d
- Bayes Update (correct) = p*(1-s) / [p*(1-s) + (1-p)*g]
- Bayes Update (incorrect) = p*s / [p*s + (1-p)*(1-g)]
- Learn = p + (1-p)*T (T is transition probability, T_EXERCISE=0.05, T_LESSON=0.20)

All numeric constants are synthetic defaults.

## Entropy
Entropy represents the uncertainty about whether a concept is known. It can rise when conflicting evidence is received (e.g., p=0.9 and student gets incorrect).
- H(p) = - (p * log2(p) + (1-p) * log2(1-p))
