#!/usr/bin/env python3
"""
Compliant Restaurant Lead-Gen Bot — entry point.
Run: python lead_gen_bot.py
Logic lives in the lead_gen/ package.
"""

# Re-export for backward compatibility: from lead_gen_bot import run_pipeline
from lead_gen.pipeline import run_pipeline, main

if __name__ == "__main__":
    main()
