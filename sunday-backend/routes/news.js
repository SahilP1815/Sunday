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
// ─── Tavily News Search ────────────────────────────────────────
async function tavilyNewsSearch(category, q, apiKey) {
  const query = q ? q : `latest news about ${category}`;
  const { data } = await axios.post('https://api.tavily.com/search', {
    api_key: apiKey,
    query: query,
    topic: 'news',
    max_results: 5,
  }, {
    headers: { 'Content-Type': 'application/json' },
    timeout: 10000,
  });

  return (data.results || []).map(r => ({
    title:       r.title || '',
    description: r.content || '',
    content:     r.content || null,
    url:         r.url || null,
    image:       null,
    source:      'Tavily News',
    publishedAt: new Date().toISOString(),
  }));
}

// ─── GET /api/news ────────────────────────────────────────────
router.get('/', async (req, res) => {
  const gnewsKey = req.headers['x-gnews-api-key'] || process.env.GNEWS_API_KEY;
  const tavilyKey = req.headers['x-tavily-api-key'] || process.env.TAVILY_API_KEY;

  if (!gnewsKey && !tavilyKey) {
    return res.status(503).json({
      error: 'Neither GNEWS_API_KEY nor TAVILY_API_KEY is configured. Add one of them to your settings or backend .env file.',
      hint:  'GNews offers a free tier at https://gnews.io, and Tavily is available at https://tavily.com',
    });
  }

  const category = VALID_CATS.has(req.query.category) ? req.query.category : 'general';
  const country  = VALID_CTRY.has(req.query.country)  ? req.query.country  : 'in';
  const lang     = VALID_LANGS.has(req.query.lang)    ? req.query.lang     : 'en';
  const max      = Math.min(Math.max(parseInt(req.query.max, 10) || 5, 1), 10);
  const q        = req.query.q ? req.query.q.slice(0, 100) : undefined;

  try {
    if (gnewsKey) {
      const params = { token: gnewsKey, category, country, lang, max };
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
    } else {
      const articles = await tavilyNewsSearch(category, q, tavilyKey);
      return res.json({
        category,
        country,
        total:    articles.length,
        articles,
      });
    }

  } catch (err) {
    const status  = err.response?.status  || 502;
    const message = err.response?.data?.errors?.[0] || err.message;
    console.error('[news] Error fetching news:', message);
    return res.status(status).json({ error: 'Failed to fetch news.', detail: message });
  }
});

export default router;
