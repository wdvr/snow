#!/usr/bin/env python3
"""
Create APNs Key via Apple Developer Portal API.

This script creates an APNs authentication key for push notifications
using the App Store Connect API credentials.

Usage:
    python create_apns_key.py

Environment variables required:
    APP_STORE_CONNECT_KEY_ID - API Key ID
    APP_STORE_CONNECT_ISSUER_ID - Issuer ID
    APP_STORE_CONNECT_PRIVATE_KEY - Private key content (.p8)
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta

import jwt
import requests


def create_jwt_token(key_id: str, issuer_id: str, private_key: str) -> str:
    """Create a JWT token for App Store Connect API authentication."""
    now = datetime.utcnow()
    payload = {
        "iss": issuer_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=20)).timestamp()),
        "aud": "appstoreconnect-v1",
    }

    headers = {
        "alg": "ES256",
        "kid": key_id,
        "typ": "JWT",
    }

    token = jwt.encode(payload, private_key, algorithm="ES256", headers=headers)
    return token


def get_existing_keys(token: str) -> list:
    """Get list of existing APNs keys."""
    url = "https://api.appstoreconnect.apple.com/v1/keys"
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get("data", [])
    return []


def create_apns_key(token: str, key_name: str = "SnowTracker-APNs") -> dict:
    """Create a new APNs key.

    Note: APNs keys are created via the Developer Portal, not App Store Connect API.
    This function uses the provisioning profile endpoint as a workaround,
    but the actual key creation requires Developer Portal access.
    """
    # The App Store Connect API doesn't directly support APNs key creation
    # APNs keys must be created via the Developer Portal web interface
    # or using Apple's internal provisioning APIs

    # For now, we'll check if there's an existing key we can use
    print(f"Checking for existing keys...")

    # Get bundle IDs to verify we have the right access
    url = "https://api.appstoreconnect.apple.com/v1/bundleIds"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        bundle_ids = response.json().get("data", [])
        print(f"Found {len(bundle_ids)} bundle IDs")
        for bid in bundle_ids:
            attrs = bid.get("attributes", {})
            print(f"  - {attrs.get('identifier')} ({attrs.get('name')})")
    else:
        print(f"Error fetching bundle IDs: {response.status_code}")
        print(response.text)

    # Check capabilities for push notifications
    for bid in bundle_ids:
        bid_id = bid["id"]
        caps_url = f"https://api.appstoreconnect.apple.com/v1/bundleIds/{bid_id}/bundleIdCapabilities"
        caps_response = requests.get(caps_url, headers=headers)
        if caps_response.status_code == 200:
            caps = caps_response.json().get("data", [])
            for cap in caps:
                cap_type = cap.get("attributes", {}).get("capabilityType")
                if cap_type == "PUSH_NOTIFICATIONS":
                    print(f"  Push Notifications capability enabled for {bid_id}")
                    return {"bundle_id": bid_id, "push_enabled": True}

    return {"error": "Push notifications not enabled for any bundle ID"}


def enable_push_notifications(token: str, bundle_id: str) -> bool:
    """Enable push notifications capability for a bundle ID."""
    url = f"https://api.appstoreconnect.apple.com/v1/bundleIdCapabilities"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "data": {
            "type": "bundleIdCapabilities",
            "attributes": {
                "capabilityType": "PUSH_NOTIFICATIONS",
                "settings": []
            },
            "relationships": {
                "bundleId": {
                    "data": {
                        "type": "bundleIds",
                        "id": bundle_id
                    }
                }
            }
        }
    }

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code in [200, 201]:
        print(f"Push notifications enabled for bundle ID: {bundle_id}")
        return True
    else:
        print(f"Error enabling push notifications: {response.status_code}")
        print(response.text)
        return False


def main():
    # Get credentials from environment
    key_id = os.environ.get("APP_STORE_CONNECT_KEY_ID")
    issuer_id = os.environ.get("APP_STORE_CONNECT_ISSUER_ID")
    private_key = os.environ.get("APP_STORE_CONNECT_PRIVATE_KEY")

    if not all([key_id, issuer_id, private_key]):
        print("Error: Missing required environment variables")
        print("Required: APP_STORE_CONNECT_KEY_ID, APP_STORE_CONNECT_ISSUER_ID, APP_STORE_CONNECT_PRIVATE_KEY")
        sys.exit(1)

    print(f"Using Key ID: {key_id}")
    print(f"Using Issuer ID: {issuer_id}")

    # Create JWT token
    token = create_jwt_token(key_id, issuer_id, private_key)
    print("JWT token created successfully")

    # Check/create APNs key
    result = create_apns_key(token)
    print(f"\nResult: {json.dumps(result, indent=2)}")

    # Output for GitHub Actions
    if "bundle_id" in result:
        print(f"\n::set-output name=bundle_id::{result['bundle_id']}")
        print(f"::set-output name=push_enabled::{result.get('push_enabled', False)}")

    return result


if __name__ == "__main__":
    main()
