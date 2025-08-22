#!/usr/bin/env python3
"""
Get the public key for the private key in .env
"""

import nacl.signing
import base64
import os
from dotenv import load_dotenv

load_dotenv()

private_key_b64 = os.getenv('ROBINHOOD_PRIVATE_KEY')
print(f"Private key from .env: {private_key_b64}")

# Decode and get public key
private_key_bytes = base64.b64decode(private_key_b64)
signing_key = nacl.signing.SigningKey(private_key_bytes)
public_key = signing_key.verify_key

public_key_b64 = base64.b64encode(public_key.encode()).decode()
print(f"Matching public key: {public_key_b64}")
print()
print("You need to upload THIS public key to Robinhood:")
print(public_key_b64)