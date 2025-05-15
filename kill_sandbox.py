#!/usr/bin/env python3
"""
Kill an E2B sandbox by ID.
Usage: python kill_sandbox.py <sandbox_id>
"""
import sys
import os
from dotenv import load_dotenv

if len(sys.argv) != 2:
    print("Usage: python kill_sandbox.py <sandbox_id>")
    sys.exit(1)

sandbox_id = sys.argv[1]

# Load environment variables
load_dotenv()

try:
    from e2b_code_interpreter import Sandbox
except ImportError:
    print("e2b_code_interpreter not installed. Please install it first.")
    sys.exit(1)

api_key = os.getenv("E2B_API_KEY")
if not api_key:
    print("ERROR: E2B_API_KEY environment variable not set. Please set it in your .env file or environment.")
    sys.exit(1)
os.environ["E2B_API_KEY"] = api_key

try:
    sandbox = Sandbox(id=sandbox_id)
    print(f"Killing sandbox {sandbox_id}...")
    sandbox.kill()
    print("Sandbox killed.")
except Exception as e:
    print(f"Error killing sandbox: {e}")
    sys.exit(1)
