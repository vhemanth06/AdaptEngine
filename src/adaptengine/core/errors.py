class AdaptEngineError(Exception):
    pass

class ValidationError(AdaptEngineError):
    pass

class DuplicateIdError(ValidationError):
    pass

class UnknownConceptError(ValidationError):
    pass

class DifficultyError(ValidationError):
    pass

class UnreviewedContentError(ValidationError):
    pass

class CycleError(AdaptEngineError):
    pass
