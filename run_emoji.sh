#!/usr/bin/env bash
cd "$(dirname "$0")"
export QT_QPA_PLATFORM=xcb
if [ -f "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem" ]; then
    export SSL_CERT_FILE="/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem"
fi
exec .venv/bin/python emojikryptograf.py "$@"
