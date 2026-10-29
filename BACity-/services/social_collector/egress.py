"""Restricted CONNECT egress. No credentials, persistence or arbitrary destinations."""
import ipaddress
import select
import socket
import socketserver
import time

# A small deployment allowlist, not a user-editable proxy destination registry.
HOSTS={'api.apify.com','api.scrapingant.com','instagram.com','www.instagram.com','facebook.com','www.facebook.com',
       'tiktok.com','www.tiktok.com','novacvernovka.eu','www.novacvernovka.eu',
       'staratrznica.sk','www.staratrznica.sk','visitbratislava.com','www.visitbratislava.com',
       'goout.net','www.goout.net'}

class Proxy(socketserver.StreamRequestHandler):
    timeout=10
    def handle(self):
        self.connection.settimeout(10)
        line=self.rfile.readline(2049)
        try:
            method,destination,version=line.decode('ascii').strip().split(' ')
            host,port=destination.rsplit(':',1)
        except (ValueError,UnicodeError):
            return
        image_host=host.endswith('.cdninstagram.com') or host.endswith('.fbcdn.net')
        if method!='CONNECT' or (host not in HOSTS and not image_host) or port!='443' or version not in ('HTTP/1.0','HTTP/1.1'):
            self.wfile.write(b'HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n'); return
        for _ in range(32):
            header=self.rfile.readline(2049)
            if header in (b'\r\n',b'\n'):
                break
            if len(header)>2048:
                return
        else:
            return
        try:
            addresses=list(dict.fromkeys(x[4][0] for x in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)))
            if not addresses or any(not ipaddress.ip_address(x).is_global for x in addresses):
                return
            with socket.create_connection((addresses[0],443),timeout=10) as upstream:
                self.wfile.write(b'HTTP/1.1 200 Connection Established\r\n\r\n'); self.wfile.flush()
                ends=[self.connection,upstream]; total=0; deadline=time.monotonic()+30
                while time.monotonic()<deadline and total<5*1024*1024:
                    ready,_,_=select.select(ends,[],[],1)
                    for source in ready:
                        chunk=source.recv(min(65536,5*1024*1024-total))
                        if not chunk:
                            return
                        total+=len(chunk)
                        (upstream if source is self.connection else self.connection).sendall(chunk)
        except OSError:
            return

class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address=True
    daemon_threads=True
    # A single collector may fetch a small number of assets. Bound accepted threads.
    def process_request(self,request,address):
        import threading
        if threading.active_count()>16:
            request.close(); return
        super().process_request(request,address)

if __name__=='__main__':
    with Server(('0.0.0.0',3128),Proxy) as server:
        server.serve_forever()
