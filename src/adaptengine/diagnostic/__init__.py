from .engine import (
    AdaptiveDiagnostic,
    DiagnosticResult,
    StopReason,
    ConceptDiagnosticResult,
    DiagnosticItemLog,
)
from .scoring import compute_eig, candidate_sort_key
from .bisection import BisectionDiagnostic

# F1 (D49): diagnostic_method -> class; every class has run(state, response_provider, ...)
DIAGNOSTICS = {"sweep": AdaptiveDiagnostic, "bisection": BisectionDiagnostic}

__all__ = [
    "AdaptiveDiagnostic",
    "BisectionDiagnostic",
    "DIAGNOSTICS",
    "DiagnosticResult",
    "StopReason",
    "ConceptDiagnosticResult",
    "DiagnosticItemLog",
    "compute_eig",
    "candidate_sort_key",
]
