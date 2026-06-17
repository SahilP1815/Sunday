// ============================================================
//  routes/chat.js — /api/chat  &  /api/chat/stream
//  Core Sunday AI endpoint — proxies to Anthropic Claude or Google Gemini
// ============================================================

import { Router } from 'express';
import Anthropic from '@anthropic-ai/sdk';
import { GoogleGenerativeAI } from '@google/generative-ai';
import { SUNDAY_SYSTEM_PROMPT, MODEL_CONFIG, SUNDAY_TOOLS } from '../config/agentConfig.js';

const router = Router();
// Anthropic client (fallback)
const anthropicClient = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY || 'dummy_key' });
// Gemini client – enabled when GEMINI_API_KEY is present
const useGemini = !!process.env.GEMINI_API_KEY;
let geminiClient = null;
if (useGemini) {
  const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);
  geminiClient = genAI.getGenerativeModel({
    model: 'gemini-3.5-flash',
    systemInstruction: SUNDAY_SYSTEM_PROMPT,
  });
}

function formatGeminiMessages(messages) {
  return messages.map(m => ({
    role: m.role === 'assistant' ? 'model' : 'user',
    parts: [{ text: m.content }]
  }));
}

// ─── Helper: sanitise history ─────────────────────────────────
// Anthropic expects alternating user/assistant turns. Strip anything
// that would cause a 400, and ensure history starts with a user turn.
function sanitiseHistory(history = []) {
  if (!Array.isArray(history)) return [];

  const valid = history
    .filter(m => m && ['user', 'assistant'].includes(m.role) && typeof m.content === 'string')
    .map(m => ({ role: m.role, content: m.content.slice(0, 8000) }));  // cap per-message

  // Anthropic requires history to start with a user turn
  const firstUser = valid.findIndex(m => m.role === 'user');
  return firstUser > 0 ? valid.slice(firstUser) : valid;
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
    // Choose backend based on available key
    if (useGemini && geminiClient) {
      const geminiResponse = await geminiClient.generateContent({
        contents: formatGeminiMessages(messages)
      });
      const reply = geminiResponse.response.candidates[0].content.parts[0].text.trim();
      return res.json({
        reply,
        sources: [],
        usage: {},
        stop_reason: 'end_turn'
      });
    } else {
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

      return res.json({
        reply,
        sources: [],
        usage: response.usage,
        stop_reason: response.stop_reason,
      });
    }

  } catch (err) {
    console.error('[chat] Chat error:', err.message);
    const status  = err.status || 500;
    const message = err.message || 'Sunday encountered an internal error.';
    return res.status(status).json({ error: message });
  }
});

// ─── POST /api/chat/stream ────────────────────────────────────
// Server-Sent Events (SSE) streaming response
router.post('/stream', async (req, res) => {
  const { message, history } = req.body;

  if (!message || typeof message !== 'string' || !message.trim()) {
    return res.status(400).json({ error: 'message is required.' });
  }

  // Set SSE headers
  res.setHeader('Content-Type',  'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection',    'keep-alive');
  res.setHeader('X-Accel-Buffering', 'no');  // disable nginx buffering
  res.flushHeaders();

  const send = (event, data) => {
    res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
  };

  const messages = [
    ...sanitiseHistory(history),
    { role: 'user', content: message.trim() },
  ];

  try {
    if (useGemini && geminiClient) {
      const result = await geminiClient.generateContentStream({
        contents: formatGeminiMessages(messages)
      });

      for await (const chunk of result.stream) {
        const text = chunk.text();
        send('delta', { text });
      }

      send('done', {
        stop_reason: 'end_turn',
        usage: {}
      });
      res.end();
    } else {
      const stream = anthropicClient.messages.stream({
        model:      MODEL_CONFIG.model,
        max_tokens: MODEL_CONFIG.max_tokens,
        system:     SUNDAY_SYSTEM_PROMPT,
        messages,
        ...(SUNDAY_TOOLS.length > 0 && { tools: SUNDAY_TOOLS }),
      });

      stream.on('text', (text) => send('delta', { text }));

      stream.on('message', (msg) => {
        send('done', {
          stop_reason: msg.stop_reason,
          usage:       msg.usage,
        });
        res.end();
      });

      stream.on('error', (err) => {
        console.error('[stream] error:', err.message);
        send('error', { message: err.message });
        res.end();
      });

      req.on('close', () => stream.controller?.abort());
    }

  } catch (err) {
    console.error('[stream] fatal:', err.message);
    send('error', { message: err.message });
    res.end();
  }
});

export default router;
