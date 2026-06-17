// ============================================================
//  routes/market.js — /api/market/:symbol  &  /api/market/batch
//  Real-time market data via Yahoo Finance (no API key needed)
// ============================================================

import { Router } from 'express';
import YahooFinance from 'yahoo-finance2';
const yahooFinance = new YahooFinance();

const router = Router();

// ─── Symbol aliases → Yahoo Finance tickers ──────────────────
const ALIASES = {
  // Indian indices
  nifty:    '^NSEI',
  nifty50:  '^NSEI',
  sensex:   '^BSESN',
  banknifty:'^NSEBANK',

  // US indices
  nasdaq:   '^IXIC',
  dow:      '^DJI',
  sp500:    '^GSPC',
  s500:     '^GSPC',
  vix:      '^VIX',

  // Global indices
  ftse:     '^FTSE',
  nikkei:   '^N225',
  hangseng: '^HSI',
  dax:      '^GDAXI',
  cac:      '^FCHI',

  // Crypto
  bitcoin:  'BTC-USD',
  btc:      'BTC-USD',
  ethereum: 'ETH-USD',
  eth:      'ETH-USD',
  bnb:      'BNB-USD',
  xrp:      'XRP-USD',
  sol:      'SOL-USD',
  doge:     'DOGE-USD',

  // Commodities
  gold:     'GC=F',
  silver:   'SI=F',
  crude:    'CL=F',
  oil:      'CL=F',
  natgas:   'NG=F',

  // Forex
  usdinr:   'USDINR=X',
  eurusd:   'EURUSD=X',
  gbpusd:   'GBPUSD=X',
  usdjpy:   'USDJPY=X',
  eurinr:   'EURINR=X',
};

function resolveSymbol(raw) {
  const key = raw.toLowerCase().trim();
  return ALIASES[key] || raw.toUpperCase();
}

// ─── Format a single Yahoo Finance quote ─────────────────────
function formatQuote(q, originalSymbol) {
  const price  = q.regularMarketPrice       ?? null;
  const change = q.regularMarketChange      ?? null;
  const pct    = q.regularMarketChangePercent ?? null;
  const high   = q.regularMarketDayHigh     ?? null;
  const low    = q.regularMarketDayLow      ?? null;
  const open   = q.regularMarketOpen        ?? null;
  const prev   = q.regularMarketPreviousClose ?? null;
  const vol    = q.regularMarketVolume      ?? null;
  const cap    = q.marketCap                ?? null;
  const ts     = q.regularMarketTime
    ? new Date(q.regularMarketTime * 1000).toISOString()
    : new Date().toISOString();

  const direction = change > 0 ? '↑' : change < 0 ? '↓' : '→';

  return {
    symbol:        q.symbol || originalSymbol,
    name:          q.shortName || q.longName || q.symbol || originalSymbol,
    price:         price,
    currency:      q.currency || 'USD',
    change:        change     !== null ? +change.toFixed(4)  : null,
    changePercent: pct        !== null ? +pct.toFixed(2)     : null,
    direction,
    dayHigh:       high       !== null ? +high.toFixed(4)    : null,
    dayLow:        low        !== null ? +low.toFixed(4)     : null,
    open:          open       !== null ? +open.toFixed(4)    : null,
    previousClose: prev       !== null ? +prev.toFixed(4)   : null,
    volume:        vol,
    marketCap:     cap,
    exchange:      q.fullExchangeName || q.exchange || null,
    marketState:   q.marketState || null,
    timestamp:     ts,
  };
}

// ─── GET /api/market/batch?symbols=a,b,c ─────────────────────
// Must be defined BEFORE /:symbol to avoid 'batch' matching as a symbol
router.get('/batch', async (req, res) => {
  const raw = req.query.symbols || '';
  if (!raw.trim()) {
    return res.status(400).json({ error: 'Provide ?symbols=nifty,btc,AAPL' });
  }

  const inputs   = raw.split(',').map(s => s.trim()).filter(Boolean).slice(0, 20);
  const tickers  = inputs.map(resolveSymbol);
  const results  = {};
  const errors   = {};

  await Promise.allSettled(
    inputs.map(async (input, i) => {
      const ticker = tickers[i];
      try {
        const q = await yahooFinance.quote(ticker);
        results[input] = formatQuote(q, ticker);
      } catch (err) {
        errors[input] = `Unable to fetch ${ticker}: ${err.message}`;
      }
    })
  );

  return res.json({ results, errors: Object.keys(errors).length ? errors : undefined });
});

// ─── GET /api/market/:symbol ──────────────────────────────────
router.get('/:symbol', async (req, res) => {
  const ticker = resolveSymbol(req.params.symbol);

  try {
    const q    = await yahooFinance.quote(ticker);
    const data = formatQuote(q, ticker);
    return res.json(data);
  } catch (err) {
    console.error(`[market] Error fetching ${ticker}:`, err.message);
    return res.status(502).json({
      error:  `Failed to fetch data for "${req.params.symbol}".`,
      detail: err.message,
    });
  }
});

export default router;
