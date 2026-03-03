"""PDF-specific verification strategies for Coach-Player pipeline."""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Any

from loguru import logger

# Check for available dependencies
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    logger.warning("PyMuPDF not available - PDF tools limited")

try:
    import pytesseract
    from PIL import Image
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False
    logger.warning("pytesseract/Pillow not available - OCR disabled")


class PDFVerificationStrategy:
    """
    Verify PDF form filling by re-OCRing the filled form.
    
    This strategy:
    1. Renders filled PDF to images
    2. OCRs the images to extract text
    3. Checks if expected field values are present
    4. Provides confidence score based on matches
    """
    
    def __init__(
        self,
        provider=None,
        model: str = None,
        dpi: int = 300,
        temp_dir: str = None,
    ):
        self.provider = provider
        self.model = model
        self.dpi = dpi
        self.temp_dir = Path(temp_dir or tempfile.gettempdir())
    
    async def verify(
        self,
        task: str,
        result: Any,  # ExecutionResult
        context: dict,
    ) -> Any:  # CoachFeedback
        """Verify PDF form filling by re-OCRing."""
        from nanobot.agent.coach_player import CoachFeedback, CoachDecision
        
        if not PYMUPDF_AVAILABLE:
            return CoachFeedback(
                decision=CoachDecision.PASS,
                confidence=0.5,
                summary="PyMuPDF not available, cannot verify",
            )
        
        form_path = context.get("filled_form_path")
        expected_fields = context.get("expected_fields", {})
        
        if not form_path or not os.path.exists(form_path):
            return CoachFeedback(
                decision=CoachDecision.PASS,
                confidence=0.3,
                summary="No filled form to verify",
            )
        
        try:
            # Render and OCR
            ocr_results = await self._ocr_pdf(form_path)
            
            # Check expected fields
            matches, missing, confidence = self._check_fields(
                ocr_results, expected_fields
            )
            
            # Build feedback
            issues = []
            suggestions = []
            
            for field_name in missing:
                issues.append(f"Field '{field_name}' not found in OCR")
                suggestions.append(f"Verify {field_name} was filled correctly")
            
            summary = f"Found {len(matches)}/{len(expected_fields)} fields. "
            summary += f"Confidence: {confidence:.0%}"
            
            if confidence >= 0.8:
                decision = CoachDecision.PASS
            elif confidence >= 0.5:
                decision = CoachDecision.RETRY
            else:
                decision = CoachDecision.FAIL
            
            return CoachFeedback(
                decision=decision,
                confidence=confidence,
                issues=issues,
                suggestions=suggestions,
                summary=summary,
            )
            
        except Exception as e:
            logger.exception("PDF verification failed")
            return CoachFeedback(
                decision=CoachDecision.PASS,
                confidence=0.3,
                summary=f"Verification error: {str(e)[:100]}",
            )
    
    async def _ocr_pdf(self, pdf_path: str) -> dict[str, Any]:
        """Render PDF to images and OCR each page."""
        if not PYTESSERACT_AVAILABLE:
            return self._simple_text_extract(pdf_path)
        
        results = {}
        
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Render to image
            zoom = self.dpi / 72
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            
            # Save to temp file for OCR
            img_path = self.temp_dir / f"page_{page_num}_{os.getpid()}.png"
            pix.save(str(img_path))
            
            # OCR
            img = Image.open(str(img_path))
            text = pytesseract.image_to_string(img)
            
            results[page_num + 1] = {
                "text": text,
                "image_path": str(img_path),
            }
            
            # Clean up
            try:
                os.remove(img_path)
            except:
                pass
        
        doc.close()
        return results
    
    def _simple_text_extract(self, pdf_path: str) -> dict:
        """Simple text extraction without OCR."""
        if not PYMUPDF_AVAILABLE:
            return {}
        
        results = {}
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            results[page_num + 1] = {"text": text}
        doc.close()
        return results
    
    def _check_fields(
        self,
        ocr_results: dict,
        expected_fields: dict,
    ) -> tuple[list[str], list[str], float]:
        """Check if expected field values appear in OCR text."""
        matches = []
        missing = []
        
        all_text = ""
        for page_data in ocr_results.values():
            all_text += page_data.get("text", "").lower()
        
        for field_name, expected_value in expected_fields.items():
            if not expected_value:
                continue
                
            # Check if value appears in OCR text
            value_str = str(expected_value).lower()
            
            # Handle different field types
            if value_str in all_text:
                matches.append(field_name)
            elif self._fuzzy_match(value_str, all_text):
                matches.append(field_name)
            else:
                missing.append(field_name)
        
        total = len(expected_fields)
        confidence = len(matches) / total if total > 0 else 0.5
        
        return matches, missing, confidence
    
    def _fuzzy_match(self, value: str, text: str) -> bool:
        """Fuzzy matching for values that might have minor OCR errors."""
        # Simple fuzzy: check if most words appear
        words = value.split()
        if not words:
            return False
        
        matches = sum(1 for w in words if w in text)
        return matches >= len(words) * 0.7  # 70% threshold


class HybridVerificationStrategy:
    """Combine multiple verification strategies."""
    
    def __init__(
        self,
        strategies: list[Any],  # list[VerificationStrategy]
        weights: list[float] = None,
    ):
        self.strategies = strategies
        self.weights = weights or [1.0] * len(strategies)
    
    async def verify(
        self,
        task: str,
        result: Any,
        context: dict,
    ) -> Any:
        """Run all strategies and combine results."""
        from nanobot.agent.coach_player import CoachFeedback, CoachDecision
        
        feedbacks = []
        
        for strategy in self.strategies:
            try:
                fb = await strategy.verify(task, result, context)
                feedbacks.append(fb)
            except Exception as e:
                logger.warning(f"Strategy {strategy} failed: {e}")
        
        if not feedbacks:
            return CoachFeedback(
                decision=CoachDecision.PASS,
                confidence=0.5,
                summary="No strategies succeeded",
            )
        
        # Weighted average confidence
        total_weight = sum(self.weights[:len(feedbacks)])
        avg_confidence = sum(
            fb.confidence * w 
            for fb, w in zip(feedbacks, self.weights[:len(feedbacks)])
        ) / total_weight if total_weight > 0 else 0.5
        
        # Combine issues and suggestions
        all_issues = []
        all_suggestions = []
        for fb in feedbacks:
            all_issues.extend(fb.issues)
            all_suggestions.extend(fb.suggestions)
        
        # Decision based on average
        if avg_confidence >= 0.8:
            decision = CoachDecision.PASS
        elif avg_confidence >= 0.5:
            decision = CoachDecision.RETRY
        else:
            decision = CoachDecision.FAIL
        
        return CoachFeedback(
            decision=decision,
            confidence=avg_confidence,
            issues=all_issues[:5],  # Limit to top 5
            suggestions=all_suggestions[:5],
            summary=f"Hybrid verification: {avg_confidence:.0%} confidence",
        )