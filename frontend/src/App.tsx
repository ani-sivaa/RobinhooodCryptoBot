import { useState, useEffect } from 'react';
import { Play, Square, TrendingUp, DollarSign, Activity, BarChart3, AlertTriangle } from 'lucide-react';

interface BotStatus {
  is_running: boolean;
  symbols: string[];
  total_trades: number;
  open_positions: number;
  performance_metrics: {
    total_trades: number;
    winning_trades: number;
    total_pnl: number;
    max_drawdown: number;
    sharpe_ratio: number;
  };
  risk_metrics: {
    account_balance: number;
    daily_losses: number;
    daily_loss_limit: number;
    available_buying_power: number;
  };
}

interface Portfolio {
  account_info: {
    account_number: string;
    status: string;
    buying_power: string;
    buying_power_currency: string;
  };
  holdings: any[];
  risk_metrics: {
    account_balance: number;
    daily_losses: number;
    available_buying_power: number;
  };
}

interface Trade {
  timestamp: string;
  symbol: string;
  side: string;
  quantity: number;
  price: number;
  quote_amount: number;
  signal_strength?: number;
  confidence?: number;
}

interface TradingSignal {
  symbol: string;
  action: string;
  strength: number;
  confidence: number;
  current_price: number;
  indicators: {
    rsi: number;
    macd: number;
    sma_20: number;
  };
}

const API_BASE = 'http://localhost:8000';

function App() {
  const [botStatus, setBotStatus] = useState<BotStatus | null>(null);
  const [, setPortfolio] = useState<Portfolio | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [signals, setSignals] = useState<TradingSignal[]>([]);
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [manualTrade, setManualTrade] = useState({
    symbol: 'BTC',
    side: 'buy',
    amount: 10
  });

  const [strategyParams, setStrategyParams] = useState({
    confidence_threshold: 0.6,
    signal_strength_threshold: 0.7,
    symbols: ['BTC', 'ETH']
  });

  const fetchBotStatus = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/bot/status`);
      const data = await response.json();
      setBotStatus(data);
    } catch (err) {
      console.error('Error fetching bot status:', err);
    }
  };

  const fetchPortfolio = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/portfolio`);
      const data = await response.json();
      setPortfolio(data);
    } catch (err) {
      console.error('Error fetching portfolio:', err);
    }
  };

  const fetchTrades = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/trades`);
      const data = await response.json();
      setTrades(data);
    } catch (err) {
      console.error('Error fetching trades:', err);
    }
  };

  const fetchSignals = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/signals`);
      const data = await response.json();
      setSignals(data.signals || []);
    } catch (err) {
      console.error('Error fetching signals:', err);
    }
  };

  const startBot = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/api/bot/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbols: strategyParams.symbols,
          account_balance: 100.0
        })
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to start bot');
      }
      
      await fetchBotStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start bot');
    } finally {
      setLoading(false);
    }
  };

  const stopBot = async () => {
    setLoading(true);
    try {
      await fetch(`${API_BASE}/api/bot/stop`, { method: 'POST' });
      await fetchBotStatus();
    } catch (err) {
      setError('Failed to stop bot');
    } finally {
      setLoading(false);
    }
  };

  const executeTradingCycle = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/bot/execute-cycle`, { method: 'POST' });
      const data = await response.json();
      console.log('Trading cycle result:', data);
      await fetchBotStatus();
      await fetchTrades();
      await fetchSignals();
    } catch (err) {
      setError('Failed to execute trading cycle');
    } finally {
      setLoading(false);
    }
  };

  const executeManualTrade = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/trade/manual`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(manualTrade)
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Trade failed');
      }
      
      await fetchTrades();
      await fetchPortfolio();
      setManualTrade({ symbol: 'BTC', side: 'buy', amount: 10 });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Trade failed');
    } finally {
      setLoading(false);
    }
  };

  const updateStrategy = async () => {
    setLoading(true);
    try {
      await fetch(`${API_BASE}/api/strategy/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(strategyParams)
      });
      await fetchBotStatus();
    } catch (err) {
      setError('Failed to update strategy');
    } finally {
      setLoading(false);
    }
  };

  const trainModel = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/model/train`, { method: 'POST' });
      const data = await response.json();
      console.log('Training result:', data);
    } catch (err) {
      setError('Failed to train model');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBotStatus();
    fetchPortfolio();
    fetchTrades();
    fetchSignals();

    const interval = setInterval(() => {
      fetchBotStatus();
      fetchSignals();
    }, 30000); // Update every 30 seconds

    return () => clearInterval(interval);
  }, []);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount);
  };

  const formatPercentage = (value: number) => {
    return `${(value * 100).toFixed(2)}%`;
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-3">
              <TrendingUp className="h-8 w-8 text-blue-600" />
              <h1 className="text-xl font-bold text-gray-900">
                Robinhood Crypto Bot - $100 Budget
              </h1>
            </div>
            <div className="flex items-center gap-4">
              {botStatus && (
                <span className={`badge ${botStatus.is_running ? 'badge-success' : 'badge-danger'}`}>
                  {botStatus.is_running ? 'Running' : 'Stopped'}
                </span>
              )}
              {botStatus?.is_running ? (
                <button 
                  onClick={stopBot} 
                  disabled={loading}
                  className="button button-danger flex items-center gap-2"
                >
                  <Square className="h-4 w-4" />
                  Stop Bot
                </button>
              ) : (
                <button 
                  onClick={startBot} 
                  disabled={loading}
                  className="button button-primary flex items-center gap-2"
                >
                  <Play className="h-4 w-4" />
                  Start Bot
                </button>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Error Display */}
      {error && (
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-4">
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-red-600" />
            <span className="text-red-800">{error}</span>
            <button 
              onClick={() => setError(null)}
              className="ml-auto text-red-600 hover:text-red-800"
            >
              ×
            </button>
          </div>
        </div>
      )}

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Status Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="card">
            <div className="card-content">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Account Balance</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {formatCurrency(botStatus?.risk_metrics?.account_balance || 100)}
                  </p>
                </div>
                <DollarSign className="h-8 w-8 text-green-600" />
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-content">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Total Trades</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {botStatus?.performance_metrics?.total_trades || 0}
                  </p>
                </div>
                <Activity className="h-8 w-8 text-blue-600" />
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-content">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">P&L</p>
                  <p className={`text-2xl font-bold ${(botStatus?.performance_metrics?.total_pnl || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {formatCurrency(botStatus?.performance_metrics?.total_pnl || 0)}
                  </p>
                </div>
                <TrendingUp className="h-8 w-8 text-purple-600" />
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-content">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Open Positions</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {botStatus?.open_positions || 0}
                  </p>
                </div>
                <BarChart3 className="h-8 w-8 text-orange-600" />
              </div>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="tabs">
          <div className="tabs-list">
            {[
              { id: 'overview', label: 'Overview' },
              { id: 'trades', label: 'Trades' },
              { id: 'signals', label: 'Signals' },
              { id: 'strategy', label: 'Strategy' },
              { id: 'manual', label: 'Manual Trade' }
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`tabs-trigger ${activeTab === tab.id ? 'active' : ''}`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Overview Tab */}
          {activeTab === 'overview' && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="card">
                  <div className="card-header">
                    <h3 className="card-title">Portfolio Summary</h3>
                  </div>
                  <div className="card-content">
                    <div className="space-y-4">
                      <div className="flex justify-between">
                        <span className="text-gray-600">Available Cash:</span>
                        <span className="font-medium">
                          {formatCurrency(botStatus?.risk_metrics?.available_buying_power || 100)}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Daily Losses:</span>
                        <span className="font-medium text-red-600">
                          {formatCurrency(botStatus?.risk_metrics?.daily_losses || 0)}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Daily Loss Limit:</span>
                        <span className="font-medium">
                          {formatCurrency(botStatus?.risk_metrics?.daily_loss_limit || 10)}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Win Rate:</span>
                        <span className="font-medium">
                          {botStatus?.performance_metrics?.total_trades ? 
                            formatPercentage((botStatus.performance_metrics.winning_trades || 0) / botStatus.performance_metrics.total_trades) : 
                            '0.00%'
                          }
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="card">
                  <div className="card-header">
                    <h3 className="card-title">Bot Controls</h3>
                  </div>
                  <div className="card-content">
                    <div className="space-y-4">
                      <button
                        onClick={executeTradingCycle}
                        disabled={!botStatus?.is_running || loading}
                        className="button button-primary w-full"
                      >
                        Execute Trading Cycle
                      </button>
                      <button
                        onClick={trainModel}
                        disabled={loading}
                        className="button button-secondary w-full"
                      >
                        Train ML Model
                      </button>
                      <div className="text-sm text-gray-600">
                        <p>Symbols: {botStatus?.symbols?.join(', ') || 'None'}</p>
                        <p>Last update: {new Date().toLocaleTimeString()}</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Trades Tab */}
          {activeTab === 'trades' && (
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">Recent Trades</h3>
              </div>
              <div className="card-content">
                {trades.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b">
                          <th className="text-left py-2">Time</th>
                          <th className="text-left py-2">Symbol</th>
                          <th className="text-left py-2">Side</th>
                          <th className="text-left py-2">Quantity</th>
                          <th className="text-left py-2">Price</th>
                          <th className="text-left py-2">Amount</th>
                          <th className="text-left py-2">Confidence</th>
                        </tr>
                      </thead>
                      <tbody>
                        {trades.slice(-10).reverse().map((trade, index) => (
                          <tr key={index} className="border-b">
                            <td className="py-2 text-sm">
                              {new Date(trade.timestamp).toLocaleString()}
                            </td>
                            <td className="py-2 font-medium">{trade.symbol}</td>
                            <td className="py-2">
                              <span className={`badge ${trade.side === 'buy' ? 'badge-success' : 'badge-danger'}`}>
                                {trade.side.toUpperCase()}
                              </span>
                            </td>
                            <td className="py-2">{trade.quantity.toFixed(6)}</td>
                            <td className="py-2">{formatCurrency(trade.price)}</td>
                            <td className="py-2">{formatCurrency(trade.quote_amount)}</td>
                            <td className="py-2">
                              {trade.confidence ? formatPercentage(trade.confidence) : 'N/A'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-gray-500 text-center py-8">No trades yet</p>
                )}
              </div>
            </div>
          )}

          {/* Signals Tab */}
          {activeTab === 'signals' && (
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">Current Trading Signals</h3>
              </div>
              <div className="card-content">
                {signals.length > 0 ? (
                  <div className="grid gap-4">
                    {signals.map((signal, index) => (
                      <div key={index} className="border rounded-lg p-4">
                        <div className="flex justify-between items-start mb-2">
                          <div>
                            <h4 className="font-semibold">{signal.symbol}</h4>
                            <span className={`badge ${signal.action === 'buy' ? 'badge-success' : 'badge-danger'}`}>
                              {signal.action.toUpperCase()}
                            </span>
                          </div>
                          <div className="text-right">
                            <p className="text-sm text-gray-600">Strength: {formatPercentage(signal.strength)}</p>
                            <p className="text-sm text-gray-600">Confidence: {formatPercentage(signal.confidence)}</p>
                          </div>
                        </div>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                          <div>
                            <span className="text-gray-600">Price:</span>
                            <span className="ml-1 font-medium">{formatCurrency(signal.current_price)}</span>
                          </div>
                          <div>
                            <span className="text-gray-600">RSI:</span>
                            <span className="ml-1 font-medium">{signal.indicators.rsi?.toFixed(2) || 'N/A'}</span>
                          </div>
                          <div>
                            <span className="text-gray-600">MACD:</span>
                            <span className="ml-1 font-medium">{signal.indicators.macd?.toFixed(4) || 'N/A'}</span>
                          </div>
                          <div>
                            <span className="text-gray-600">SMA20:</span>
                            <span className="ml-1 font-medium">{signal.indicators.sma_20 ? formatCurrency(signal.indicators.sma_20) : 'N/A'}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-gray-500 text-center py-8">No active signals</p>
                )}
              </div>
            </div>
          )}

          {/* Strategy Tab */}
          {activeTab === 'strategy' && (
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">Strategy Configuration</h3>
              </div>
              <div className="card-content">
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Confidence Threshold
                    </label>
                    <input
                      type="number"
                      min="0.1"
                      max="0.9"
                      step="0.1"
                      value={strategyParams.confidence_threshold}
                      onChange={(e) => setStrategyParams({
                        ...strategyParams,
                        confidence_threshold: parseFloat(e.target.value)
                      })}
                      className="input"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Signal Strength Threshold
                    </label>
                    <input
                      type="number"
                      min="0.1"
                      max="1.0"
                      step="0.1"
                      value={strategyParams.signal_strength_threshold}
                      onChange={(e) => setStrategyParams({
                        ...strategyParams,
                        signal_strength_threshold: parseFloat(e.target.value)
                      })}
                      className="input"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Trading Symbols (comma-separated)
                    </label>
                    <input
                      type="text"
                      value={strategyParams.symbols.join(', ')}
                      onChange={(e) => setStrategyParams({
                        ...strategyParams,
                        symbols: e.target.value.split(',').map(s => s.trim()).filter(s => s)
                      })}
                      className="input"
                      placeholder="BTC, ETH, DOGE"
                    />
                  </div>
                  
                  <button
                    onClick={updateStrategy}
                    disabled={loading}
                    className="button button-primary"
                  >
                    Update Strategy
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Manual Trade Tab */}
          {activeTab === 'manual' && (
            <div className="card">
              <div className="card-header">
                <h3 className="card-title">Manual Trade Execution</h3>
              </div>
              <div className="card-content">
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Symbol
                    </label>
                    <select
                      value={manualTrade.symbol}
                      onChange={(e) => setManualTrade({...manualTrade, symbol: e.target.value})}
                      className="select"
                    >
                      <option value="BTC">BTC</option>
                      <option value="ETH">ETH</option>
                      <option value="DOGE">DOGE</option>
                      <option value="LTC">LTC</option>
                    </select>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Side
                    </label>
                    <select
                      value={manualTrade.side}
                      onChange={(e) => setManualTrade({...manualTrade, side: e.target.value})}
                      className="select"
                    >
                      <option value="buy">Buy</option>
                      <option value="sell">Sell</option>
                    </select>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Amount (USD)
                    </label>
                    <input
                      type="number"
                      min="5"
                      max="50"
                      value={manualTrade.amount}
                      onChange={(e) => setManualTrade({...manualTrade, amount: parseFloat(e.target.value)})}
                      className="input"
                    />
                  </div>
                  
                  <button
                    onClick={executeManualTrade}
                    disabled={loading || !botStatus}
                    className="button button-primary"
                  >
                    Execute Trade
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
