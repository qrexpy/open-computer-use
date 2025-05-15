#!/usr/bin/env python3
"""
Quick fix for the "Port 6080 Connection Refused" error in Open Computer Use.
This script takes a sandbox ID as input and attempts to fix the VNC connection.
"""

import sys
import os
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure E2B
if not os.getenv("E2B_API_KEY"):
    print("ERROR: E2B_API_KEY environment variable not set")
    sys.exit(1)

os.environ["E2B_API_KEY"] = os.getenv("E2B_API_KEY")

def print_usage():
    print("Usage: python fix_port_6080.py <sandbox_id>")
    print("Example: python fix_port_6080.py inqe6qn2vxy2p8m838i21")
    print("\nOr run without arguments to use the sandbox ID from .env.sandbox file")

def main():
    # Check if sandbox ID was provided
    if len(sys.argv) > 1:
        sandbox_id = sys.argv[1]
    else:
        # Try to read from .env.sandbox file
        try:
            with open(".env.sandbox", "r") as f:
                for line in f:
                    if line.startswith("SANDBOX_ID="):
                        sandbox_id = line.strip().split("=")[1]
                        break
                else:
                    print("No SANDBOX_ID found in .env.sandbox file")
                    print_usage()
                    sys.exit(1)
        except FileNotFoundError:
            print("No .env.sandbox file found and no sandbox ID provided")
            print_usage()
            sys.exit(1)
    
    print(f"Attempting to fix VNC connection for sandbox {sandbox_id}")
    
    # Import here to avoid circular imports
    try:
        from os_computer_use.streaming import Sandbox
    except ImportError:
        print("Error: Could not import Sandbox class. Make sure you're in the project directory.")
        sys.exit(1)
    
    # Create a new sandbox with the given ID
    sandbox = Sandbox()
    sandbox.id = sandbox_id
    
    print("Checking VNC server status...")
    
    # Check if VNC processes are running
    try:
        result = sandbox.commands.run("ps aux | grep -v grep | grep -E 'vnc|VNC'", timeout=5)
        if result.stdout:
            print("VNC processes found:")
            print(result.stdout.strip())
        else:
            print("No VNC processes found")
    except Exception as e:
        print(f"Error checking VNC processes: {e}")
    
    # Check if port 6080 is listening
    try:
        result = sandbox.commands.run("netstat -tuln | grep 6080", timeout=5)
        if result.stdout:
            print("Port 6080 is listening:")
            print(result.stdout.strip())
            print("VNC server appears to be working correctly!")
            return
        else:
            print("Port 6080 is NOT listening")
    except Exception as e:
        print(f"Error checking port 6080: {e}")
    
    # Try to fix the issue
    print("\nAttempting to fix VNC server...")
    
    # Kill any existing VNC processes
    try:
        sandbox.commands.run("pkill -f 'x11vnc|Xtightvnc' || true", timeout=5)
        print("Stopped any existing VNC processes")
    except Exception as e:
        print(f"Error stopping VNC processes: {e}")
    
    # Wait a moment
    time.sleep(2)
    
    # Try to restart VNC through the stream API
    try:
        print("Starting VNC server through E2B stream API...")
        sandbox.stream.start()
        print("VNC server started")
    except Exception as e:
        print(f"Error starting VNC server through E2B: {e}")
    
    # Wait for initialization
    print("Waiting for VNC server to initialize...")
    time.sleep(5)
    
    # Check if port 6080 is now listening
    try:
        result = sandbox.commands.run("netstat -tuln | grep 6080", timeout=5)
        if result.stdout:
            print("Port 6080 is now listening:")
            print(result.stdout.strip())
            print("VNC server fix was successful!")
            
            # Get and display the VNC URL
            try:
                vnc_url = sandbox.stream.get_url()
                print(f"\nVNC URL: {vnc_url}")
                print("\nYou can now open this URL in your browser to connect to the VNC server.")
            except Exception as e:
                print(f"Error getting VNC URL: {e}")
                
            return
        else:
            print("Port 6080 is still NOT listening")
    except Exception as e:
        print(f"Error checking port 6080: {e}")
    
    # If still not working, try manual approach
    print("\nTrying manual VNC server start...")
    try:
        sandbox.commands.run("x11vnc -display :0 -forever -nopw -quiet", background=True, timeout=5)
        print("Started x11vnc manually")
    except Exception as e:
        print(f"Error starting x11vnc manually: {e}")
    
    # Wait a moment
    time.sleep(3)
    
    # Check if port 6080 is now listening
    try:
        result = sandbox.commands.run("netstat -tuln | grep 6080", timeout=5)
        if result.stdout:
            print("Port 6080 is now listening after manual start:")
            print(result.stdout.strip())
            print("VNC server fix was successful!")
            
            # Get and display the VNC URL
            try:
                vnc_url = sandbox.stream.get_url()
                print(f"\nVNC URL: {vnc_url}")
                print("\nYou can now open this URL in your browser to connect to the VNC server.")
            except Exception as e:
                print(f"Error getting VNC URL: {e}")
                
            return
        else:
            print("Port 6080 is still NOT listening after manual attempt")
            print("Unable to fix VNC server connection")
    except Exception as e:
        print(f"Error checking port 6080: {e}")

if __name__ == "__main__":
    main()
