# Custom NoVNC Proxy with LocalStorage Fix
import os
import re
import argparse
from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.parse
import urllib.request

class NoVNCProxyHandler(SimpleHTTPRequestHandler):
    """Custom HTTP server that redirects noVNC requests through a proxy with localStorage fix"""
    
    def do_GET(self):
        if self.path == '/' or self.path.startswith('/?'):
            # Extract the original VNC URL from query parameters
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            
            original_url = params.get('url', [''])[0]
            
            if original_url:
                # Ensure the URL has reconnection parameters
                if 'reconnect=' not in original_url:
                    if '?' in original_url:
                        original_url += '&reconnect=true&reconnect_delay=2000'
                    else:
                        original_url += '?reconnect=true&reconnect_delay=2000'
                
                # Serve our proxy HTML page with the original URL as a parameter
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
                self.end_headers()
                
                # Read our proxy HTML template
                novnc_fix_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'novnc_fix.html')
                with open(novnc_fix_path, 'rb') as f:
                    content = f.read()
                
                # Check if URL is accessible before redirecting
                try:
                    # Try to reach the URL with a HEAD request
                    req = urllib.request.Request(original_url, method='HEAD')
                    urllib.request.urlopen(req, timeout=5)
                    print(f"VNC URL is accessible: {original_url}")
                except Exception as e:
                    print(f"Warning: VNC URL might not be accessible: {e}")
                    # We'll still try to redirect, but log the warning
                
                self.wfile.write(content)
            else:
                # If no URL provided, return an error
                self.send_response(400)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b'<html><body><h1>Error: Missing noVNC URL</h1></body></html>')
        else:
            # For other requests, pass through to the original path
            super().do_GET()

def start_novnc_proxy(port=8899):
    """Start a proxy server that applies localStorage fix for noVNC connections"""
    server_address = ('', port)
    httpd = HTTPServer(server_address, NoVNCProxyHandler)
    print(f"Starting NoVNC Proxy server on port {port}")
    httpd.serve_forever()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Start a NoVNC proxy with localStorage fix')
    parser.add_argument('--port', type=int, default=8899, help='Port to run the proxy server on')
    args = parser.parse_args()
    
    start_novnc_proxy(args.port)
