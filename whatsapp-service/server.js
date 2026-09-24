require('dotenv').config();
const express = require('express');
const cors = require('cors');
const { startSession, stopSession, getSessionInfo, sendMessage } = require('./sessionManager');

const app = express();
app.use(cors());
app.use(express.json());

const PORT = process.env.PORT || 4001;

app.get('/health', (req, res) => res.json({ ok: true }));

app.post('/session/:botId/start', async (req, res) => {
  try {
    const info = await startSession(req.params.botId);
    res.json(info);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

app.get('/session/:botId/status', (req, res) => {
  res.json(getSessionInfo(req.params.botId));
});

app.delete('/session/:botId', async (req, res) => {
  try {
    await stopSession(req.params.botId);
    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Optional: manual send, handy for testing without going through a real chat
app.post('/session/:botId/send', async (req, res) => {
  const { to, text } = req.body;
  try {
    await sendMessage(req.params.botId, to, text);
    res.json({ ok: true });
  } catch (err) {
    res.status(400).json({ error: err.message });
  }
});

app.listen(PORT, () => {
  console.log(`WhatsApp service running on http://localhost:${PORT}`);
});
