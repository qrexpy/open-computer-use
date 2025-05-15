from e2b_desktop import Sandbox as SandboxBase
import asyncio
import os
import signal
import sys
import threading
import time


class Sandbox(SandboxBase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._keep_alive_thread = None
        self._should_stop = False
        self._last_activity = time.time()
        # Start the keep-alive thread
        self._start_keep_alive()
        
        # Generate a unique ID for this sandbox instance
        import uuid
        self.id = str(uuid.uuid4())

    def _start_keep_alive(self):
        """Start a thread that keeps the sandbox connection alive"""
        def keep_alive_worker():
            print("Started sandbox keep-alive thread")
            while not self._should_stop:
                try:
                    # If it's been more than 30 seconds since last activity, send a keep-alive
                    if time.time() - self._last_activity > 30:
                        # Set a long timeout to prevent the sandbox from disconnecting
                        self.set_timeout(300)  # 5 minutes
                        # Send a harmless command to keep the connection active
                        result = self.commands.run("echo keep-alive", timeout=5)
                        if result and result.stdout and 'keep-alive' in result.stdout:
                            self._last_activity = time.time()
                            print("Sent keep-alive to sandbox")
                        else:
                            print("Keep-alive failed, may need to reconnect")
                    # Check every 20 seconds
                    time.sleep(20)
                except Exception as e:
                    print(f"Keep-alive error: {e}")
                    time.sleep(5)  # On error, wait a bit before retrying
        
        self._keep_alive_thread = threading.Thread(target=keep_alive_worker, daemon=True)
        self._keep_alive_thread.start()

    def set_timeout(self, timeout_seconds):
        """Set the timeout for the sandbox"""
        super().set_timeout(timeout_seconds)
        self._last_activity = time.time()

    def start_stream(self):
        # Command to start streaming using ffmpeg
        command = "ffmpeg -f x11grab -s 1024x768 -framerate 30 -i {self._display} -vcodec libx264 -preset ultrafast -tune zerolatency -f mpegts -listen 1 http://localhost:8080"
        # Run the command in the background
        process = self.commands.run(
            command,
            background=True,
        )
        self.process = process
        self._last_activity = time.time()
        return f"https://{self.get_host(8080)}"

    def ensure_vnc_ready(self, max_retries=3):
        """Ensure VNC server is running and port 6080 is listening. Auto-fix if not."""
        for attempt in range(1, max_retries + 1):
            # Check for VNC process
            proc_result = self.commands.run("ps aux | grep -v grep | grep -E 'vnc|VNC'", timeout=5)
            port_result = self.commands.run("netstat -tuln | grep 6080", timeout=5)
            if proc_result.stdout and port_result.stdout:
                return True
            # Try to fix: kill and restart VNC
            self.commands.run("pkill -f 'x11vnc|Xtightvnc' || true", timeout=5)
            time.sleep(2)
            try:
                self.stream.start()
            except Exception:
                pass
            time.sleep(3)
            # Manual fallback
            port_result = self.commands.run("netstat -tuln | grep 6080", timeout=5)
            if port_result.stdout:
                return True
            self.commands.run("x11vnc -display :0 -forever -nopw -quiet", background=True, timeout=5)
            time.sleep(3)
        # Final check
        port_result = self.commands.run("netstat -tuln | grep 6080", timeout=5)
        if port_result.stdout:
            return True
        raise RuntimeError("Unable to start VNC server on port 6080 after multiple attempts.")

    def get_url(self):
        self.ensure_vnc_ready()
        return super().get_url()

    def kill(self):
        # Signal the keep-alive thread to stop
        self._should_stop = True
        
        # Kill the streaming process along with the sandbox
        if hasattr(self, "process"):
            self.process.kill()
        
        # Wait for the keep-alive thread to finish
        if self._keep_alive_thread and self._keep_alive_thread.is_alive():
            self._keep_alive_thread.join(timeout=2)
            
        super().kill()


# Client to view and save a live display stream from the sandbox
class DisplayClient:
    def __init__(self, output_dir="."):
        self.process = None
        # Define output stream and file paths
        self.output_stream = f"{output_dir}/output.ts"
        self.output_file = f"{output_dir}/output.mp4"

    async def start(self, stream_url, title="Sandbox", delay=0):
        title = title.replace("'", "\\'")
        # Start a subprocess to both view and save the stream
        self.process = await asyncio.create_subprocess_shell(
            f"sleep {delay} && ffmpeg -reconnect 1 -i {stream_url} -c:v libx264 -preset fast -crf 23 "
            f"-c:a aac -b:a 128k -f mpegts -loglevel quiet - | tee {self.output_stream} | "
            f"ffplay -autoexit -i -loglevel quiet -window_title '{title}' -",
            preexec_fn=os.setsid,
            stdin=asyncio.subprocess.DEVNULL,
        )

    async def stop(self):
        if self.process:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
            await self.process.wait()

    async def save_stream(self):
        # Convert the saved stream to an mp4 file
        process = await asyncio.create_subprocess_shell(
            f"ffmpeg -i {self.output_stream} -c:v copy -c:a copy -loglevel quiet {self.output_file}"
        )
        await process.wait()

        if process.returncode == 0:
            print(f"Stream saved successfully as {self.output_file}.")
        else:
            print(f"Failed to save the stream as {self.output_file}.")
