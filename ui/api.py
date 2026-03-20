import os
import time
import json
import threading
import subprocess
from http.server import SimpleHTTPRequestHandler, HTTPServer
import socketserver

# Global state to keep track of audio updates and messages
API_STATE = {
    "updated_at": 0.0,
    "messages": [],  # List of {"role": "user"|"agent", "text": "...", "timestamp": float}
    "listen_active": False
}

# Lock for thread-safe message access
_messages_lock = threading.Lock()


def push_message(role: str, text: str):
    """Thread-safe helper to add a message to the log."""
    with _messages_lock:
        API_STATE["messages"].append({
            "role": role,
            "text": text,
            "timestamp": time.time()
        })
        # Keep only the last 50 messages
        if len(API_STATE["messages"]) > 50:
            API_STATE["messages"] = API_STATE["messages"][-50:]


class CORSRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        SimpleHTTPRequestHandler.end_headers(self)

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        try:
            if self.path == '/status':
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = json.dumps({"updated_at": API_STATE["updated_at"]})
                self.wfile.write(response.encode('utf-8'))
            elif self.path == '/api/messages':
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                with _messages_lock:
                    response = json.dumps({"messages": API_STATE["messages"]})
                self.wfile.write(response.encode('utf-8'))
            elif self.path.startswith('/audio.wav'):
                # Serve the latest.wav file
                self.path = '/latest.wav'
                super().do_GET()
            else:
                # For resolving standard SimpleHTTPRequestHandler routes (like if they fetch index)
                super().do_GET()
        except (BrokenPipeError, ConnectionResetError):
            # Client disconnected early, ignore gracefully
            pass

    def do_POST(self):
        if self.path == '/api/messages':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body)
                role = data.get("role", "agent")
                text = data.get("text", "")
                push_message(role, text)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"ok": true}')
            except Exception as e:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
        elif self.path == '/api/listen_toggle':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body)
                API_STATE["listen_active"] = bool(data.get("state", False))
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"listen_active": API_STATE["listen_active"]}).encode('utf-8'))
            except Exception as e:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress standard HTTP server logging to keep the CLI clean"""
        pass

def kill_process_on_port(port):
    """Kills any process currently listening on the given port."""
    try:
        # Find PID(s) of process listening on the port
        result = subprocess.check_output(f"lsof -t -i:{port}", shell=True)
        pids = result.decode().strip().split('\n')
        for pid in pids:
            if pid:
                print(f"[UI Server] Terminating existing process {pid} on port {port}...")
                os.kill(int(pid), 9) # SIGKILL
                time.sleep(1) # Give it a second to free the port
    except subprocess.CalledProcessError:
        # No process found on the port
        pass

def run_server(port=8080):
    # Kill existing processes on this port
    kill_process_on_port(port)

    # Change working directory specifically for the server so it serves from ui/
    current_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_dir)
    
    # Allows fast restart
    socketserver.TCPServer.allow_reuse_address = True
    
    server_address = ('', port)
    try:
        httpd = socketserver.TCPServer(server_address, CORSRequestHandler)
        print(f"\n[UI Server] Running on http://localhost:{port}/")
        httpd.serve_forever()
    except OSError as e:
        print(f"\n[UI Server] Could not start on port {port}: {e}")
        print("[UI Server] (This usually means another instance of K.I.T.E. is already running)")

def start_server_in_background(port=8080):
    thread = threading.Thread(target=run_server, args=(port,))
    thread.daemon = True
    thread.start()

def notify_audio_updated():
    API_STATE["updated_at"] = time.time()
