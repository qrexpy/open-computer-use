from os_computer_use.streaming import Sandbox, DisplayClient
# Use custom browser implementation instead of the default one
from os_computer_use.custom_browser import Browser
from os_computer_use.sandbox_agent import SandboxAgent
from os_computer_use.logging import Logger
import asyncio
import argparse
import webbrowser
import urllib.parse
import time

import os
from dotenv import load_dotenv

logger = Logger()

# Load environment variables from .env file
load_dotenv()

# Configure E2B
os.environ["E2B_API_KEY"] = os.getenv("E2B_API_KEY")


async def start(user_input=None, output_dir=None, use_proxy=False, proxy_port=8899):
    sandbox = None
    client = None
    browser = None
    
    try:
        # Create a sandbox with a longer initial timeout
        print("Starting the sandbox...")
        sandbox = Sandbox()
        sandbox.set_timeout(300)  # 5 minutes initial timeout
        
        # Save the sandbox ID for potential reconnection
        sandbox_id = sandbox.id
        print(f"Sandbox ID: {sandbox_id}")
        
        # Create a .env.sandbox file to store the sandbox ID for potential manual reconnection
        with open(f"{output_dir}/.env.sandbox", "w") as f:
            f.write(f"SANDBOX_ID={sandbox_id}\n")
        print(f"Sandbox ID saved to {output_dir}/.env.sandbox for potential reconnection")

        agent = SandboxAgent(sandbox, output_dir)

        print("Starting the VNC server...")
        try:
            sandbox.stream.start()
            vnc_url = sandbox.stream.get_url()
            print(f"VNC server ready at: {vnc_url}")
            sandbox.commands.run("echo VNC server initialized")
        except Exception as e:
            print(f"Error starting VNC server: {e}")
            vnc_url = sandbox.stream.get_url()
            print(f"Attempting to continue with URL: {vnc_url}")

        # Start the noVNC proxy if requested
        proxy_process = None
        if use_proxy:
            from multiprocessing import Process
            from os_computer_use.novnc_proxy import start_novnc_proxy
            
            print(f"Starting noVNC proxy on port {proxy_port}...")
            proxy_process = Process(target=start_novnc_proxy, args=(proxy_port,))
            proxy_process.daemon = True
            proxy_process.start()
            
            # Modify the URL to go through our proxy
            original_url = vnc_url
            vnc_url = f"http://localhost:{proxy_port}/?url={urllib.parse.quote(original_url)}"
            print(f"Redirecting through proxy: {vnc_url}")

        print("Starting the VNC client...")
        try:
            # Get the VNC URL
            vnc_url = vnc_url.strip()
            
            # Add reconnection parameters if not already present
            if 'reconnect=' not in vnc_url:
                if '?' in vnc_url:
                    vnc_url += '&reconnect=true&reconnect_delay=2000'
                else:
                    vnc_url += '?reconnect=true&reconnect_delay=2000'
                print(f"Added reconnection parameters to VNC URL")
            
            # Try to open the VNC client directly in the user's browser
            # This is more reliable and avoids localStorage issues
            print(f"Opening noVNC client at: {vnc_url}")
            browser = Browser()
            browser.open(vnc_url)
            
        except Exception as e:
            print(f"Error opening browser window: {e}")
            print("Opening URL in your default browser instead...")
            webbrowser.open(vnc_url)

        while True:
            # Send a periodic keep-alive to the sandbox
            try:
                # Check if sandbox is still running 
                check_result = sandbox.commands.run("echo connection-check", timeout=5)
                if check_result and check_result.stdout and 'connection-check' in check_result.stdout:
                    # Connection is good, refresh timeout
                    sandbox.set_timeout(300)  # 5 minutes timeout
                else:
                    print("Warning: Sandbox connection check failed")
            except Exception as e:
                print(f"Sandbox connection error: {e}")
                # Could implement automatic reconnection here if needed
            
            # Ask for user input, and exit if the user presses ctl-c
            if user_input is None:
                try:
                    user_input = input("USER: ")
                except KeyboardInterrupt:
                    break
            # Run the agent, and go back to the prompt if the user presses ctl-c
            else:
                try:
                    agent.run(user_input)
                    user_input = None
                except KeyboardInterrupt:
                    user_input = None
                except Exception as e:
                    logger.print_colored(f"An error occurred: {e}", "red")
                    user_input = None

    finally:
        #if client:
        #    print("Stopping the display client...")
        #    try:
        #        await client.stop()
        #    except Exception as e:
        #        print(f"Error stopping display client: {str(e)}")

        if sandbox:
            print("Stopping the sandbox...")
            try:
                sandbox.kill()
            except Exception as e:
                print(f"Error stopping sandbox: {str(e)}")

        #if client:
        #    print("Saving the stream as mp4...")
        #    try:
        #        await client.save_stream()
        #    except Exception as e:
        #        print(f"Error saving stream: {str(e)}")

        print("Stopping the VNC client...")
        try:
            browser.close()
        except Exception as e:
            print(f"Error stopping VNC client: {str(e)}")


def initialize_output_directory(directory_format):
    run_id = 1
    while os.path.exists(directory_format(run_id)):
        run_id += 1
    os.makedirs(directory_format(run_id), exist_ok=True)
    return directory_format(run_id)


def main():
    parser = argparse.ArgumentParser(description="Open Computer Use")
    parser.add_argument("--prompt", type=str, help="User prompt for the agent")
    parser.add_argument("--proxy", action='store_true', help="Use the noVNC proxy to fix localStorage issues")
    parser.add_argument("--proxy-port", type=int, default=8899, help="Port for noVNC proxy server")
    args = parser.parse_args()

    output_dir = initialize_output_directory(lambda id: f"./output/run_{id}")
    loop = asyncio.get_event_loop()
    
    loop.run_until_complete(start(user_input=args.prompt, output_dir=output_dir, 
                                 use_proxy=args.proxy, proxy_port=args.proxy_port))
