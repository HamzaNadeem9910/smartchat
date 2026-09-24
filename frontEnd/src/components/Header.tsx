import React from 'react';
import { Link } from 'react-router-dom';
import { Menu } from 'lucide-react';
import Logo from './Logo';

export default function Header() {
  return (
    <header className="bg-white shadow-sm border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Logo */}
          <Logo />

          {/* Navigation */}
          <nav className="hidden md:flex items-center space-x-8">
            <Link to="/pricing" className="text-gray-700 hover:text-gray-900 transition-colors">
              Pricing
            </Link>
            <Link to="/enterprise" className="text-gray-700 hover:text-gray-900 transition-colors">
              Enterprise
            </Link>
            <Link to="/about" className="text-gray-700 hover:text-gray-900 transition-colors">
              About Us
            </Link>
            <Link to="/contact" className="text-gray-700 hover:text-gray-900 transition-colors">
              Contact Us
            </Link>
            <Link to="/dashboard" className="text-gray-700 hover:text-gray-900 transition-colors">
              Dashboard
            </Link>
          </nav>

          {/* Mobile menu button */}
          <button className="md:hidden">
            <Menu className="w-6 h-6 text-gray-700" />
          </button>
        </div>
      </div>
    </header>
  );
}