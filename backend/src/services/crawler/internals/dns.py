import socket


def is_domain_resolvable(domain: str) -> bool:
    try:
        socket.gethostbyname(domain)
        return True
    except (socket.gaierror, socket.herror, Exception):
        if not domain.startswith("www."):
            try:
                socket.gethostbyname(f"www.{domain}")
                return True
            except Exception:
                pass
        return False
