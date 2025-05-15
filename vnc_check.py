#!/usr/bin/env python
# Utility to verify and fix VNC connections for the Open Computer Use project

import argparse
import os
import sys
import time
import subprocess
import requests
from dotenv import load_dotenv
from os_computer_use.streaming import Sandbox

def check_vnc_connectivity(url, timeout=5):
    """Check if VNC URL is accessible"""
    try:
        response = requests.head(url, timeout=timeout)
        if response.status_code < 400:
            return True, f"VNC URL is accessible (status code: {response.status_code})"
        else:
            return False, f"VNC URL returned error status code: {response.status_code}"
    except requests.exceptions.RequestException as e:
        return False, f"Error accessing VNC URL: {e}"

def test_sandbox_vnc(sandbox):
    """Test VNC functionality on a sandbox"""
    print("Testing VNC server setup...")
    
    # Check if VNC server is running in the sandbox
    try:
        result = sandbox.commands.run("ps aux | grep -v grep | grep -E 'vnc|VNC'", timeout=5)
        if result.stdout:
            print("✓ VNC server process is running:")
            print(result.stdout.strip())
        else:
            print("✗ No VNC server process found")
            return False
    except Exception as e:
        print(f"✗ Error checking VNC process: {e}")
        return False
    
    # Check if port 6080 is actually listening
    try:
        port_result = sandbox.commands.run("netstat -tuln | grep 6080", timeout=5)
        if port_result.stdout:
            print("✓ Port 6080 is open and listening:")
            print(port_result.stdout.strip())
        else:
            print("✗ Port 6080 is not listening!")
            return False
    except Exception as e:
        print(f"✗ Error checking port 6080: {e}")
        # Not a fatal error
    
    # Test VNC URL
    try:
        vnc_url = sandbox.stream.get_url()
        print(f"VNC URL: {vnc_url}")
        
        success, message = check_vnc_connectivity(vnc_url)
        if success:
            print(f"✓ {message}")
        else:
            print(f"✗ {message}")
            return False
    except Exception as e:
        print(f"✗ Error getting VNC URL: {e}")
        return False
    
    print("✓ VNC connectivity test passed")
    return True

def restart_vnc_server(sandbox):
    """Restart the VNC server in the sandbox"""
    print("Restarting VNC server...")
    
    try:
        # Stop any existing VNC processes
        sandbox.commands.run("pkill -f 'x11vnc|Xtightvnc' || true", timeout=5)
        print("✓ Stopped existing VNC processes")
        
        # Wait a moment
        time.sleep(2)
        
        # Start the VNC server
        print("Starting new VNC server...")
        sandbox.stream.start()
        
        # Allow time for initialization
        print("Waiting for VNC server to initialize...")
        time.sleep(5)
        
        # Check if VNC is running
        result = sandbox.commands.run("ps aux | grep -v grep | grep -E 'vnc|VNC'", timeout=5)
        if result.stdout:
            print("✓ VNC server process started:")
            print(result.stdout.strip())
            
            # Verify port 6080 is actually listening
            port_result = sandbox.commands.run("netstat -tuln | grep 6080", timeout=5)
            if port_result.stdout:
                print("✓ Port 6080 is open and listening:")
                print(port_result.stdout.strip())
            else:
                print("✗ Port 6080 is not listening!")
                # Try to manually start VNC server
                print("Attempting to manually start VNC server...")
                sandbox.commands.run("x11vnc -display :0 -forever -nopw -quiet", background=True, timeout=5)
                time.sleep(3)
                
                # Check again
                port_result = sandbox.commands.run("netstat -tuln | grep 6080", timeout=5)
                if port_result.stdout:
                    print("✓ Port 6080 is now listening after manual start")
                else:
                    print("✗ Failed to get port 6080 listening")
            
            # Get the URL
            vnc_url = sandbox.stream.get_url()
            print(f"New VNC URL: {vnc_url}")
            return True
        else:
            print("✗ Failed to start VNC server")
            return False
    except Exception as e:
        print(f"✗ Error restarting VNC server: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Check and fix VNC connectivity")
    parser.add_argument("--sandbox-id", type=str, help="Specific sandbox ID to check")
    parser.add_argument("--restart", action="store_true", help="Restart VNC server if not working")
    parser.add_argument("--registry", type=str, default="sandbox_registry.json", 
                        help="Registry file with sandbox IDs")
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Configure E2B
    if not os.getenv("E2B_API_KEY"):
        print("ERROR: E2B_API_KEY environment variable not set")
        sys.exit(1)
    
    sandbox = None
    
    try:
        if args.sandbox_id:
            print(f"Connecting to sandbox {args.sandbox_id}...")
            try:
                sandbox = Sandbox()
                sandbox.id = args.sandbox_id
            except Exception as e:
                print(f"Error connecting to sandbox {args.sandbox_id}: {e}")
                sys.exit(1)
            
            # Test VNC connectivity
            vnc_working = test_sandbox_vnc(sandbox)
            
            # Restart VNC if needed and requested
            if not vnc_working and args.restart:
                print("VNC not working. Attempting to restart...")
                restart_vnc_server(sandbox)
                
                # Test again after restart
                print("Testing VNC after restart...")
                vnc_working = test_sandbox_vnc(sandbox)
                
                if vnc_working:
                    print("✓ VNC server successfully restarted")
                else:
                    print("✗ VNC server still not working after restart")
        else:
            print("No sandbox ID specified. Creating a new sandbox...")
            sandbox = Sandbox()
            sandbox_id = sandbox.id
            print(f"Created new sandbox with ID: {sandbox_id}")
            
            # Test VNC connectivity
            vnc_working = test_sandbox_vnc(sandbox)
            
            if vnc_working:
                print(f"✓ New sandbox {sandbox_id} has working VNC")
            else:
                print(f"✗ New sandbox {sandbox_id} has VNC issues")
                
                if args.restart:
                    print("Attempting to restart VNC...")
                    restart_vnc_server(sandbox)
                    
                    # Test again after restart
                    print("Testing VNC after restart...")
                    vnc_working = test_sandbox_vnc(sandbox)
                    
                    if vnc_working:
                        print("✓ VNC server successfully restarted")
                    else:
                        print("✗ VNC server still not working after restart")
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if sandbox and not args.sandbox_id:
            print("Cleaning up sandbox...")
            sandbox.kill()

if __name__ == "__main__":
    main()
