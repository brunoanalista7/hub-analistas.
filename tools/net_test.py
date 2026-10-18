"""Teste de rede: roda no PC reserva ANTES de instalar o Hub.

Responde se outros computadores da empresa conseguem abrir uma página servida
por este PC (o Firewall do Windows pode bloquear). Só usa a biblioteca padrão:

    python tools\\net_test.py

Depois, em OUTRO PC, abra o endereço que aparecer. Ctrl+C para parar.
"""

import socket
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 8800


class Hello(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = "<h1>Hub: conexão OK</h1><p>Este PC aceita conexões de outros computadores.</p>".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)
        print(f"  pedido recebido de {self.client_address[0]}")

    def log_message(self, *args) -> None:
        pass


def local_ips() -> list[str]:
    try:
        return sorted({info[4][0] for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)})
    except OSError:
        return []


if __name__ == "__main__":
    name = socket.gethostname()
    print("Hub: teste de rede")
    print(f"Em OUTRO computador, abra:  http://{name}:{PORT}")
    for ip in local_ips():
        print(f"                       ou:  http://{ip}:{PORT}")
    print("Se o Windows mostrar um aviso do Firewall, anote o que ele pede (permissão de administrador?).")
    print("Ctrl+C para parar.\n")
    try:
        HTTPServer(("0.0.0.0", PORT), Hello).serve_forever()
    except KeyboardInterrupt:
        print("Parado.")
