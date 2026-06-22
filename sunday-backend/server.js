// ============================================================
//  server.js — Sunday AI Backend Entry Point
//  Run:  node server.js        (production)
//        node --watch server.js (dev / auto-restart)
// ============================================================

import 'dotenv/config';
import express      from 'express';
import cors         from 'cors';
import chatRouter   from './routes/chat.js';
import marketRouter from './routes/market.js';
import newsRouter   from './routes/news.js';
import searchRouter from './routes/search.js';
import speechRouter from './routes/speech.js';
import { requestLogger, generalLimiter, chatLimiter } from './middleware/rateLimiter.js';

// ─── Validate critical env ────────────────────────────────────
if (!process.env.ANTHROPIC_API_KEY) {
  console.error('\x1b[31m[FATAL] ANTHROPIC_API_KEY is missing from .env — Sunday cannot start.\x1b[0m');
  process.exit(1);
}

const app  = express();
const PORT = parseInt(process.env.PORT, 10) || 3001;

// ─── CORS ─────────────────────────────────────────────────────
const allowedOrigin = process.env.FRONTEND_URL || '*';
app.use(cors({
  origin:      allowedOrigin === '*' ? true : allowedOrigin,
  methods:     ['GET', 'POST', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization'],
}));

// ─── Body parsing ─────────────────────────────────────────────
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: false }));

// ─── Request logger ───────────────────────────────────────────
app.use(requestLogger);

// ─── Global rate limiter ──────────────────────────────────────
app.use(generalLimiter);

// ─── Health / root ────────────────────────────────────────────
app.get('/', (req, res) => {
  res.json({
    agent:   'Sunday AI Backend',
    version: '1.0.0',
    status:  'online',
    time:    new Date().toISOString(),
    endpoints: {
      chat:   'POST /api/chat',
      stream: 'POST /api/chat/stream',
      market: 'GET  /api/market/:symbol',
      batch:  'GET  /api/market/batch?symbols=a,b,c',
      news:   'GET  /api/news?category=business&country=in&max=5',
      search: 'GET  /api/search?q=your+query',
    },
  });
});

app.get('/health', (req, res) => res.json({ status: 'ok', uptime: process.uptime() }));

// ─── API routes ───────────────────────────────────────────────
app.use('/api/chat',   chatLimiter, chatRouter);
app.use('/api/market', marketRouter);
app.use('/api/news',   newsRouter);
app.use('/api/search', searchRouter);
app.use('/api/speech', speechRouter);

// ─── 404 handler ──────────────────────────────────────────────
app.use((req, res) => {
  res.status(404).json({ error: `No route found for ${req.method} ${req.originalUrl}` });
});

// ─── Global error handler ─────────────────────────────────────
app.use((err, req, res, next) => {
  console.error('\x1b[31m[ERROR]\x1b[0m', err.message);
  res.status(err.status || 500).json({ error: err.message || 'Internal server error.' });
});

// ─── Start ────────────────────────────────────────────────────
app.listen(PORT, () => {
  const line = '─'.repeat(52);
  console.log(`\x1b[36m${line}\x1b[0m`);
  console.log(`  \x1b[1m\x1b[36mSunday AI Backend\x1b[0m  \x1b[2mv1.0.0\x1b[0m`);
  console.log(`${line}`);
  console.log(`  \x1b[32m●\x1b[0m  Server     → http://localhost:${PORT}`);
  console.log(`  \x1b[32m●\x1b[0m  Chat       → POST /api/chat`);
  console.log(`  \x1b[32m●\x1b[0m  Stream     → POST /api/chat/stream`);
  console.log(`  \x1b[32m●\x1b[0m  Market     → GET  /api/market/:symbol`);
  console.log(`  \x1b[32m●\x1b[0m  News       → GET  /api/news`);
  console.log(`  \x1b[32m●\x1b[0m  Search     → GET  /api/search`);
  console.log(`  \x1b[33m●\x1b[0m  CORS       → ${allowedOrigin}`);
  console.log(`  \x1b[33m●\x1b[0m  GNews      → ${process.env.GNEWS_API_KEY  ? '\x1b[32mconfigured\x1b[0m' : '\x1b[90mnot set\x1b[0m'}`);
  console.log(`  \x1b[33m●\x1b[0m  SerpAPI    → ${process.env.SERPAPI_KEY    ? '\x1b[32mconfigured\x1b[0m' : '\x1b[90musing DDG fallback\x1b[0m'}`);
  console.log(`  \x1b[33m●\x1b[0m  Tavily     → ${process.env.TAVILY_API_KEY  ? '\x1b[32mconfigured\x1b[0m' : '\x1b[90mnot set\x1b[0m'}`);
  console.log(`\x1b[36m${line}\x1b[0m\n`);
});

export default app;
