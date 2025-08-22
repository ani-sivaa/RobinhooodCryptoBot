#!/usr/bin/env python3
"""
Test Ed25519 signature against Robinhood docs example
"""

import nacl.signing
import base64
import json

# Example values from docs
private_key_base64 = "xQnTJVeQLmw1/Mg2YimEViSpw/SdJcgNXZ5kQkAXNPU="
api_key = "rh-api-6148effc-c0b1-486c-8940-a1d099456be6"
timestamp = "1698708981"
path = "/api/v1/crypto/trading/orders/"
method = "POST"
body = {
    "client_order_id": "131de903-5a9c-4260-abc1-28d562a5dcf0",
    "side": "buy",
    "symbol": "BTC-USD",
    "type": "market",
    "market_order_config": {
        "asset_quantity": "0.1"
    }
}

# Expected signature from docs
expected_signature = "q/nEtxp/P2Or3hph3KejBqnw5o9qeuQ+hYRnB56FaHbjDsNUY9KhB1asMxohDnzdVFSD7StaTqjSd9U9HvaRAw=="

# Try different JSON serialization - maybe it's the exact body from docs
body_str = '{"client_order_id":"131de903-5a9c-4260-abc1-28d562a5dcf0","side":"buy","symbol":"BTC-USD","type":"market","market_order_config":{"asset_quantity":"0.1"}}'
print(f"Trying exact body from docs...")

# Also try our JSON dumps
our_body_str = json.dumps(body, separators=(',', ':'))
print(f"Our JSON:  {our_body_str}")
print(f"Doc JSON:  {body_str}")
print(f"JSON match: {our_body_str == body_str}")
print(f"Body string: {body_str}")

# Create message
message = f"{api_key}{timestamp}{path}{method}{body_str}"
print(f"Message to sign: {message}")

# Sign with our implementation
private_key_bytes = base64.b64decode(private_key_base64)
signing_key = nacl.signing.SigningKey(private_key_bytes)
signed_message = signing_key.sign(message.encode('utf-8'))
signature = base64.b64encode(signed_message.signature).decode('utf-8')

print(f"Our signature:      {signature}")
print(f"Expected signature: {expected_signature}")
print(f"Signatures match: {signature == expected_signature}")