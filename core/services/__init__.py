"""Core services — pure DB / business-logic helpers shared by handlers.

Per ADR-0001, services must NOT import from `markets/*`. Handler layer
bridges core ↔ markets when needed.
"""
