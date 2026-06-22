// ============================================================
//  routes/chat.js — /api/chat  &  /api/chat/stream
//  Priority: Sarvam AI → Google Gemini → Anthropic Claude
// ============================================================

import { Router } from 'express';
import Anthropic from '@anthropic-ai/sdk';
import { GoogleGenerativeAI } from '@google/generative-ai';
import axios from 'axios';
import { SUNDAY_SYSTEM_PROMPT, MODEL_CONFIG, SUNDAY_TOOLS } from '../config/agentConfig.js';

const router = Router();

// ── Sarvam AI client (primary) ────────────────────────────────
const SARVAM_API_URL  = 'https://api.sarvam.ai/v1/chat/completions';
const SARVAM_MODEL    = 'sarvam-m';
const SARVAM_FALLBACK = 'sarvam-30b';
const useSarvam = !!process.env.SARVAM_API_KEY;

// ── Gemini client (secondary fallback) ───────────────────────
const useGemini = !!process.env.GEMINI_API_KEY;
let geminiClient = null;
if (useGemini) {
  const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);
  geminiClient = genAI.getGenerativeModel({
    model: 'gemini-2.5-flash',
    systemInstruction: SUNDAY_SYSTEM_PROMPT,
  });
}

// ── Anthropic client (tertiary fallback) ─────────────────────
const anthropicClient = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY || 'dummy_key' });

// ── Helpers ───────────────────────────────────────────────────

function sanitiseHistory(history = []) {
  if (!Array.isArray(history)) return [];
  const valid = history
    .filter(m => m && ['user', 'assistant'].includes(m.role) && typeof m.content === 'string')
    .map(m => ({ role: m.role, content: m.content.slice(0, 8000) }));
  const firstUser = valid.findIndex(m => m.role === 'user');
  return firstUser > 0 ? valid.slice(firstUser) : valid;
}

function formatGeminiMessages(messages) {
  return messages.map(m => ({
    role: m.role === 'assistant' ? 'model' : 'user',
    parts: [{ text: m.content }]
  }));
}

/**
 * Call Sarvam AI chat completions.
 * Returns the reply string. Throws on any non-2xx status.
 */
async function callSarvam(messages) {
  const headers = {
    'api-subscription-key': process.env.SARVAM_API_KEY,
    'Content-Type': 'application/json'
  };

  // Prepend system prompt
  const sarvamMessages = [
    { role: 'system', content: SUNDAY_SYSTEM_PROMPT },
    ...messages
  ];

  let payload = { model: SARVAM_MODEL, messages: sarvamMessages, temperature: 0.7 };
  let response = await axios.post(SARVAM_API_URL, payload, { headers, timeout: 15000 });

  if (response.status === 404) {
    // Retry with fallback model name
    payload.model = SARVAM_FALLBACK;
    response = await axios.post(SARVAM_API_URL, payload, { headers, timeout: 15000 });
  }

  return response.data.choices[0].message.content.trim();
}

// ─── POST /api/chat ────────────────────────────────────────────
router.post('/', async (req, res) => {
  const { message, history } = req.body;

  if (!message || typeof message !== 'string' || !message.trim()) {
    return res.status(400).json({ error: 'message is required and must be a non-empty string.' });
  }

  const messages = [
    ...sanitiseHistory(history),
    { role: 'user', content: message.trim() },
  ];

  try {
    // 1. Sarvam AI (primary)
    if (useSarvam) {
      try {
        const reply = await callSarvam(messages);
        return res.json({ reply, sources: [], usage: {}, stop_reason: 'end_turn', engine: 'sarvam' });
      } catch (err) {
        console.warn('[chat] Sarvam failed, falling back:', err.message);
      }
    }

    // 2. Gemini (secondary)
    if (useGemini && geminiClient) {
      try {
        const geminiResponse = await geminiClient.generateContent({
          contents: formatGeminiMessages(messages)
        });
        const reply = geminiResponse.response.candidates[0].content.parts[0].text.trim();
        return res.json({ reply, sources: [], usage: {}, stop_reason: 'end_turn', engine: 'gemini' });
      } catch (err) {
        console.warn('[chat] Gemini failed, falling back:', err.message);
      }
    }

    // 3. Anthropic Claude (tertiary)
    const response = await anthropicClient.messages.create({
      model:      MODEL_CONFIG.model,
      max_tokens: MODEL_CONFIG.max_tokens,
      system:     SUNDAY_SYSTEM_PROMPT,
      messages,
      ...(SUNDAY_TOOLS.length > 0 && { tools: SUNDAY_TOOLS }),
    });

    const reply = response.content
      .filter(block => block.type === 'text')
      .map(block => block.text)
      .join('\n')
      .trim();

    return res.json({ reply, sources: [], usage: response.usage, stop_reason: response.stop_reason, engine: 'anthropic' });

  } catch (err) {
    console.error('[chat] All engines failed:', err.message);
    return res.status(err.status || 500).json({ error: err.message || 'Sunday encountered an internal error.' });
  }
});

// ─── POST /api/chat/stream ────────────────────────────────────
router.post('/stream', async (req, res) => {
  const { message, history } = req.body;

  if (!message || typeof message !== 'string' || !message.trim()) {
    return res.status(400).json({ error: 'message is required.' });
  }

  res.setHeader('Content-Type',  'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection',    'keep-alive');
  res.setHeader('X-Accel-Buffering', 'no');
  res.flushHeaders();

  const send = (event, data) => {
    res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
  };

  const messages = [
    ...sanitiseHistory(history),
    { role: 'user', content: message.trim() },
  ];

  try {
    // 1. Sarvam AI — non-streaming (send as one chunk)
    if (useSarvam) {
      try {
        const reply = await callSarvam(messages);
        send('delta', { text: reply });
        send('done', { stop_reason: 'end_turn', usage: {}, engine: 'sarvam' });
        return res.end();
      } catch (err) {
        console.warn('[stream] Sarvam failed, falling back:', err.message);
      }
    }

    // 2. Gemini streaming
    if (useGemini && geminiClient) {
      try {
        const result = await geminiClient.generateContentStream({
          contents: formatGeminiMessages(messages)
        });
        for await (const chunk of result.stream) {
          send('delta', { text: chunk.text() });
        }
        send('done', { stop_reason: 'end_turn', usage: {}, engine: 'gemini' });
        return res.end();
      } catch (err) {
        console.warn('[stream] Gemini failed, falling back:', err.message);
      }
    }

    // 3. Anthropic streaming
    const stream = anthropicClient.messages.stream({
      model:      MODEL_CONFIG.model,
      max_tokens: MODEL_CONFIG.max_tokens,
      system:     SUNDAY_SYSTEM_PROMPT,
      messages,
      ...(SUNDAY_TOOLS.length > 0 && { tools: SUNDAY_TOOLS }),
    });

    stream.on('text',    (text) => send('delta', { text }));
    stream.on('message', (msg)  => { send('done', { stop_reason: msg.stop_reason, usage: msg.usage, engine: 'anthropic' }); res.end(); });
    stream.on('error',   (err)  => { send('error', { message: err.message }); res.end(); });
    req.on('close', () => stream.controller?.abort());

  } catch (err) {
    console.error('[stream] fatal:', err.message);
    send('error', { message: err.message });
    res.end();
  }
});

export default router;
