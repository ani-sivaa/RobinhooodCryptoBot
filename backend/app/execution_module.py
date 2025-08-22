import asyncio
import aiohttp
import time
import base64
from typing import Optional, Dict, List
from datetime import datetime
import logging
import nacl.signing
from .models import Trade, OrderType, OrderSide, OrderStatus, Portfolio
from .config import settings

logger = logging.getLogger(__name__)

class ExecutionModule:
    """
    Execution Module component - places and manages trades on Robinhood
    via the API as recommended in the research report.
    """
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.base_url = settings.robinhood_api_url
        self.api_key = settings.robinhood_api_key
        self.private_key = settings.robinhood_private_key
        
        self.rate_limit_requests = 100
        self.rate_limit_window = 60  # seconds
        self.request_timestamps = []
        
        self.paper_trades = []
        self.paper_portfolio = {
            "cash": settings.trading_budget,
            "positions": {},
            "total_value": settings.trading_budget
        }
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def place_order(
        self, 
        symbol: str, 
        side: OrderSide, 
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None
    ) -> Trade:
        """Place a trade order"""
        
        if settings.paper_trading_mode:
            return await self._place_paper_order(symbol, side, order_type, quantity, price, stop_price)
        else:
            return await self._place_real_order(symbol, side, order_type, quantity, price, stop_price)
    
    async def _place_paper_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None
    ) -> Trade:
        """Simulate order placement for paper trading"""
        
        order_id = f"paper_{int(time.time())}_{len(self.paper_trades)}"
        
        if order_type == OrderType.MARKET:
            execution_price = price or 50000.0  # Default BTC price for simulation
        else:
            execution_price = price
        
        trade = Trade(
            id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            status=OrderStatus.FILLED,  # Assume immediate fill for paper trading
            timestamp=datetime.now(),
            filled_price=execution_price,
            filled_quantity=quantity
        )
        
        if side == OrderSide.BUY:
            cost = quantity * execution_price
            if self.paper_portfolio["cash"] >= cost:
                self.paper_portfolio["cash"] -= cost
                current_position = self.paper_portfolio["positions"].get(symbol, 0)
                self.paper_portfolio["positions"][symbol] = current_position + quantity
                logger.info(f"Paper trade executed: BUY {quantity} {symbol} @ ${execution_price}")
            else:
                trade.status = OrderStatus.REJECTED
                logger.warning(f"Paper trade rejected: Insufficient funds")
        
        elif side == OrderSide.SELL:
            current_position = self.paper_portfolio["positions"].get(symbol, 0)
            if current_position >= quantity:
                proceeds = quantity * execution_price
                self.paper_portfolio["cash"] += proceeds
                self.paper_portfolio["positions"][symbol] = current_position - quantity
                logger.info(f"Paper trade executed: SELL {quantity} {symbol} @ ${execution_price}")
            else:
                trade.status = OrderStatus.REJECTED
                logger.warning(f"Paper trade rejected: Insufficient {symbol} position")
        
        self.paper_portfolio["total_value"] = self.paper_portfolio["cash"]
        for pos_symbol, pos_quantity in self.paper_portfolio["positions"].items():
            self.paper_portfolio["total_value"] += pos_quantity * execution_price
        
        self.paper_trades.append(trade)
        return trade
    
    async def _place_real_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None
    ) -> Trade:
        """Place actual order via Robinhood API"""
        
        if not self.api_key or not self.private_key:
            logger.error("Robinhood API credentials not configured")
            return Trade(
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                status=OrderStatus.REJECTED,
                timestamp=datetime.now()
            )
        
        if not await self._check_rate_limit():
            logger.warning("Rate limit exceeded, delaying order")
            await asyncio.sleep(1)
        
        try:
            order_data = {
                "symbol": symbol,
                "side": side.value,
                "type": order_type.value,
                "quantity": str(quantity)
            }
            
            if price:
                order_data["price"] = str(price)
            if stop_price:
                order_data["stop_price"] = str(stop_price)
            
            endpoint = "/api/v1/crypto/orders/"
            headers = self._create_auth_headers("POST", endpoint, order_data)
            
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            async with self.session.post(
                f"{self.base_url}{endpoint}",
                json=order_data,
                headers=headers
            ) as response:
                
                if response.status == 201:
                    result = await response.json()
                    
                    return Trade(
                        id=result.get("id"),
                        symbol=symbol,
                        side=side,
                        order_type=order_type,
                        quantity=quantity,
                        price=price,
                        status=OrderStatus.PENDING,
                        timestamp=datetime.now()
                    )
                else:
                    error_text = await response.text()
                    logger.error(f"Order placement failed: {response.status} - {error_text}")
                    
                    return Trade(
                        symbol=symbol,
                        side=side,
                        order_type=order_type,
                        quantity=quantity,
                        price=price,
                        status=OrderStatus.REJECTED,
                        timestamp=datetime.now()
                    )
        
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return Trade(
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                status=OrderStatus.REJECTED,
                timestamp=datetime.now()
            )
    
    async def get_portfolio(self) -> Portfolio:
        """Get current portfolio status"""
        
        if settings.paper_trading_mode:
            return Portfolio(
                total_value=self.paper_portfolio["total_value"],
                available_cash=self.paper_portfolio["cash"],
                positions=self.paper_portfolio["positions"].copy(),
                daily_pnl=0.0,  # Would calculate based on daily changes
                total_pnl=self.paper_portfolio["total_value"] - settings.trading_budget,
                last_updated=datetime.now()
            )
        else:
            return await self._get_real_portfolio()
    
    async def _get_real_portfolio(self) -> Portfolio:
        """Get portfolio from Robinhood API"""
        
        try:
            if not await self._check_rate_limit():
                await asyncio.sleep(1)
            
            endpoint = "/api/v1/crypto/trading/accounts/"
            headers = self._create_auth_headers("GET", endpoint)
            
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            async with self.session.get(
                f"{self.base_url}{endpoint}",
                headers=headers
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    
                    return Portfolio(
                        total_value=float(data.get("total_equity", 0)),
                        available_cash=float(data.get("buying_power", 0)),
                        positions={},  # Would parse positions from API response
                        daily_pnl=float(data.get("total_return_today", 0)),
                        total_pnl=float(data.get("total_return", 0)),
                        last_updated=datetime.now()
                    )
                else:
                    logger.error(f"Failed to fetch portfolio: {response.status}")
                    return Portfolio(
                        total_value=settings.trading_budget,
                        available_cash=settings.trading_budget,
                        positions={},
                        daily_pnl=0.0,
                        total_pnl=0.0,
                        last_updated=datetime.now()
                    )
        
        except Exception as e:
            logger.error(f"Error fetching portfolio: {e}")
            return Portfolio(
                total_value=settings.trading_budget,
                available_cash=settings.trading_budget,
                positions={},
                daily_pnl=0.0,
                total_pnl=0.0,
                last_updated=datetime.now()
            )
    
    async def get_order_status(self, order_id: str) -> OrderStatus:
        """Get the status of a specific order"""
        
        if settings.paper_trading_mode:
            return OrderStatus.FILLED
        
        try:
            if not await self._check_rate_limit():
                await asyncio.sleep(1)
            
            endpoint = f"/api/v1/crypto/orders/{order_id}/"
            headers = self._create_auth_headers("GET", endpoint)
            
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            async with self.session.get(
                f"{self.base_url}{endpoint}",
                headers=headers
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    status_map = {
                        "pending": OrderStatus.PENDING,
                        "filled": OrderStatus.FILLED,
                        "cancelled": OrderStatus.CANCELLED,
                        "rejected": OrderStatus.REJECTED
                    }
                    return status_map.get(data.get("state", "pending"), OrderStatus.PENDING)
                else:
                    logger.error(f"Failed to fetch order status: {response.status}")
                    return OrderStatus.PENDING
        
        except Exception as e:
            logger.error(f"Error fetching order status: {e}")
            return OrderStatus.PENDING
    
    def _create_auth_headers(self, method: str, endpoint: str, body: Dict = None) -> Dict[str, str]:
        """Create authenticated headers for Robinhood API (Ed25519 signing)"""
        
        # Create timestamp (current time in seconds)
        timestamp = str(int(time.time()))
        
        # Create message to sign: api_key + timestamp + path + method + body (from Robinhood docs)
        # NOTE: Robinhood uses Python dict string representation, not JSON!
        body_str = ""
        if body:
            body_str = str(body)  # Python dict representation, not JSON
        
        message = f"{self.api_key}{timestamp}{endpoint}{method.upper()}{body_str}"
        
        # Create Ed25519 signature
        try:
            # Decode the base64 private key
            private_key_bytes = base64.b64decode(self.private_key)
            signing_key = nacl.signing.SigningKey(private_key_bytes)
            
            # Sign the message
            signed_message = signing_key.sign(message.encode('utf-8'))
            signature = base64.b64encode(signed_message.signature).decode('utf-8')
            
        except Exception as e:
            logger.error(f"Error creating Ed25519 signature: {e}")
            raise
        
        return {
            'x-api-key': self.api_key,
            'x-timestamp': timestamp,
            'x-signature': signature,
            'Content-Type': 'application/json; charset=utf-8'
        }
    
    async def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits (100 requests per minute)"""
        current_time = time.time()
        
        self.request_timestamps = [
            ts for ts in self.request_timestamps 
            if current_time - ts < self.rate_limit_window
        ]
        
        if len(self.request_timestamps) < self.rate_limit_requests:
            self.request_timestamps.append(current_time)
            return True
        
        return False
    
    def get_trade_history(self) -> List[Trade]:
        """Get trade history"""
        if settings.paper_trading_mode:
            return self.paper_trades.copy()
        else:
            return []
