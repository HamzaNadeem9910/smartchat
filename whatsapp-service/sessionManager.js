const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
  downloadMediaMessage,
} = require('@whiskeysockets/baileys');
const QRCode = require('qrcode');
const axios = require('axios');
const path = require('path');
const fs = require('fs');
const pino = require('pino');

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';
const SESSIONS_DIR = path.join(__dirname, 'sessions');

// Fixed number that gets the "connected!" chat opened on it after ANY bot
// links via QR — set this in .env, e.g. ADMIN_NOTIFY_NUMBER=03107125676
// Accepts local Pakistani format (0...) or already-international (92... / +92...).
const ADMIN_NOTIFY_NUMBER = process.env.ADMIN_NOTIFY_NUMBER || '';

function toWhatsAppJid(rawNumber) {
  if (!rawNumber) return null;
  let digits = rawNumber.replace(/[^\d]/g, ''); // strip spaces, +, -, ()
  if (digits.startsWith('0')) {
    digits = '92' + digits.slice(1); // local 03XXXXXXXXX -> 923XXXXXXXXX
  }
  return `${digits}@s.whatsapp.net`;
}

if (!fs.existsSync(SESSIONS_DIR)) fs.mkdirSync(SESSIONS_DIR, { recursive: true });

// In-memory registry: botId -> { sock, status, qr, phoneNumber }
const sessions = {};

function getSessionInfo(botId) {
  const s = sessions[botId];
  if (!s) return { status: 'not_started', qr: null, phoneNumber: null };
  return { status: s.status, qr: s.qr || null, phoneNumber: s.phoneNumber || null };
}

async function notifyBackend(botId, status, phoneNumber) {
  try {
    await axios.post(`${BACKEND_URL}/api/whatsapp/status`, {
      bot_id: botId,
      status,
      phone_number: phoneNumber,
    });
  } catch (err) {
    console.error(`[${botId}] Failed to notify backend of status change:`, err.message);
  }
}

async function startSession(botId) {
  if (sessions[botId] && sessions[botId].status === 'connected') {
    return getSessionInfo(botId);
  }

  const sessionPath = path.join(SESSIONS_DIR, String(botId));
  const { state, saveCreds } = await useMultiFileAuthState(sessionPath);
  const { version } = await fetchLatestBaileysVersion();

  const sock = makeWASocket({
    version,
    auth: state,
    logger: pino({ level: 'silent' }),
  });

  sessions[botId] = { sock, status: 'pending', qr: null, phoneNumber: null, hadFreshQr: false };

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', async (update) => {
    const { connection, qr, lastDisconnect } = update;

    if (qr) {
      sessions[botId].qr = await QRCode.toDataURL(qr);
      sessions[botId].status = 'pending';
      sessions[botId].hadFreshQr = true; // a real scan-to-pair just happened
    }

    if (connection === 'open') {
      const phoneNumber = sock.user?.id?.split(':')[0] || null;
      sessions[botId].status = 'connected';
      sessions[botId].qr = null;
      sessions[botId].phoneNumber = phoneNumber;
      console.log(`[${botId}] WhatsApp connected: ${phoneNumber}`);
      notifyBackend(botId, 'connected', phoneNumber);

      // Send a one-time confirmation to the fixed ADMIN_NOTIFY_NUMBER so a
      // chat opens there instantly after linking — regardless of which
      // owner's number just got connected. Only fires on a fresh QR
      // pairing, not on every automatic reconnect using saved credentials
      // (otherwise every server restart would spam this number).
      if (sessions[botId].hadFreshQr) {
        sessions[botId].hadFreshQr = false;
        const notifyJid = toWhatsAppJid(ADMIN_NOTIFY_NUMBER);
        if (notifyJid) {
          try {
            await sock.sendMessage(notifyJid, {
              text: `✅ WhatsApp connected for bot #${botId} (number: ${phoneNumber}). Messages sent to that number now get automatic replies.`,
            });
          } catch (err) {
            console.error(`[${botId}] Failed to send connect notification:`, err.message);
          }
        } else {
          console.warn(`[${botId}] ADMIN_NOTIFY_NUMBER not set in .env — skipping connect notification`);
        }
      }
    }

    if (connection === 'close') {
      const statusCode = lastDisconnect?.error?.output?.statusCode;
      const loggedOut = statusCode === DisconnectReason.loggedOut;

      sessions[botId].status = 'disconnected';
      notifyBackend(botId, 'disconnected', null);

      if (loggedOut) {
        console.log(`[${botId}] Logged out — clearing saved session`);
        fs.rmSync(sessionPath, { recursive: true, force: true });
        delete sessions[botId];
      } else {
        console.log(`[${botId}] Connection dropped — reconnecting in 2s`);
        setTimeout(() => startSession(botId), 2000);
      }
    }
  });

  sock.ev.on('messages.upsert', async ({ messages, type }) => {
    if (type !== 'notify') return;
    const msg = messages[0];
    if (!msg.message || msg.key.fromMe) return;

    const from = msg.key.remoteJid;
    if (from.endsWith('@g.us')) return; // ignore group chats for now

    // WhatsApp sometimes wraps a document as documentMessage directly, and
    // sometimes as documentWithCaptionMessage.message.documentMessage when
    // it's sent with a caption — check both shapes.
    const documentMessage =
      msg.message.documentMessage ||
      msg.message.documentWithCaptionMessage?.message?.documentMessage ||
      null;

    const isPdf = documentMessage?.mimetype === 'application/pdf';

    const text =
      msg.message.conversation ||
      msg.message.extendedTextMessage?.text ||
      msg.message.imageMessage?.caption ||
      documentMessage?.caption ||
      '';

    if (!text && !isPdf) return;

    let fileBase64 = null;
    let fileName = null;

    if (isPdf) {
      try {
        const buffer = await downloadMediaMessage(
          msg,
          'buffer',
          {},
          { logger: pino({ level: 'silent' }), reuploadRequest: sock.updateMediaMessage }
        );
        fileBase64 = buffer.toString('base64');
        fileName = documentMessage.fileName || 'transcript.pdf';
      } catch (err) {
        console.error(`[${botId}] Failed to download PDF:`, err.message);
        await sock.sendMessage(from, {
          text: "I couldn't download that file — could you try sending it again?",
        });
        return;
      }
    }

    try {
      await sock.sendPresenceUpdate('composing', from);
      const { data } = await axios.post(`${BACKEND_URL}/api/whatsapp/incoming`, {
        bot_id: botId,
        sender: from,
        message: text,
        file_base64: fileBase64,
        file_name: fileName,
      });

      if (data.reply) {
        await sock.sendMessage(from, { text: data.reply });
      }

      // Restaurant bot menu replies include image URLs (e.g. burger pics) —
      // send each as a real WhatsApp image message with the item name/price
      // as the caption, one message per item.
      if (Array.isArray(data.images) && data.images.length) {
        for (const img of data.images) {
          try {
            await sock.sendMessage(from, {
              image: { url: img.url },
              caption: img.caption || '',
            });
          } catch (imgErr) {
            console.error(`[${botId}] Failed to send image ${img.url}:`, imgErr.message);
          }
        }
      }
    } catch (err) {
      console.error(`[${botId}] Failed to process message:`, err.message);
      await sock.sendMessage(from, {
        text: 'Sorry, something went wrong on our end. Please try again shortly.',
      });
    }
  });

  return getSessionInfo(botId);
}

async function stopSession(botId) {
  const s = sessions[botId];
  if (!s) return;
  await s.sock.logout().catch(() => {});
  delete sessions[botId];
}

async function sendMessage(botId, to, text) {
  const s = sessions[botId];
  if (!s || s.status !== 'connected') throw new Error('Session not connected');
  const jid = to.includes('@') ? to : `${to}@s.whatsapp.net`;
  await s.sock.sendMessage(jid, { text });
}

module.exports = { startSession, stopSession, getSessionInfo, sendMessage };