import { useEffect, useRef, useState } from "react";

interface WhatsAppConnectProps {
  botId: number;
  apiBaseUrl?: string; // defaults to your FastAPI backend origin
}

type SessionStatus = "not_started" | "pending" | "connected" | "disconnected";

interface SessionInfo {
  status: SessionStatus;
  qr: string | null;
  phoneNumber: string | null;
}

export default function WhatsAppConnect({
  botId,
  apiBaseUrl = "",
}: WhatsAppConnectProps) {
  const [info, setInfo] = useState<SessionInfo>({
    status: "not_started",
    qr: null,
    phoneNumber: null,
  });
  const [loading, setLoading] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const fetchStatus = async () => {
    const res = await fetch(`${apiBaseUrl}/api/whatsapp/sessions/${botId}/status`);
    const data: SessionInfo = await res.json();
    setInfo(data);
    if (data.status === "connected") stopPolling();
  };

  const handleConnect = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${apiBaseUrl}/api/whatsapp/sessions/${botId}/start`, {
        method: "POST",
      });
      const data: SessionInfo = await res.json();
      setInfo(data);

      stopPolling();
      pollRef.current = setInterval(fetchStatus, 3000);
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnect = async () => {
    await fetch(`${apiBaseUrl}/api/whatsapp/sessions/${botId}`, { method: "DELETE" });
    stopPolling();
    setInfo({ status: "disconnected", qr: null, phoneNumber: null });
  };

  useEffect(() => {
    fetchStatus();
    return stopPolling;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [botId]);

  return (
    <div className="rounded-xl border border-gray-200 p-4">
      <h3 className="font-semibold text-gray-900 mb-3">WhatsApp integration</h3>

      {info.status === "connected" && (
        <div>
          <p className="text-sm text-gray-600 mb-3">Connected — {info.phoneNumber}</p>
          <button
            onClick={handleDisconnect}
            className="bg-red-50 text-red-600 hover:bg-red-100 px-4 py-2 rounded-lg text-sm font-medium transition"
          >
            Disconnect
          </button>
        </div>
      )}

      {info.status === "pending" && info.qr && (
        <div>
          <p className="text-sm text-gray-600 mb-3">
            Scan this QR code with WhatsApp (Settings → Linked devices → Link a device):
          </p>
          <img
            src={info.qr}
            alt="WhatsApp pairing QR code"
            width={240}
            height={240}
            className="rounded-lg border border-gray-200"
          />
        </div>
      )}

      {info.status === "pending" && !info.qr && (
        <p className="text-sm text-gray-400">Waiting for QR code…</p>
      )}

      {(info.status === "not_started" || info.status === "disconnected") && (
        <button
          onClick={handleConnect}
          disabled={loading}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition disabled:opacity-50"
        >
          {loading ? "Starting..." : "Connect WhatsApp"}
        </button>
      )}
    </div>
  );
}