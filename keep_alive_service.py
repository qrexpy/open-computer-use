#!/usr/bin/env python
# Script to periodically keep an E2B sandbox alive

import argparse
import os
import time
import sys
import json
import datetime
from dotenv import load_dotenv
from os_computer_use.streaming import Sandbox

def save_sandbox_info(sandboxes, file_path="sandbox_registry.json"):
    """Save sandbox information to a file for persistence"""
    data = {
        "last_updated": datetime.datetime.now().isoformat(),
        "sandboxes": [
            {"id": sandbox_id, "created": datetime.datetime.now().isoformat()}
            for sandbox_id in sandboxes
        ]
    }
    
    try:
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Saved sandbox information to {file_path}")
    except Exception as e:
        print(f"Error saving sandbox information: {e}")

def load_sandbox_info(file_path="sandbox_registry.json"):
    """Load sandbox information from a file"""
    if not os.path.exists(file_path):
        return []
    
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
        return [sandbox["id"] for sandbox in data.get("sandboxes", [])]
    except Exception as e:
        print(f"Error loading sandbox information: {e}")
        return []

def main():
    parser = argparse.ArgumentParser(description="Keep a series of E2B sandboxes alive indefinitely")
    parser.add_argument("--interval", type=int, default=12, help="Hours between sandbox refreshes")
    parser.add_argument("--days", type=int, default=30, help="Number of days to keep each sandbox alive")
    parser.add_argument("--count", type=int, default=1, help="Number of sandboxes to maintain")
    parser.add_argument("--check-interval", type=int, default=15, help="Minutes between connection checks")
    parser.add_argument("--registry", type=str, default="sandbox_registry.json", help="File to store sandbox information")
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Configure E2B
    if not os.getenv("E2B_API_KEY"):
        print("ERROR: E2B_API_KEY environment variable not set")
        sys.exit(1)
    
    # Load existing sandbox IDs from registry
    sandboxes = load_sandbox_info(args.registry)
    print(f"Loaded {len(sandboxes)} sandbox IDs from registry")
    
    # Active sandbox objects
    active_sandboxes = {}
    
    print(f"Starting keep-alive service for {args.count} sandboxes")
    print(f"Creating a new sandbox every {args.interval} hours")
    print(f"Checking connections every {args.check_interval} minutes")
    print("Press Ctrl+C to stop")
    
    try:
        refresh_count = 0
        while True:
            refresh_count += 1
            
            # Create a new sandbox if we don't have enough
            while len(sandboxes) < args.count:
                try:
                    print(f"Creating new sandbox ({len(sandboxes)+1}/{args.count})...")
                    sandbox = Sandbox()
                    sandbox_id = sandbox.id
                    sandboxes.append(sandbox_id)
                    active_sandboxes[sandbox_id] = sandbox
                    
                    print(f"Created sandbox with ID: {sandbox_id}")
                    
                    # Set timeout but don't kill it
                    sandbox.set_timeout(args.days * 24 * 60 * 60)
                    
                    # Test that the connection works
                    result = sandbox.commands.run("echo 'Connection test successful'", timeout=5)
                    if result and result.stdout:
                        print(f"Sandbox connection test: {result.stdout.strip()}")
                    
                    # Save updated sandbox information
                    save_sandbox_info(sandboxes, args.registry)
                    
                except Exception as e:
                    print(f"Error creating sandbox: {e}")
                    time.sleep(60)  # Wait a bit before retrying
            
            print(f"[{refresh_count}] Currently maintaining {len(sandboxes)} sandboxes")
            
            # Check all sandbox connections
            for sandbox_id in list(sandboxes):
                try:
                    # Get or create sandbox object
                    if sandbox_id not in active_sandboxes:
                        try:
                            # This will attempt to reconnect to an existing sandbox
                            # but will fail if the sandbox no longer exists
                            sandbox = Sandbox()
                            sandbox.id = sandbox_id
                            active_sandboxes[sandbox_id] = sandbox
                        except Exception as e:
                            print(f"Error reconnecting to sandbox {sandbox_id}: {e}")
                            sandboxes.remove(sandbox_id)
                            continue
                    
                    sandbox = active_sandboxes[sandbox_id]
                    
                    # Check connection and refresh timeout
                    try:
                        sandbox.set_timeout(args.days * 24 * 60 * 60)
                        result = sandbox.commands.run("echo 'keep-alive'", timeout=5)
                        if result and "keep-alive" in result.stdout:
                            print(f"Sandbox {sandbox_id} is responsive")
                        else:
                            print(f"Sandbox {sandbox_id} did not respond correctly")
                    except Exception as e:
                        print(f"Error communicating with sandbox {sandbox_id}: {e}")
                        sandboxes.remove(sandbox_id)
                        del active_sandboxes[sandbox_id]
                except Exception as e:
                    print(f"Error checking sandbox {sandbox_id}: {e}")
            
            # Save updated sandbox information
            save_sandbox_info(sandboxes, args.registry)
            
            # Save updated sandbox information
            save_sandbox_info(sandboxes, args.registry)
            
            # Sleep until next check interval
            next_check = time.time() + (args.check_interval * 60)
            next_check_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(next_check))
            print(f"Next connection check at {next_check_str}")
            
            time.sleep(args.check_interval * 60)
                
    except KeyboardInterrupt:
        print("\nKeep-alive service stopped.")
        print("Saving sandbox registry before exit...")
        save_sandbox_info(sandboxes, args.registry)
    except Exception as e:
        print(f"ERROR: Keep-alive service failed: {e}")
        # Save sandbox registry before exit
        save_sandbox_info(sandboxes, args.registry)
        sys.exit(1)

if __name__ == "__main__":
    main()
