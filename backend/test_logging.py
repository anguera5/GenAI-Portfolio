#!/usr/bin/env python3
"""
Demonstration script to test backend logging functionality.
This script makes sample API calls to demonstrate the logging output.
"""

import requests
import json
import time

# Configuration
BASE_URL = "http://localhost:8000"
API_KEY = "test-key"  # Replace with actual API key for real testing

def print_section(title):
    """Print a section header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60 + "\n")

def test_root_endpoint():
    """Test the root endpoint."""
    print_section("Test 1: Root Endpoint")
    try:
        response = requests.get(f"{BASE_URL}/api/")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        print("\n✓ Check backend logs for [REQUEST] and [RESPONSE] entries")
    except Exception as e:
        print(f"Error: {e}")

def test_generate_code():
    """Test the code generation endpoint."""
    print_section("Test 2: Generate Code Endpoint")
    payload = {
        "prompt": "Create a function to calculate fibonacci numbers",
        "language": "python",
        "api_key": API_KEY
    }
    try:
        print(f"Sending request to /api/generate...")
        response = requests.post(
            f"{BASE_URL}/api/generate",
            json=payload,
            timeout=30
        )
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            code = result.get("code", "")
            print(f"Generated {len(code)} characters of code")
            print("\n✓ Check backend logs for:")
            print("  - [USER_ACTION][generate] entry")
            print("  - [SUCCESS][generate] entry")
        else:
            print(f"Error Response: {response.text}")
            print("\n✓ Check backend logs for [ERROR][generate] entry")
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        print("\n✓ Check backend logs for error with stack trace")

def test_invalid_endpoint():
    """Test an invalid endpoint to trigger 404."""
    print_section("Test 3: Invalid Endpoint (404)")
    try:
        response = requests.get(f"{BASE_URL}/api/nonexistent")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        print("\n✓ Check backend logs for [REQUEST] with status=404")
    except Exception as e:
        print(f"Error: {e}")

def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("  Backend Logging Demonstration")
    print("=" * 60)
    print("\nThis script demonstrates the logging functionality.")
    print("Watch the backend logs in another terminal:")
    print("  tail -f /var/log/genai-portfolio/app.log")
    print("\nPress Enter to continue...")
    input()
    
    # Test 1: Root endpoint
    test_root_endpoint()
    time.sleep(1)
    
    # Test 2: Generate code (will fail without valid API key)
    test_generate_code()
    time.sleep(1)
    
    # Test 3: Invalid endpoint
    test_invalid_endpoint()
    
    print("\n" + "=" * 60)
    print("  Demonstration Complete!")
    print("=" * 60)
    print("\nReview the backend logs to see:")
    print("  1. Request IDs and metadata")
    print("  2. User action logging")
    print("  3. Success/error logging")
    print("  4. Request duration tracking")
    print("  5. Error stack traces (if any)")
    print("\n")

if __name__ == "__main__":
    main()
