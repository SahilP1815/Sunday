// ============================================================
//  rateLimiter.js — Rate limiting + request logging middleware
// ============================================================

import rateLimit from 'express-rate-limit';

// ─── Colour helpers for terminal output ───────────────────────
const c = {
  reset: '\x1b[0m',
  dim:   '\x1b[2m',
  cyan:  '\x1b[36m',
  green: '\x1b[32m',
  yellow:'\x1b[33m',
  red:   '\x1b[31m',
  blue:  '\x1b[34m',
  gray:  '\x1b[90m',
};

function methodColour(method) {
  const map = { GET: c.green, POST: c.cyan, PUT: c.yellow, DELETE: c.red, PATCH: c.blue };
  return (map[method] || c.dim) + method + c.reset;
}

function statusColour(status) {
  if (status < 300) return c.green + status + c.reset;
  if (status < 400) return c.cyan  + status + c.reset;
  if (status < 500) return c.yellow + status + c.reset;
  return c.red + status + c.reset;
}

// ─── Request logger ────────────────────────────────────────────
export function requestLogger(req, res, next) {
  const start = Date.now();
  const ts    = new Date().toISOString().replace('T', ' ').slice(0, 19);

  res.on('finish', () => {
    const ms   = Date.now() - start;
    const size = res.getHeader('content-length')
      ? `${res.getHeader('content-length')}B`
      : '-';

    console.log(
      `${c.gray}[${ts}]${c.reset} ` +
      `${methodColour(req.method).padEnd(18)} ` +
      `${c.dim}${req.originalUrl.padEnd(40)}${c.reset} ` +
      `${statusColour(res.statusCode)} ` +
      `${c.gray}${ms}ms ${size}${c.reset}`
    );
  });

  next();
}

// ─── General API rate limiter (all routes) ─────────────────────
export const generalLimiter = rateLimit({
  windowMs: 60 * 1000,          // 1 minute window
  max: 60,                       // 60 requests / minute
  standardHeaders: true,
  legacyHeaders: false,
  message: {
    error: 'Too many requests. Please slow down.',
    retryAfter: '60 seconds',
  },
  handler: (req, res, next, options) => {
    console.warn(
      `${c.yellow}[RATE LIMIT]${c.reset} ${req.ip} exceeded general limit on ${req.originalUrl}`
    );
    res.status(429).json(options.message);
  },
});

// ─── Strict limiter for the AI chat endpoint ──────────────────
export const chatLimiter = rateLimit({
  windowMs: 60 * 1000,          // 1 minute window
  max: 20,                       // 20 chat requests / minute
  standardHeaders: true,
  legacyHeaders: false,
  message: {
    error: 'Chat rate limit reached. Wait a moment before sending more messages.',
    retryAfter: '60 seconds',
  },
  handler: (req, res, next, options) => {
    console.warn(
      `${c.red}[CHAT LIMIT]${c.reset} ${req.ip} hit chat rate limit`
    );
    res.status(429).json(options.message);
  },
});
