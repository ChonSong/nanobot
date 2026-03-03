"""Coach-Player tool for verified task execution."""

from pathlib import Path
from typing import Any

from loguru import logger

from nanobot.agent.coach_player import (
    CoachPlayer,
    CoachDecision,
    ExecutionResult,
    LLMVerificationStrategy,
)
from nanobot.agent.verification.pdf import PDFVerificationStrategy


class CoachPlayerTool:
    """
    Tool wrapper for Coach-Player verified execution.
    
    This tool allows the agent to execute tasks with iterative
    verification and confidence scoring.
    """
    
    name = "coach_player"
    description = "Execute tasks with iterative verification, confidence scoring, and automatic retry. Use for complex tasks requiring high reliability (form filling, data extraction, etc.)"
    
    parameters = {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "Description of the task to execute",
            },
            "context": {
                "type": "object",
                "description": "Additional context for the task (files, data, etc.)",
            },
            "verification_mode": {
                "type": "string",
                "enum": ["llm", "pdf", "none"],
                "default": "llm",
                "description": "Verification strategy to use",
            },
            "max_iterations": {
                "type": "integer",
                "default": 3,
                "description": "Maximum verification iterations",
            },
            "confidence_threshold": {
                "type": "number",
                "default": 0.8,
                "description": "Minimum confidence threshold (0-1)",
            },
        },
        "required": ["task"],
    }
    
    def __init__(self, agent_loop):
        self.agent_loop = agent_loop
    
    async def execute(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        verification_mode: str = "llm",
        max_iterations: int = 3,
        confidence_threshold: float = 0.8,
    ) -> str:
        """
        Execute a task with Coach-Player verification.
        
        Args:
            task: Task description
            context: Additional context
            verification_mode: Verification strategy
            max_iterations: Max coach iterations
            confidence_threshold: Min confidence
            
        Returns:
            Execution result with confidence score
        """
        logger.info(f"CoachPlayerTool executing: {task[:50]}...")
        
        # Build verification strategy
        verification = None
        if verification_mode == "llm" and self.agent_loop:
            verification = LLMVerificationStrategy(
                provider=self.agent_loop.provider,
                model=self.agent_loop.model,
            )
        elif verification_mode == "pdf" and self.agent_loop:
            verification = PDFVerificationStrategy(
                provider=self.agent_loop.provider,
                model=self.agent_loop.model,
            )
        
        # Create Coach-Player
        coach_player = CoachPlayer(
            agent_loop=self.agent_loop,
            max_coach_iterations=max_iterations,
            confidence_threshold=confidence_threshold,
            verification_strategy=verification,
        )
        
        # Execute
        try:
            result = await coach_player.execute(
                task=task,
                context=context or {},
            )
            
            # Format result
            return self._format_result(result)
            
        except Exception as e:
            logger.error(f"CoachPlayerTool error: {e}")
            return f"Error: {str(e)}"
    
    def _format_result(self, result: ExecutionResult) -> str:
        """Format execution result for tool output."""
        lines = [
            f"✅ Task completed",
            f"Confidence: {result.confidence:.0%}",
            f"Iterations: {result.player_iterations}",
            "",
        ]
        
        if result.evidence:
            lines.append("Evidence:")
            for e in result.evidence[:3]:
                lines.append(f"  - {e}")
            lines.append("")
        
        if result.error:
            lines.append(f"Error: {result.error}")
        
        lines.append(f"\n{result.content}")
        
        return "\n".join(lines)
    
    def to_schema(self) -> dict[str, Any]:
        """Convert tool to OpenAI function schema format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }


def register_coach_player_tool(agent_loop) -> CoachPlayerTool:
    """Register the Coach-Player tool with an agent loop."""
    tool = CoachPlayerTool(agent_loop)
    agent_loop.tools.register(tool)
    logger.info("✅ Coach-Player tool registered")
    return tool
