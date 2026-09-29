# discovery.py
import socket
import threading

DISCOVERY_PORT = 55555
MAGIC = "CMMS_V1"


def start_discovery_server():
    def _loop():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("", DISCOVERY_PORT))
        except OSError:
            return
        while True:
            try:
                data, addr = sock.recvfrom(1024)
                if data.decode(errors="ignore") == MAGIC:
                    sock.sendto(f"{MAGIC}:SERVER".encode(), addr)
            except OSError:
                break
    threading.Thread(target=_loop, daemon=True).start()


def discover_server(timeout=6):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(timeout)
    try:
        sock.sendto(MAGIC.encode(), ("255.255.255.255", DISCOVERY_PORT))
        data, addr = sock.recvfrom(1024)
        if data.decode(errors="ignore").startswith(MAGIC):
            return addr[0]
    except (socket.timeout, OSError):
        pass
    finally:
        sock.close()
    return None