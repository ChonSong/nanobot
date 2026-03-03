"""Coach-Player pipeline implementation.

This module provides an iterative execution pattern inspired by g3,
where a "Coach" evaluates the player's output and decides whether
to pass, retry, or fail.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from loguru import logger


class CoachDecision(Enum):
    """Decision from the coach after evaluating player output."""
    PASS = "pass"      # Good enough, proceed with result
    RETRY = "retry"   # Not good, try again with feedback
    FAIL = "fail"     # Cannot complete, give up


@dataclass
class ExecutionResult:
    """Result from player execution with evidence for coach evaluation."""
    content: str
    confidence: float  # 0.0 to 1.0
    evidence: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    player_iterations: int = 0
    error: str | None = None
    
    def is_successful(self) -> bool:
        return self.error is None and self.confidence > 0


@dataclass
class CoachFeedback:
    """Feedback from coach to guide player retry."""
    decision: CoachDecision
    confidence: float
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    summary: str = ""


class VerificationStrategy:
    """Base class for verification strategies."""
    
    async def verify(
        self,
        task: str,
        result: ExecutionResult,
        context: dict,
    ) -> CoachFeedback:
        """Verify the result and provide feedback."""
        raise NotImplementedError


class LLMVerificationStrategy(VerificationStrategy):
    """Use LLM to evaluate its own output."""
    
    def __init__(self, provider, model: str = None, temperature: float = 0.3):
        self.provider = provider
        self.model = model
        self.temperature = temperature
    
    VERIFY_PROMPT = """You are a Coach evaluating a Player's work on a task.

TASK: {task}

PLAYER'S RESULT:
{result}

EVIDENCE:
{evidence}

TOOLS USED: {tools_used}

Evaluate the result and provide:
1. Confidence score (0.0-1.0): How confident are you that the task is complete?
2. Issues (list): What's wrong or missing?
3. Suggestions (list): How can the player improve?

Respond in this format:
CONFIDENCE: 0.85
ISSUES:
- Issue 1
- Issue 2
SUGGESTIONS:
- Suggestion 1
- Suggestion 2
SUMMARY: Brief evaluation"""
    
    async def verify(
        self,
        task: str,
        result: ExecutionResult,
        context: dict,
    ) -> CoachFeedback:
        prompt = self.VERIFY_PROMPT.format(
            task=task,
            result=result.content[:2000],  # Limit length
            evidence="\n".join(result.evidence[:5]) if result.evidence else "No evidence",
            tools_used=", ".join(result.tools_used) if result.tools_used else "None",
        )
        
        response = await self.provider.chat(
            messages=[{"role": "user", "content": prompt}],
            model=self.model,
            temperature=self.temperature,
            max_tokens=500,
        )
        
        return self._parse_response(response.content or "")
    
    def _parse_response(self, response: str) -> CoachFeedback:
        """Parse LLM response into CoachFeedback."""
        confidence = 0.5
        issues = []
        suggestions = []
        summary = ""
        
        for line in response.split("\n"):
            line = line.strip()
            if line.startswith("CONFIDENCE:"):
                try:
                    confidence = float(line.split(":")[1].strip())
                except (ValueError, IndexError):
                    pass
            elif line.startswith("ISSUES:"):
                state = "issues"
            elif line.startswith("SUGGESTIONS:"):
                state = "suggestions"
            elif line.startswith("SUMMARY:"):
                summary = line.split(":", 1)[1].strip()
                state = None
            elif line.startswith("- ") and state == "issues":
                issues.append(line[2:])
            elif line.startswith("- ") and state == "suggestions":
                suggestions.append(line[2:])
            elif line and state in ("issues", "suggestions"):
                # Continuation of list
                if state == "issues":
                    issues.append(line)
                else:
                    suggestions.append(line)
        
        if confidence >= 0.8:
            decision = CoachDecision.PASS
        elif confidence >= 0.4:
            decision = CoachDecision.RETRY
        else:
            decision = CoachDecision.FAIL
            
        return CoachFeedback(
            decision=decision,
            confidence=confidence,
            issues=issues,
            suggestions=suggestions,
            summary=summary or response[:200],
        )


class CoachPlayer:
    """
    Coach-Player pipeline for iterative task execution.
    
    The Player executes tasks using tools. The Coach evaluates the output
    and decides whether to pass, retry with feedback, or fail.
    """
    
    def __init__(
        self,
        agent_loop,
        max_coach_iterations: int = 3,
        confidence_threshold: float = 0.8,
        verification_strategy: VerificationStrategy | None = None,
    ):
        """
        Initialize Coach-Player pipeline.
        
        Args:
            agent_loop: Existing AgentLoop instance for tool execution
            max_coach_iterations: Maximum times coach can request retry
            confidence_threshold: Minimum confidence to consider PASS
            verification_strategy: Strategy for verifying results
        """
        self.agent_loop = agent_loop
        self.max_coach_iterations = max_coach_iterations
        self.confidence_threshold = confidence_threshold
        self.verification_strategy = verification_strategy
        
    async def execute(
        self,
        task: str,
        context: dict | None = None,
        on_progress: Callable[[str], asyncio.coroutines] | None = None,
    ) -> ExecutionResult:
        """
        Execute task with coach-player iterative loop.
        
        Args:
            task: Task description for the player
            context: Additional context (form data, files, etc.)
            on_progress: Callback for progress updates
            
        Returns:
            ExecutionResult with final output and confidence
        """
        context = context or {}
        all_tools_used: list[str] = []
        feedback_history: list[CoachFeedback] = []
        
        if on_progress:
            await on_progress(f"🎯 Starting Coach-Player pipeline for: {task[:50]}...")
        
        for coach_iter in range(1, self.max_coach_iterations + 1):
            if on_progress:
                await on_progress(f"🔄 Coach iteration {coach_iter}/{self.max_coach_iterations}")
            
            # Build player prompt with feedback from previous retries
            player_prompt = self._build_player_prompt(task, context, feedback_history)
            
            # Execute via agent loop
            try:
                result = await self._player_execute(
                    player_prompt,
                    context,
                    on_progress,
                )
                all_tools_used.extend(result.tools_used)
                
                if result.error:
                    if on_progress:
                        await on_progress(f"❌ Player error: {result.error}")
                    return result
                    
            except Exception as e:
                logger.exception("Player execution failed")
                return ExecutionResult(
                    content="",
                    confidence=0.0,
                    error=str(e),
                    tools_used=all_tools_used,
                )
            
            # Coach evaluates
            if self.verification_strategy:
                feedback = await self.verification_strategy.verify(task, result, context)
            else:
                # Default: assume pass with confidence based on tool success
                feedback = CoachFeedback(
                    decision=CoachDecision.PASS,
                    confidence=result.confidence,
                    summary="No verification strategy, defaulting to pass",
                )
            
            feedback_history.append(feedback)
            
            if on_progress:
                await on_progress(
                    f"📊 Coach: {feedback.decision.value} "
                    f"(confidence: {feedback.confidence:.0%})"
                )
            
            if feedback.decision == CoachDecision.PASS:
                if on_progress:
                    await on_progress(f"✅ Task completed with confidence {feedback.confidence:.0%}")
                return ExecutionResult(
                    content=result.content,
                    confidence=feedback.confidence,
                    evidence=result.evidence,
                    tools_used=all_tools_used,
                    player_iterations=coach_iter,
                )
            
            elif feedback.decision == CoachDecision.FAIL:
                if on_progress:
                    await on_progress(f"❌ Coach decided to fail: {feedback.summary}")
                return ExecutionResult(
                    content=result.content,
                    confidence=feedback.confidence,
                    evidence=result.evidence,
                    tools_used=all_tools_used,
                    player_iterations=coach_iter,
                    error=f"Coach failed: {feedback.summary}",
                )
            
            # RETRY: continue loop with feedback
            if on_progress and feedback.suggestions:
                await on_progress(f"💡 Coach suggestions: {'; '.join(feedback.suggestions[:2])}")
        
        # Max iterations reached
        last_feedback = feedback_history[-1] if feedback_history else None
        return ExecutionResult(
            content=result.content if 'result' in locals() else "",
            confidence=last_feedback.confidence if last_feedback else 0.0,
            evidence=result.evidence if 'result' in locals() else [],
            tools_used=all_tools_used,
            player_iterations=self.max_coach_iterations,
            error="Max coach iterations reached",
        )
    
    def _build_player_prompt(
        self,
        task: str,
        context: dict,
        feedback_history: list[CoachFeedback],
    ) -> str:
        """Build prompt for player, incorporating previous feedback if any."""
        prompt = f"Task: {task}"
        
        if context.get("form_path"):
            prompt += f"\nForm file: {context['form_path']}"
        if context.get("data"):
            prompt += f"\nData to use: {context['data']}"
        
        if feedback_history:
            prompt += "\n\nPrevious attempts feedback:"
            for i, fb in enumerate(feedback_history, 1):
                prompt += f"\n--- Attempt {i} ---"
                prompt += f"\nIssues: {', '.join(fb.issues) if fb.issues else 'None'}"
                prompt += f"\nSuggestions: {', '.join(fb.suggestions) if fb.suggestions else 'None'}"
            
            prompt += "\n\nPlease address the above issues and try again."
        
        return prompt
    
    async def _player_execute(
        self,
        prompt: str,
        context: dict,
        on_progress: Callable,
    ) -> ExecutionResult:
        """Execute task via the agent loop."""
        # Use agent_loop's provider and tools
        # We create a simplified message flow
        
        # Get tool definitions
        tool_defs = self.agent_loop.tools.get_definitions()
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant executing a task."},
            {"role": "user", "content": prompt},
        ]
        
        tools_used = []
        all_evidence = []
        iteration = 0
        max_iterations = self.agent_loop.max_iterations
        
        while iteration < max_iterations:
            iteration += 1
            
            response = await self.agent_loop.provider.chat(
                messages=messages,
                tools=tool_defs,
                model=self.agent_loop.model,
                temperature=self.agent_loop.temperature,
                max_tokens=self.agent_loop.max_tokens,
            )
            
            if response.has_tool_calls:
                # Execute tool calls
                tool_call_dicts = []
                for tc in response.tool_calls:
                    tools_used.append(tc.name)
                    args_str = tc.arguments
                    
                    if on_progress:
                        await on_progress(f"🔧 Tool: {tc.name}")
                    
                    result = await self.agent_loop.tools.execute(tc.name, tc.arguments)
                    all_evidence.append(f"{tc.name}: {result[:200] if isinstance(result, str) else str(result)}")
                    
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": tc.arguments,
                            }
                        }]
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": str(result)[:1000],
                    })
            else:
                # Done
                content = response.content or ""
                break
        
        # Estimate confidence based on tools used and iterations
        confidence = self._estimate_confidence(tools_used, iteration, all_evidence)
        
        return ExecutionResult(
            content=content if 'content' in locals() else "",
            confidence=confidence,
            evidence=all_evidence,
            tools_used=tools_used,
            player_iterations=iteration,
        )
    
    def _estimate_confidence(
        self,
        tools_used: list[str],
        iterations: int,
        evidence: list[str],
    ) -> float:
        """Estimate confidence based on execution metrics."""
        # Base confidence
        confidence = 0.5
        
        # More tools = more thorough execution
        if len(tools_used) >= 3:
            confidence += 0.2
        elif len(tools_used) >= 1:
            confidence += 0.1
        
        # Fewer iterations is better (efficient)
        if iterations <= 3:
            confidence += 0.2
        elif iterations > 10:
            confidence -= 0.1
        
        # Evidence present
        if evidence:
            confidence += 0.1
        
        return min(1.0, max(0.0, confidence))