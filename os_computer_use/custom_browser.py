# custom_browser.py - Use PyWebView with Qt instead of GTK
import os
import time
import threading
from multiprocessing import Process, Queue
import webview
import webbrowser

# Force the use of Qt backend
os.environ["WEBVIEW_GUI"] = "qt"

class Browser:
    def __init__(self):
        self.width = 1024
        self.height = 768
        self.window_frame_height = 29  # Additional px for window border
        self.command_queue = Queue()
        self.webview_process = None
        self.is_running = False

    def open(self, url, width=None, height=None):
        """
        Open a browser window with the given URL

        Args:
            url (str): The URL to open
            width (int, optional): Window width
            height (int, optional): Window height
        """
        if self.is_running:
            print("Browser window is already running")
            return

        self.width = width or self.width
        self.height = height or self.height

        print(f"URL: {url}")

        # Add reconnection parameters to the URL if using noVNC
        if 'vnc.html' in url or 'autoconnect=true' in url:
            # Add parameters to help with connection stability
            if '?' in url:
                url += '&reconnect=true&reconnect_delay=2000'
            else:
                url += '?reconnect=true&reconnect_delay=2000'
            print(f"Added reconnection parameters: {url}")

        # First attempt: try to use the default web browser
        # This is more reliable and avoids localStorage issues with noVNC
        try:
            print("Opening URL in default browser...")
            webbrowser.open(url)
            self.is_running = True
            return
        except Exception as e:
            print(f"Failed to open URL in default browser: {e}")
            print("Falling back to PyWebView...")

        # Fall back to webview if the default browser fails
        try:
            # Start webview in separate process
            self.webview_process = Process(
                target=self._create_window,
                args=(url, self.width, self.height, self.command_queue),
            )
            self.webview_process.start()
            self.is_running = True
        except Exception as e:
            print(f"Failed to open PyWebView: {e}")
            print(f"Please manually open this URL in your browser: {url}")

    def close(self):
        """Close the browser window"""
        if not self.is_running:
            print("No browser window is running")
            return

        self.command_queue.put("close")
        if self.webview_process:
            self.webview_process.join()
            self.webview_process = None
        self.is_running = False

    @staticmethod
    def _create_window(url, width, height, command_queue):
        """Create a webview window in a separate process"""

        def check_queue():
            while True:
                if not command_queue.empty():
                    command = command_queue.get()
                    if command == "close":
                        window.destroy()
                        break
                time.sleep(1)  # Check every second
                
        # Fix for localStorage issues in noVNC
        js_fix = """
        // localStorage polyfill
        if (!window.localStorage) {
            console.log("Adding localStorage polyfill for noVNC");
            var storage = {};
            window.localStorage = {
                getItem: function(key) { return storage[key] || null; },
                setItem: function(key, value) { storage[key] = value; },
                removeItem: function(key) { delete storage[key]; },
                clear: function() { storage = {}; },
                key: function(n) { return Object.keys(storage)[n] || null; },
                get length() { return Object.keys(storage).length; }
            };
        }
        // Check if localStorage is actually working
        try {
            window.localStorage.setItem('__test__', '1');
            window.localStorage.removeItem('__test__');
        } catch (e) {
            console.log("localStorage test failed, applying polyfill anyway");
            var storage = {};
            window.localStorage = {
                getItem: function(key) { return storage[key] || null; },
                setItem: function(key, value) { storage[key] = value; },
                removeItem: function(key) { delete storage[key]; },
                clear: function() { storage = {}; },
                key: function(n) { return Object.keys(storage)[n] || null; },
                get length() { return Object.keys(storage).length; }
            };
        }

        // Add reconnection handling for noVNC
        window.addEventListener('load', function() {
            if (typeof RFB !== 'undefined') {
                console.log("noVNC detected, adding connection event listeners");
                document.addEventListener('disconnect', function() {
                    console.log("Disconnect detected, will try to reconnect");
                    setTimeout(function() {
                        console.log("Attempting to reconnect...");
                        if (typeof connect !== 'undefined') {
                            connect();
                        } else {
                            location.reload();
                        }
                    }, 2000);
                });
            }
        });
        """

        window_frame_height = 29
        
        try:
            # Try to create the window with Qt backend using js_fix as user_agent
            window = webview.create_window(
                "Browser Window", 
                url, 
                width=width, 
                height=height + window_frame_height,
                js_api=None,
                min_size=(800, 600),
                user_agent=f"Mozilla/5.0 WebView Custom Browser<script>{js_fix}</script>"
            )
            
            # Also inject the fix after window is loaded for good measure
            window.evaluate_js(js_fix)

            # Start queue checking in a separate thread
            t = threading.Thread(target=check_queue)
            t.daemon = True
            t.start()

            webview.start()
        except Exception as e:
            print(f"Error creating window with PyWebView: {e}")
            print("Please open this URL in your external browser:")
            print(url)
