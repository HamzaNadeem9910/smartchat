import React, { useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import Header from '../../components/Header';
import Logo from '../../components/Logo';
import { authAPI } from '../../services/apiService';

export default function SignupPage() {
  const [name, setName]                     = useState('');
  const [email, setEmail]                   = useState('');
  const [password, setPassword]             = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError]                   = useState<string | null>(null);
  const [success, setSuccess]               = useState<string | null>(null);
  const [isLoading, setIsLoading]           = useState(false);

  const navigate = useNavigate();
  const location = useLocation() as any;

  // Carry through whatever plan/destination was set before signup
  const from         = location.state?.from         || '/dashboard';
  const selectedPlan = location.state?.selectedPlan || null;
  const planPrice    = location.state?.planPrice    || null;
  const isYearly     = location.state?.isYearly     || false;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters.');
      return;
    }

    setIsLoading(true);
    try {
      await authAPI.signup({ name, email, password, plan: 'free' });

      setSuccess('Account created! Redirecting to sign in...');

      // ── KEY FIX: pass plan state through to LoginPage ──────────
      setTimeout(() => {
        navigate('/login', {
          replace: true,
          state: { from, selectedPlan, planPrice, isYearly },
        });
      }, 1200);
    } catch (err: any) {
      setError(err.message || 'Failed to create account. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-white">
      <Header />
      <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center bg-gradient-to-b from-gray-50 to-white p-6">
        <div className="w-full max-w-lg bg-white rounded-2xl shadow-xl overflow-hidden">
          <div className="p-8 sm:p-10 lg:p-12">

          <div className="flex items-center space-x-4 mb-6">
            <Logo className="" showText={false} />
            <div>
              <h2 className="text-2xl font-semibold text-gray-900">Create your account</h2>
              <p className="text-sm text-gray-500">
                {selectedPlan
                  ? `Sign up to continue with the ${selectedPlan} plan`
                  : 'Sign up to access your dashboard.'}
              </p>
            </div>
          </div>

          {/* Show selected plan if coming from pricing */}
          {selectedPlan && (
            <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
              <p className="text-sm text-blue-800">
                <span className="font-semibold">Selected Plan:</span> {selectedPlan.charAt(0).toUpperCase() + selectedPlan.slice(1)}
                {planPrice > 0 && (
                  <span> — Rs {planPrice.toLocaleString()}/{isYearly ? 'yr' : 'mo'}</span>
                )}
                {selectedPlan === 'standard' && (
                  <span className="ml-2 text-emerald-700 font-medium">(7-day free trial available)</span>
                )}
              </p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {error   && <div className="text-red-600 text-sm bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</div>}
            {success && <div className="text-green-700 text-sm bg-green-50 border border-green-200 rounded-lg px-3 py-2">{success}</div>}

            <div>
              <label className="block text-sm text-gray-700 mb-2">Full Name</label>
              <input
                type="text" required value={name}
                onChange={e => setName(e.target.value)}
                placeholder="John Doe"
                className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-300"
              />
            </div>

            <div>
              <label className="block text-sm text-gray-700 mb-2">Email</label>
              <input
                type="email" required value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-300"
              />
            </div>

            <div>
              <label className="block text-sm text-gray-700 mb-2">Password</label>
              <input
                type="password" required minLength={6} value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="At least 6 characters"
                className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-300"
              />
            </div>

            <div>
              <label className="block text-sm text-gray-700 mb-2">Confirm Password</label>
              <input
                type="password" required minLength={6} value={confirmPassword}
                onChange={e => setConfirmPassword(e.target.value)}
                placeholder="Repeat your password"
                className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-300"
              />
            </div>

            <button
              type="submit" disabled={isLoading}
              className="w-full bg-gradient-to-r from-green-500 to-blue-600 text-white px-5 py-3 rounded-lg font-medium shadow hover:from-green-600 hover:to-blue-700 transition disabled:opacity-50"
            >
              {isLoading ? 'Creating account...' : 'Create account'}
            </button>

            <div className="pt-2 text-center text-sm text-gray-600">
              Already have an account?{' '}
              <Link
                to="/login"
                state={{ from, selectedPlan, planPrice, isYearly }}
                className="text-blue-600 font-medium hover:underline"
              >
                Sign in
              </Link>
            </div>
          </form>

        </div>
      </div>
    </div>
  </div>
  );
}