#!/usr/bin/env python3
"""
PackAssist – Mesh Simplification Micro-server
Exposes a single POST /api/simplify endpoint that uses PyMeshLab's
Quadric-Edge-Collapse decimation with topology + normal preservation.

Run:  python mesh_server.py            (defaults to port 8787)
      python mesh_server.py --port 9000

The web UI calls this when available; if it's offline the JS-only
SimplifyModifier fallback is used instead.
"""

import argparse
import io
import os
import sys
import tempfile
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import json

# ---------------------------------------------------------------------------
# Dependency check
# ---------------------------------------------------------------------------
try:
    import pymeshlab
    HAS_PYMESHLAB = True
except ImportError:
    HAS_PYMESHLAB = False
    print("[mesh_server] WARNING: pymeshlab not installed. "
          "Run:  pip install pymeshlab")

# ---------------------------------------------------------------------------
# Simplification logic
# ---------------------------------------------------------------------------

def simplify_stl(input_bytes: bytes, target_ratio: float) -> bytes:
    """
    Simplify an STL mesh in-memory.

    Parameters
    ----------
    input_bytes : bytes
        Raw STL file content (binary or ASCII).
    target_ratio : float
        Fraction of faces to keep (0.01 – 1.0).

    Returns
    -------
    bytes
        Simplified STL (binary format).
    """
    if not HAS_PYMESHLAB:
        raise RuntimeError("pymeshlab is not installed")

    # Write input to temp file (PyMeshLab needs a path)
    with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as tmp_in:
        tmp_in.write(input_bytes)
        tmp_in_path = tmp_in.name

    tmp_out_path = tmp_in_path + "_simplified.stl"

    try:
        ms = pymeshlab.MeshSet()
        ms.load_new_mesh(tmp_in_path)

        original_faces = ms.current_mesh().face_number()
        original_verts = ms.current_mesh().vertex_number()
        target_faces = max(12, int(original_faces * target_ratio))

        print(f"[simplify] Original: {original_verts:,} verts, "
              f"{original_faces:,} faces → target {target_faces:,} faces "
              f"(ratio {target_ratio:.2%})")

        # Primary method: Quadric Edge Collapse with topology + normal preservation
        try:
            ms.meshing_decimation_quadric_edge_collapse(
                targetfacenum=target_faces,
                preservenormal=True,
                preservetopology=True,
                optimalplacement=True,
                qualitythr=0.5,
            )
        except Exception:
            # Fallback: older API name or different parameter set
            try:
                ms.apply_filter(
                    'simplification_quadric_edge_collapse_decimation',
                    targetfacenum=target_faces,
                    preservenormal=True,
                    preservetopology=True,
                    optimalplacement=True,
                )
            except Exception:
                # Last resort: clustering decimation
                ms.meshing_decimation_clustering(
                    threshold=pymeshlab.AbsoluteValue(
                        ms.current_mesh().bounding_box().diagonal() *
                        (1 - target_ratio) * 0.02
                    )
                )

        # Cleanup
        try:
            ms.meshing_remove_duplicate_vertices()
            ms.meshing_remove_unreferenced_vertices()
        except Exception:
            pass

        final_verts = ms.current_mesh().vertex_number()
        final_faces = ms.current_mesh().face_number()
        print(f"[simplify] Result:   {final_verts:,} verts, "
              f"{final_faces:,} faces")

        ms.save_current_mesh(tmp_out_path, binary=True)

        with open(tmp_out_path, "rb") as f:
            result_bytes = f.read()

        return result_bytes

    finally:
        # Clean up temp files
        for p in (tmp_in_path, tmp_out_path):
            try:
                os.unlink(p)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# HTTP Server
# ---------------------------------------------------------------------------

class SimplifyHandler(BaseHTTPRequestHandler):
    """Minimal CORS-enabled handler for mesh simplification."""

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers",
                         "Content-Type, X-Target-Ratio")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):
        """Health check."""
        parsed = urlparse(self.path)
        if parsed.path in ("/api/health", "/api/simplify"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._cors_headers()
            self.end_headers()
            info = {
                "status": "ok",
                "pymeshlab": HAS_PYMESHLAB,
                "version": "1.0.0",
            }
            self.wfile.write(json.dumps(info).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/simplify":
            self.send_response(404)
            self.end_headers()
            return

        if not HAS_PYMESHLAB:
            self._error(503, "pymeshlab not installed on server")
            return

        try:
            # Read body
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                self._error(400, "Empty body — send the STL binary data")
                return

            body = self.rfile.read(content_length)

            # Get target ratio from header or query string
            ratio_str = self.headers.get("X-Target-Ratio")
            if not ratio_str:
                qs = parse_qs(parsed.query)
                ratio_str = qs.get("ratio", ["0.5"])[0]

            target_ratio = max(0.01, min(1.0, float(ratio_str)))

            result_bytes = simplify_stl(body, target_ratio)

            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(result_bytes)))
            self._cors_headers()
            self.end_headers()
            self.wfile.write(result_bytes)

        except Exception as e:
            traceback.print_exc()
            self._error(500, str(e))

    def _error(self, code, message):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())

    def log_message(self, fmt, *args):
        # Cleaner log format
        print(f"[mesh_server] {args[0]}")


def main():
    parser = argparse.ArgumentParser(description="PackAssist Mesh Simplification Server")
    parser.add_argument("--port", type=int, default=8787,
                        help="Port to listen on (default: 8787)")
    args = parser.parse_args()

    if not HAS_PYMESHLAB:
        print("=" * 60)
        print("  pymeshlab is NOT installed.")
        print("  Install it:  pip install pymeshlab")
        print("  The server will start but return 503 on /api/simplify")
        print("=" * 60)

    server = HTTPServer(("0.0.0.0", args.port), SimplifyHandler)
    print(f"[mesh_server] Listening on http://0.0.0.0:{args.port}")
    print(f"[mesh_server] POST /api/simplify  (body=STL, header X-Target-Ratio)")
    print(f"[mesh_server] GET  /api/health")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[mesh_server] Shutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
