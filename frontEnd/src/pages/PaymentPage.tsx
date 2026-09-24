import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Check, Zap, Crown, Shield, Clock, CreditCard,
  Smartphone, Building2, ChevronRight, AlertCircle,
  CheckCircle, Loader2, X, Star
} from 'lucide-react';
import { API_BASE_URL as API_BASE } from '../services/apiService';


interface PlanLimits {
  plan: string;
  max_bots: number;
  max_messages: number;
  can_change_logo: boolean;
  smartchat_branding: boolean;
  price_pkr: number;
  trial_days: number;
}

const PLANS: Record<string, PlanLimits> = {
  standard: {
    plan: 'standard', max_bots: 2, max_messages: 1000,
    can_change_logo: false, smartchat_branding: true,
    price_pkr: 4499, trial_days: 7,
  },
  premium: {
    plan: 'premium', max_bots: 4, max_messages: -1,
    can_change_logo: true, smartchat_branding: false,
    price_pkr: 5999, trial_days: 0,
  },
};

type Step = 'select' | 'pay' | 'confirm';
type Method = 'jazzcash' | 'easypaisa' | 'bank' | 'trial';

function getAuth() {
  try { return JSON.parse(localStorage.getItem('auth') || ''); } catch { return null; }
}

export default function PaymentPage() {
  const navigate   = useNavigate();
  const location   = useLocation();
  const state      = location.state as { selectedPlan?: string } | null;

  const [step,     setStep]     = useState<Step>('select');
  const [plan,     setPlan]     = useState<string>(state?.selectedPlan || 'standard');
  const [method,   setMethod]   = useState<Method>('jazzcash');
  const [txnId,    setTxnId]    = useState('');
  const [notes,    setNotes]    = useState('');
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState('');
  const [success,  setSuccess]  = useState('');
  const [paymentId,setPaymentId]= useState<number | null>(null);

  const auth = getAuth();

  useEffect(() => {
    if (!auth) {
      navigate('/login', {
        state: {
          from: '/payment',
          selectedPlan: plan,       // preserves whichever plan they picked
        }
      });
    }
  }, []);

  const selected = PLANS[plan];

  async function handleTrial() {
    if (!auth) return;
    setLoading(true); setError('');
    try {
      const res = await fetch(`${API_BASE}/payments/initiate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${auth.token}` },
        body: JSON.stringify({
          plan, amount: 0, payment_method: 'manual',
          activate_trial: true, notes: '7-day free trial',
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to activate trial');
      setPaymentId(data.id);
      setSuccess('🎉 Your 7-day free trial has been activated!');
      setStep('confirm');
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }

  async function handlePayment() {
    if (!auth) return;
    if (method !== 'trial' && !txnId.trim()) {
      setError('Please enter your transaction ID.'); return;
    }
    setLoading(true); setError('');
    try {
      const res = await fetch(`${API_BASE}/payments/initiate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${auth.token}` },
        body: JSON.stringify({
          plan,
          amount: selected.price_pkr,
          payment_method: method,
          transaction_id: txnId.trim() || null,
          activate_trial: false,
          notes,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Payment submission failed');
      setPaymentId(data.id);
      setSuccess('✅ Payment submitted! Our team will verify within 24 hours and activate your plan.');
      setStep('confirm');
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }

  // ─── Step 1: Plan Selection ───────────────────────────────────
  function renderSelect() {
    return (
      <div className="space-y-6">
        <div className="text-center mb-8">
          <h2 className="text-2xl font-bold text-gray-900">Choose Your Plan</h2>
          <p className="text-gray-500 mt-1">Select the plan that fits your needs</p>
        </div>

        <div className="grid md:grid-cols-2 gap-5">
          {/* Standard */}
          <button
            onClick={() => setPlan('standard')}
            className={`relative text-left p-6 rounded-2xl border-2 transition-all duration-200 ${
              plan === 'standard'
                ? 'border-blue-500 bg-blue-50 shadow-lg shadow-blue-100'
                : 'border-gray-200 bg-white hover:border-blue-300 hover:shadow-md'
            }`}
          >
            {plan === 'standard' && (
              <div className="absolute top-3 right-3 w-6 h-6 bg-blue-500 rounded-full flex items-center justify-center">
                <Check className="w-3.5 h-3.5 text-white" />
              </div>
            )}
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-blue-100 rounded-xl flex items-center justify-center">
                <Zap className="w-5 h-5 text-blue-600" />
              </div>
              <div>
                <h3 className="font-bold text-gray-900 text-lg">Standard</h3>
                <div className="flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5 text-emerald-500" />
                  <span className="text-xs text-emerald-600 font-medium">7 Days Free Trial</span>
                </div>
              </div>
            </div>
            <div className="mb-4">
              <span className="text-3xl font-bold text-gray-900">Rs {PLANS.standard.price_pkr.toLocaleString()}</span>
              <span className="text-gray-400 text-sm">/month</span>
            </div>
            <ul className="space-y-2.5">
              {[
                '2 Chatbots',
                '1,000 messages/month',
                '7-day free trial',
                'Knowledge base upload',
                'SmartChat branding',
              ].map(f => (
                <li key={f} className="flex items-center gap-2 text-sm text-gray-600">
                  <Check className="w-4 h-4 text-blue-500 flex-shrink-0" />{f}
                </li>
              ))}
              <li className="flex items-center gap-2 text-sm text-gray-400">
                <X className="w-4 h-4 text-gray-300 flex-shrink-0" />Custom logo
              </li>
            </ul>
          </button>

          {/* Premium */}
          <button
            onClick={() => setPlan('premium')}
            className={`relative text-left p-6 rounded-2xl border-2 transition-all duration-200 ${
              plan === 'premium'
                ? 'border-purple-500 bg-purple-50 shadow-lg shadow-purple-100'
                : 'border-gray-200 bg-white hover:border-purple-300 hover:shadow-md'
            }`}
          >
            <div className="absolute top-3 left-1/2 -translate-x-1/2 -translate-y-1/2">
              <span className="bg-gradient-to-r from-purple-600 to-pink-600 text-white text-xs font-bold px-3 py-1 rounded-full shadow">
                MOST POPULAR
              </span>
            </div>
            {plan === 'premium' && (
              <div className="absolute top-3 right-3 w-6 h-6 bg-purple-500 rounded-full flex items-center justify-center">
                <Check className="w-3.5 h-3.5 text-white" />
              </div>
            )}
            <div className="flex items-center gap-3 mb-4 mt-2">
              <div className="w-10 h-10 bg-purple-100 rounded-xl flex items-center justify-center">
                <Crown className="w-5 h-5 text-purple-600" />
              </div>
              <div>
                <h3 className="font-bold text-gray-900 text-lg">Premium</h3>
                <span className="text-xs text-purple-600 font-medium">Full access, no limits</span>
              </div>
            </div>
            <div className="mb-4">
              <span className="text-3xl font-bold text-gray-900">Rs {PLANS.premium.price_pkr.toLocaleString()}</span>
              <span className="text-gray-400 text-sm">/month</span>
            </div>
            <ul className="space-y-2.5">
              {[
                '4 Chatbots',
                'Unlimited messages',
                'Custom bot logo',
                'No SmartChat branding',
                'Knowledge base upload',
                'Priority support',
              ].map(f => (
                <li key={f} className="flex items-center gap-2 text-sm text-gray-600">
                  <Check className="w-4 h-4 text-purple-500 flex-shrink-0" />{f}
                </li>
              ))}
            </ul>
          </button>
        </div>

        {/* Trial banner for standard */}
        {plan === 'standard' && (
          <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 flex items-start gap-3">
            <Star className="w-5 h-5 text-emerald-500 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-emerald-800">7-Day Free Trial Available!</p>
              <p className="text-xs text-emerald-600 mt-0.5">
                Try Standard plan free for 7 days — no payment required. Cancel anytime.
              </p>
            </div>
          </div>
        )}

        <div className="flex gap-3 pt-2">
          {plan === 'standard' && (
            <button
              onClick={() => { setMethod('trial'); handleTrial(); }}
              disabled={loading}
              className="flex-1 flex items-center justify-center gap-2 py-3 px-4 rounded-xl border-2 border-emerald-500 text-emerald-700 font-semibold hover:bg-emerald-50 transition disabled:opacity-50"
            >
              <Clock className="w-4 h-4" /> Start Free Trial
            </button>
          )}
          <button
            onClick={() => setStep('pay')}
            className={`${plan === 'standard' ? 'flex-1' : 'w-full'} flex items-center justify-center gap-2 py-3 px-4 rounded-xl text-white font-semibold transition ${
              plan === 'premium'
                ? 'bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 shadow-lg shadow-purple-200'
                : 'bg-blue-600 hover:bg-blue-700'
            }`}
          >
            Pay Rs {selected.price_pkr.toLocaleString()}
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    );
  }

  // ─── Step 2: Payment Form ─────────────────────────────────────
  function renderPay() {
    const methods = [
      { id: 'jazzcash',  label: 'JazzCash',       icon: <Smartphone className="w-4 h-4" />, account: '03XX-XXXXXXX', color: 'text-red-600' },
      { id: 'easypaisa', label: 'EasyPaisa',       icon: <Smartphone className="w-4 h-4" />, account: '03XX-XXXXXXX', color: 'text-green-600' },
      { id: 'bank',      label: 'Bank Transfer',   icon: <Building2  className="w-4 h-4" />, account: 'IBAN: PK00XXXX0000000000000000', color: 'text-blue-600' },
    ] as const;

    const active = methods.find(m => m.id === method);

    return (
      <div className="space-y-6">
        {/* Back + summary */}
        <div className="flex items-center gap-3">
          <button onClick={() => setStep('select')} className="text-gray-400 hover:text-gray-700 transition">
            ← Back
          </button>
          <div className="flex-1" />
          <div className="bg-gray-100 rounded-lg px-4 py-2 text-sm font-medium text-gray-700">
            {plan === 'standard' ? '🔷 Standard' : '👑 Premium'} — Rs {selected.price_pkr.toLocaleString()}
          </div>
        </div>

        <div>
          <h2 className="text-2xl font-bold text-gray-900">Payment Details</h2>
          <p className="text-gray-500 text-sm mt-1">Send payment and enter your transaction ID below</p>
        </div>

        {/* Payment method tabs */}
        <div className="grid grid-cols-3 gap-2">
          {methods.map(m => (
            <button
              key={m.id}
              onClick={() => setMethod(m.id)}
              className={`flex flex-col items-center gap-1.5 p-3 rounded-xl border-2 transition-all text-sm font-medium ${
                method === m.id
                  ? `border-blue-500 bg-blue-50 ${m.color}`
                  : 'border-gray-200 text-gray-500 hover:border-gray-300'
              }`}
            >
              {m.icon}
              <span className="text-xs">{m.label}</span>
            </button>
          ))}
        </div>

        {/* Account info box */}
        {active && (
          <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 space-y-3">
            <p className="text-sm font-semibold text-gray-700">Send Rs {selected.price_pkr.toLocaleString()} to:</p>
            <div className="bg-white border border-gray-200 rounded-lg p-3">
              <p className="text-xs text-gray-400 mb-0.5">{active.label} Account</p>
              <p className={`font-mono font-bold ${active.color}`}>{active.account}</p>
            </div>
            <div className="flex items-start gap-2 text-xs text-gray-500">
              <AlertCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
              <span>After sending, copy your transaction ID and paste it below. We'll verify and activate your plan within 24 hours.</span>
            </div>
          </div>
        )}

        {/* Transaction ID */}
        <div className="space-y-1.5">
          <label className="text-sm font-medium text-gray-700">Transaction ID *</label>
          <input
            value={txnId}
            onChange={e => setTxnId(e.target.value)}
            placeholder="e.g. AA00AB1234567"
            className="w-full border border-gray-300 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition font-mono"
          />
        </div>

        {/* Notes */}
        <div className="space-y-1.5">
          <label className="text-sm font-medium text-gray-700">Notes <span className="text-gray-400">(optional)</span></label>
          <input
            value={notes}
            onChange={e => setNotes(e.target.value)}
            placeholder="Your phone number or any note for verification"
            className="w-full border border-gray-300 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
          />
        </div>

        {error && (
          <div className="flex items-center gap-2 bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">
            <AlertCircle className="w-4 h-4 flex-shrink-0" /> {error}
          </div>
        )}

        {/* Summary */}
        <div className="bg-gray-50 rounded-xl p-4 space-y-2 text-sm">
          <div className="flex justify-between text-gray-600">
            <span>{plan === 'standard' ? 'Standard Plan' : 'Premium Plan'}</span>
            <span>Rs {selected.price_pkr.toLocaleString()}</span>
          </div>
          <div className="flex justify-between text-gray-600"><span>Billing Period</span><span>1 Month</span></div>
          <div className="border-t border-gray-200 pt-2 flex justify-between font-bold text-gray-900">
            <span>Total</span><span>Rs {selected.price_pkr.toLocaleString()} PKR</span>
          </div>
        </div>

        <button
          onClick={handlePayment}
          disabled={loading || !txnId.trim()}
          className="w-full flex items-center justify-center gap-2 py-3.5 px-6 rounded-xl text-white font-semibold bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition shadow-lg shadow-blue-100"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <CreditCard className="w-4 h-4" />}
          {loading ? 'Submitting...' : 'Submit Payment'}
        </button>

        <p className="text-center text-xs text-gray-400 flex items-center justify-center gap-1.5">
          <Shield className="w-3.5 h-3.5" /> Secure — Payment verified manually by our team
        </p>
      </div>
    );
  }

  // ─── Step 3: Confirmation ─────────────────────────────────────
  function renderConfirm() {
    const isTrial = method === 'trial';
    return (
      <div className="text-center py-8 space-y-6">
        <div className={`w-20 h-20 mx-auto rounded-full flex items-center justify-center ${
          isTrial ? 'bg-emerald-100' : 'bg-blue-100'
        }`}>
          <CheckCircle className={`w-10 h-10 ${isTrial ? 'text-emerald-500' : 'text-blue-500'}`} />
        </div>

        <div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">
            {isTrial ? 'Trial Activated! 🎉' : 'Payment Submitted!'}
          </h2>
          <p className="text-gray-500 max-w-sm mx-auto text-sm leading-relaxed">{success}</p>
        </div>

        {paymentId && (
          <div className="bg-gray-50 rounded-xl p-4 inline-block mx-auto">
            <p className="text-xs text-gray-400 mb-1">Payment Reference</p>
            <p className="font-mono font-bold text-gray-800">#{String(paymentId).padStart(6, '0')}</p>
          </div>
        )}

        {!isTrial && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-700 text-left space-y-1 max-w-sm mx-auto">
            <p className="font-semibold">⏳ What happens next?</p>
            <p>Our team will verify your transaction ID within 24 hours and activate your {plan} plan.</p>
            <p>You'll have access to all {plan} features immediately after verification.</p>
          </div>
        )}

        <div className="flex gap-3 justify-center pt-2">
          <button
            onClick={() => navigate('/dashboard')}
            className="flex items-center gap-2 py-3 px-6 rounded-xl bg-gray-900 text-white font-semibold hover:bg-gray-800 transition"
          >
            Go to Dashboard <ChevronRight className="w-4 h-4" />
          </button>
          {!isTrial && (
            <button
              onClick={() => { setStep('select'); setTxnId(''); setNotes(''); setError(''); setSuccess(''); }}
              className="py-3 px-6 rounded-xl border border-gray-300 text-gray-700 font-semibold hover:bg-gray-50 transition"
            >
              Submit Another
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 flex items-center justify-center p-4">
      <div className="w-full max-w-2xl">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 bg-white border border-gray-200 rounded-full px-4 py-2 text-sm text-gray-600 shadow-sm mb-4">
            <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
            SmartChat Plans
          </div>
          <h1 className="text-3xl font-bold text-gray-900">Unlock Your Plan</h1>
        </div>

        {/* Progress steps */}
        <div className="flex items-center justify-center gap-2 mb-8">
          {(['select', 'pay', 'confirm'] as Step[]).map((s, i) => {
            const stepIdx = { select: 0, pay: 1, confirm: 2 };
            const current = stepIdx[step];
            const thisIdx = stepIdx[s];
            return (
              <div key={s} className="flex items-center gap-2">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
                  thisIdx < current ? 'bg-blue-500 text-white' :
                  thisIdx === current ? 'bg-blue-600 text-white shadow-lg shadow-blue-200' :
                  'bg-gray-200 text-gray-400'
                }`}>
                  {thisIdx < current ? <Check className="w-3.5 h-3.5" /> : i + 1}
                </div>
                <span className={`text-xs font-medium hidden sm:block ${
                  thisIdx === current ? 'text-blue-600' : 'text-gray-400'
                }`}>
                  {['Choose Plan', 'Payment', 'Confirm'][i]}
                </span>
                {i < 2 && <div className={`w-8 h-0.5 ${thisIdx < current ? 'bg-blue-400' : 'bg-gray-200'}`} />}
              </div>
            );
          })}
        </div>

        {/* Card */}
        <div className="bg-white rounded-3xl shadow-xl shadow-blue-100/50 border border-gray-100 p-8">
          {error && step !== 'pay' && (
            <div className="flex items-center gap-2 bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700 mb-6">
              <AlertCircle className="w-4 h-4 flex-shrink-0" /> {error}
            </div>
          )}
          {step === 'select'  && renderSelect()}
          {step === 'pay'     && renderPay()}
          {step === 'confirm' && renderConfirm()}
        </div>

        <p className="text-center text-xs text-gray-400 mt-6">
          Questions? Contact us at{' '}
          <a href="mailto:support@smartchat.io" className="text-blue-500 hover:underline">support@smartchat.io</a>
        </p>
      </div>
    </div>
  );
}
