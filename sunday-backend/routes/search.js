// ============================================================
//  routes/search.js — /api/search
//  Web search via SerpAPI (with DuckDuckGo fallback)
// ============================================================

import { Router } from 'express';
import axios from 'axios';

const router = Router();

// ─── SerpAPI search ───────────────────────────────────────────
async function serpSearch(query) {
  const { data } = await axios.get('https://serpapi.com/search', {
    params: {
      api_key: process.env.SERPAPI_KEY,
      q:       query,
      engine:  'google',
      num:     5,
      hl:      'en',
      gl:      'in',
    },
    timeout: 10000,
  });

  const results = [];

  // Featured snippet (answer box)
  if (data.answer_box) {
    const ab = data.answer_box;
    results.push({
      type:    'answer_box',
      title:   ab.title   || ab.question || 'Answer',
      snippet: ab.answer  || ab.snippet  || ab.result || '',
      url:     ab.link    || null,
      source:  'Google Answer Box',
    });
  }

  // Knowledge graph
  if (data.knowledge_graph) {
    const kg = data.knowledge_graph;
    results.push({
      type:    'knowledge_graph',
      title:   kg.title || '',
      snippet: kg.description || '',
      url:     kg.website || null,
      source:  'Google Knowledge Graph',
    });
  }

  // Organic results
  (data.organic_results || []).slice(0, 5).forEach(r => {
    results.push({
      type:    'organic',
      title:   r.title   || '',
      snippet: r.snippet || '',
      url:     r.link    || null,
      source:  r.displayed_link || r.source || '',
    });
  });

  return results;
}

// ─── DuckDuckGo Instant Answers fallback ─────────────────────
async function ddgSearch(query) {
  const { data } = await axios.get('https://api.duckduckgo.com/', {
    params: { q: query, format: 'json', no_redirect: 1, no_html: 1, skip_disambig: 1 },
    timeout: 8000,
  });

  const results = [];

  if (data.AbstractText) {
    results.push({
      type:    'abstract',
      title:   data.Heading || query,
      snippet: data.AbstractText,
      url:     data.AbstractURL || null,
      source:  data.AbstractSource || 'DuckDuckGo',
    });
  }

  if (data.Answer) {
    results.push({
      type:    'instant_answer',
      title:   'Instant Answer',
      snippet: data.Answer,
      url:     null,
      source:  'DuckDuckGo',
    });
  }

  (data.RelatedTopics || []).slice(0, 4).forEach(t => {
    if (t.Text && t.FirstURL) {
      results.push({
        type:    'related',
        title:   t.Text.split(' - ')[0] || t.Text,
        snippet: t.Text,
        url:     t.FirstURL,
        source:  'DuckDuckGo',
      });
    }
  });

  return results;
}

// ─── GET /api/search?q=... ────────────────────────────────────
router.get('/', async (req, res) => {
  const q = (req.query.q || '').trim();

  if (!q) {
    return res.status(400).json({ error: 'Provide a search query: ?q=your+query' });
  }
  if (q.length > 300) {
    return res.status(400).json({ error: 'Query too long (max 300 characters).' });
  }

  const hasSerpKey = Boolean(process.env.SERPAPI_KEY);
  const engine     = hasSerpKey ? 'serpapi' : 'duckduckgo';

  try {
    const results = hasSerpKey
      ? await serpSearch(q)
      : await ddgSearch(q);

    return res.json({
      query:   q,
      engine,
      count:   results.length,
      results,
    });

  } catch (err) {
    console.error(`[search] ${engine} error:`, err.message);

    // If SerpAPI failed, try DuckDuckGo as last resort
    if (hasSerpKey) {
      try {
        const fallback = await ddgSearch(q);
        return res.json({
          query:   q,
          engine:  'duckduckgo_fallback',
          count:   fallback.length,
          results: fallback,
          warning: 'SerpAPI failed; used DuckDuckGo as fallback.',
        });
      } catch (fbErr) {
        console.error('[search] DDG fallback also failed:', fbErr.message);
      }
    }

    return res.status(502).json({
      error:  'Search failed.',
      detail: err.message,
    });
  }
});

export default router;
