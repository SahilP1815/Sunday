// ============================================================
//  routes/news.js — /api/news
//  Fetches top headlines via GNews API (free tier)
// ============================================================

import { Router } from 'express';
import axios from 'axios';

const router = Router();

const GNEWS_BASE  = 'https://gnews.io/api/v4/top-headlines';
const VALID_CATS  = new Set(['general','business','technology','sports','science','health','entertainment']);
const VALID_LANGS = new Set(['en','hi','de','fr','es','ar','zh']);
const VALID_CTRY  = new Set(['in','us','gb','au','ca','de','fr','jp','cn','br','za','ng','ae']);

// ─── GET /api/news ────────────────────────────────────────────
// Query params:
//   category  — one of VALID_CATS (default: general)
//   country   — ISO-3166 2-letter code (default: in)
//   lang      — ISO-639 language code (default: en)
//   max       — number of articles, 1–10 (default: 5)
//   q         — optional search keyword filter
router.get('/', async (req, res) => {
  const apiKey = req.headers['x-gnews-api-key'] || process.env.GNEWS_API_KEY;

  if (!apiKey) {
    return res.status(503).json({
      error: 'GNEWS_API_KEY is not configured. Add it to your settings or backend .env file.',
      hint:  'Free tier available at https://gnews.io',
    });
  }

  const category = VALID_CATS.has(req.query.category) ? req.query.category : 'general';
  const country  = VALID_CTRY.has(req.query.country)  ? req.query.country  : 'in';
  const lang     = VALID_LANGS.has(req.query.lang)    ? req.query.lang     : 'en';
  const max      = Math.min(Math.max(parseInt(req.query.max, 10) || 5, 1), 10);
  const q        = req.query.q ? req.query.q.slice(0, 100) : undefined;

  try {
    const params = { token: apiKey, category, country, lang, max };
    if (q) params.q = q;

    const { data } = await axios.get(GNEWS_BASE, { params, timeout: 8000 });

    const articles = (data.articles || []).map(a => ({
      title:       a.title,
      description: a.description,
      content:     a.content?.slice(0, 500) || null,
      url:         a.url,
      image:       a.image || null,
      source:      a.source?.name || null,
      publishedAt: a.publishedAt,
    }));

    return res.json({
      category,
      country,
      total:    data.totalArticles ?? articles.length,
      articles,
    });

  } catch (err) {
    const status  = err.response?.status  || 502;
    const message = err.response?.data?.errors?.[0] || err.message;
    console.error('[news] GNews error:', message);
    return res.status(status).json({ error: 'Failed to fetch news.', detail: message });
  }
});

export default router;
