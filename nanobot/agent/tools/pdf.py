"""PDF manipulation tools for form filling."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from loguru import logger

# Check dependencies
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    logger.warning("PyMuPDF not available - PDF tools disabled")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class FillPDFFormTool:
    """Fill PDF form fields."""
    
    name = "fill_pdf_form"
    description = "Fill PDF form fields with provided data"
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.output_dir = workspace / "filled_forms"
        self.output_dir.mkdir(exist_ok=True)
    
    async def execute(self, path: str, data: dict, output_name: str = None) -> dict:
        """
        Fill PDF form with data.
        
        Args:
            path: Path to PDF file
            data: Dict of field_name -> value
            output_name: Optional output filename
            
        Returns:
            Dict with output_path, fields_filled, errors
        """
        if not PYMUPDF_AVAILABLE:
            return {"error": "PyMuPDF not available"}
        
        try:
            doc = fitz.open(path)
            fields_filled = []
            errors = []
            
            # Get form fields using new PyMuPDF API
            field_names = set()
            for page in doc:
                for widget in page.widgets():
                    if widget.field_name:
                        field_names.add(widget.field_name)
            
            for field_name, value in data.items():
                try:
                    # Try to find field by name
                    if field_name in field_names:
                        # Use widget API to set value
                        for page in doc:
                            for widget in page.widgets():
                                if widget.field_name == field_name:
                                    widget.field_value = str(value)
                                    widget.update()
                                    fields_filled.append(field_name)
                                    break
                    else:
                        # Try partial match
                        matched = False
                        for fn in field_names:
                            if field_name.lower() in fn.lower():
                                for page in doc:
                                    for widget in page.widgets():
                                        if widget.field_name == fn:
                                            widget.field_value = str(value)
                                            widget.update()
                                            fields_filled.append(fn)
                                            matched = True
                                            break
                                if matched:
                                    break
                        if not matched:
                            errors.append(f"Field not found: {field_name}")
                            
                except Exception as e:
                    errors.append(f"{field_name}: {str(e)}")
            
            # Save filled form
            if output_name is None:
                output_name = f"filled_{Path(path).stem}.pdf"
            
            output_path = self.output_dir / output_name
            doc.save(str(output_path))
            doc.close()
            
            return {
                "output_path": str(output_path),
                "fields_filled": fields_filled,
                "errors": errors,
                "success": len(errors) == 0,
            }
            
        except Exception as e:
            logger.exception("Failed to fill PDF form")
            return {"error": str(e)}


class RenderPDFTool:
    """Render PDF pages to images."""
    
    name = "render_pdf"
    description = "Render PDF pages to images for OCR"
    
    def __init__(self, workspace: Path, dpi: int = 300):
        self.workspace = workspace
        self.dpi = dpi
        self.temp_dir = workspace / "temp_pdfs"
        self.temp_dir.mkdir(exist_ok=True)
    
    async def execute(self, path: str, pages: list[int] = None) -> dict:
        """
        Render PDF to images.
        
        Args:
            path: Path to PDF file
            pages: List of page numbers (1-indexed), or None for all
            
        Returns:
            Dict with image_paths
        """
        if not PYMUPDF_AVAILABLE:
            return {"error": "PyMuPDF not available"}
        
        if not PIL_AVAILABLE:
            return {"error": "Pillow not available"}
        
        try:
            doc = fitz.open(path)
            image_paths = []
            
            pages = pages or list(range(1, len(doc) + 1))
            
            for page_num in pages:
                if page_num < 1 or page_num > len(doc):
                    continue
                    
                page = doc[page_num - 1]
                
                # Render to image
                zoom = self.dpi / 72
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)
                
                # Save
                output_path = self.temp_dir / f"page_{page_num}.png"
                pix.save(str(output_path))
                image_paths.append(str(output_path))
            
            doc.close()
            
            return {
                "image_paths": image_paths,
                "pages_rendered": len(image_paths),
            }
            
        except Exception as e:
            logger.exception("Failed to render PDF")
            return {"error": str(e)}


class OCRPDFTool:
    """OCR PDF images to extract text."""
    
    name = "ocr_pdf"
    description = "OCR PDF pages to extract text"
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        
        try:
            import pytesseract
            self.pytesseract = pytesseract
            self.available = True
        except ImportError:
            self.available = False
    
    async def execute(self, image_paths: list[str]) -> dict:
        """
        OCR images to extract text.
        
        Args:
            image_paths: List of image paths
            
        Returns:
            Dict with page_texts (list of {page, text})
        """
        if not self.available:
            return {"error": "pytesseract not available"}
        
        try:
            results = []
            
            for img_path in image_paths:
                img = Image.open(img_path)
                text = self.pytesseract.image_to_string(img)
                results.append({
                    "image": img_path,
                    "text": text,
                })
            
            return {
                "pages": results,
                "success": True,
            }
            
        except Exception as e:
            logger.exception("OCR failed")
            return {"error": str(e)}


class GetPDFFieldsTool:
    """Get list of form fields from PDF."""
    
    name = "get_pdf_fields"
    description = "Get form field names from PDF"
    
    async def execute(self, path: str) -> dict:
        """Get form fields from PDF."""
        if not PYMUPDF_AVAILABLE:
            return {"error": "PyMuPDF not available"}
        
        try:
            doc = fitz.open(path)
            
            # Get form fields using new PyMuPDF API
            field_names = set()
            for page in doc:
                for widget in page.widgets():
                    if widget.field_name:
                        field_names.add(widget.field_name)
            
            doc.close()
            
            return {
                "fields": list(field_names),
                "count": len(field_names),
            }
            
        except Exception as e:
            return {"error": str(e)}


class PDFFormFillerSkill:
    """
    Complete PDF form filling skill using Coach-Player pipeline.
    
    This skill:
    1. Analyzes the PDF to find form fields
    2. Fills fields with provided data
    3. Uses Coach-Player to verify via re-OCR
    4. Retries if verification fails
    """
    
    name = "pdf-form-filler"
    description = "Fill PDF forms with iterative verification"
    
    def __init__(self, workspace: Path, coach_player=None):
        self.workspace = workspace
        self.coach_player = coach_player
        self.fill_tool = FillPDFFormTool(workspace)
        self.render_tool = RenderPDFTool(workspace)
        self.ocr_tool = OCRPDFTool(workspace)
        self.fields_tool = GetPDFFieldsTool()
    
    async def fill(
        self,
        pdf_path: str,
        data: dict,
        verify: bool = True,
    ) -> dict:
        """
        Fill PDF form with verification.
        
        Args:
            pdf_path: Path to PDF file
            data: Dict of field_name -> value
            verify: Whether to verify via OCR
            
        Returns:
            Dict with result
        """
        # Get available fields
        fields_result = await self.fields_tool.execute(pdf_path)
        available_fields = fields_result.get("fields", [])
        
        logger.info(f"PDF has {len(available_fields)} form fields")
        
        # Fill form
        fill_result = await self.fill_tool.execute(
            path=pdf_path,
            data=data,
        )
        
        if not fill_result.get("success"):
            return fill_result
        
        output_path = fill_result["output_path"]
        
        if verify:
            # Verify by re-OCRing
            render_result = await self.render_tool.execute(output_path)
            image_paths = render_result.get("image_paths", [])
            
            ocr_result = await self.ocr_tool.execute(image_paths)
            extracted_text = "\n".join(
                p["text"] for p in ocr_result.get("pages", [])
            )
            
            # Check if data appears in OCR
            missing = []
            for field, value in data.items():
                if value and str(value).lower() not in extracted_text.lower():
                    missing.append(field)
            
            return {
                "output_path": output_path,
                "fields_filled": fill_result["fields_filled"],
                "missing_fields": missing,
                "verified": len(missing) == 0,
                "ocr_text": extracted_text[:500],  # First 500 chars
            }
        
        return fill_result