import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import HomePage from './pages/HomePage.tsx';
import PricingPage from './pages/PricingPage.tsx';
import EnterprisePage from './pages/EnterprisePage.tsx';
import AboutPage from './pages/AboutPage';
import ContactPage from './pages/ContactPage';
import DashboardPage from './pages/DashboardPage';
import AdminDashboardPage from './pages/AdminDashboardPage';
import LoginPage from './pages/auth/LoginPage';
import SignupPage from './pages/auth/SignupPage';
import AdminLoginPage from './pages/auth/AdminLoginPage';
import PaymentPage from './pages/PaymentPage';
import RequireAuth from './components/RequireAuth';
import RequireAdminAuth from './components/RequireAdminAuth';
import RequirePlan from './components/RequirePlan';
import './index.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>

        {/* Public */}
        <Route path="/"               element={<HomePage />} />
        <Route path="/pricing"        element={<PricingPage />} />
        <Route path="/enterprise"     element={<EnterprisePage />} />
        <Route path="/about"          element={<AboutPage />} />
        <Route path="/contact"        element={<ContactPage />} />
        <Route path="/login"          element={<LoginPage />} />
        <Route path="/signup"         element={<SignupPage />} />
        <Route path="/admin/login"    element={<AdminLoginPage />} />

        {/* Payment — requires login, but NOT a paid plan yet (they're trying to pay) */}
        <Route path="/payment" element={
          <RequireAuth>
            <PaymentPage />
          </RequireAuth>
        } />

        {/* Dashboard — requires login AND an active paid plan / trial */}
        <Route path="/dashboard" element={
          <RequireAuth>
            <RequirePlan>
              <DashboardPage />
            </RequirePlan>
          </RequireAuth>
        } />

        {/* Admin */}
        <Route path="/admin/dashboard" element={
          <RequireAdminAuth>
            <AdminDashboardPage />
          </RequireAdminAuth>
        } />

      </Routes>
    </BrowserRouter>
  </StrictMode>
);