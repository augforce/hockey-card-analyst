"""PDF report rendering for engine results.

Pure presentation layer: takes the engine's structured output (model or
dict), renders HTML from templates styled with the module's own design
tokens, and converts to PDF locally via WeasyPrint. No vision, no network,
no LLM.
"""
from reports.render import REPORT_KINDS, render_html, render_pdf

__all__ = ["REPORT_KINDS", "render_html", "render_pdf"]
