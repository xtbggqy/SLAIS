# This file makes the 'slais' directory a Python package.
# It should be kept minimal and not contain re-exports of agent classes,
# as agents are now in a separate top-level 'agents' package.

# Example of what NOT to have here:
# from ..agents.pdf_parsing_agent import PDFParsingAgent # Incorrect path after refactor
# from agents import PDFParsingAgent # This would be a re-export, avoid for clean separation
