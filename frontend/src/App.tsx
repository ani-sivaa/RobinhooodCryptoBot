import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './components/ui/card';
import { Button } from './components/ui/button';
import { Badge } from './components/ui/badge';
import { Alert, AlertDescription } from './components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './components/ui/tabs';
import { Input } from './components/ui/input';
import { Label } from './components/ui/label';
import { 
  Tooltip, 
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell
} from 'recharts';
import { 
  Play, 
  Square, 
  AlertTriangle, 
  DollarSign,
  Activity,
  Settings
} from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface BotStatus {
  is_running: boolean;
  paper_trading_mode: boolean;
  portfolio?: Portfolio;
  risk_metrics?: RiskMetrics;
  last_analysis?: Record<string, any>;
}

interface Portfolio {
  total_value: number;
  available_cash: number;
  positions: Record<string, number>;
  daily_pnl: number;
  total_pnl: number;
  last_updated: string;
}

interface Trade {
  id?: string;
  symbol: string;
  side: string;
  order_type: string;
  quantity: number;
  price?: number;
  filled_price?: number;
  filled_quantity?: number;
  status: string;
  timestamp: string;
}

interface NewsItem {
  title: string;
  content: string;
  source: string;
  sentiment: string;
  timestamp: string;
}

interface RiskMetrics {
  daily_trades_count: number;
  daily_trades_limit: number;
  daily_loss: number;
  daily_loss_limit: number;
  daily_loss_percentage: number;
  available_cash: number;
  portfolio_value: number;
  max_trade_value: number;
  risk_level: string;
  trading_enabled: boolean;
}

function App() {
  const [botStatus, setBotStatus] = useState<BotStatus | null>(null);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [riskMetrics, setRiskMetrics] = useState<RiskMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [systemErrors, setSystemErrors] = useState<any[]>([]);
  
  // Authentication state
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [sessionToken, setSessionToken] = useState<string | null>(localStorage.getItem('sessionToken'));
  const [loginPassword, setLoginPassword] = useState('');
  
  const [manualTrade, setManualTrade] = useState({
    symbol: 'dogecoin',
    side: 'buy',
    quantity: 100,
    order_type: 'market'
  });
  
  const [strategyConfig, setStrategyConfig] = useState({
    parameters: {
      rsi_oversold: 30,
      rsi_overbought: 70,
      macd_threshold: 0.001,
      confidence_threshold: 0.6
    },
    risk_limits: {
      max_position_size: 0.1,
      stop_loss_pct: 0.02,
      take_profit_pct: 0.05
    },
    enabled: true,
    name: 'combined'
  });

  const login = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: loginPassword })
      });
      
      if (response.ok) {
        const data = await response.json();
        setSessionToken(data.token);
        setIsLoggedIn(true);
        localStorage.setItem('sessionToken', data.token);
        setLoginPassword('');
        setError(null);
        await loadInitialData();
      } else {
        setError('Invalid password');
      }
    } catch (err) {
      setError('Login failed: ' + (err as Error).message);
    }
  };

  const logout = async () => {
    try {
      if (sessionToken) {
        await fetch(`${API_BASE_URL}/api/logout`, {
          method: 'POST',
          headers: { 'Authorization': sessionToken }
        });
      }
    } catch (err) {
      console.error('Logout error:', err);
    } finally {
      setSessionToken(null);
      setIsLoggedIn(false);
      localStorage.removeItem('sessionToken');
    }
  };

  const fetchBotStatus = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/status`);
      if (response.ok) {
        const data = await response.json();
        setBotStatus(data);
        setPortfolio(data.portfolio);
        setRiskMetrics(data.risk_metrics);
      }
    } catch (err) {
      console.error('Error fetching bot status:', err);
    }
  };

  const fetchTrades = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/trades`);
      if (response.ok) {
        const data = await response.json();
        setTrades(data);
      }
    } catch (err) {
      console.error('Error fetching trades:', err);
    }
  };

  const fetchNews = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/news?limit=10`);
      if (response.ok) {
        const data = await response.json();
        setNews(data);
      }
    } catch (err) {
      console.error('Error fetching news:', err);
    }
  };

  const fetchSystemErrors = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/errors`);
      if (response.ok) {
        const data = await response.json();
        setSystemErrors(data);
      }
    } catch (err) {
      console.error('Error fetching system errors:', err);
    }
  };

  const resolveError = async (errorId: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/errors/resolve/${errorId}`, {
        method: 'POST'
      });
      if (response.ok) {
        await fetchSystemErrors();
      }
    } catch (err) {
      console.error('Error resolving error:', err);
    }
  };

  const startBot = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/start`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': sessionToken || ''
        },
        body: JSON.stringify({ symbols: ['bitcoin', 'ethereum', 'cardano', 'solana'] })
      });
      
      if (response.ok) {
        await fetchBotStatus();
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to start bot');
      }
    } catch (err) {
      setError('Error starting bot: ' + (err as Error).message);
    }
  };

  const stopBot = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/stop`, { 
        method: 'POST',
        headers: { 'Authorization': sessionToken || '' }
      });
      if (response.ok) {
        await fetchBotStatus();
      }
    } catch (err) {
      setError('Error stopping bot: ' + (err as Error).message);
    }
  };

  const emergencyStop = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/emergency-stop`, { 
        method: 'POST',
        headers: { 'Authorization': sessionToken || '' }
      });
      if (response.ok) {
        await fetchBotStatus();
      }
    } catch (err) {
      setError('Error in emergency stop: ' + (err as Error).message);
    }
  };

  const executeManualTrade = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/trade/manual`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': sessionToken || ''
        },
        body: JSON.stringify(manualTrade)
      });
      
      if (response.ok) {
        await fetchTrades();
        await fetchBotStatus();
        setManualTrade({ ...manualTrade, quantity: 0.001 });
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to execute trade');
      }
    } catch (err) {
      setError('Error executing trade: ' + (err as Error).message);
    }
  };

  const updateStrategy = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/strategy/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(strategyConfig)
      });
      
      if (response.ok) {
        await fetchBotStatus();
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to update strategy');
      }
    } catch (err) {
      setError('Error updating strategy: ' + (err as Error).message);
    }
  };

  const loadInitialData = async () => {
    setLoading(true);
    await Promise.all([
      fetchBotStatus(),
      fetchTrades(),
      fetchNews(),
      fetchSystemErrors()
    ]);
    setLoading(false);
  };

  useEffect(() => {
    // Check if user is already logged in
    if (sessionToken) {
      setIsLoggedIn(true);
      loadInitialData();
    } else {
      setLoading(false);
    }

    let interval: NodeJS.Timeout;
    let newsInterval: NodeJS.Timeout;
    
    if (isLoggedIn) {
      interval = setInterval(() => {
        fetchBotStatus();
        fetchTrades();
        fetchSystemErrors();
      }, 10000);

      newsInterval = setInterval(fetchNews, 300000);
    }

    return () => {
      if (interval) clearInterval(interval);
      if (newsInterval) clearInterval(newsInterval);
    };
  }, [isLoggedIn, sessionToken]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Activity className="h-8 w-8 animate-spin mx-auto mb-4" />
          <p>Loading trading dashboard...</p>
        </div>
      </div>
    );
  }

  if (!isLoggedIn) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <CardTitle className="text-2xl">Trading Bot Login</CardTitle>
            <CardDescription>Enter your password to access the dashboard</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {error && (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && login()}
                placeholder="Enter your password"
              />
            </div>
            <Button onClick={login} className="w-full">
              Login
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const portfolioChartData = portfolio ? [
    { name: 'Cash', value: portfolio.available_cash, color: '#8884d8' },
    { name: 'Positions', value: portfolio.total_value - portfolio.available_cash, color: '#82ca9d' }
  ] : [];

  return (
    <div className="min-h-screen bg-gray-50 p-4">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Crypto Trading Bot Dashboard</h1>
            <p className="text-gray-600">Robinhood API Integration • $100 Budget</p>
          </div>
          
          <div className="flex space-x-2">
            <Button
              onClick={startBot}
              disabled={botStatus?.is_running}
              className="bg-green-600 hover:bg-green-700"
            >
              <Play className="h-4 w-4 mr-2" />
              Start Bot
            </Button>
            
            <Button
              onClick={stopBot}
              disabled={!botStatus?.is_running}
              variant="outline"
            >
              <Square className="h-4 w-4 mr-2" />
              Stop Bot
            </Button>
            
            <Button
              onClick={emergencyStop}
              variant="destructive"
            >
              <AlertTriangle className="h-4 w-4 mr-2" />
              Emergency Stop
            </Button>
            
            <Button
              onClick={logout}
              variant="outline"
              size="sm"
            >
              Logout
            </Button>
          </div>
        </div>

        {/* Error Alert */}
        {error && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
            <Button 
              variant="outline" 
              size="sm" 
              onClick={() => setError(null)}
              className="ml-auto"
            >
              Dismiss
            </Button>
          </Alert>
        )}

        {/* Status Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Bot Status</CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                <Badge variant={botStatus?.is_running ? "default" : "secondary"}>
                  {botStatus?.is_running ? "Running" : "Stopped"}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground">
                {botStatus?.paper_trading_mode ? "Paper Trading" : "Live Trading"}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Portfolio Value</CardTitle>
              <DollarSign className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                ${portfolio?.total_value?.toFixed(2) || '0.00'}
              </div>
              <p className="text-xs text-muted-foreground">
                P&L: ${portfolio?.total_pnl?.toFixed(2) || '0.00'}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Available Cash</CardTitle>
              <DollarSign className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                ${portfolio?.available_cash?.toFixed(2) || '0.00'}
              </div>
              <p className="text-xs text-muted-foreground">
                Ready to trade
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Risk Level</CardTitle>
              <AlertTriangle className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                <Badge variant={
                  riskMetrics?.risk_level === 'HIGH' ? 'destructive' :
                  riskMetrics?.risk_level === 'MEDIUM' ? 'default' : 'secondary'
                }>
                  {riskMetrics?.risk_level || 'LOW'}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground">
                Daily Loss: ${riskMetrics?.daily_loss?.toFixed(2) || '0.00'}
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Main Content Tabs */}
        <Tabs defaultValue="overview" className="space-y-4">
          <TabsList className="grid w-full grid-cols-6">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="trades">Trades</TabsTrigger>
            <TabsTrigger value="strategy">Strategy</TabsTrigger>
            <TabsTrigger value="news">News</TabsTrigger>
            <TabsTrigger value="manual">Manual Trade</TabsTrigger>
            <TabsTrigger value="logs">System Logs</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-4">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Portfolio Allocation */}
              <Card>
                <CardHeader>
                  <CardTitle>Portfolio Allocation</CardTitle>
                </CardHeader>
                <CardContent>
                  <ResponsiveContainer width="100%" height={300}>
                    <PieChart>
                      <Pie
                        data={portfolioChartData}
                        cx="50%"
                        cy="50%"
                        outerRadius={80}
                        fill="#8884d8"
                        dataKey="value"
                        label={({ name, value }) => `${name}: $${value.toFixed(2)}`}
                      >
                        {portfolioChartData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(value: number) => `$${value.toFixed(2)}`} />
                    </PieChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>

              {/* Current Positions */}
              <Card>
                <CardHeader>
                  <CardTitle>Current Positions</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {portfolio?.positions && Object.keys(portfolio.positions).length > 0 ? (
                      Object.entries(portfolio.positions).map(([symbol, quantity]) => (
                        <div key={symbol} className="flex justify-between items-center p-2 bg-gray-50 rounded">
                          <span className="font-medium">{symbol.toUpperCase()}</span>
                          <span>{quantity.toFixed(6)}</span>
                        </div>
                      ))
                    ) : (
                      <p className="text-gray-500 text-center py-4">No positions</p>
                    )}
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Market Analysis */}
            <Card>
              <CardHeader>
                <CardTitle>Latest Market Analysis</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  {botStatus?.last_analysis && Object.entries(botStatus.last_analysis).map(([symbol, analysis]: [string, any]) => (
                    <div key={symbol} className="p-4 border rounded-lg">
                      <h4 className="font-semibold mb-2">{symbol.toUpperCase()}</h4>
                      <div className="space-y-1 text-sm">
                        <div className="flex justify-between">
                          <span>Signal:</span>
                          <Badge variant={
                            analysis.signal === 'buy' ? 'default' :
                            analysis.signal === 'sell' ? 'destructive' : 'secondary'
                          }>
                            {analysis.signal?.toUpperCase()}
                          </Badge>
                        </div>
                        <div className="flex justify-between">
                          <span>Confidence:</span>
                          <span>{(analysis.confidence * 100).toFixed(1)}%</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Price:</span>
                          <span>${analysis.price?.toFixed(2)}</span>
                        </div>
                        <p className="text-xs text-gray-600 mt-2">{analysis.reasoning}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="trades" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Trade History</CardTitle>
                <CardDescription>Recent trading activity</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {trades.length > 0 ? (
                    trades.slice(0, 20).map((trade, index) => (
                      <div key={index} className="flex justify-between items-center p-3 border rounded-lg">
                        <div className="flex items-center space-x-3">
                          <Badge variant={trade.side === 'buy' ? 'default' : 'destructive'}>
                            {trade.side.toUpperCase()}
                          </Badge>
                          <span className="font-medium">{trade.symbol.toUpperCase()}</span>
                          <span>{trade.quantity.toFixed(6)}</span>
                        </div>
                        <div className="text-right">
                          <div className="font-medium">${trade.filled_price?.toFixed(2) || trade.price?.toFixed(2)}</div>
                          <div className="text-sm text-gray-500">
                            {new Date(trade.timestamp).toLocaleString()}
                          </div>
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="text-gray-500 text-center py-8">No trades yet</p>
                  )}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="strategy" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Strategy Configuration</CardTitle>
                <CardDescription>Adjust trading parameters in real-time</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-3">
                    <h4 className="font-semibold">Technical Indicators</h4>
                    <div className="space-y-2">
                      <div>
                        <Label htmlFor="rsi_oversold">RSI Oversold Threshold</Label>
                        <Input
                          id="rsi_oversold"
                          type="number"
                          value={strategyConfig.parameters.rsi_oversold}
                          onChange={(e) => setStrategyConfig({
                            ...strategyConfig,
                            parameters: {
                              ...strategyConfig.parameters,
                              rsi_oversold: parseFloat(e.target.value)
                            }
                          })}
                        />
                      </div>
                      <div>
                        <Label htmlFor="rsi_overbought">RSI Overbought Threshold</Label>
                        <Input
                          id="rsi_overbought"
                          type="number"
                          value={strategyConfig.parameters.rsi_overbought}
                          onChange={(e) => setStrategyConfig({
                            ...strategyConfig,
                            parameters: {
                              ...strategyConfig.parameters,
                              rsi_overbought: parseFloat(e.target.value)
                            }
                          })}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="space-y-3">
                    <h4 className="font-semibold">Risk Management</h4>
                    <div className="space-y-2">
                      <div>
                        <Label htmlFor="max_position_size">Max Position Size (%)</Label>
                        <Input
                          id="max_position_size"
                          type="number"
                          step="0.01"
                          value={strategyConfig.risk_limits.max_position_size * 100}
                          onChange={(e) => setStrategyConfig({
                            ...strategyConfig,
                            risk_limits: {
                              ...strategyConfig.risk_limits,
                              max_position_size: parseFloat(e.target.value) / 100
                            }
                          })}
                        />
                      </div>
                      <div>
                        <Label htmlFor="stop_loss_pct">Stop Loss (%)</Label>
                        <Input
                          id="stop_loss_pct"
                          type="number"
                          step="0.01"
                          value={strategyConfig.risk_limits.stop_loss_pct * 100}
                          onChange={(e) => setStrategyConfig({
                            ...strategyConfig,
                            risk_limits: {
                              ...strategyConfig.risk_limits,
                              stop_loss_pct: parseFloat(e.target.value) / 100
                            }
                          })}
                        />
                      </div>
                    </div>
                  </div>
                </div>

                <Button onClick={updateStrategy} className="w-full">
                  <Settings className="h-4 w-4 mr-2" />
                  Update Strategy
                </Button>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="news" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Crypto News Feed</CardTitle>
                <CardDescription>Latest cryptocurrency market news</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {news.length > 0 ? (
                    news.map((item, index) => (
                      <div key={index} className="p-4 border rounded-lg">
                        <div className="flex justify-between items-start mb-2">
                          <h4 className="font-semibold text-sm">{item.title}</h4>
                          <Badge variant={
                            item.sentiment === 'positive' ? 'default' :
                            item.sentiment === 'negative' ? 'destructive' : 'secondary'
                          }>
                            {item.sentiment}
                          </Badge>
                        </div>
                        <p className="text-sm text-gray-600 mb-2">{item.content}</p>
                        <div className="flex justify-between text-xs text-gray-500">
                          <span>{item.source}</span>
                          <span>{new Date(item.timestamp).toLocaleString()}</span>
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="text-gray-500 text-center py-8">No news available</p>
                  )}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="manual" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Manual Trade Execution</CardTitle>
                <CardDescription>Execute trades manually with risk validation</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="trade_symbol">Symbol</Label>
                    <select
                      id="trade_symbol"
                      className="w-full p-2 border rounded"
                      value={manualTrade.symbol}
                      onChange={(e) => setManualTrade({...manualTrade, symbol: e.target.value})}
                    >
                      <option value="dogecoin">Dogecoin (~$0.08 - Cheapest)</option>
                      <option value="cardano">Cardano (~$0.35)</option>
                      <option value="stellar">Stellar (~$0.09)</option>
                      <option value="polygon">Polygon (~$0.40)</option>
                      <option value="solana">Solana (~$20)</option>
                      <option value="ethereum">Ethereum (~$2,400)</option>
                      <option value="bitcoin">Bitcoin (~$35,000)</option>
                    </select>
                  </div>

                  <div>
                    <Label htmlFor="trade_side">Side</Label>
                    <select
                      id="trade_side"
                      className="w-full p-2 border rounded"
                      value={manualTrade.side}
                      onChange={(e) => setManualTrade({...manualTrade, side: e.target.value})}
                    >
                      <option value="buy">Buy</option>
                      <option value="sell">Sell</option>
                    </select>
                  </div>

                  <div>
                    <Label htmlFor="trade_quantity">Quantity</Label>
                    <Input
                      id="trade_quantity"
                      type="number"
                      step="1"
                      value={manualTrade.quantity}
                      onChange={(e) => setManualTrade({...manualTrade, quantity: parseFloat(e.target.value)})}
                      placeholder="e.g. 100 DOGE = ~$8"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Recommended: 100+ for cheap coins, 0.001+ for expensive coins
                    </p>
                  </div>

                  <div>
                    <Label htmlFor="trade_type">Order Type</Label>
                    <select
                      id="trade_type"
                      className="w-full p-2 border rounded"
                      value={manualTrade.order_type}
                      onChange={(e) => setManualTrade({...manualTrade, order_type: e.target.value})}
                    >
                      <option value="market">Market</option>
                      <option value="limit">Limit</option>
                    </select>
                  </div>
                </div>

                <Button onClick={executeManualTrade} className="w-full">
                  Execute Trade
                </Button>
              </CardContent>
            </Card>
          </TabsContent>

          {/* System Logs Tab */}
          <TabsContent value="logs" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <AlertTriangle className="h-5 w-5" />
                  <span>System Error Logs</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {systemErrors.length === 0 ? (
                    <p className="text-gray-500 text-center py-8">No system errors recorded</p>
                  ) : (
                    systemErrors.map((error: any) => (
                      <div key={error.id} className={`p-4 rounded-lg border ${
                        error.severity === 'critical' ? 'border-red-500 bg-red-50' :
                        error.severity === 'high' ? 'border-orange-500 bg-orange-50' :
                        error.severity === 'medium' ? 'border-yellow-500 bg-yellow-50' :
                        'border-blue-500 bg-blue-50'
                      }`}>
                        <div className="flex justify-between items-start">
                          <div className="flex-1">
                            <div className="flex items-center space-x-2 mb-2">
                              <Badge variant={
                                error.severity === 'critical' ? 'destructive' :
                                error.severity === 'high' ? 'destructive' :
                                error.severity === 'medium' ? 'secondary' :
                                'default'
                              }>
                                {error.error_type}
                              </Badge>
                              <Badge variant={error.resolved ? 'default' : 'outline'}>
                                {error.resolved ? 'Resolved' : 'Active'}
                              </Badge>
                              <span className="text-sm text-gray-500">
                                {new Date(error.timestamp).toLocaleString()}
                              </span>
                            </div>
                            <p className="font-medium mb-1">{error.message}</p>
                            {error.details && Object.keys(error.details).length > 0 && (
                              <details className="text-sm text-gray-600">
                                <summary className="cursor-pointer">Details</summary>
                                <pre className="mt-2 p-2 bg-gray-100 rounded text-xs overflow-auto">
                                  {JSON.stringify(error.details, null, 2)}
                                </pre>
                              </details>
                            )}
                          </div>
                          {!error.resolved && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => resolveError(error.id)}
                            >
                              Mark Resolved
                            </Button>
                          )}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}

export default App;
