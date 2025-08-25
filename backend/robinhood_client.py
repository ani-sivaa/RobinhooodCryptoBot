import base64
import datetime
import json
from typing import Any, Dict, Optional, List
import uuid
import requests
from nacl.signing import SigningKey
import time
import logging

logger = logging.getLogger(__name__)

class RobinhoodClient:
    """
    Official Robinhood API client for cryptocurrency trading
    Following the documentation at https://docs.robinhood.com/crypto/trading/
    """
    
    def __init__(self, api_key: str, private_key_base64: str):
        self.api_key = api_key
        private_key_seed = base64.b64decode(private_key_base64)
        self.private_key = SigningKey(private_key_seed)
        self.base_url = "https://trading.robinhood.com"
        self.last_request_time = 0
        self.min_request_interval = 0.6  # Rate limiting: 100 req/min
    
    def _rate_limit(self):
        """Ensure we don't exceed rate limits"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last)
        self.last_request_time = time.time()
    
    def _generate_signature(self, method: str, path: str, body: str, timestamp: str) -> str:
        """Generate Ed25519 signature for API authentication"""
        message = f"{method}|{path}|{body}|{timestamp}"
        signature = self.private_key.sign(message.encode()).signature
        return base64.b64encode(signature).decode()
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Make authenticated request to Robinhood API"""
        self._rate_limit()
        
        url = f"{self.base_url}{endpoint}"
        timestamp = str(int(datetime.datetime.now().timestamp()))
        body = json.dumps(data) if data else ""
        
        signature = self._generate_signature(method, endpoint, body, timestamp)
        
        headers = {
            "x-api-key": self.api_key,
            "x-signature": signature,
            "x-timestamp": timestamp,
            "Content-Type": "application/json"
        }
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=30)
            elif method == "POST":
                response = requests.post(url, headers=headers, data=body, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise
    
    def get_account(self) -> Dict:
        """Get account information"""
        return self._make_request("GET", "/api/v1/crypto/trading/accounts/")
    
    def get_holdings(self) -> List[Dict]:
        """Get current crypto holdings"""
        return self._make_request("GET", "/api/v1/crypto/trading/holdings/")
    
    def get_trading_pairs(self) -> List[Dict]:
        """Get available trading pairs"""
        return self._make_request("GET", "/api/v1/crypto/trading/trading_pairs/")
    
    def get_best_bid_ask(self, trading_pair_ids: List[str]) -> List[Dict]:
        """Get best bid/ask prices for trading pairs"""
        params = {"trading_pair_ids": ",".join(trading_pair_ids)}
        endpoint = f"/api/v1/crypto/trading/best_bid_ask/?{requests.compat.urlencode(params)}"
        return self._make_request("GET", endpoint)
    
    def get_estimated_price(self, trading_pair_id: str, side: str, quantity: str) -> Dict:
        """Get estimated price for a trade"""
        params = {
            "trading_pair_id": trading_pair_id,
            "side": side,
            "quantity": quantity
        }
        endpoint = f"/api/v1/crypto/trading/estimated_price/?{requests.compat.urlencode(params)}"
        return self._make_request("GET", endpoint)
    
    def place_order(self, order_data: Dict) -> Dict:
        """Place a new crypto order"""
        return self._make_request("POST", "/api/v1/crypto/trading/orders/", order_data)
    
    def get_orders(self, limit: int = 20) -> List[Dict]:
        """Get order history"""
        params = {"limit": limit}
        endpoint = f"/api/v1/crypto/trading/orders/?{requests.compat.urlencode(params)}"
        return self._make_request("GET", endpoint)
    
    def cancel_order(self, order_id: str) -> Dict:
        """Cancel an open order"""
        return self._make_request("POST", f"/api/v1/crypto/trading/orders/{order_id}/cancel/")
    
    def create_market_order(self, symbol: str, side: str, quote_amount: float) -> Dict:
        """Create a market order with quote amount (USD)"""
        order_data = {
            "client_order_id": str(uuid.uuid4()),
            "side": side,
            "type": "market",
            "market_order_config": {
                "quote_amount": str(quote_amount)
            },
            "symbol": symbol
        }
        return self.place_order(order_data)
    
    def create_limit_order(self, symbol: str, side: str, asset_quantity: float, limit_price: float) -> Dict:
        """Create a limit order"""
        order_data = {
            "client_order_id": str(uuid.uuid4()),
            "side": side,
            "type": "limit",
            "limit_order_config": {
                "asset_quantity": str(asset_quantity),
                "limit_price": str(limit_price),
                "time_in_force": "gtc"
            },
            "symbol": symbol
        }
        return self.place_order(order_data)
    
    def create_stop_loss_order(self, symbol: str, side: str, asset_quantity: float, stop_price: float) -> Dict:
        """Create a stop loss order"""
        order_data = {
            "client_order_id": str(uuid.uuid4()),
            "side": side,
            "type": "stop_loss",
            "stop_loss_order_config": {
                "asset_quantity": str(asset_quantity),
                "stop_price": str(stop_price),
                "time_in_force": "gtc"
            },
            "symbol": symbol
        }
        return self.place_order(order_data)
