# Deployment Guide

## Backend Deployment

### Option 1: Railway
1. Connect your GitHub repository to Railway
2. Select the backend folder as the root directory
3. Railway will automatically detect the Python project
4. Set environment variables in Railway dashboard
5. Deploy using the provided `deployment/railway.toml` configuration

### Option 2: Render
1. Connect your GitHub repository to Render
2. Use the `deployment/render.yaml` configuration
3. Set environment variables in Render dashboard
4. Deploy as a web service

### Environment Variables (Backend)
Set these in your deployment platform:
- `ROBINHOOD_API_KEY`: Your Robinhood API key
- `ROBINHOOD_PRIVATE_KEY`: Your Robinhood private key
- `COINGECKO_API_KEY`: CoinGecko API key
- `NEWSDATA_API_KEY`: NewsData.io API key
- `SECRET_KEY`: Generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- `TRADING_BUDGET`: 100.0
- `PAPER_TRADING_MODE`: false
- `ALLOWED_ORIGINS`: Your frontend domain (e.g., https://your-app.vercel.app)

## Frontend Deployment

### Vercel
1. Connect your GitHub repository to Vercel
2. Set the root directory to `frontend`
3. Set build command: `npm run build`
4. Set output directory: `dist`
5. Set environment variable `VITE_API_URL` to your backend URL

### Environment Variables (Frontend)
- `VITE_API_URL`: Your deployed backend URL

## Testing Deployment

1. Verify backend health: `GET https://your-backend-url/healthz`
2. Test frontend connectivity to backend
3. Start with paper trading mode for initial testing
4. Switch to live trading with small amounts ($5-10 trades)

## Monitoring

- Check error logs in the System Logs tab of the dashboard
- Monitor API rate limits and trading performance
- Set up uptime monitoring for 24/7 operation

## Security Notes

- Never commit `.env` files with real credentials
- Use environment variables for all sensitive data
- Restrict CORS origins to your actual domains
- Monitor error logs for security issues
