import React, { useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import Header from '../../components/Header';
import Logo from '../../components/Logo';
import { authAPI } from '../../services/apiService';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const location = useLocation() as any;

  const from = location.state?.from || '/dashboard';
  const selectedPlan = location.state?.selectedPlan;
  const planPrice = location.state?.planPrice;
  const isYearly = location.state?.isYearly;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      const response = await authAPI.login({ email, password });
      
      // Store auth data
      localStorage.setItem('auth', JSON.stringify({
        email: response.email,
        user_id: response.user_id,
        token: response.access_token,
        plan: response.plan,
        name: response.name,
        loginTime: new Date().toISOString()
      }));
      
      // Navigate with plan info if available
      if (selectedPlan) {
        navigate(from, { 
          replace: true, 
          state: { 
            selectedPlan, 
            planPrice, 
            isYearly 
          } 
        });
      } else {
        navigate(from, { replace: true });
      }
    } catch (err: any) {
      setError(err.message || 'Invalid email or password.');
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
              <div>
                <Logo className="" showText={false} />
              </div>
              <div>
                <h2 className="text-2xl font-semibold text-gray-900">Welcome back</h2>
                <p className="text-sm text-gray-500">
                  {selectedPlan
                    ? `Sign in to continue with ${selectedPlan} plan`
                    : 'Sign in to continue to your dashboard.'}
                </p>
              </div>
            </div>

            {selectedPlan && (
              <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                <p className="text-sm text-blue-800">
                  <span className="font-semibold">Selected Plan:</span> {selectedPlan}
                  {planPrice > 0 && <span> - ${planPrice}/{isYearly ? 'year' : 'month'}</span>}
                </p>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              {error && <div className="text-red-600 text-sm">{error}</div>}

              <div>
                <label className="block text-sm text-gray-700 mb-2">Email</label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-300"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-700 mb-2">Password</label>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Your password"
                  className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-300"
                />
              </div>

              <div className="flex items-center justify-between">
                <button
                  type="submit"
                  disabled={isLoading}
                  className="flex-1 bg-gradient-to-r from-blue-600 to-indigo-600 text-white px-5 py-3 rounded-lg font-medium shadow hover:from-blue-700 hover:to-indigo-700 transition disabled:opacity-50"
                >
                  {isLoading ? 'Signing in...' : 'Sign in'}
                </button>
              </div>

              <div className="pt-4 text-center text-sm text-gray-600">
                Don't have an account? <Link to="/signup" className="text-blue-600 font-medium">Create one</Link>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
