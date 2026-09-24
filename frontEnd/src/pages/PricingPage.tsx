import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Check, X, ArrowRight, MessageCircle, Zap, Crown,
  Clock, Shield, Star, CreditCard, ChevronRight
} from 'lucide-react';
import Header from '../components/Header';
import Footer from '../components/Footer';

export default function PricingPage() {
  const [isYearly, setIsYearly] = useState(false);
  const navigate = useNavigate();

  // Monthly prices in PKR
  const PRICES = { standard: 4499, premium: 5999 };
  // 20% yearly discount
  const yearly = (p: number) => Math.round(p * 0.8);

  const handlePlanSelect = (planName: string, planPrice: number) => {
    const authRaw = localStorage.getItem('auth');
    const destination = '/payment';
    const planState = { selectedPlan: planName.toLowerCase(), planPrice, isYearly };

    if (authRaw) {
      navigate(destination, { state: planState });
    } else {
      navigate('/login', { state: { from: destination, ...planState } });
    }
  };

  return (
    <div className="min-h-screen bg-black">
      <Header />

      {/* ── Hero ─────────────────────────────────────────────── */}
      <section className="relative bg-gradient-to-br from-gray-900 via-black to-gray-800 py-20 overflow-hidden">
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute -top-40 -right-40 w-80 h-80 bg-gradient-to-br from-purple-500/20 to-pink-500/20 rounded-full blur-3xl animate-pulse" />
          <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-gradient-to-br from-blue-500/20 to-cyan-500/20 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />
        </div>

        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center relative z-10">
          <div className="inline-flex items-center space-x-2 bg-gray-800 text-purple-400 px-4 py-2 rounded-full text-sm font-medium mb-8 border border-purple-500/30">
            <CreditCard className="w-4 h-4" />
            <span>Transparent Pricing Plans</span>
          </div>

          <h1 className="text-5xl lg:text-6xl font-bold text-white mb-6">
            Choose the perfect plan<br />for your business
          </h1>

          <p className="text-xl text-gray-300 max-w-2xl mx-auto mb-12">
            Start with a free trial and scale as you grow. No hidden fees, cancel anytime.
          </p>

          {/* Billing toggle */}
          <div className="flex items-center justify-center gap-6 mb-6">
            <button
              onClick={() => setIsYearly(false)}
              className={`text-lg font-medium px-4 py-2 rounded-lg transition-all ${
                !isYearly ? 'text-white bg-gray-800' : 'text-gray-400 hover:text-gray-300 hover:bg-gray-800'
              }`}
            >
              Monthly
            </button>

            <button
              onClick={() => setIsYearly(v => !v)}
              className={`relative w-16 h-8 rounded-full transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-purple-400 focus:ring-offset-2 focus:ring-offset-gray-900 flex items-center ${
                isYearly
                  ? 'bg-gradient-to-r from-purple-600 to-pink-600 shadow-lg shadow-purple-500/30'
                  : 'bg-gray-600'
              }`}
              aria-label={`Switch to ${isYearly ? 'monthly' : 'yearly'} billing`}
            >
              <div className={`absolute w-6 h-6 bg-white rounded-full shadow-lg transform transition-transform duration-300 ${
                isYearly ? 'translate-x-9' : 'translate-x-1'
              }`} />
            </button>

            <button
              onClick={() => setIsYearly(true)}
              className={`text-lg font-medium px-4 py-2 rounded-lg transition-all flex items-center gap-2 ${
                isYearly ? 'text-white bg-gray-800' : 'text-gray-400 hover:text-gray-300 hover:bg-gray-800'
              }`}
            >
              Yearly
              <span className="bg-gradient-to-r from-purple-500 to-pink-500 text-white px-3 py-1 rounded-full text-xs font-medium">
                Save 20%
              </span>
            </button>
          </div>
        </div>
      </section>

      {/* ── Pricing Cards ────────────────────────────────────── */}
      <section className="py-20 bg-black">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid md:grid-cols-2 gap-8 max-w-3xl mx-auto">

            {/* ── Standard ── */}
            <div className="bg-gray-900 rounded-2xl p-8 shadow-lg border-2 border-gray-700 hover:border-blue-500 hover:shadow-2xl hover:shadow-blue-500/20 transition-all duration-300 hover:scale-105 flex flex-col">
              <div className="mb-8">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 bg-blue-500/20 rounded-xl flex items-center justify-center">
                    <Zap className="w-5 h-5 text-blue-400" />
                  </div>
                  <h3 className="text-2xl font-bold text-white">Standard</h3>
                </div>

                <div className="mb-3">
                  <span className="text-4xl font-bold text-white">
                    Rs {isYearly
                      ? yearly(PRICES.standard).toLocaleString()
                      : PRICES.standard.toLocaleString()}
                  </span>
                  <span className="text-gray-400">/month</span>
                  {isYearly && (
                    <div className="text-sm text-blue-400 mt-1">
                      Billed yearly — save Rs {((PRICES.standard - yearly(PRICES.standard)) * 12).toLocaleString()}/yr
                    </div>
                  )}
                </div>

                <p className="text-gray-400 text-sm">Perfect for small businesses getting started with AI chatbots.</p>

                {/* Trial badge */}
                <div className="mt-4 flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/30 rounded-lg px-3 py-2">
                  <Clock className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                  <span className="text-emerald-400 text-sm font-medium">7-day free trial — no payment required</span>
                </div>
              </div>

              <ul className="space-y-3 mb-8 flex-1">
                {[
                  { text: '2 Chatbots', yes: true },
                  { text: '1,000 messages / month', yes: true },
                  { text: 'Knowledge base upload (PDF, DOCX, FAQ)', yes: true },
                  { text: 'Standard AI responses', yes: true },
                  { text: 'Email support', yes: true },
                  { text: '7-day free trial', yes: true },
                  { text: 'SmartChat branding shown', yes: false, note: true },
                  { text: 'Custom bot logo', yes: false },
                  { text: 'Remove branding', yes: false },
                ].map(({ text, yes, note }) => (
                  <li key={text} className="flex items-start gap-3">
                    {yes
                      ? <Check className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
                      : <X className="w-4 h-4 text-gray-600 flex-shrink-0 mt-0.5" />
                    }
                    <span className={`text-sm ${yes ? 'text-gray-300' : note ? 'text-gray-500' : 'text-gray-600'}`}>
                      {text}
                    </span>
                  </li>
                ))}
              </ul>

              <div className="space-y-3">
                <button
                  onClick={() => handlePlanSelect('standard', 0)}
                  className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl border-2 border-emerald-500 text-emerald-400 font-semibold hover:bg-emerald-500/10 transition"
                >
                  <Clock className="w-4 h-4" /> Start Free Trial
                </button>
                <button
                  onClick={() => handlePlanSelect('standard', isYearly ? yearly(PRICES.standard) : PRICES.standard)}
                  className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold transition shadow-lg shadow-blue-900/30"
                >
                  Pay Rs {(isYearly ? yearly(PRICES.standard) : PRICES.standard).toLocaleString()}
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* ── Premium ── */}
            <div className="relative bg-gray-900 rounded-2xl p-8 shadow-lg border-2 border-purple-500 hover:shadow-2xl hover:shadow-purple-500/30 transition-all duration-300 hover:scale-105 flex flex-col">
              {/* Most popular badge */}
              <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                <span className="bg-gradient-to-r from-purple-600 to-pink-600 text-white px-4 py-1.5 rounded-full text-sm font-semibold shadow-lg">
                  ✦ Most Popular
                </span>
              </div>

              <div className="mb-8 mt-2">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 bg-purple-500/20 rounded-xl flex items-center justify-center">
                    <Crown className="w-5 h-5 text-purple-400" />
                  </div>
                  <h3 className="text-2xl font-bold text-white">Premium</h3>
                </div>

                <div className="mb-3">
                  <span className="text-4xl font-bold text-white">
                    Rs {isYearly
                      ? yearly(PRICES.premium).toLocaleString()
                      : PRICES.premium.toLocaleString()}
                  </span>
                  <span className="text-gray-400">/month</span>
                  {isYearly && (
                    <div className="text-sm text-purple-400 mt-1">
                      Billed yearly — save Rs {((PRICES.premium - yearly(PRICES.premium)) * 12).toLocaleString()}/yr
                    </div>
                  )}
                </div>

                <p className="text-gray-400 text-sm">Full power for growing teams — unlimited messages, zero branding.</p>

                {/* No trial note */}
                <div className="mt-4 flex items-center gap-2 bg-purple-500/10 border border-purple-500/30 rounded-lg px-3 py-2">
                  <Star className="w-4 h-4 text-purple-400 flex-shrink-0" />
                  <span className="text-purple-400 text-sm font-medium">Full access from day one — no waiting</span>
                </div>
              </div>

              <ul className="space-y-3 mb-8 flex-1">
                {[
                  { text: '4 Chatbots', yes: true },
                  { text: 'Unlimited messages', yes: true },
                  { text: 'Knowledge base upload (PDF, DOCX, FAQ)', yes: true },
                  { text: 'Advanced AI responses', yes: true },
                  { text: 'Priority support', yes: true },
                  { text: 'Custom bot logo', yes: true },
                  { text: 'No SmartChat branding', yes: true },
                  { text: 'Full branding control', yes: true },
                  { text: 'Analytics dashboard', yes: true },
                ].map(({ text, yes }) => (
                  <li key={text} className="flex items-start gap-3">
                    <Check className="w-4 h-4 text-purple-400 flex-shrink-0 mt-0.5" />
                    <span className="text-sm text-gray-300">{text}</span>
                  </li>
                ))}
              </ul>

              <button
                onClick={() => handlePlanSelect('premium', isYearly ? yearly(PRICES.premium) : PRICES.premium)}
                className="w-full flex items-center justify-center gap-2 py-3.5 px-4 rounded-xl bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-semibold transition shadow-lg shadow-purple-900/40"
              >
                Get Premium
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>

          </div>

          {/* Reassurance strip */}
          <div className="flex flex-wrap items-center justify-center gap-8 mt-12 text-gray-500 text-sm">
            <div className="flex items-center gap-2"><Shield className="w-4 h-4 text-gray-600" /> Secure manual verification</div>
            <div className="flex items-center gap-2"><Check className="w-4 h-4 text-gray-600" /> Cancel anytime</div>
            <div className="flex items-center gap-2"><Clock className="w-4 h-4 text-gray-600" /> Activated within 24 hours</div>
          </div>
        </div>
      </section>

      {/* ── Feature Comparison Table ─────────────────────────── */}
      <section className="bg-gray-900 py-20">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-4xl font-bold text-white mb-4">Compare all features</h2>
            <p className="text-gray-400">Everything you get with each plan.</p>
          </div>

          <div className="overflow-x-auto bg-black rounded-2xl border border-gray-700">
            <table className="w-full border-collapse">
              <thead>
                <tr className="border-b border-gray-700 bg-gray-800">
                  <th className="text-left py-4 px-6 font-semibold text-white">Feature</th>
                  <th className="text-center py-4 px-6 font-semibold text-blue-400">Standard</th>
                  <th className="text-center py-4 px-6 font-semibold text-purple-400">Premium</th>
                </tr>
              </thead>
              <tbody>
                {[
                  { feature: 'Price / month',         std: 'Rs 4,499',  prem: 'Rs 5,999' },
                  { feature: 'Chatbots',               std: '2',         prem: '4' },
                  { feature: 'Messages / month',       std: '1,000',     prem: 'Unlimited' },
                  { feature: 'Free trial',             std: '7 days',    prem: false },
                  { feature: 'Knowledge base upload',  std: true,        prem: true },
                  { feature: 'Custom bot logo',        std: false,       prem: true },
                  { feature: 'Remove SmartChat branding', std: false,    prem: true },
                  { feature: 'Analytics dashboard',    std: false,       prem: true },
                  { feature: 'Priority support',       std: false,       prem: true },
                  { feature: 'Payment method',         std: 'JazzCash / EasyPaisa / Bank', prem: 'JazzCash / EasyPaisa / Bank' },
                ].map((row, i) => (
                  <tr key={i} className="border-b border-gray-800 hover:bg-gray-800/50 transition-colors">
                    <td className="py-4 px-6 text-gray-300">{row.feature}</td>
                    <td className="py-4 px-6 text-center">
                      {typeof row.std === 'boolean'
                        ? row.std
                          ? <Check className="w-5 h-5 text-blue-400 mx-auto" />
                          : <X className="w-5 h-5 text-gray-600 mx-auto" />
                        : <span className="text-gray-300 text-sm">{row.std}</span>
                      }
                    </td>
                    <td className="py-4 px-6 text-center">
                      {typeof row.prem === 'boolean'
                        ? row.prem
                          ? <Check className="w-5 h-5 text-purple-400 mx-auto" />
                          : <X className="w-5 h-5 text-gray-600 mx-auto" />
                        : <span className="text-gray-300 text-sm">{row.prem}</span>
                      }
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* ── FAQ ──────────────────────────────────────────────── */}
      <section className="bg-black py-20">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-4xl font-bold text-white mb-4">Frequently asked questions</h2>
          </div>

          <div className="space-y-6">
            {[
              {
                q: 'How does the 7-day free trial work?',
                a: 'The Standard plan free trial activates instantly — no payment needed. You get full Standard plan access for 7 days. After the trial, you can pay Rs 4,499 to continue or let it expire.',
              },
              {
                q: 'How do I pay?',
                a: 'We accept JazzCash, EasyPaisa, and bank transfer. After sending payment, you enter your transaction ID on the payment page. Our team verifies it within 24 hours and activates your plan.',
              },
              {
                q: 'Can I upgrade from Standard to Premium later?',
                a: 'Yes. You can upgrade at any time. Contact our support team and we\'ll apply a prorated credit for your remaining Standard days.',
              },
              {
                q: 'What happens when my plan expires?',
                a: 'Your account automatically reverts to the free tier (1 bot, 200 messages/month). Your chatbot data is never deleted — you just need to renew to restore access.',
              },
              {
                q: 'Do you offer refunds?',
                a: 'Since payments are verified manually, contact our support within 7 days of activation if you have an issue and we\'ll sort it out.',
              },
              {
                q: 'Can I cancel anytime?',
                a: 'Yes. Plans are monthly. Simply don\'t renew and your plan stays active until the period ends, then reverts to free.',
              },
            ].map((faq, i) => (
              <div key={i} className="bg-gray-900 rounded-2xl p-7 border border-gray-700 hover:border-purple-500/50 transition-all duration-300">
                <h3 className="text-lg font-semibold text-white mb-3">{faq.q}</h3>
                <p className="text-gray-400 leading-relaxed">{faq.a}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ──────────────────────────────────────────────── */}
      <section className="bg-gradient-to-br from-purple-900 via-black to-pink-900 py-20 relative overflow-hidden">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute -top-40 -right-40 w-80 h-80 bg-purple-500/20 rounded-full blur-3xl animate-pulse" />
          <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-pink-500/20 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />
        </div>

        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 text-center relative z-10">
          <h2 className="text-4xl lg:text-5xl font-bold text-white mb-6">
            Ready to get started?
          </h2>
          <p className="text-xl text-purple-100 mb-10 max-w-xl mx-auto">
            Try Standard free for 7 days, or go Premium for full power from day one.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <button
              onClick={() => handlePlanSelect('standard', 0)}
              className="flex items-center justify-center gap-2 bg-white text-gray-900 px-8 py-4 rounded-xl text-lg font-semibold hover:bg-gray-100 transition shadow-xl"
            >
              Start Free Trial <ArrowRight className="w-5 h-5" />
            </button>
            <button
              onClick={() => handlePlanSelect('premium', PRICES.premium)}
              className="flex items-center justify-center gap-2 border-2 border-white/30 text-white px-8 py-4 rounded-xl text-lg font-semibold hover:bg-white/10 transition"
            >
              Get Premium <Crown className="w-5 h-5" />
            </button>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-6 mt-8 text-purple-200 text-sm">
            <div className="flex items-center gap-2"><Check className="w-4 h-4 text-purple-400" /> No credit card for trial</div>
            <div className="flex items-center gap-2"><Check className="w-4 h-4 text-purple-400" /> Cancel anytime</div>
            <div className="flex items-center gap-2"><Check className="w-4 h-4 text-purple-400" /> Activated within 24 hrs</div>
          </div>
        </div>
      </section>

      <Footer />

      {/* Chat widget */}
      <div className="fixed bottom-6 right-6 z-50">
        <button className="w-14 h-14 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 rounded-full flex items-center justify-center shadow-lg hover:shadow-2xl hover:shadow-purple-500/50 transition-all duration-300 transform hover:scale-110">
          <MessageCircle className="w-6 h-6 text-white" />
        </button>
      </div>
    </div>
  );
}