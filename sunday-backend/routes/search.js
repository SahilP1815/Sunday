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

// ─── Tavily Search ─────────────────────────────────────────────
async function tavilySearch(query, apiKey) {
  const { data } = await axios.post('https://api.tavily.com/search', {
    api_key: apiKey,
    query: query,
    search_depth: 'basic',
    include_answer: true,
    max_results: 5,
  }, {
    headers: { 'Content-Type': 'application/json' },
    timeout: 10000,
  });

  const results = [];

  // If Tavily returned a direct answer, include it as an answer box
  if (data.answer) {
    results.push({
      type: 'answer_box',
      title: 'Tavily Answer',
      snippet: data.answer,
      url: null,
      source: 'Tavily AI Answer',
    });
  }

  // Organic results
  (data.results || []).slice(0, 5).forEach(r => {
    results.push({
      type: 'organic',
      title: r.title || '',
      snippet: r.content || '',
      url: r.url || null,
      source: 'Tavily Search',
    });
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

  const tavilyKey = req.headers['x-tavily-api-key'] || process.env.TAVILY_API_KEY;
  const serpKey   = process.env.SERPAPI_KEY;

  let engine = 'duckduckgo';
  if (tavilyKey) {
    engine = 'tavily';
  } else if (serpKey) {
    engine = 'serpapi';
  }

  try {
    let results;
    if (tavilyKey) {
      results = await tavilySearch(q, tavilyKey);
    } else if (serpKey) {
      results = await serpSearch(q);
    } else {
      results = await ddgSearch(q);
    }

    return res.json({
      query:   q,
      engine,
      count:   results.length,
      results,
    });

  } catch (err) {
    console.error(`[search] ${engine} error:`, err.message);

    // Try fallbacks
    try {
      let fallbackResults;
      let fallbackEngine;

      if (engine === 'tavily' && serpKey) {
        fallbackEngine = 'serpapi';
        fallbackResults = await serpSearch(q);
      } else if (engine !== 'duckduckgo') {
        fallbackEngine = 'duckduckgo';
        fallbackResults = await ddgSearch(q);
      }

      if (fallbackResults) {
        return res.json({
          query:   q,
          engine:  `${engine}_fallback_to_${fallbackEngine}`,
          count:   fallbackResults.length,
          results: fallbackResults,
          warning: `${engine} failed; used ${fallbackEngine} as fallback.`,
        });
      }
    } catch (fbErr) {
      console.error('[search] Fallback also failed:', fbErr.message);
    }

    return res.status(502).json({
      error:  'Search failed.',
      detail: err.message,
    });
  }
});

export default router;
