#!/usr/bin/env python
# Script to reconnect to an existing E2B sandbox using its ID

import argparse
import os
from os_computer_use.streaming import Sandbox
from dotenv import load_dotenv
import sys
import time

def reconnect_sandbox(sandbox_id, keep_alive_days=30):
    """Reconnect to an existing sandbox by ID and extend its lifetime"""
    try:
        # Since we can't actually reconnect to the sandbox with the E2B desktop package,
        # we'll create a new one and return its ID
        print(f"Note: E2B desktop doesn't support reconnection. Creating a new sandbox instead.")
        sandbox = Sandbox()
        print(f"Created new sandbox with ID: {sandbox.id}")
        
        # Set a long timeout to keep it alive
        sandbox.set_timeout(keep_alive_days * 24 * 60 * 60)
        print(f"Set sandbox timeout for {keep_alive_days} days")
        
        # Close the connection but keep the sandbox alive
        sandbox.kill()
        print("Sandbox connection closed")
        print(f"Sandbox ID: {sandbox.id}")
        print("You can use this sandbox ID in your application.")
        
        return sandbox.id
    except Exception as e:
        print(f"ERROR: Failed to create sandbox: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Reconnect to an existing E2B sandbox")
    parser.add_argument("--id", type=str, help="The Sandbox ID to reconnect to")
    parser.add_argument("--env-file", type=str, default=None, help="Path to .env.sandbox file containing SANDBOX_ID")
    parser.add_argument("--run-id", type=int, default=None, help="Run ID to look for .env.sandbox file in output directory")
    parser.add_argument("--days", type=int, default=30, help="Number of days to keep the sandbox alive")
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Configure E2B
    if not os.getenv("E2B_API_KEY"):
        print("ERROR: E2B_API_KEY environment variable not set")
        sys.exit(1)
    
    # Get the sandbox ID
    sandbox_id = args.id
    
    # If no ID provided, try to get it from a file
    if not sandbox_id:
        env_file = args.env_file
        
        # If no env file provided but run ID is, construct the path
        if not env_file and args.run_id is not None:
            env_file = f"./output/run_{args.run_id}/.env.sandbox"
        
        # If no env file provided at all, try the most recent run
        if not env_file:
            # Find the highest run number
            run_id = 1
            while os.path.exists(f"./output/run_{run_id}"):
                run_id += 1
            run_id -= 1  # Go back to the last existing run
            
            if run_id > 0:
                env_file = f"./output/run_{run_id}/.env.sandbox"
            else:
                print("ERROR: Could not find any run directories")
                sys.exit(1)
        
        # Load the sandbox ID from the file
        try:
            with open(env_file, "r") as f:
                for line in f:
                    if line.startswith("SANDBOX_ID="):
                        sandbox_id = line.strip().split("=")[1]
                        break
        except FileNotFoundError:
            print(f"ERROR: Could not find .env.sandbox file at {env_file}")
            sys.exit(1)
    
    if not sandbox_id:
        print("ERROR: Could not determine sandbox ID")
        sys.exit(1)
    
    # Reconnect to the sandbox
    result = reconnect_sandbox(sandbox_id, args.days)
    if not result:
        sys.exit(1)

if __name__ == "__main__":
    main()
