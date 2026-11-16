#!/usr/bin/env python3
"""RoofLamp 本機伺服器：靜態檔 + POST /step（呼叫 build123d 產生精確 STEP）。"""
import os, subprocess, sys, tempfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(ROOT, '.venv', 'bin', 'python')
os.chdir(ROOT)


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def do_POST(self):
        if self.path != '/step':
            self.send_error(404)
            return
        body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, 'out.step')
            r = subprocess.run([PY, os.path.join(ROOT, 'step_gen.py'), out], input=body,
                               capture_output=True, timeout=120)
            if r.returncode != 0 or not os.path.exists(out):
                msg = (r.stderr or 'STEP 產生失敗'.encode('utf-8'))[-800:]
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(msg)
                return
            data = open(out, 'rb').read()
        self.send_response(200)
        self.send_header('Content-Type', 'application/step')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8090
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
