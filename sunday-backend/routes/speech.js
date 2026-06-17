// ============================================================
//  routes/speech.js — /api/speech/stt  &  /api/speech/tts
//  Proxy endpoints for Sarvam AI Speech Services
// ============================================================

import { Router } from 'express';
import axios from 'axios';

const router = Router();

// Retrieve Sarvam API Subscription Key
const getApiKey = () => process.env.SARVAM_API_KEY || '';

// ─── POST /api/speech/stt ──────────────────────────────────────
// Transcribe audio data (expects base64 encoded audio in JSON)
router.post('/stt', async (req, res) => {
  const { audio, model = 'saaras:v3', mode = 'transcribe' } = req.body;

  if (!audio) {
    return res.status(400).json({ error: 'Audio data (base64) is required.' });
  }

  const apiKey = getApiKey();
  if (!apiKey) {
    return res.status(500).json({ error: 'SARVAM_API_KEY is not configured on the backend.' });
  }

  try {
    // Convert base64 audio to Buffer
    const buffer = Buffer.from(audio, 'base64');
    
    // Wrap in a Blob and append to native FormData
    const blob = new Blob([buffer], { type: 'audio/wav' });
    const formData = new FormData();
    formData.append('file', blob, 'audio.wav');
    formData.append('model', model);
    formData.append('mode', mode);

    const response = await fetch('https://api.sarvam.ai/speech-to-text', {
      method: 'POST',
      headers: {
        'api-subscription-key': apiKey
      },
      body: formData
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`Sarvam STT API returned ${response.status}: ${errText}`);
    }

    const data = await response.json();
    return res.json({
      transcript: data.transcript,
      language_code: data.language_code
    });
  } catch (err) {
    console.error('[STT Error]', err.message);
    return res.status(500).json({ error: err.message });
  }
});

// ─── POST /api/speech/tts ──────────────────────────────────────
// Synthesize text to speech
router.post('/tts', async (req, res) => {
  const { text, languageCode = 'hi-IN', speaker = 'shubh', model = 'bulbul:v3' } = req.body;

  if (!text) {
    return res.status(400).json({ error: 'Text is required.' });
  }

  const apiKey = getApiKey();
  if (!apiKey) {
    return res.status(500).json({ error: 'SARVAM_API_KEY is not configured on the backend.' });
  }

  try {
    const response = await axios.post(
      'https://api.sarvam.ai/text-to-speech',
      {
        text,
        speaker,
        target_language_code: languageCode,
        model
      },
      {
        headers: {
          'api-subscription-key': apiKey,
          'Content-Type': 'application/json'
        }
      }
    );

    if (response.data && response.data.audios && response.data.audios.length > 0) {
      return res.json({ audio: response.data.audios[0] });
    } else {
      throw new Error('No audio returned from Sarvam TTS API.');
    }
  } catch (err) {
    console.error('[TTS Error]', err.message);
    const status = err.response?.status || 500;
    const msg = err.response?.data?.error || err.message;
    return res.status(status).json({ error: msg });
  }
});

export default router;
