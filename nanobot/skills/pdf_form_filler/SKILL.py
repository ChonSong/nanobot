"""PDF Form Filler skill using Coach-Player pipeline."""

from pathlib import Path
from typing import Any

from loguru import logger

from nanobot.agent.coach_player import (
    CoachPlayer,
    CoachDecision,
    CoachFeedback,
    ExecutionResult,
)
from nanobot.agent.verification.pdf import PDFVerificationStrategy
from nanobot.agent.tools.pdf import PDFFormFillerSkill


class PDFFormFillerSkill:
    """
    PDF Form Filler skill with Coach-Player verification.
    
    Uses iterative verification to ensure forms are filled correctly.
    """
    
    name = "pdf-form-filler"
    description = "Fill PDF forms with Coach-Player verification"
    
    def __init__(self, workspace: Path, agent_loop=None):
        self.workspace = workspace
        self.agent_loop = agent_loop
        
        # Initialize Coach-Player with PDF verification
        if agent_loop:
            pdf_verification = PDFVerificationStrategy(
                provider=agent_loop.provider,
                model=agent_loop.model,
            )
            
            self.coach_player = CoachPlayer(
                agent_loop=agent_loop,
                max_coach_iterations=3,
                confidence_threshold=0.8,
                verification_strategy=pdf_verification,
            )
        
        # PDF filler tool
        self.pdf_filler = PDFFormFillerSkill(workspace)
    
    async def fill_form(
        self,
        pdf_path: str,
        data: dict,
        verify: bool = True,
    ) -> dict:
        """
        Fill a PDF form with data.
        
        Args:
            pdf_path: Path to the PDF form
            data: Dict of field names to values
            verify: Whether to verify via OCR
            
        Returns:
            Dict with filled form path and verification results
        """
        logger.info(f"Filling PDF form: {pdf_path}")
        
        # Use Coach-Player for verified filling
        if self.coach_player and verify:
            return await self._fill_with_coach(pdf_path, data)
        else:
            # Direct fill without verification
            return await self.pdf_filler.fill(pdf_path, data, verify=verify)
    
    async def _fill_with_coach(self, pdf_path: str, data: dict) -> dict:
        """Fill with Coach-Player verification loop."""
        
        # Build task description
        field_list = ", ".join(f"{k}={v}" for k, v in list(data.items())[:5])
        task = f"Fill PDF form at {pdf_path} with the following data: {field_list}"
        
        # Execute with Coach-Player
        result = await self.coach_player.execute(
            task=task,
            context={
                "pdf_path": pdf_path,
                "data": data,
                "expected_fields": data,
                "filled_form_path": None,  # Will be set by player
                "verification": "re-ocr",
            },
        )
        
        return {
            "success": result.is_successful(),
            "confidence": result.confidence,
            "iterations": result.player_iterations,
            "content": result.content,
            "error": result.error,
        }
    
    async def analyze_form(self, pdf_path: str) -> dict:
        """Analyze PDF form to find available fields."""
        from nanobot.agent.tools.pdf import GetPDFFieldsTool
        
        tool = GetPDFFieldsTool()
        return await tool.execute(pdf_path)


# Skill loader function
def load_skill(workspace: Path, agent_loop=None) -> PDFFormFillerSkill:
    """Load the PDF form filler skill."""
    return PDFFormFillerSkill(workspace=workspace, agent_loop=agent_loop)