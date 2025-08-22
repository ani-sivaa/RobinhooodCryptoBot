#!/usr/bin/env python3
"""
Robinhood API Connection Test Script
Tests API configuration without making any trades
"""

import asyncio
import aiohttp
import os
import time
import base64
import json
from datetime import datetime
from dotenv import load_dotenv
import nacl.signing

# Load environment variables
load_dotenv()

class RobinhoodAPITester:
    def __init__(self):
        self.api_key = os.getenv('ROBINHOOD_API_KEY')
        self.private_key = os.getenv('ROBINHOOD_PRIVATE_KEY')
        self.base_url = os.getenv('ROBINHOOD_API_URL', 'https://api.robinhood.com')
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def _create_headers(self, method: str, endpoint: str, body: dict = None):
        """Create Ed25519 signed headers for API requests"""
        if not self.api_key or not self.private_key:
            return {}
            
        # Create timestamp
        timestamp = str(int(time.time()))
        
        # Create message to sign: api_key + timestamp + path + method + body (from docs)
        # NOTE: Robinhood uses Python dict string representation, not JSON!
        body_str = ""
        if body:
            body_str = str(body)  # Python dict representation, not JSON
        
        message = f"{self.api_key}{timestamp}{endpoint}{method.upper()}{body_str}"
        
        try:
            # Decode the base64 private key and sign
            private_key_bytes = base64.b64decode(self.private_key)
            signing_key = nacl.signing.SigningKey(private_key_bytes)
            signed_message = signing_key.sign(message.encode('utf-8'))
            signature = base64.b64encode(signed_message.signature).decode('utf-8')
            
            return {
                'x-api-key': self.api_key,
                'x-timestamp': timestamp,
                'x-signature': signature,
                'Content-Type': 'application/json; charset=utf-8',
                'User-Agent': 'RobinhoodAPITester/1.0'
            }
        except Exception as e:
            print(f"❌ Error creating signature: {e}")
            return {}
    
    async def test_authentication(self):
        """Test if API key is valid"""
        print("🔐 Testing API Authentication...")
        
        if not self.api_key:
            print("❌ ROBINHOOD_API_KEY not found in environment")
            return False
            
        if not self.private_key:
            print("❌ ROBINHOOD_PRIVATE_KEY not found in environment")
            return False
            
        print(f"✅ API Key found: {self.api_key[:20]}...")
        print(f"✅ Private Key found: {self.private_key[:20]}...")
        
        # Test basic auth with crypto trading accounts endpoint (from official docs)
        endpoint = "/api/v1/crypto/trading/accounts/"
        headers = self._create_headers("GET", endpoint)
        
        if not headers:
            print("❌ Failed to create authentication headers")
            return False
        
        try:
            async with self.session.get(f"{self.base_url}{endpoint}", headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Authentication successful")
                    if 'username' in data:
                        print(f"   Username: {data.get('username')}")
                    return True
                else:
                    print(f"❌ Authentication failed: HTTP {response.status}")
                    error_text = await response.text()
                    print(f"   Error: {error_text[:200]}...")
                    return False
                    
        except Exception as e:
            print(f"❌ Authentication test failed: {e}")
            return False
    
    async def test_account_info(self):
        """Test fetching account information"""
        print("\n👤 Testing Account Information...")
        
        endpoints_to_test = [
            ("/accounts/", "Account Details"),
            ("/user/", "User Profile"),
            ("/user/basic_info/", "Basic Info")
        ]
        
        for endpoint, description in endpoints_to_test:
            try:
                headers = self._create_headers("GET", endpoint)
                async with self.session.get(f"{self.base_url}{endpoint}", headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ {description}: Success")
                        
                        # Print relevant info
                        if endpoint == "/accounts/":
                            if isinstance(data, dict) and 'results' in data:
                                accounts = data['results']
                                if accounts:
                                    account = accounts[0]
                                    print(f"   Account Type: {account.get('type', 'N/A')}")
                                    print(f"   Account Status: {account.get('state', 'N/A')}")
                        
                    else:
                        print(f"❌ {description}: HTTP {response.status}")
                        
            except Exception as e:
                print(f"❌ {description}: {e}")
    
    async def test_portfolio_endpoints(self):
        """Test different portfolio endpoints"""
        print("\n💰 Testing Portfolio Endpoints...")
        
        portfolio_endpoints = [
            # Official Robinhood Crypto API endpoints from docs
            ("/api/v1/crypto/trading/accounts/", "Crypto Trading Accounts"),
            ("/api/v1/crypto/trading/holdings/", "Crypto Holdings"),
            ("/api/v1/crypto/trading/orders/", "Crypto Orders"),
            ("/api/v1/crypto/trading/trading_pairs/", "Trading Pairs"),
            ("/api/v1/crypto/marketdata/best_bid_ask/", "Best Bid Ask"),
        ]
        
        working_endpoints = []
        
        for endpoint, description in portfolio_endpoints:
            try:
                headers = self._create_headers("GET", endpoint)
                async with self.session.get(f"{self.base_url}{endpoint}", headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ {description}: Success")
                        working_endpoints.append((endpoint, description))
                        
                        # Show some data structure
                        if isinstance(data, dict):
                            if 'results' in data:
                                print(f"   Results count: {len(data['results'])}")
                            elif 'count' in data:
                                print(f"   Count: {data['count']}")
                                
                    elif response.status == 404:
                        print(f"❌ {description}: Not Found (404)")
                    elif response.status == 401:
                        print(f"❌ {description}: Unauthorized (401)")
                    elif response.status == 403:
                        print(f"❌ {description}: Forbidden (403)")
                    else:
                        print(f"❌ {description}: HTTP {response.status}")
                        
            except Exception as e:
                print(f"❌ {description}: {e}")
        
        print(f"\n📊 Working endpoints: {len(working_endpoints)}")
        for endpoint, desc in working_endpoints:
            print(f"   {endpoint} - {desc}")
    
    async def test_market_data(self):
        """Test fetching market data"""
        print("\n📈 Testing Market Data...")
        
        symbols = ["BTC-USD", "ETH-USD", "DOGE-USD"]  # Robinhood crypto symbols
        
        for symbol in symbols:
            try:
                # Use official Robinhood crypto market data endpoint
                endpoint = f"/api/v1/crypto/marketdata/best_bid_ask/"
                headers = self._create_headers("GET", endpoint)
                params = {"symbol": symbol}
                
                async with self.session.get(f"{self.base_url}{endpoint}", headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ {symbol} market data: Success")
                        
                        if 'results' in data and data['results']:
                            result = data['results'][0] 
                            ask_price = result.get('ask_price', 'N/A')
                            bid_price = result.get('bid_price', 'N/A')
                            print(f"   Ask: ${ask_price}, Bid: ${bid_price}")
                        
                    else:
                        print(f"❌ {symbol} market data: HTTP {response.status}")
                        
            except Exception as e:
                print(f"❌ {symbol} market data: {e}")
    
    async def run_all_tests(self):
        """Run all API tests"""
        print("🚀 Starting Robinhood API Configuration Test\n")
        print(f"Base URL: {self.base_url}")
        print(f"Timestamp: {datetime.now()}\n")
        
        # Test authentication first
        auth_success = await self.test_authentication()
        
        if auth_success:
            await self.test_account_info()
            await self.test_portfolio_endpoints()
            await self.test_market_data()
        else:
            print("\n❌ Authentication failed - skipping other tests")
            print("\nPlease check:")
            print("1. ROBINHOOD_API_KEY is valid")
            print("2. API key has proper permissions")
            print("3. Robinhood account is active")
        
        print("\n✅ Test completed!")

async def main():
    async with RobinhoodAPITester() as tester:
        await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())