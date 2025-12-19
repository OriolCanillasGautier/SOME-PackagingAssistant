
import http.server
import socketserver
import os
import csv
import json

import shutil
from datetime import datetime

PORT = 8000
WEB_DIR = "web"
LIBRARY_DIR = os.path.join(WEB_DIR, "library")
LIBRARY_CSV = os.path.join(WEB_DIR, "library.csv")

# Ensure library directory exists
if not os.path.exists(LIBRARY_DIR):
    os.makedirs(LIBRARY_DIR)

# Ensure CSV exists
if not os.path.exists(LIBRARY_CSV):
    with open(LIBRARY_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['ID', 'Name', 'Filename', 'Date', 'Dimensions', 'Weight'])

class PackAssistHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # API: Get Library
        if self.path == '/api/library':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            files = []
            if os.path.exists(LIBRARY_CSV):
                try:
                    with open(LIBRARY_CSV, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        files = list(reader)
                        # Sort by Date desc
                        files.sort(key=lambda x: x.get('Date', ''), reverse=True)
                except Exception as e:
                    print(f"Error reading CSV: {e}")
            
            self.wfile.write(json.dumps(files).encode())
            return

        # Serve static files from WEB_DIR
        # We need to map requests to the web directory
        # e.g. /index.html -> web/index.html
        # e.g. /library/file.stl -> web/library/file.stl
        
        # Determine strict path to check existence
        
        # Hack to serve from web subdirectory without changing cwd completely for the process
        # SimpleHTTPRequestHandler serves from current directory by default.
        # We'll prepend 'web' to the path if it's not starting with api
        
        original_path = self.path
        if not self.path.startswith('/api'):
            # Basic routing
            if self.path == '/':
                self.path = '/index.html'
            
            # Construct local path
            # self.directory is usually os.getcwd()
            # We want to serve relative to 'web'
            
            # Check if attempting to access library directly
            # /library/something.stl -> web/library/something.stl
            
            # This is slightly tricky with SimpleHTTPRequestHandler.
            # Easiest is to change directory for the server, but we are running script from root.
            # Let's override translate_path or just use os.chdir before starting server? 
            # Ideally we keep logic here.
            
            pass 

        # Delegate to super, but we need to ensure it looks in 'web' folder
        # 'directory' parameter exists in Python 3.7+ for SimpleHTTPRequestHandler
        # but let's just use the constructor argument in main
        return super().do_GET()

    def do_POST(self):
        if self.path == '/api/upload':
            try:
                content_type = self.headers.get('Content-Type')
                if not content_type or 'multipart/form-data' not in content_type:
                    self.send_error(400, "Content-Type must be multipart/form-data")
                    return
                
                # Get boundary
                boundary = content_type.split("boundary=")[1].encode()
                
                # Read content length
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length)
                
                # Split by boundary
                parts = body.split(b'--' + boundary)
                
                filename = None
                file_data = None
                dims = "0x0x0"
                weight = "0"
                
                for part in parts:
                    if b'Content-Disposition' not in part:
                        continue
                        
                    # Split headers and body
                    # Find the first blank line (double CRLF or LF)
                    # Headers end with \r\n\r\n
                    if b'\r\n\r\n' in part:
                        header_part, content = part.split(b'\r\n\r\n', 1)
                    else:
                        continue
                        
                    # Remove trailing \r\n
                    content = content.rstrip(b'\r\n')
                    
                    headers = header_part.decode('utf-8', errors='ignore')
                    
                    # Check name
                    if 'name="file"' in headers:
                        # Extract filename
                        import re
                        m = re.search(r'filename="([^"]+)"', headers)
                        if m:
                            filename = m.group(1)
                            file_data = content
                    elif 'name="dimensions"' in headers:
                        dims = content.decode('utf-8')
                    elif 'name="weight"' in headers:
                        weight = content.decode('utf-8')

                if not filename or not file_data:
                    self.send_error(400, "No file found")
                    return

                # Sanitize filename
                filename = os.path.basename(filename)
                filename = "".join(x for x in filename if x.isalnum() or x in "._- ") # Basic sanitization
                
                # Unique ID
                file_id = str(int(datetime.now().timestamp() * 1000))
                
                # Save file
                save_path = os.path.join(LIBRARY_DIR, filename)
                
                with open(save_path, 'wb') as f:
                    f.write(file_data)

                # Update CSV
                row = [
                    file_id,
                    filename, # Name (display)
                    filename, # Filename (path relative to library/)
                    datetime.now().isoformat(),
                    dims,
                    weight
                ]
                
                with open(LIBRARY_CSV, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(row)

                # Response
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "id": file_id, "filename": filename}).encode())
                return
            except Exception as e:
                print(f"Upload error: {e}")
                self.send_error(500, f"Upload error: {e}")
                return
            
        self.send_error(404)

if __name__ == "__main__":
    # Change directory to web root for static serving convenience??
    # No, because we need to write to library which is in web/library.
    # The handler needs to know to serve from 'web'.
    
    # We will subclass and set directory if supported, or just os.chdir("web") and handle paths carefully.
    # Actually, simpler: os.chdir('web') makes 'web' the root.
    # But then server.py is outside.
    # We can run `python server.py` from root, and inside we `os.chdir('web')` BUT `server.py` file handle is already open so it might be fine?
    # No, if we chdir, we need to adjust relative paths for CSV writing if they were relative.
    # Best approach: Pass `directory="web"` to SimpleHTTPRequestHandler if Python 3.7+
    
    # Check python version
    import sys
    
    # For compatibility, we'll just handle the serving logic by os.chdir logic
    # But we want to keep server.py in root.
    
    # Let's rely on 'directory' arg in Partial
    from functools import partial
    
    print(f"Starting server on port {PORT}...")
    print(f"Serving files from {WEB_DIR}")
    print(f"Library at {LIBRARY_DIR}")

    handler = partial(PackAssistHandler, directory=WEB_DIR)
    
    # Re-define CSV path relative to CWD (which is root)
    # The handler runs in a context where 'directory' handles the GET static files.
    # But do_POST and do_GET custom logic runs in standard context.
    
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        print("Server running. Access at http://localhost:8000")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
