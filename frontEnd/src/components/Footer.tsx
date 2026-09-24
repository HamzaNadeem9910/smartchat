import React from 'react';
import { Link } from 'react-router-dom';
import { MessageCircle, Linkedin, Twitter, Youtube, Instagram, Mail, Phone, MapPin, ArrowRight } from 'lucide-react';

export default function Footer() {
  return (
    <footer className="bg-gradient-to-br from-gray-900 via-black to-gray-800 text-white relative overflow-hidden">
      {/* Background Pattern */}
      <div className="absolute inset-0 opacity-5">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-blue-500 rounded-full filter blur-3xl"></div>
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-purple-500 rounded-full filter blur-3xl"></div>
      </div>
      
      <div className="relative">
        {/* Main Footer Content */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-12">
            {/* Company Info */}
            <div className="lg:col-span-1 space-y-6">
              <div className="flex items-center space-x-3 mb-6">
                <div className="w-10 h-10 bg-gradient-to-r from-blue-500 to-purple-600 rounded-xl flex items-center justify-center shadow-lg">
                  <MessageCircle className="w-6 h-6 text-white" />
                </div>
                <span className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
                  Smartchat
                </span>
              </div>
              
              <p className="text-gray-300 leading-relaxed">
                Revolutionizing customer engagement with AI-powered chatbots that understand, learn, and adapt to your business needs.
              </p>
              
              {/* Contact Info */}
              <div className="space-y-3">
                <div className="flex items-center space-x-3 text-gray-400">
                  <Mail className="w-4 h-4" />
                  <span className="text-sm">hello@smartchat.com</span>
                </div>
                <div className="flex items-center space-x-3 text-gray-400">
                  <Phone className="w-4 h-4" />
                  <span className="text-sm">+92 310 7125676</span>
                </div>
                <div className="flex items-center space-x-3 text-gray-400">
                  <MapPin className="w-4 h-4" />
                  <span className="text-sm">Gujranwala , Pakistan</span>
                </div>
              </div>
              
              {/* Newsletter Signup */}
              <div className="mt-8">
                <h4 className="text-sm font-semibold text-white mb-3">Stay Updated</h4>
                <div className="flex">
                  <input 
                    type="email" 
                    placeholder="Enter your email"
                    className="flex-1 bg-gray-800/50 border border-gray-600 rounded-l-lg px-4 py-3 text-white placeholder-gray-400 focus:outline-none focus:border-blue-500 transition-colors"
                  />
                  <button className="bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 px-6 py-3 rounded-r-lg transition-all duration-300 transform hover:scale-105">
                    <ArrowRight className="w-5 h-5" />
                  </button>
                </div>
              </div>
            </div>

            {/* Product Links */}
            <div>
              <h3 className="text-lg font-semibold mb-6 text-white">Product</h3>
              <ul className="space-y-4">
                <li><a href="#" className="text-gray-400 hover:text-blue-400 transition-colors duration-200 flex items-center group">
                  <span>Features</span>
                  <ArrowRight className="w-4 h-4 ml-2 opacity-0 group-hover:opacity-100 transform group-hover:translate-x-1 transition-all duration-200" />
                </a></li>
                <li><Link to="/pricing" className="text-gray-400 hover:text-blue-400 transition-colors duration-200 flex items-center group">
                  <span>Pricing</span>
                  <ArrowRight className="w-4 h-4 ml-2 opacity-0 group-hover:opacity-100 transform group-hover:translate-x-1 transition-all duration-200" />
                </Link></li>
                <li><a href="#" className="text-gray-400 hover:text-blue-400 transition-colors duration-200 flex items-center group">
                  <span>Integrations</span>
                  <ArrowRight className="w-4 h-4 ml-2 opacity-0 group-hover:opacity-100 transform group-hover:translate-x-1 transition-all duration-200" />
                </a></li>
                <li><a href="#" className="text-gray-400 hover:text-blue-400 transition-colors duration-200 flex items-center group">
                  <span>API</span>
                  <ArrowRight className="w-4 h-4 ml-2 opacity-0 group-hover:opacity-100 transform group-hover:translate-x-1 transition-all duration-200" />
                </a></li>
                <li><a href="#" className="text-gray-400 hover:text-blue-400 transition-colors duration-200 flex items-center group">
                  <span>Security</span>
                  <ArrowRight className="w-4 h-4 ml-2 opacity-0 group-hover:opacity-100 transform group-hover:translate-x-1 transition-all duration-200" />
                </a></li>
              </ul>
            </div>

            {/* Resources Links */}
            <div>
              <h3 className="text-lg font-semibold mb-6 text-white">Resources</h3>
              <ul className="space-y-4">
                <li><a href="#" className="text-gray-400 hover:text-blue-400 transition-colors duration-200 flex items-center group">
                  <span>Documentation</span>
                  <ArrowRight className="w-4 h-4 ml-2 opacity-0 group-hover:opacity-100 transform group-hover:translate-x-1 transition-all duration-200" />
                </a></li>
                <li><a href="#" className="text-gray-400 hover:text-blue-400 transition-colors duration-200 flex items-center group">
                  <span>Tutorials</span>
                  <ArrowRight className="w-4 h-4 ml-2 opacity-0 group-hover:opacity-100 transform group-hover:translate-x-1 transition-all duration-200" />
                </a></li>
                <li><a href="#" className="text-gray-400 hover:text-blue-400 transition-colors duration-200 flex items-center group">
                  <span>Blog</span>
                  <ArrowRight className="w-4 h-4 ml-2 opacity-0 group-hover:opacity-100 transform group-hover:translate-x-1 transition-all duration-200" />
                </a></li>
                <li><a href="#" className="text-gray-400 hover:text-blue-400 transition-colors duration-200 flex items-center group">
                  <span>Case Studies</span>
                  <ArrowRight className="w-4 h-4 ml-2 opacity-0 group-hover:opacity-100 transform group-hover:translate-x-1 transition-all duration-200" />
                </a></li>
                <li><a href="#" className="text-gray-400 hover:text-blue-400 transition-colors duration-200 flex items-center group">
                  <span>Support</span>
                  <ArrowRight className="w-4 h-4 ml-2 opacity-0 group-hover:opacity-100 transform group-hover:translate-x-1 transition-all duration-200" />
                </a></li>
              </ul>
            </div>

            {/* Company Links */}
            <div>
              <h3 className="text-lg font-semibold mb-6 text-white">Company</h3>
              <ul className="space-y-4">
                <li><a href="#" className="text-gray-400 hover:text-blue-400 transition-colors duration-200 flex items-center group">
                  <span>About Us</span>
                  <ArrowRight className="w-4 h-4 ml-2 opacity-0 group-hover:opacity-100 transform group-hover:translate-x-1 transition-all duration-200" />
                </a></li>
                <li><a href="#" className="text-gray-400 hover:text-blue-400 transition-colors duration-200 flex items-center group">
                  <span>Careers</span>
                  <ArrowRight className="w-4 h-4 ml-2 opacity-0 group-hover:opacity-100 transform group-hover:translate-x-1 transition-all duration-200" />
                </a></li>
                <li><a href="#" className="text-gray-400 hover:text-blue-400 transition-colors duration-200 flex items-center group">
                  <span>Press</span>
                  <ArrowRight className="w-4 h-4 ml-2 opacity-0 group-hover:opacity-100 transform group-hover:translate-x-1 transition-all duration-200" />
                </a></li>
                <li><a href="#" className="text-gray-400 hover:text-blue-400 transition-colors duration-200 flex items-center group">
                  <span>Partners</span>
                  <ArrowRight className="w-4 h-4 ml-2 opacity-0 group-hover:opacity-100 transform group-hover:translate-x-1 transition-all duration-200" />
                </a></li>
              </ul>
            </div>
          </div>
        </div>

        {/* Social Links & Bottom Bar */}
        <div className="border-t border-gray-700/50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            <div className="flex flex-col md:flex-row justify-between items-center space-y-6 md:space-y-0">
              {/* Social Links */}
              <div className="flex items-center space-x-6">
                <span className="text-gray-400 text-sm font-medium">Follow us:</span>
                <div className="flex items-center space-x-4">
                  <a href="#" className="w-10 h-10 bg-gray-800/50 hover:bg-blue-600 rounded-xl flex items-center justify-center transition-all duration-300 transform hover:scale-110 hover:shadow-lg">
                    <Linkedin className="w-5 h-5" />
                  </a>
                  <a href="#" className="w-10 h-10 bg-gray-800/50 hover:bg-pink-600 rounded-xl flex items-center justify-center transition-all duration-300 transform hover:scale-110 hover:shadow-lg">
                    <Instagram className="w-5 h-5" />
                  </a>
                  <a href="#" className="w-10 h-10 bg-gray-800/50 hover:bg-blue-400 rounded-xl flex items-center justify-center transition-all duration-300 transform hover:scale-110 hover:shadow-lg">
                    <Twitter className="w-5 h-5" />
                  </a>
                  <a href="#" className="w-10 h-10 bg-gray-800/50 hover:bg-red-600 rounded-xl flex items-center justify-center transition-all duration-300 transform hover:scale-110 hover:shadow-lg">
                    <Youtube className="w-5 h-5" />
                  </a>
                </div>
              </div>
              
              {/* Legal Links & Copyright */}
              <div className="flex flex-col md:flex-row items-center space-y-4 md:space-y-0 md:space-x-8">
                <div className="flex items-center space-x-6 text-sm">
                  <a href="#" className="text-gray-400 hover:text-white transition-colors duration-200">Privacy Policy</a>
                  <a href="#" className="text-gray-400 hover:text-white transition-colors duration-200">Terms of Service</a>
                  <a href="#" className="text-gray-400 hover:text-white transition-colors duration-200">Cookie Policy</a>
                </div>
                <div className="text-gray-400 text-sm">
                  © 2026 Smartchat. All rights reserved.
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Trust Badges */}
        <div className="bg-gradient-to-r from-gray-800/30 to-gray-700/30 backdrop-blur-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
            <div className="flex items-center justify-center space-x-12">
              <div className="flex items-center space-x-3">
                <div className="w-12 h-12 bg-gradient-to-r from-green-500 to-emerald-600 rounded-xl flex items-center justify-center shadow-lg">
                  <div className="text-center">
                    <div className="text-xs font-bold text-white">SOC 2</div>
                    <div className="text-xs text-white opacity-80">TYPE II</div>
                  </div>
                </div>
                <span className="text-sm font-medium text-gray-300">SOC 2 Certified</span>
              </div>
              
              <div className="flex items-center space-x-3">
                <div className="w-12 h-12 bg-gradient-to-r from-blue-500 to-cyan-600 rounded-xl flex items-center justify-center shadow-lg">
                  <div className="text-center">
                    <div className="text-xs font-bold text-white">GDPR</div>
                    <div className="text-xs text-white opacity-80">Ready</div>
                  </div>
                </div>
                <span className="text-sm font-medium text-gray-300">GDPR Compliant</span>
              </div>
              
              <div className="flex items-center space-x-3">
                <div className="w-12 h-12 bg-gradient-to-r from-purple-500 to-pink-600 rounded-xl flex items-center justify-center shadow-lg">
                  <div className="text-center">
                    <div className="text-xs font-bold text-white">99.9%</div>
                    <div className="text-xs text-white opacity-80">Uptime</div>
                  </div>
                </div>
                <span className="text-sm font-medium text-gray-300">High Availability</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}