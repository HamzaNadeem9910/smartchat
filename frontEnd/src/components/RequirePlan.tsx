import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2, Crown, Zap, AlertCircle, Clock } from 'lucide-react';

import { API_BASE_URL as API_BASE } from '../services/apiService';

function getAuth() {
  try { return JSON.parse(localStorage.getItem('auth') || ''); } catch { return null; }
}

interface Props {
  children: React.ReactNode;
}

export default function RequirePlan({ children }: Props) {
  const navigate = useNavigate();
  const [checking, setChecking]     = useState(true);
  const [planStatus, setPlanStatus] = useState<string | null>(null);
  const [planName, setPlanName]     = useState<string>('free');
  const [hasPending, setHasPending] = useState(false);

  useEffect(() => {
    const auth = getAuth();
    if (!auth?.token) {
      navigate('/login', { replace: true });
      return;
    }

    fetch(`${API_BASE}/payments/limits`, {
      headers: { Authorization: `Bearer ${auth.token}` },
    })
      .then(r => r.json())
      .then(async data => {
        setPlanName(data.plan     || 'free');
        setPlanStatus(data.status || 'free');

        const allowed = ['active', 'trial'].includes(data.status) && data.plan !== 'free';
        if (!allowed) {
          // Check if there's a pending payment waiting for admin confirmation
          const histRes = await fetch(`${API_BASE}/payments/history`, {
            headers: { Authorization: `Bearer ${auth.token}` },
          });
          const history = await histRes.json();
          const pending = Array.isArray(history) && history.some(
            (p: any) => p.status === 'pending'
          );
          setHasPending(pending);
        }

        setChecking(false);
      })
      .catch(() => {
        setChecking(false);
        setPlanStatus('unknown');
      });
  }, []);

  // ── Loading ────────────────────────────────────────────────
  if (checking) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4 text-gray-400">
          <Loader2 className="w-8 h-8 animate-spin" />
          <p className="text-sm">Checking your plan...</p>
        </div>
      </div>
    );
  }

  const isActive = ['active', 'trial'].includes(planStatus ?? '') && planName !== 'free';

  // ── Active plan → show dashboard ──────────────────────────
  if (isActive) return <>{children}</>;

  // ── Pending payment → waiting for admin confirmation ──────
  if (hasPending) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center p-6">
        <div className="w-full max-w-md bg-gray-900 rounded-3xl border border-yellow-500/30 p-10 text-center shadow-2xl">

          <div className="w-16 h-16 mx-auto mb-6 rounded-full bg-yellow-500/10 border border-yellow-500/30 flex items-center justify-center">
            <Clock className="w-8 h-8 text-yellow-400 animate-pulse" />
          </div>

          <h1 className="text-2xl font-bold text-white mb-3">
            Payment under review
          </h1>

          <p className="text-gray-400 text-sm leading-relaxed mb-6">
            We've received your payment details. Our team is verifying your
            transaction and will activate your plan within{' '}
            <span className="text-yellow-400 font-medium">24 hours</span>.
          </p>

          {/* Progress steps */}
          <div className="bg-gray-800 rounded-2xl p-5 mb-8 text-left space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-2.5 h-2.5 rounded-full bg-yellow-400 animate-pulse flex-shrink-0" />
              <p className="text-sm text-gray-300">Payment submitted — awaiting verification</p>
            </div>
            <div className="flex items-center gap-3">
              <div className="w-2.5 h-2.5 rounded-full bg-gray-600 flex-shrink-0" />
              <p className="text-sm text-gray-500">Admin confirms transaction ID</p>
            </div>
            <div className="flex items-center gap-3">
              <div className="w-2.5 h-2.5 rounded-full bg-gray-600 flex-shrink-0" />
              <p className="text-sm text-gray-500">Dashboard unlocked ✓</p>
            </div>
          </div>

          <p className="text-xs text-gray-500 mb-6">
            Questions? Email{' '}
            <a href="mailto:support@smartchat.io" className="text-blue-400 hover:underline">
              support@smartchat.io
            </a>
          </p>

          <button
            onClick={() => window.location.reload()}
            className="w-full py-3 px-6 rounded-xl border border-gray-600 text-gray-300 hover:bg-gray-800 font-medium transition text-sm"
          >
            Refresh to check status
          </button>

          <button
            onClick={() => { localStorage.removeItem('auth'); navigate('/login', { replace: true }); }}
            className="mt-4 text-sm text-gray-500 hover:text-gray-300 transition block mx-auto"
          >
            Sign out
          </button>

        </div>
      </div>
    );
  }

  // ── No plan, no pending → upgrade wall ────────────────────
  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-6">
      <div className="w-full max-w-md bg-gray-900 rounded-3xl border border-gray-700 p-10 text-center shadow-2xl">

        <div className="w-16 h-16 mx-auto mb-6 rounded-full bg-yellow-500/10 border border-yellow-500/30 flex items-center justify-center">
          {planStatus === 'expired'
            ? <AlertCircle className="w-8 h-8 text-yellow-400" />
            : <Crown className="w-8 h-8 text-yellow-400" />
          }
        </div>

        <h1 className="text-2xl font-bold text-white mb-3">
          {planStatus === 'expired'
            ? 'Your plan has expired'
            : 'Upgrade to access the dashboard'}
        </h1>

        <p className="text-gray-400 text-sm leading-relaxed mb-8">
          {planStatus === 'expired'
            ? 'Your plan expired. Renew to continue using SmartChat and access all your chatbots.'
            : 'The dashboard is available on Standard and Premium plans. Start with a 7-day free trial — no payment needed.'
          }
        </p>

        <div className="grid grid-cols-2 gap-3 mb-6">
          <button
            onClick={() => navigate('/payment', { state: { selectedPlan: 'standard' } })}
            className="flex flex-col items-center gap-2 p-4 rounded-2xl border-2 border-blue-500/50 bg-blue-500/10 hover:bg-blue-500/20 transition"
          >
            <Zap className="w-5 h-5 text-blue-400" />
            <span className="text-white font-semibold text-sm">Standard</span>
            <span className="text-blue-400 text-xs">Rs 4,499/mo</span>
            <span className="text-emerald-400 text-xs font-medium">7-day free trial</span>
          </button>

          <button
            onClick={() => navigate('/payment', { state: { selectedPlan: 'premium' } })}
            className="flex flex-col items-center gap-2 p-4 rounded-2xl border-2 border-purple-500/50 bg-purple-500/10 hover:bg-purple-500/20 transition"
          >
            <Crown className="w-5 h-5 text-purple-400" />
            <span className="text-white font-semibold text-sm">Premium</span>
            <span className="text-purple-400 text-xs">Rs 5,999/mo</span>
            <span className="text-gray-500 text-xs">Full access</span>
          </button>
        </div>

        <button
          onClick={() => navigate('/payment', { state: { selectedPlan: 'standard' } })}
          className="w-full py-3 px-6 rounded-xl bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white font-semibold transition shadow-lg"
        >
          Choose a Plan
        </button>

        <button
          onClick={() => { localStorage.removeItem('auth'); navigate('/login', { replace: true }); }}
          className="mt-4 text-sm text-gray-500 hover:text-gray-300 transition block mx-auto"
        >
          Sign out
        </button>

      </div>
    </div>
  );
}
