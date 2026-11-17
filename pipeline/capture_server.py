"""Serve the site and save PNG frames POSTed to /frame?i=N."""
import http.server, os, sys, urllib.parse
SITE, OUT = sys.argv[1], sys.argv[2]
class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=SITE, **k)
    def do_POST(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        n = int(self.headers['Content-Length'])
        with open(os.path.join(OUT, 'f%04d.png' % int(q['i'][0])), 'wb') as f: f.write(self.rfile.read(n))
        self.send_response(204); self.end_headers()
    def log_message(self, *a): pass
http.server.ThreadingHTTPServer(('127.0.0.1', 4180), H).serve_forever()
