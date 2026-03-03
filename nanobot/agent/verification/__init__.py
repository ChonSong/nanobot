"""Verification strategies for Coach-Player pipeline."""

from nanobot.agent.coach_player import (
    CoachDecision,
    CoachFeedback,
    ExecutionResult,
    VerificationStrategy,
    LLMVerificationStrategy,
)

from nanobot.agent.verification.pdf import (
    PDFVerificationStrategy,
    HybridVerificationStrategy,
)

__all__ = [
    "CoachDecision",
    "CoachFeedback", 
    "ExecutionResult",
    "VerificationStrategy",
    "LLMVerificationStrategy",
    "PDFVerificationStrategy",
    "HybridVerificationStrategy",
]