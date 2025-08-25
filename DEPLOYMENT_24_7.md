# 24/7 Deployment Guide for Robinhood Crypto Trading Bot

This guide provides comprehensive instructions for deploying the cryptocurrency trading bot for continuous 24/7 operation.

## Quick Start with Docker

### Prerequisites
- Docker and Docker Compose installed
- Robinhood API credentials

### 1. Set Environment Variables
```bash
export ROBINHOOD_API_KEY="your_api_key_here"
export ROBINHOOD_PRIVATE_KEY="your_base64_private_key_here"
```

### 2. Run with Docker Compose
```bash
# Clone the repository
git clone https://github.com/ani-sivaa/RobinhooodCryptoBot.git
cd RobinhooodCryptoBot

# Start the services
docker-compose up -d

# View logs
docker-compose logs -f backend
```

### 3. Access the Dashboard
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Health Check: http://localhost:8000/health

## Cloud Deployment Options

### Railway (Recommended for Backend)

1. **Connect Repository**
   - Go to [Railway](https://railway.app)
   - Connect your GitHub repository
   - Select the `RobinhooodCryptoBot` repository

2. **Configure Environment Variables**
   ```
   ROBINHOOD_API_KEY=your_api_key_here
   ROBINHOOD_PRIVATE_KEY=your_base64_private_key_here
   TRADING_BUDGET=100.0
   MAX_RISK_PER_TRADE=0.03
   DAILY_LOSS_LIMIT=0.15
   ```

3. **Deploy**
   - Railway will automatically use the `deployment/railway.toml` configuration
   - The service will be available at your Railway-provided URL

### Render (Alternative Backend Option)

1. **Connect Repository**
   - Go to [Render](https://render.com)
   - Create a new Web Service
   - Connect your GitHub repository

2. **Configure Service**
   - Use the `deployment/render.yaml` configuration
   - Set environment variables in the Render dashboard

3. **Deploy**
   - Render will automatically build and deploy your service

### Vercel (Frontend Only)

1. **Connect Repository**
   - Go to [Vercel](https://vercel.com)
   - Import your GitHub repository

2. **Configure Build Settings**
   - Framework Preset: Vite
   - Root Directory: `frontend`
   - Build Command: `npm run build`
   - Output Directory: `dist`

3. **Environment Variables**
   ```
   VITE_API_URL=https://your-backend-url.railway.app
   ```

## Monitoring and Health Checks

### Health Check Endpoints
- **Basic Health**: `GET /health`
- **Bot Status**: `GET /api/bot/status`
- **Trading Signals**: `GET /api/signals`
- **Portfolio**: `GET /api/portfolio`

### Automated Monitoring Features
- **Health Monitoring**: Automatic bot restart if unresponsive for 30+ minutes
- **API Connection Monitoring**: Restart on repeated API failures
- **Error Recovery**: Automatic retry with exponential backoff
- **Logging**: Comprehensive logging for debugging and monitoring

### Setting Up External Monitoring (Optional)

#### UptimeRobot
1. Create account at [UptimeRobot](https://uptimerobot.com)
2. Add HTTP(s) monitor for your health endpoint
3. Set check interval to 5 minutes
4. Configure alerts via email/SMS

#### Healthchecks.io
1. Create account at [Healthchecks.io](https://healthchecks.io)
2. Create a new check with 10-minute interval
3. Add webhook URL to your bot's health check routine

## Configuration for Aggressive Trading

### Current Aggressive Settings
- **Risk per Trade**: 3% of account balance
- **Daily Loss Limit**: 15% of account balance
- **Trading Interval**: Every 3 minutes
- **Analysis Interval**: Every 3 minutes
- **Confidence Threshold**: 0.55 (lower = more trades)
- **Signal Strength Threshold**: 0.6 (lower = more trades)

### Supported Cryptocurrencies
- BTC (Bitcoin)
- ETH (Ethereum)
- DOGE (Dogecoin)
- LTC (Litecoin)

## Security Best Practices

### API Key Management
- Never commit API keys to version control
- Use environment variables for all sensitive data
- Rotate API keys regularly
- Monitor API usage and set up alerts

### Network Security
- Use HTTPS for all communications
- Implement rate limiting
- Monitor for unusual activity
- Set up IP whitelisting if supported

## Troubleshooting

### Common Issues

#### Bot Not Starting
1. Check API credentials are correct
2. Verify Robinhood API access
3. Check logs for specific error messages
4. Ensure sufficient account balance

#### Trades Not Executing
1. Verify bot is running: `GET /api/bot/status`
2. Check trading signals: `GET /api/signals`
3. Review risk management limits
4. Check account balance and buying power

#### High Memory Usage
1. Restart the bot periodically
2. Monitor database size
3. Clean up old trade history
4. Consider upgrading server resources

### Log Analysis
```bash
# View real-time logs
docker-compose logs -f backend

# Search for errors
docker-compose logs backend | grep ERROR

# Check specific time range
docker-compose logs --since="2024-01-01T00:00:00" backend
```

## Performance Optimization

### Resource Requirements
- **Minimum**: 512MB RAM, 1 CPU core
- **Recommended**: 1GB RAM, 2 CPU cores
- **Storage**: 10GB for logs and data

### Scaling Considerations
- Monitor CPU and memory usage
- Set up log rotation
- Consider database optimization for large trade histories
- Implement caching for frequently accessed data

## Backup and Recovery

### Data Backup
- Trading database is stored in Docker volume `trading_data`
- Backup regularly: `docker run --rm -v trading_data:/data -v $(pwd):/backup alpine tar czf /backup/trading_data.tar.gz /data`

### Disaster Recovery
1. Keep API credentials secure and backed up
2. Document configuration settings
3. Test recovery procedures regularly
4. Monitor for data corruption

## Support and Maintenance

### Regular Maintenance Tasks
- Monitor bot performance weekly
- Review trading results monthly
- Update dependencies quarterly
- Backup data regularly

### Getting Help
- Check logs for error messages
- Review GitHub issues
- Monitor Robinhood API status
- Contact support if needed

## Legal and Compliance

### Important Disclaimers
- Trading cryptocurrencies involves substantial risk
- Past performance does not guarantee future results
- Only trade with money you can afford to lose
- Comply with local regulations and tax requirements

### Risk Management
- Never exceed your risk tolerance
- Monitor positions regularly
- Set appropriate stop losses
- Diversify your investments

---

**Note**: This bot is for educational and experimental purposes. Always test thoroughly with small amounts before deploying with significant capital.
