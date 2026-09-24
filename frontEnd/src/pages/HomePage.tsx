import { useState, useEffect } from 'react';
import { 
  Send, 
  MessageCircle, 
  Play,
  Pause,
  Shield,
  Check,
  Star,
  Zap,
  Globe,
  ArrowRight,
  Quote,
  ChevronRight,
  Rocket,
  Clock,
  BarChart3,
  Settings
} from 'lucide-react';
import Header from '../components/Header';
import Footer from '../components/Footer';

export default function HomePage() {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentMessageIndex, setCurrentMessageIndex] = useState(0);
  const [isTyping, setIsTyping] = useState(false);
  const [activeTab, setActiveTab] = useState<UseCaseKey>('customer-service');

  const conversationFlow = [
    { type: 'bot', message: "Hi! How can I help you today?", delay: 1000 },
    { type: 'user', message: "Uni konsi degrees offer kar rahi hain?", delay: 2200 },
    { type: 'bot', message: "Hamari university computer science, business administration, engineering, aur design mein undergraduate aur graduate programs offer karti hai.", delay: 2600 },
    { type: 'user', message: "Admission ka process kya hai?", delay: 2200 },
    { type: 'bot', message: "Aap online application bhar sakte hain, required documents upload kar sakte hain, aur entrance test ya interview ke liye schedule kar sakte hain.", delay: 2600 },
    { type: 'bot', message: "Kya aap apply karna chahenge? Agar haan, to hum lead capture kar sakte hain jisme name, phone, aur address liya ja sake.", delay: 2800 }
  ];

  useEffect(() => {
    let timer: NodeJS.Timeout | undefined;
    if (isPlaying && currentMessageIndex < conversationFlow.length) {
      setIsTyping(true);
      timer = setTimeout(() => {
        setIsTyping(false);
        setCurrentMessageIndex(prev => prev + 1);
      }, conversationFlow[currentMessageIndex].delay);
    } else if (isPlaying && currentMessageIndex >= conversationFlow.length) {
      timer = setTimeout(() => {
        setCurrentMessageIndex(0);
      }, 3000);
    }
    return () => {
      if (timer) clearTimeout(timer);
    };
  }, [isPlaying, currentMessageIndex]);

  useEffect(() => {
    const startTimer = setTimeout(() => {
      setIsPlaying(true);
    }, 500);
    return () => clearTimeout(startTimer);
  }, []);

  const handlePlayPause = () => {
    setIsPlaying(!isPlaying);
    if (!isPlaying && currentMessageIndex >= conversationFlow.length) {
      setCurrentMessageIndex(0);
    }
  };

  const displayedMessages = conversationFlow.slice(0, currentMessageIndex);

  const useCases = {
    'customer-service': {
      title: 'Customer Service',
      description: 'Automate support with intelligent responses',
      features: ['24/7 availability', 'Instant responses', 'Multi-language support', 'Escalation to humans'],
      demo: 'Customer asking about refund policy'
    },
    'lead-generation': {
      title: 'Lead Generation',
      description: 'Capture and qualify leads automatically',
      features: ['Lead scoring', 'Contact collection', 'Qualification questions', 'CRM integration'],
      demo: 'Visitor interested in product demo'
    },
    'sales-support': {
      title: 'Sales Support',
      description: 'Guide prospects through the sales funnel',
      features: ['Product recommendations', 'Pricing information', 'Demo scheduling', 'Follow-up automation'],
      demo: 'Prospect asking about pricing plans'
    }
  } as const;

  type UseCaseKey = keyof typeof useCases;

  return (
    <div className="min-h-screen bg-white">
      <Header />

      {/* Hero Section */}
      <section className="relative bg-gradient-to-br from-gray-900 via-black to-gray-800 pt-20 pb-32 overflow-hidden">
        {/* Background Elements */}
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute -top-40 -right-40 w-80 h-80 bg-gradient-to-br from-purple-500/20 to-pink-500/20 rounded-full blur-3xl animate-pulse"></div>
          <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-gradient-to-br from-blue-500/20 to-cyan-500/20 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }}></div>
          <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-gradient-to-br from-indigo-500/10 to-purple-500/10 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '2s' }}></div>
        </div>

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-16 items-center">
            {/* Left Column - Hero Content */}
            <div className="space-y-8">
              <div className="inline-flex items-center space-x-2 bg-gray-800 text-purple-400 px-4 py-2 rounded-full text-sm font-medium animate-fade-in-up border border-purple-500/30">
                <MessageCircle className="w-4 h-4" />
                <span>Smart Customer Support Platform</span>
              </div>
              
              <h1 className="text-5xl lg:text-7xl font-bold text-white leading-tight animate-fade-in-up" style={{ animationDelay: '0.1s' }}>
                Build chatbots that 
                <span className="bg-gradient-to-r from-purple-400 via-pink-400 to-cyan-400 bg-clip-text text-transparent animate-gradient-x"> deliver results</span>
              </h1>
              
              <p className="text-xl text-gray-300 leading-relaxed animate-fade-in-up" style={{ animationDelay: '0.2s' }}>
                Create smart chatbots that understand your customers, provide instant support, and drive business growth. No coding required.
              </p>

              <div className="flex flex-col sm:flex-row gap-4 animate-fade-in-up" style={{ animationDelay: '0.3s' }}>
                <button className="group bg-gradient-to-r from-purple-600 to-pink-600 text-white px-8 py-4 rounded-xl font-semibold text-lg hover:from-purple-700 hover:to-pink-700 transform hover:scale-105 transition-all duration-300 shadow-lg hover:shadow-2xl hover:shadow-purple-500/25 flex items-center space-x-2 animate-pulse-glow">
                  <span>Start Building Free</span>
                  <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform duration-200" />
                </button>
                <button className="group border-2 border-gray-600 text-gray-300 px-8 py-4 rounded-xl font-semibold text-lg hover:border-purple-500 hover:bg-gray-800 transition-all duration-300 flex items-center space-x-2 hover:shadow-lg hover:shadow-purple-500/20">
                  <Play className="w-5 h-5" />
                  <span>Watch Demo</span>
                </button>
              </div>

              <div className="flex items-center space-x-8 text-gray-400 animate-fade-in-up" style={{ animationDelay: '0.4s' }}>
                <div className="flex items-center space-x-2">
                  <Check className="w-4 h-4 text-purple-400" />
                  <span className="text-sm">No credit card required</span>
                </div>
                <div className="flex items-center space-x-2">
                  <Check className="w-4 h-4 text-purple-400" />
                  <span className="text-sm">Setup in 5 minutes</span>
                </div>
              </div>
            </div>

            {/* Right Column - Interactive Demo */}
            <div className="relative animate-fade-in-up" style={{ animationDelay: '0.2s' }}>
              <div className="bg-gray-800 rounded-2xl shadow-2xl border border-gray-700 overflow-hidden hover:shadow-purple-500/20 transition-all duration-300 animate-float">
                {/* Chat Header */}
                <div className="bg-gradient-to-r from-purple-600 to-pink-600 px-6 py-4">
                  <div className="flex items-center space-x-3">
                    <div className="w-10 h-10 bg-white rounded-full flex items-center justify-center">
                      <MessageCircle className="w-5 h-5 text-purple-600" />
                    </div>
                    <div>
                      <h3 className="text-white font-semibold">Support Assistant</h3>
                      <p className="text-purple-100 text-sm flex items-center">
                        <div className="w-2 h-2 bg-cyan-400 rounded-full mr-2 animate-pulse"></div>
                        Online • Ready to help
                      </p>
                    </div>
                  </div>
                </div>

                {/* Chat Messages */}
                <div className="p-6 space-y-4 h-96 overflow-y-auto bg-gray-900">
                  {displayedMessages.map((msg, index) => (
                    <div key={index} className={`flex items-start space-x-3 ${msg.type === 'user' ? 'justify-end' : ''} animate-fade-in`}>
                      {msg.type === 'bot' && (
                        <div className="w-8 h-8 bg-gradient-to-br from-purple-500 to-pink-500 rounded-full flex items-center justify-center flex-shrink-0 animate-pulse">
                          <MessageCircle className="w-4 h-4 text-white" />
                        </div>
                      )}
                      <div className={`rounded-2xl px-4 py-3 max-w-xs lg:max-w-md ${
                        msg.type === 'bot' 
                          ? 'bg-gray-800 border border-gray-600 text-gray-200 shadow-sm' 
                          : 'bg-gradient-to-r from-purple-600 to-pink-600 text-white'
                      }`}>
                        <p className="text-sm">{msg.message}</p>
                      </div>
                      {msg.type === 'user' && (
                        <div className="w-8 h-8 bg-gray-300 rounded-full flex-shrink-0"></div>
                      )}
                    </div>
                  ))}
                  
                  {isTyping && (
                    <div className="flex items-start space-x-3 animate-fade-in">
                      <div className="w-8 h-8 bg-gradient-to-br from-purple-500 to-pink-500 rounded-full flex items-center justify-center animate-pulse">
                        <MessageCircle className="w-4 h-4 text-white" />
                      </div>
                      <div className="bg-gray-800 border border-gray-600 rounded-2xl px-4 py-3 shadow-sm">
                        <div className="flex space-x-1">
                          <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce"></div>
                          <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                          <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Chat Input */}
                <div className="border-t border-gray-700 p-4 bg-gray-800">
                  <div className="flex items-center space-x-3">
                    <div className="flex-1 relative">
                      <input
                        type="text"
                        placeholder="Type your message..."
                        className="w-full px-4 py-3 bg-gray-700 border border-gray-600 text-white rounded-xl focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent placeholder-gray-400"
                      />
                      <button className="absolute right-3 top-1/2 transform -translate-y-1/2 p-1">
                        <Send className="w-5 h-5 text-gray-400 hover:text-purple-400 transition-colors" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              {/* Play Button */}
              <div className="flex justify-center mt-6">
                <button
                  onClick={handlePlayPause}
                  className="w-16 h-16 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 rounded-full flex items-center justify-center transition-all duration-300 shadow-lg hover:shadow-2xl hover:shadow-purple-500/50 transform hover:scale-110 animate-pulse-glow"
                >
                  {isPlaying ? (
                    <Pause className="w-6 h-6 text-white" />
                  ) : (
                    <Play className="w-6 h-6 text-white ml-1" />
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Trusted By Section */}
      <section className="py-16 bg-gray-900 border-b border-gray-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <p className="text-lg text-gray-400">
              <span className="font-semibold text-white">Trusted by 10,00+</span> businesses worldwide
            </p>
          </div>
          
          <div className="flex flex-wrap justify-center items-center gap-8 md:gap-12 opacity-60 animate-fade-in">
            <div className="text-2xl font-bold text-gray-400 hover:text-purple-400 transition-colors duration-300">SIEMENS</div>
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-gray-600 rounded-full"></div>
              <span className="text-xl font-semibold text-gray-400 hover:text-purple-400 transition-colors duration-300">POSTMAN</span>
            </div>
            <div className="text-xl font-bold text-gray-400 hover:text-purple-400 transition-colors duration-300">pwc</div>
            <div className="text-xl font-bold text-gray-400 hover:text-purple-400 transition-colors duration-300">+alpian</div>
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-gray-600 rounded-full"></div>
              <span className="text-xl font-semibold text-gray-400 hover:text-purple-400 transition-colors duration-300">Opal</span>
            </div>
            <div className="text-xl font-bold text-gray-400 hover:text-purple-400 transition-colors duration-300">alBaraka<span className="text-sm">%</span></div>
          </div>
        </div>
      </section>

      {/* Use Cases Section */}
      <section className="py-24 bg-black">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-4xl lg:text-5xl font-bold text-white mb-6 animate-fade-in-up">
              Perfect for every business scenario
            </h2>
            <p className="text-xl text-gray-300 max-w-3xl mx-auto animate-fade-in-up" style={{ animationDelay: '0.1s' }}>
              From customer support to lead generation, our chatbots adapt to your specific use case and deliver results.
            </p>
          </div>

          {/* Use Case Tabs */}
          <div className="flex flex-wrap justify-center gap-4 mb-12">
            {Object.entries(useCases).map(([key, useCase]) => (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                className={`px-6 py-3 rounded-xl font-semibold transition-all duration-200 ${
                  activeTab === key
                    ? 'bg-gradient-to-r from-purple-600 to-pink-600 text-white shadow-lg hover:shadow-purple-500/25'
                    : 'bg-gray-800 text-gray-300 hover:bg-gray-700 border border-gray-600 hover:border-purple-500'
                }`}
              >
                {useCase.title}
              </button>
            ))}
          </div>

          {/* Active Use Case Content */}
          <div className="bg-gray-900 rounded-2xl p-8 shadow-lg border border-gray-700 animate-fade-in">
            <div className="grid lg:grid-cols-2 gap-12 items-center">
              <div>
                <h3 className="text-3xl font-bold text-white mb-4">
                  {useCases[activeTab].title}
                </h3>
                <p className="text-xl text-gray-300 mb-8">
                  {useCases[activeTab].description}
                </p>
                <div className="grid grid-cols-2 gap-4">
                  {useCases[activeTab].features.map((feature, index) => (
                    <div key={index} className="flex items-center space-x-3">
                      <Check className="w-5 h-5 text-purple-400 flex-shrink-0" />
                      <span className="text-gray-300">{feature}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="bg-gradient-to-br from-gray-800 to-gray-700 rounded-2xl p-8 border border-gray-600">
                <div className="text-center">
                  <div className="w-20 h-20 bg-gradient-to-br from-purple-600 to-pink-600 rounded-2xl flex items-center justify-center mx-auto mb-6 animate-pulse">
                    <MessageCircle className="w-10 h-10 text-white" />
                  </div>
                  <h4 className="text-xl font-semibold text-white mb-4">Live Demo</h4>
                  <p className="text-gray-300">{useCases[activeTab].demo}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-24 bg-gray-900">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-4xl lg:text-5xl font-bold text-white mb-6 animate-fade-in-up">
              Everything you need to succeed
            </h2>
            <p className="text-xl text-gray-300 max-w-3xl mx-auto animate-fade-in-up" style={{ animationDelay: '0.1s' }}>
              Powerful features designed to help you create, deploy, and optimize AI chatbots that deliver exceptional customer experiences.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {[
              {
                icon: <Zap className="w-8 h-8" />,
                title: "Quick Setup",
                description: "Get your chatbot up and running in minutes with our intuitive drag-and-drop builder.",
                color: "from-yellow-400 to-orange-500"
              },
              {
                icon: <MessageCircle className="w-8 h-8" />,
                title: "Smart Conversations",
                description: "Natural, human-like conversations that understand context and provide helpful responses.",
                color: "from-purple-400 to-purple-600"
              },
              {
                icon: <Globe className="w-8 h-8" />,
                title: "Multi-Channel Support",
                description: "Deploy across websites, messaging apps, and social media platforms seamlessly.",
                color: "from-cyan-400 to-cyan-600"
              },
              {
                icon: <BarChart3 className="w-8 h-8" />,
                title: "Real-Time Analytics",
                description: "Track performance, user satisfaction, and conversation insights with detailed analytics.",
                color: "from-blue-400 to-blue-600"
              },
              {
                icon: <Shield className="w-8 h-8" />,
                title: "Enterprise Security",
                description: "Bank-level security with SOC 2 compliance and end-to-end encryption.",
                color: "from-pink-400 to-pink-600"
              },
              {
                icon: <Settings className="w-8 h-8" />,
                title: "Easy Integrations",
                description: "Connect with your favorite tools including CRM, helpdesk, and marketing platforms.",
                color: "from-indigo-400 to-indigo-600"
              }
            ].map((feature, index) => (
              <div key={index} className="group p-8 rounded-2xl border border-gray-700 hover:border-purple-500 hover:shadow-lg hover:shadow-purple-500/20 transition-all duration-300 bg-gray-800 animate-fade-in-up hover:scale-105" style={{ animationDelay: `${index * 0.1}s` }}>
                <div className={`w-16 h-16 bg-gradient-to-br ${feature.color} rounded-2xl flex items-center justify-center text-white mb-6 group-hover:scale-110 transition-transform duration-300`}>
                  {feature.icon}
                </div>
                <h3 className="text-xl font-semibold text-white mb-3">{feature.title}</h3>
                <p className="text-gray-300 leading-relaxed">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-24 bg-gradient-to-br from-purple-900 via-black to-pink-900 relative overflow-hidden">
        {/* Animated Background Elements */}
        <div className="absolute inset-0">
          <div className="absolute top-10 left-10 w-32 h-32 bg-purple-500/20 rounded-full blur-xl animate-pulse"></div>
          <div className="absolute bottom-10 right-10 w-40 h-40 bg-pink-500/20 rounded-full blur-xl animate-pulse" style={{ animationDelay: '1s' }}></div>
          <div className="absolute top-1/2 left-1/4 w-24 h-24 bg-cyan-500/20 rounded-full blur-xl animate-pulse" style={{ animationDelay: '2s' }}></div>
        </div>
        
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-4xl lg:text-5xl font-bold text-white mb-6 animate-fade-in-up">
              Proven results that speak for themselves
            </h2>
            <p className="text-xl text-purple-100 max-w-3xl mx-auto animate-fade-in-up" style={{ animationDelay: '0.1s' }}>
              Join thousands of businesses that have transformed their customer experience with our AI chatbots.
            </p>
          </div>

          <div className="grid md:grid-cols-4 gap-8">
            {[
              { number: "10,000+", label: "Active Chatbots", icon: <MessageCircle className="w-8 h-8" /> },
              { number: "50M+", label: "Conversations Handled", icon: <MessageCircle className="w-8 h-8" /> },
              { number: "95%", label: "Customer Satisfaction", icon: <Star className="w-8 h-8" /> },
              { number: "24/7", label: "Uptime Guarantee", icon: <Clock className="w-8 h-8" /> }
            ].map((stat, index) => (
              <div key={index} className="text-center animate-fade-in-up hover:scale-105 transition-transform duration-300" style={{ animationDelay: `${index * 0.1}s` }}>
                <div className="w-16 h-16 bg-white bg-opacity-20 rounded-2xl flex items-center justify-center text-white mx-auto mb-4 animate-pulse">
                  {stat.icon}
                </div>
                <div className="text-4xl font-bold text-white mb-2 animate-bounce" style={{ animationDelay: `${index * 0.2}s` }}>{stat.number}</div>
                <div className="text-purple-100">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Testimonials Section */}
      <section className="py-24 bg-black">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-4xl lg:text-5xl font-bold text-white mb-6 animate-fade-in-up">
              What our customers say
            </h2>
            <p className="text-xl text-gray-300 max-w-3xl mx-auto animate-fade-in-up" style={{ animationDelay: '0.1s' }}>
              Don't just take our word for it. See what businesses like yours are saying about their experience.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {[
              {
                quote: "Our customer response time went from hours to seconds. The AI understands context perfectly and provides accurate answers every time.",
                author: "Sarah Johnson",
                role: "Head of Customer Success",
                company: "TechFlow Inc.",
                rating: 5,
                avatar: "SJ"
              },
              {
                quote: "Implementation was incredibly smooth. Within a week, we were handling 80% of customer inquiries automatically with high satisfaction scores.",
                author: "Michael Chen",
                role: "Operations Director",
                company: "GrowthLabs",
                rating: 5,
                avatar: "MC"
              },
              {
                quote: "The analytics dashboard gives us incredible insights into customer behavior. We've improved our products based on chatbot conversations.",
                author: "Emily Rodriguez",
                role: "Product Manager",
                company: "InnovateCorp",
                rating: 5,
                avatar: "ER"
              }
            ].map((testimonial, index) => (
              <div key={index} className="bg-gray-900 border border-gray-700 rounded-2xl p-8 relative hover:border-purple-500 transition-all duration-300 hover:shadow-lg hover:shadow-purple-500/20 animate-fade-in-up hover:scale-105" style={{ animationDelay: `${index * 0.1}s` }}>
                <Quote className="w-8 h-8 text-purple-400 mb-6" />
                
                <div className="flex mb-6">
                  {[...Array(testimonial.rating)].map((_, i) => (
                    <Star key={i} className="w-5 h-5 text-yellow-400 fill-current animate-pulse" style={{ animationDelay: `${i * 0.1}s` }} />
                  ))}
                </div>
                
                <p className="text-gray-300 mb-8 leading-relaxed text-lg">"{testimonial.quote}"</p>
                
                <div className="flex items-center">
                  <div className="w-12 h-12 bg-gradient-to-br from-purple-500 to-pink-500 rounded-full flex items-center justify-center text-white font-semibold mr-4 animate-pulse">
                    {testimonial.avatar}
                  </div>
                  <div>
                    <div className="font-semibold text-white">{testimonial.author}</div>
                    <div className="text-sm text-gray-400">{testimonial.role}</div>
                    <div className="text-sm text-gray-500">{testimonial.company}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-24 bg-gradient-to-br from-gray-900 via-purple-900 to-black relative overflow-hidden">
        {/* Animated Background */}
        <div className="absolute inset-0">
          <div className="absolute top-0 left-0 w-full h-full bg-gradient-to-r from-purple-500/10 to-pink-500/10 animate-pulse"></div>
          <div className="absolute -top-40 -right-40 w-80 h-80 bg-gradient-to-br from-purple-500/20 to-pink-500/20 rounded-full blur-3xl animate-pulse"></div>
          <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-gradient-to-br from-cyan-500/20 to-blue-500/20 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }}></div>
        </div>
        
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-4xl lg:text-5xl font-bold text-white mb-6 animate-fade-in-up">
            Ready to transform your customer experience?
          </h2>
          <p className="text-xl text-gray-300 mb-12 max-w-2xl mx-auto animate-fade-in-up" style={{ animationDelay: '0.1s' }}>
            Join thousands of businesses that trust our platform to deliver exceptional customer support with AI-powered chatbots.
          </p>
          
          <div className="flex flex-col sm:flex-row gap-6 justify-center items-center mb-12 animate-fade-in-up" style={{ animationDelay: '0.2s' }}>
            <button className="group bg-gradient-to-r from-purple-600 to-pink-600 text-white px-10 py-5 rounded-xl font-semibold text-lg hover:from-purple-700 hover:to-pink-700 transition-all duration-300 flex items-center space-x-3 shadow-lg hover:shadow-2xl hover:shadow-purple-500/50 transform hover:scale-110 animate-pulse-glow">
              <Rocket className="w-6 h-6" />
              <span>Start Building Free</span>
              <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform duration-200" />
            </button>
            <button className="text-gray-300 hover:text-purple-400 transition-colors duration-300 flex items-center space-x-2 text-lg hover:scale-105 transform">
              <span>Schedule a Demo</span>
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>
          
          <div className="flex flex-wrap justify-center items-center gap-8 text-gray-400 animate-fade-in-up" style={{ animationDelay: '0.3s' }}>
            <div className="flex items-center space-x-2">
              <Check className="w-4 h-4 text-purple-400" />
              <span className="text-sm">Free forever plan</span>
            </div>
            <div className="flex items-center space-x-2">
              <Check className="w-4 h-4 text-purple-400" />
              <span className="text-sm">No credit card required</span>
            </div>
            <div className="flex items-center space-x-2">
              <Check className="w-4 h-4 text-purple-400" />
              <span className="text-sm">Setup in 5 minutes</span>
            </div>
          </div>
        </div>
      </section>

      <Footer />

      {/* Floating Chat Widget */}
      <div className="fixed bottom-6 right-6 z-50">
        <button className="w-16 h-16 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 rounded-full flex items-center justify-center shadow-lg hover:shadow-2xl hover:shadow-purple-500/50 transition-all duration-300 transform hover:scale-110 animate-bounce">
          <MessageCircle className="w-7 h-7 text-white" />
        </button>
      </div>
    </div>
  );
}