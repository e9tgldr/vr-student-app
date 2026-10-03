# Generates a self-signed certificate for https://<LAN-IP>:8443 so the Quest
# browser can enter VR (WebXR needs a secure context; plain HTTP on a LAN IP
# is NOT secure, but https://localhost IS — which is why USB adb is plan A).
#
# Self-renewing: if cert.pem is missing OR expires within 14 days (or the
# LAN IP changed), a new one is written. Reuses a long-lived local CA so
# re-runs stay deterministic. Pure stdlib + cryptography (already installed).
import ipaddress
import ssl
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

HERE = Path(__file__).resolve().parent
CA_KEY = HERE / "ca.key"
CA_CERT = HERE / "ca.pem"
SERVER_KEY = HERE / "cert.key"
SERVER_CERT = HERE / "cert.pem"
RENEW_DAYS = 14


def local_ips():
    """Every usable IPv4 address of this machine (loopback excluded).
    UDP 'connect' sends no packets - it just makes the OS pick the outgoing
    route, so this works even for gateways that never answer."""
    ips = []
    targets = [("8.8.8.8", 80), ("192.168.1.1", 80), ("192.168.7.1", 80),
               ("192.168.0.1", 80), ("10.0.0.1", 80)]
    try:
        import socket
        for tgt in targets:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(tgt)
                ip = s.getsockname()[0]
                if ip and ip != "127.0.0.1" and ip not in ips:
                    ips.append(ip)
            except Exception:
                pass
            finally:
                s.close()
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip != "127.0.0.1" and not ip.startswith("169.254.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    return ips


def load_or_create_ca():
    if CA_KEY.exists() and CA_CERT.exists():
        try:
            key = serialization.load_pem_private_key(CA_KEY.read_bytes(), password=None)
            cert = x509.load_pem_x509_certificate(CA_CERT.read_bytes())
            if cert.not_valid_after_utc > datetime.now(timezone.utc) + timedelta(days=30):
                return key, cert
        except Exception:
            pass
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "vr-school-demo local CA")])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    CA_KEY.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ))
    CA_CERT.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return key, cert


def cert_covers(cert, ips):
    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        have = {str(v) for v in san.get_values_for_type(x509.IPAddress)}
        return all(str(ipaddress.ip_address(i)) in have for i in ips)
    except Exception:
        return False


def main():
    ca_key, ca_cert = load_or_create_ca()
    ips = local_ips()
    wanted = [ipaddress.ip_address(i) for i in ips]

    # Reuse an existing cert when it still covers every current IP and has runway.
    if SERVER_CERT.exists() and SERVER_KEY.exists():
        try:
            old = x509.load_pem_x509_certificate(SERVER_CERT.read_bytes())
            if (old.not_valid_after_utc > datetime.now(timezone.utc) + timedelta(days=RENEW_DAYS)
                    and cert_covers(old, ips)):
                print("cert OK (reused): covers %s, expires %s" % (
                    ", ".join(ips) or "?", old.not_valid_after_utc.date()))
                return 0
        except Exception:
            pass

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "vr-school-demo")])
    names = [x509.DNSName("localhost")] + [x509.IPAddress(i) for i in wanted]
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=825))
        .add_extension(x509.SubjectAlternativeName(names), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    SERVER_KEY.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ))
    SERVER_CERT.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    print("cert written: covers %s + localhost, expires %s" % (
        ", ".join(ips) or "?", cert.not_valid_after_utc.date()))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("cert generation FAILED: %r" % exc)
        sys.exit(1)