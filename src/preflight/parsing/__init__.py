"""
Preflight document parsing module.

Parses PDF, DOCX, PPTX, XLSX, and ArchiMate XML into structured
Markdown chunks ready for the embedding pipeline.

Architecture (from ARCHITECTURE.md):
  Workhorse: MarkItDown + PyMuPDF (self-hosted, all file types)
  Smart:     LlamaParse (AI-powered, for complex vendor contracts)
  Fallback:  Each parser can fail, the chain continues

No document silently fails. If every tool fails:
  "⚠ This document could not be parsed. Please provide the content in another format."
"""
