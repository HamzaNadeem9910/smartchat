import React, { useState, useEffect } from 'react';
import { 
  Menu, 
  ChevronDown, 
  Send, 
  MessageCircle, 
  Play,
  Pause,
  CreditCard,
  Bot,
  Palette,
  Shield,
  Sparkles,
  Settings,
  Lock,
  Volume2,
  Check,
  Star,
  Users,
  Zap,
  Globe,
  ArrowRight,
  Quote,
  Linkedin,
  Twitter,
  Youtube,
  Instagram,
  Mail,
  Phone,
  MapPin
} from 'lucide-react';

function App() {
  const [isPlaying, setIsPlaying] = useState(false);
  const [chatMessage, setChatMessage] = useState("I want to upg");
  const [currentMessageIndex, setCurrentMessageIndex] = useState(0);
  const [isTyping, setIsTyping] = useState(false);

  const conversationFlow = [
    { type: 'bot', message: "Hi! How can I help you today?", delay: 1000 },
    { type: 'user', message: "I want to upgrade my plan", delay: 2000 },
    { type: 'bot', message: "I'd be happy to help you upgrade! What features are you looking for?", delay: 1500 },
    { type: 'user', message: "I need more storage and advanced analytics", delay: 2500 },
    { type: 'bot', message: "Perfect! Our Pro plan includes 100GB storage and advanced analytics. Would you like me to upgrade you now?", delay: 2000 },
    { type: 'user', message: "Yes, please!", delay: 1000 },
    { type: 'bot', message: "Great! I've upgraded your account to Pro. You'll see the new features in your dashboard shortly. Is there anything else I can help with?", delay: 2500 }
  ];

  useEffect(() => {
    let timer;
    if (isPlaying && currentMessageIndex < conversationFlow.length) {
      setIsTyping(true);
      timer = setTimeout(() => {
        setIsTyping(false);
        setCurrentMessageIndex(prev => prev + 1);
      }, conversationFlow[currentMessageIndex].delay);
    } else if (isPlaying && currentMessageIndex >= conversationFlow.length) {
      // Reset conversation after completion
      setTimeout(() => {
        setCurrentMessageIndex(0);
      }, 3000);
    }
    return () => clearTimeout(timer);
  }, [isPlaying, currentMessageIndex]);

  const handlePlayPause = () => {
    setIsPlaying(!isPlaying);
    if (!isPlaying && currentMessageIndex >= conversationFlow.length) {
      setCurrentMessageIndex(0);
    }
  };

  const displayedMessages = conversationFlow.slice(0, currentMessageIndex);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            {/* Logo */}
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-black rounded-md flex items-center justify-center">
                <MessageCircle className="w-5 h-5 text-white" />
              </div>
              <span className="text-xl font-semibold text-gray-900">SmartChat</span>
            </div>

            {/* Navigation */}
            <nav className="hidden md:flex items-center space-x-8">
              <a href="#" className="text-gray-700 hover:text-gray-900 transition-colors">
                Pricing
              </a>
              <a href="#" className="text-gray-700 hover:text-gray-900 transition-colors">
                Enterprise
              </a>
              <a href="#" className="text-gray-700 hover:text-gray-900 transition-colors">
                About Us
              </a>
              <a href="#" className="text-gray-700 hover:text-gray-900 transition-colors">
                Contact Us
              </a>
              <a href="#" className="text-gray-700 hover:text-gray-900 transition-colors">
                Dashboard
              </a>
            </nav>

            {/* Mobile menu button */}
            <button className="md:hidden">
              <Menu className="w-6 h-6 text-gray-700" />
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* Video Section */}
        <div className="mb-20">
          <div className="text-center mb-12">
            <div className="inline-flex items-center space-x-2 bg-blue-100 text-blue-600 px-4 py-2 rounded-full text-sm font-medium mb-6">
              <Volume2 className="w-4 h-4" />
              <span>Live Demo</span>
            </div>
            <h2 className="text-4xl lg:text-5xl font-bold text-gray-900 mb-4">
              Watch our AI support agent in action
            </h2>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto">
              See how SmartChat handles real customer conversations with intelligent responses and seamless problem resolution.
            </p>
          </div>

          {/* Video Player */}
          <div className="max-w-4xl mx-auto">
            <div className="relative bg-white rounded-2xl shadow-2xl border border-gray-200 overflow-hidden">
              {/* Video Header */}
              <div className="bg-gradient-to-r from-blue-500 to-blue-600 px-6 py-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="w-8 h-8 bg-white rounded-full flex items-center justify-center">
                      <MessageCircle className="w-4 h-4 text-blue-600" />
                    </div>
                    <div>
                      <h3 className="text-white font-semibold">AI Support Agent</h3>
                      <p className="text-blue-100 text-sm flex items-center">
                        <div className="w-2 h-2 bg-green-400 rounded-full mr-2"></div>
                        Online • Responding instantly
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    <div className="text-blue-100 text-sm">Live conversation</div>
                    <div className="w-3 h-3 bg-red-400 rounded-full animate-pulse"></div>
                  </div>
                </div>
              </div>

              {/* Chat Messages */}
              <div className="p-6 space-y-4 h-96 overflow-y-auto bg-gray-50">
                {displayedMessages.map((msg, index) => (
                  <div key={index} className={`flex items-start space-x-3 ${msg.type === 'user' ? 'justify-end' : ''}`}>
                    {msg.type === 'bot' && (
                      <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center flex-shrink-0">
                        <Bot className="w-4 h-4 text-blue-600" />
                      </div>
                    )}
                    <div className={`rounded-lg px-4 py-3 max-w-xs lg:max-w-md ${
                      msg.type === 'bot' 
                        ? 'bg-white border border-gray-200 text-gray-800' 
                        : 'bg-blue-600 text-white'
                    } animate-fade-in`}>
                      <p className="text-sm">{msg.message}</p>
                    </div>
                    {msg.type === 'user' && (
                      <div className="w-8 h-8 bg-gray-300 rounded-full flex-shrink-0"></div>
                    )}
                  </div>
                ))}
                
                {/* Typing Indicator */}
                {isTyping && (
                  <div className="flex items-start space-x-3">
                    <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                      <Bot className="w-4 h-4 text-blue-600" />
                    </div>
                    <div className="bg-white border border-gray-200 rounded-lg px-4 py-3">
                      <div className="flex space-x-1">
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Video Controls */}
              <div className="bg-white border-t border-gray-200 px-6 py-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-4">
                    <button
                      onClick={handlePlayPause}
                      className="w-12 h-12 bg-blue-600 hover:bg-blue-700 rounded-full flex items-center justify-center transition-colors duration-200 shadow-lg"
                    >
                      {isPlaying ? (
                        <Pause className="w-5 h-5 text-white" />
                      ) : (
                        <Play className="w-5 h-5 text-white ml-0.5" />
                      )}
                    </button>
                    <div className="text-sm text-gray-600">
                      {isPlaying ? 'Playing live demo' : 'Click to start demo'}
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-2 text-sm text-gray-500">
                    <div className="flex items-center space-x-1">
                      <div className="w-2 h-2 bg-green-400 rounded-full"></div>
                      <span>AI Response Time: &lt;1s</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="grid lg:grid-cols-2 gap-12 items-center">
          {/* Left Column - Hero Content */}
          <div className="space-y-8">
            <div className="space-y-6">
              <h1 className="text-5xl lg:text-6xl font-bold text-gray-900 leading-tight">
                AI agents for magical customer experiences
              </h1>
              <p className="text-xl text-gray-600 leading-relaxed">
                SmartChat is the complete platform for building & deploying AI support agents for your business.
              </p>
            </div>

            {/* CTA Button */}
            <div className="space-y-4">
              <button className="group relative bg-gradient-to-r from-orange-500 to-pink-500 text-white px-8 py-4 rounded-lg font-semibold text-lg hover:from-orange-600 hover:to-pink-600 transform hover:scale-105 transition-all duration-200 shadow-lg hover:shadow-xl">
                Build your agent
                <div className="absolute inset-0 bg-gradient-to-r from-orange-400 to-pink-400 rounded-lg opacity-0 group-hover:opacity-20 transition-opacity duration-200"></div>
              </button>
              <div className="flex items-center space-x-2 text-gray-600">
                <CreditCard className="w-4 h-4" />
                <span className="text-sm">No credit card required</span>
              </div>
            </div>
          </div>

          {/* Right Column - Chat Demo */}
          <div className="relative">
            <div className="bg-white rounded-2xl shadow-2xl border border-gray-200 overflow-hidden">
              {/* Chat Header */}
              <div className="bg-gradient-to-r from-blue-500 to-blue-600 px-6 py-4">
                <div className="flex items-center space-x-3">
                  <div className="w-8 h-8 bg-white rounded-full flex items-center justify-center">
                    <MessageCircle className="w-4 h-4 text-blue-600" />
                  </div>
                  <div>
                    <h3 className="text-white font-semibold">Support Agent</h3>
                    <p className="text-blue-100 text-sm">Online</p>
                  </div>
                </div>
              </div>

              {/* Chat Messages */}
              <div className="p-6 space-y-4 h-80">
                <div className="flex items-start space-x-3">
                  <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                    <MessageCircle className="w-4 h-4 text-blue-600" />
                  </div>
                  <div className="bg-gray-100 rounded-lg px-4 py-3 max-w-xs">
                    <p className="text-gray-800">Hi! How can I help you today?</p>
                  </div>
                </div>

                <div className="flex items-start space-x-3 justify-end">
                  <div className="bg-blue-600 text-white rounded-lg px-4 py-3 max-w-xs">
                    <p>I want to upgrade my plan</p>
                  </div>
                  <div className="w-8 h-8 bg-gray-300 rounded-full"></div>
                </div>

                <div className="flex items-start space-x-3">
                  <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                    <MessageCircle className="w-4 h-4 text-blue-600" />
                  </div>
                  <div className="bg-gray-100 rounded-lg px-4 py-3 max-w-xs">
                    <p className="text-gray-800">I'd be happy to help you upgrade! What features are you looking for?</p>
                  </div>
                </div>
              </div>

              {/* Chat Input */}
              <div className="border-t border-gray-200 p-4">
                <div className="flex items-center space-x-3">
                  <div className="flex-1 relative">
                    <input
                      type="text"
                      value={chatMessage}
                      onChange={(e) => setChatMessage(e.target.value)}
                      placeholder="Type your message..."
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                    <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
                      <Send className="w-5 h-5 text-gray-400" />
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Play/Pause Button */}
            <div className="flex justify-center mt-8">
              <button
                onClick={() => setIsPlaying(!isPlaying)}
                className="w-16 h-16 bg-gray-200 hover:bg-gray-300 rounded-full flex items-center justify-center transition-colors duration-200 shadow-lg"
              >
                {isPlaying ? (
                  <Pause className="w-6 h-6 text-gray-700" />
                ) : (
                  <Play className="w-6 h-6 text-gray-700 ml-1" />
                )}
              </button>
            </div>
          </div>
        </div>
      </main>

      {/* Features Section */}
      <section className="bg-white py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-4xl lg:text-5xl font-bold text-gray-900 mb-6">
              Everything you need to scale customer support
            </h2>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto">
              Our comprehensive platform provides all the tools and features you need to deliver exceptional customer experiences at scale.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {[
              {
                icon: <Zap className="w-8 h-8" />,
                title: "Instant Responses",
                description: "AI-powered responses in under 1 second, ensuring your customers never wait."
              },
              {
                icon: <Globe className="w-8 h-8" />,
                title: "Multi-language Support",
                description: "Support customers in 95+ languages with automatic translation and localization."
              },
              {
                icon: <Users className="w-8 h-8" />,
                title: "Team Collaboration",
                description: "Seamless handoff between AI and human agents when complex issues arise."
              },
              {
                icon: <Shield className="w-8 h-8" />,
                title: "Enterprise Security",
                description: "SOC 2 compliant with end-to-end encryption and advanced security features."
              },
              {
                icon: <Bot className="w-8 h-8" />,
                title: "Smart Learning",
                description: "AI that learns from every interaction to provide better responses over time."
              },
              {
                icon: <Settings className="w-8 h-8" />,
                title: "Easy Integration",
                description: "Connect with your existing tools and workflows in minutes, not hours."
              }
            ].map((feature, index) => (
              <div key={index} className="group p-8 rounded-2xl border border-gray-100 hover:border-blue-200 hover:shadow-lg transition-all duration-300">
                <div className="w-16 h-16 bg-blue-100 rounded-2xl flex items-center justify-center text-blue-600 mb-6 group-hover:bg-blue-600 group-hover:text-white transition-colors duration-300">
                  {feature.icon}
                </div>
                <h3 className="text-xl font-semibold text-gray-900 mb-3">{feature.title}</h3>
                <p className="text-gray-600 leading-relaxed">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Trusted Companies Section */}
      <section className="bg-white py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <p className="text-lg text-gray-600">
              <span className="font-semibold text-gray-900">Trusted by 9000+</span> business worldwide
            </p>
          </div>
          
          {/* Company Logos */}
          <div className="flex flex-wrap justify-center items-center gap-8 md:gap-12 opacity-60">
            <div className="text-2xl font-bold text-gray-700">SIEMENS</div>
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-gray-700 rounded-full"></div>
              <span className="text-xl font-semibold text-gray-700">POSTMAN</span>
            </div>
            <div className="text-xl font-bold text-gray-700">pwc</div>
            <div className="text-xl font-bold text-gray-700">+alpian</div>
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-gray-700 rounded-full"></div>
              <span className="text-xl font-semibold text-gray-700">Opal</span>
            </div>
            <div className="text-xl font-bold text-gray-700">alBaraka<span className="text-sm">%</span></div>
          </div>
        </div>
      </section>

      {/* Highlights Section */}
      <section className="bg-gray-50 py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-16 items-center">
            {/* Left Column - Content */}
            <div className="space-y-8">
              <div className="inline-flex items-center space-x-2 bg-pink-100 text-pink-600 px-4 py-2 rounded-full text-sm font-medium">
                <div className="w-2 h-2 bg-pink-500 rounded-full"></div>
                <span>Highlights</span>
              </div>
              
              <h2 className="text-4xl lg:text-5xl font-bold text-gray-900 leading-tight">
                The complete platform for AI support agents
              </h2>
              
              <p className="text-xl text-gray-600 leading-relaxed">
                SmartChat is designed for building AI support agents that solve your customers' hardest problems while improving business outcomes.
              </p>
            </div>

            {/* Right Column - Feature Cards */}
            <div className="space-y-6">
              {/* Purpose-built for LLMs Card */}
              <div className="bg-white rounded-2xl p-8 shadow-sm border border-gray-100">
                <div className="space-y-6">
                  {/* Icons Grid */}
                  <div className="grid grid-cols-4 gap-4">
                    <div className="w-12 h-12 bg-black rounded-xl flex items-center justify-center">
                      <span className="text-white font-bold text-xl">C</span>
                    </div>
                    <div className="w-12 h-12 bg-gradient-to-br from-blue-400 to-blue-600 rounded-xl flex items-center justify-center">
                      <Bot className="w-6 h-6 text-white" />
                    </div>
                    <div className="w-12 h-12 bg-white border-2 border-gray-200 rounded-xl flex items-center justify-center">
                      <span className="text-2xl font-bold text-blue-500">AI</span>
                    </div>
                    <div className="w-12 h-12 bg-white border-2 border-gray-200 rounded-xl flex items-center justify-center">
                      <div className="w-6 h-6 bg-gradient-to-br from-red-400 to-yellow-400 rounded-full"></div>
                    </div>
                    <div className="w-12 h-12 bg-white border-2 border-gray-200 rounded-xl flex items-center justify-center">
                      <div className="w-6 h-6 bg-gradient-to-br from-green-400 to-blue-400 rounded-full"></div>
                    </div>
                    <div className="w-12 h-12 bg-white border-2 border-gray-200 rounded-xl flex items-center justify-center">
                      <div className="w-6 h-6 bg-gradient-to-br from-purple-400 to-pink-400 rounded-full"></div>
                    </div>
                    <div className="w-12 h-12 bg-white border-2 border-gray-200 rounded-xl flex items-center justify-center">
                      <Palette className="w-5 h-5 text-gray-400" />
                    </div>
                    <div className="w-12 h-12 bg-gradient-to-br from-blue-400 to-purple-600 rounded-xl"></div>
                  </div>
                  
                  <div>
                    <h3 className="text-xl font-semibold text-gray-900 mb-2">Purpose-built for LLMs</h3>
                    <p className="text-gray-600">Language models with reasoning capabilities for effective responses to complex queries.</p>
                  </div>
                </div>
              </div>

              {/* Designed for simplicity Card */}
              <div className="bg-white rounded-2xl p-8 shadow-sm border border-gray-100">
                <div className="space-y-6">
                  {/* Simple Interface Mockup */}
                  <div className="bg-gray-50 rounded-xl p-6">
                    <div className="space-y-4">
                      {/* Toolbar */}
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <div className="w-6 h-6 bg-gray-300 rounded"></div>
                          <div className="w-6 h-6 bg-gray-300 rounded"></div>
                          <div className="w-6 h-6 bg-gray-300 rounded"></div>
                          <div className="w-6 h-6 bg-gray-300 rounded"></div>
                        </div>
                        <div className="flex items-center space-x-1">
                          <div className="w-3 h-3 bg-green-400 rounded-full"></div>
                          <div className="w-3 h-3 bg-yellow-400 rounded-full"></div>
                          <div className="w-3 h-3 bg-green-300 rounded-full"></div>
                        </div>
                      </div>
                      
                      {/* Create Agent Button */}
                      <div className="flex justify-center">
                        <button className="bg-gradient-to-r from-orange-500 to-pink-500 text-white px-6 py-2 rounded-lg font-medium">
                          Create agent
                        </button>
                      </div>
                      
                      {/* Toggle and AI Reply */}
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="text-sm text-gray-600">Auto-reply</span>
                          <div className="w-10 h-6 bg-green-400 rounded-full relative">
                            <div className="w-4 h-4 bg-white rounded-full absolute right-1 top-1"></div>
                          </div>
                        </div>
                        
                        <div className="flex items-center space-x-2 text-sm text-gray-600">
                          <Sparkles className="w-4 h-4" />
                          <span>Reply with AI</span>
                        </div>
                      </div>
                    </div>
                  </div>
                  
                  <div>
                    <h3 className="text-xl font-semibold text-gray-900 mb-2">Designed for simplicity</h3>
                    <p className="text-gray-600">Create, manage, and deploy AI Agents easily, even without technical skills.</p>
                  </div>
                </div>
              </div>

              {/* Engineered for security Card */}
              <div className="bg-white rounded-2xl p-8 shadow-sm border border-gray-100">
                <div className="space-y-6">
                  {/* Security Visual */}
                  <div className="relative">
                    <div className="bg-gradient-to-br from-orange-400 to-pink-500 rounded-2xl h-24 relative overflow-hidden">
                      <div className="absolute top-4 right-4">
                        <Settings className="w-6 h-6 text-white opacity-60" />
                      </div>
                      <div className="absolute bottom-4 right-4">
                        <div className="w-4 h-4 bg-white rounded-full opacity-60"></div>
                      </div>
                    </div>
                    
                    <div className="absolute -bottom-6 left-1/2 transform -translate-x-1/2">
                      <div className="w-16 h-16 bg-black rounded-2xl flex items-center justify-center shadow-lg">
                        <Lock className="w-8 h-8 text-white" />
                      </div>
                    </div>
                  </div>
                  
                  {/* Security Dots */}
                  <div className="flex justify-center space-x-2 pt-4">
                    {[...Array(8)].map((_, i) => (
                      <div key={i} className="w-2 h-2 bg-gray-300 rounded-full"></div>
                    ))}
                  </div>
                  
                  <div>
                    <h3 className="text-xl font-semibold text-gray-900 mb-2">Engineered for security</h3>
                    <p className="text-gray-600">Enjoy peace of mind with robust encryption and strict compliance standards.</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section className="bg-gray-50 py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-4xl lg:text-5xl font-bold text-gray-900 mb-6">
              Simple, transparent pricing
            </h2>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto">
              Choose the perfect plan for your business. Start free and scale as you grow.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            {[
              {
                name: "Starter",
                price: "Free",
                description: "Perfect for small teams getting started",
                features: [
                  "Up to 100 conversations/month",
                  "Basic AI responses",
                  "Email support",
                  "Standard integrations"
                ],
                cta: "Get Started",
                popular: false
              },
              {
                name: "Professional",
                price: "$49",
                description: "Best for growing businesses",
                features: [
                  "Up to 5,000 conversations/month",
                  "Advanced AI with learning",
                  "Priority support",
                  "All integrations",
                  "Custom branding",
                  "Analytics dashboard"
                ],
                cta: "Start Free Trial",
                popular: true
              },
              {
                name: "Enterprise",
                price: "Custom",
                description: "For large organizations",
                features: [
                  "Unlimited conversations",
                  "Custom AI training",
                  "Dedicated support",
                  "Advanced security",
                  "Custom integrations",
                  "SLA guarantee"
                ],
                cta: "Contact Sales",
                popular: false
              }
            ].map((plan, index) => (
              <div key={index} className={`relative bg-white rounded-2xl p-8 shadow-sm border-2 ${plan.popular ? 'border-blue-500' : 'border-gray-100'} hover:shadow-lg transition-shadow duration-300`}>
                {plan.popular && (
                  <div className="absolute -top-4 left-1/2 transform -translate-x-1/2">
                    <span className="bg-gradient-to-r from-blue-500 to-blue-600 text-white px-4 py-2 rounded-full text-sm font-medium">
                      Most Popular
                    </span>
                  </div>
                )}
                
                <div className="text-center mb-8">
                  <h3 className="text-2xl font-bold text-gray-900 mb-2">{plan.name}</h3>
                  <div className="mb-4">
                    <span className="text-4xl font-bold text-gray-900">{plan.price}</span>
                    {plan.price !== "Free" && plan.price !== "Custom" && <span className="text-gray-600">/month</span>}
                  </div>
                  <p className="text-gray-600">{plan.description}</p>
                </div>

                <ul className="space-y-4 mb-8">
                  {plan.features.map((feature, featureIndex) => (
                    <li key={featureIndex} className="flex items-center space-x-3">
                      <Check className="w-5 h-5 text-green-500 flex-shrink-0" />
                      <span className="text-gray-700">{feature}</span>
                    </li>
                  ))}
                </ul>

                <button className={`w-full py-3 px-6 rounded-lg font-semibold transition-colors duration-200 ${
                  plan.popular 
                    ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white hover:from-blue-600 hover:to-blue-700' 
                    : 'bg-gray-100 text-gray-900 hover:bg-gray-200'
                }`}>
                  {plan.cta}
                </button>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Testimonials Section */}
      <section className="bg-white py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-4xl lg:text-5xl font-bold text-gray-900 mb-6">
              Loved by teams worldwide
            </h2>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto">
              See what our customers have to say about their experience with SmartChat.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {[
              {
                quote: "SmartChat transformed our customer support. Response times dropped from hours to seconds, and customer satisfaction increased by 40%.",
                author: "Sarah Chen",
                role: "Head of Customer Success",
                company: "TechFlow Inc.",
                rating: 5
              },
              {
                quote: "The AI is incredibly smart and learns from our specific use cases. It's like having a team of expert support agents available 24/7.",
                author: "Michael Rodriguez",
                role: "Operations Manager",
                company: "GrowthLabs",
                rating: 5
              },
              {
                quote: "Implementation was seamless, and the results were immediate. Our support team can now focus on complex issues while AI handles routine queries.",
                author: "Emily Watson",
                role: "CTO",
                company: "InnovateCorp",
                rating: 5
              }
            ].map((testimonial, index) => (
              <div key={index} className="bg-gray-50 rounded-2xl p-8 relative">
                <Quote className="w-8 h-8 text-blue-500 mb-6" />
                
                <div className="flex mb-6">
                  {[...Array(testimonial.rating)].map((_, i) => (
                    <Star key={i} className="w-5 h-5 text-yellow-400 fill-current" />
                  ))}
                </div>
                
                <p className="text-gray-700 mb-6 leading-relaxed">"{testimonial.quote}"</p>
                
                <div className="flex items-center">
                  <div className="w-12 h-12 bg-gray-300 rounded-full mr-4"></div>
                  <div>
                    <div className="font-semibold text-gray-900">{testimonial.author}</div>
                    <div className="text-sm text-gray-600">{testimonial.role}</div>
                    <div className="text-sm text-gray-500">{testimonial.company}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="bg-gradient-to-r from-blue-600 to-blue-700 py-20">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-4xl lg:text-5xl font-bold text-white mb-6">
            Ready to transform your customer support?
          </h2>
          <p className="text-xl text-blue-100 mb-8 max-w-2xl mx-auto">
            Join thousands of businesses already using SmartChat to deliver exceptional customer experiences.
          </p>
          
          <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
            <button className="group bg-white text-blue-600 px-8 py-4 rounded-lg font-semibold text-lg hover:bg-gray-50 transition-colors duration-200 flex items-center space-x-2">
              <span>Start Free Trial</span>
              <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform duration-200" />
            </button>
            <button className="text-blue-100 hover:text-white transition-colors duration-200 flex items-center space-x-2">
              <span>Schedule a Demo</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
          
          <div className="flex items-center justify-center space-x-6 mt-8 text-blue-200">
            <div className="flex items-center space-x-2">
              <Check className="w-4 h-4" />
              <span className="text-sm">No credit card required</span>
            </div>
            <div className="flex items-center space-x-2">
              <Check className="w-4 h-4" />
              <span className="text-sm">14-day free trial</span>
            </div>
            <div className="flex items-center space-x-2">
              <Check className="w-4 h-4" />
              <span className="text-sm">Cancel anytime</span>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-black text-white py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-12 mb-12">
            {/* Company Info */}
            <div className="lg:col-span-1">
              <div className="flex items-center space-x-2 mb-6">
                <div className="w-8 h-8 bg-white rounded-md flex items-center justify-center">
                  <MessageCircle className="w-5 h-5 text-black" />
                </div>
                <span className="text-xl font-semibold">SmartChat</span>
              </div>
              <p className="text-gray-400 mb-6 leading-relaxed">
                © 2025 SmartChat, Inc.
              </p>
              
              {/* Contact Button and Social Links */}
              <div className="space-y-4">
                <button className="bg-gray-800 hover:bg-gray-700 text-white px-6 py-3 rounded-lg font-medium transition-colors duration-200">
                  Contact
                </button>
                
                <div className="flex items-center space-x-4">
                  <a href="#" className="w-10 h-10 bg-gray-800 hover:bg-gray-700 rounded-lg flex items-center justify-center transition-colors duration-200">
                    <Linkedin className="w-5 h-5" />
                  </a>
                  <a href="#" className="w-10 h-10 bg-gray-800 hover:bg-gray-700 rounded-lg flex items-center justify-center transition-colors duration-200">
                    <Instagram className="w-5 h-5" />
                  </a>
                  <a href="#" className="w-10 h-10 bg-gray-800 hover:bg-gray-700 rounded-lg flex items-center justify-center transition-colors duration-200">
                    <Twitter className="w-5 h-5" />
                  </a>
                  <a href="#" className="w-10 h-10 bg-gray-800 hover:bg-gray-700 rounded-lg flex items-center justify-center transition-colors duration-200">
                    <Youtube className="w-5 h-5" />
                  </a>
                </div>
              </div>
              
              {/* Compliance Badges */}
              <div className="flex items-center space-x-4 mt-8">
                <div className="w-16 h-16 bg-gray-800 rounded-full flex items-center justify-center">
                  <div className="text-center">
                    <div className="text-xs font-bold">AICPA</div>
                    <div className="text-xs">SOC 2</div>
                  </div>
                </div>
                <div className="w-16 h-16 bg-gray-800 rounded-full flex items-center justify-center">
                  <div className="text-center">
                    <div className="text-xs font-bold">GDPR</div>
                    <div className="flex justify-center mt-1">
                      {[...Array(12)].map((_, i) => (
                        <div key={i} className="w-1 h-1 bg-white rounded-full mx-0.5" />
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Product Links */}
            <div>
              <h3 className="text-lg font-semibold mb-6">PRODUCT</h3>
              <ul className="space-y-4">
                <li><a href="#" className="text-gray-400 hover:text-white transition-colors duration-200">Customer Service</a></li>
                <li><a href="#" className="text-gray-400 hover:text-white transition-colors duration-200">Pricing</a></li>
                <li><a href="#" className="text-gray-400 hover:text-white transition-colors duration-200">Security</a></li>
                <li><a href="#" className="text-gray-400 hover:text-white transition-colors duration-200">Affiliates</a></li>
              </ul>
            </div>

            {/* Resources Links */}
            <div>
              <h3 className="text-lg font-semibold mb-6">RESOURCES</h3>
              <ul className="space-y-4">
                <li><a href="#" className="text-gray-400 hover:text-white transition-colors duration-200">Contact us</a></li>
                <li><a href="#" className="text-gray-400 hover:text-white transition-colors duration-200">API</a></li>
                <li><a href="#" className="text-gray-400 hover:text-white transition-colors duration-200">Guide</a></li>
                <li><a href="#" className="text-gray-400 hover:text-white transition-colors duration-200">Blog</a></li>
                <li><a href="#" className="text-gray-400 hover:text-white transition-colors duration-200">Changelog</a></li>
              </ul>
            </div>

            {/* Company Links */}
            <div>
              <h3 className="text-lg font-semibold mb-6">COMPANY</h3>
              <ul className="space-y-4">
                <li><a href="#" className="text-gray-400 hover:text-white transition-colors duration-200">Careers</a></li>
                <li><a href="#" className="text-gray-400 hover:text-white transition-colors duration-200">Privacy policy</a></li>
                <li><a href="#" className="text-gray-400 hover:text-white transition-colors duration-200">Terms of service</a></li>
                <li><a href="#" className="text-gray-400 hover:text-white transition-colors duration-200">DPA</a></li>
                <li><a href="#" className="text-gray-400 hover:text-white transition-colors duration-200">Cookie policy</a></li>
                <li><a href="#" className="text-gray-400 hover:text-white transition-colors duration-200">Trust center</a></li>
                <li><a href="#" className="text-gray-400 hover:text-white transition-colors duration-200">Cookie preferences</a></li>
              </ul>
            </div>
          </div>

          {/* Large SmartChat Text Background */}
          <div className="relative overflow-hidden">
            <div className="text-[12rem] lg:text-[16rem] font-bold text-gray-900 opacity-10 leading-none text-center select-none">
              SmartChat
            </div>
          </div>
        </div>
      </footer>

      {/* Chat Widget */}
      <div className="fixed bottom-6 right-6 z-50">
        <button className="w-14 h-14 bg-black hover:bg-gray-800 rounded-full flex items-center justify-center shadow-lg transition-colors duration-200">
          <MessageCircle className="w-6 h-6 text-white" />
        </button>
      </div>
    </div>
  );
}

export default App;