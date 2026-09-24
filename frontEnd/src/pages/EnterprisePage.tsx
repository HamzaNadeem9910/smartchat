import React from 'react';
import { 
  Check, 
  ArrowRight, 
  Shield, 
  Users, 
  Zap, 
  Globe, 
  Settings, 
  Lock,
  MessageCircle,
  Bot,
  Star,
  Phone,
  Mail,
  Calendar,
  Building,
  Headphones,
  Database,
  Cloud,
  Cpu,
  BarChart3
} from 'lucide-react';
import Header from '../components/Header';
import Footer from '../components/Footer';

export default function EnterprisePage() {
  return (
    <div className="min-h-screen bg-black">
      <Header />

      {/* Hero Section */}
      <section className="relative bg-gradient-to-br from-gray-900 via-black to-gray-800 py-20 overflow-hidden">
        {/* Background Elements */}
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute -top-40 -right-40 w-80 h-80 bg-gradient-to-br from-purple-500/20 to-pink-500/20 rounded-full blur-3xl animate-pulse"></div>
          <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-gradient-to-br from-blue-500/20 to-cyan-500/20 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }}></div>
        </div>
        
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            {/* Left Column - Content */}
            <div className="space-y-8">
              <div className="inline-flex items-center space-x-2 bg-gray-800 text-purple-400 px-4 py-2 rounded-full text-sm font-medium animate-fade-in-up border border-purple-500/30">
                <Building className="w-4 h-4" />
                <span>Enterprise Solutions</span>
              </div>
              
              <h1 className="text-5xl lg:text-6xl font-bold text-white leading-tight animate-fade-in-up" style={{ animationDelay: '0.1s' }}>
                Scale customer support across your entire organization
              </h1>
              
              <p className="text-xl text-gray-300 leading-relaxed animate-fade-in-up" style={{ animationDelay: '0.2s' }}>
                Enterprise-grade AI chatbot solutions designed for large organizations with advanced security, custom integrations, and dedicated support.
              </p>

              <div className="flex flex-col sm:flex-row gap-4 animate-fade-in-up" style={{ animationDelay: '0.3s' }}>
                <button className="group bg-gradient-to-r from-purple-600 to-pink-600 text-white px-8 py-4 rounded-lg font-semibold text-lg hover:from-purple-700 hover:to-pink-700 transition-all duration-200 flex items-center space-x-2 transform hover:scale-105 shadow-lg hover:shadow-2xl hover:shadow-purple-500/50 animate-pulse-glow">
                  <span>Schedule Demo</span>
                  <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform duration-200" />
                </button>
                <button className="border-2 border-gray-600 text-gray-300 px-8 py-4 rounded-lg font-semibold text-lg hover:border-purple-500 hover:bg-gray-800 transition-all duration-200 flex items-center space-x-2 hover:scale-105 transform">
                  <Phone className="w-5 h-5" />
                  <span>Contact Sales</span>
                </button>
              </div>

              <div className="flex items-center space-x-6 text-gray-400 animate-fade-in-up" style={{ animationDelay: '0.4s' }}>
                <div className="flex items-center space-x-2">
                  <Check className="w-4 h-4 text-purple-400" />
                  <span className="text-sm">Custom deployment options</span>
                </div>
                <div className="flex items-center space-x-2">
                  <Check className="w-4 h-4 text-purple-400" />
                  <span className="text-sm">Dedicated support team</span>
                </div>
              </div>
            </div>

            {/* Right Column - Visual */}
            <div className="relative animate-fade-in-up" style={{ animationDelay: '0.2s' }}>
              <div className="bg-gradient-to-br from-gray-800 to-gray-700 rounded-2xl p-8 border border-gray-600 shadow-2xl">
                <div className="grid grid-cols-2 gap-6">
                  <div className="bg-gray-900 rounded-xl p-6 shadow-lg border border-gray-600 hover:border-purple-500 transition-all duration-300 hover:scale-105">
                    <div className="w-12 h-12 bg-gradient-to-br from-purple-500 to-pink-500 rounded-lg flex items-center justify-center mb-4">
                      <Users className="w-6 h-6 text-white" />
                    </div>
                    <h3 className="font-semibold text-white mb-2">Multi-team Support</h3>
                    <p className="text-sm text-gray-300">Manage multiple departments and teams</p>
                  </div>
                  
                  <div className="bg-gray-900 rounded-xl p-6 shadow-lg border border-gray-600 hover:border-purple-500 transition-all duration-300 hover:scale-105">
                    <div className="w-12 h-12 bg-gradient-to-br from-cyan-500 to-blue-500 rounded-lg flex items-center justify-center mb-4">
                      <Shield className="w-6 h-6 text-white" />
                    </div>
                    <h3 className="font-semibold text-white mb-2">Enterprise Security</h3>
                    <p className="text-sm text-gray-300">SOC 2 Type II compliance</p>
                  </div>
                  
                  <div className="bg-gray-900 rounded-xl p-6 shadow-lg border border-gray-600 hover:border-purple-500 transition-all duration-300 hover:scale-105">
                    <div className="w-12 h-12 bg-gradient-to-br from-emerald-500 to-teal-500 rounded-lg flex items-center justify-center mb-4">
                      <Database className="w-6 h-6 text-white" />
                    </div>
                    <h3 className="font-semibold text-white mb-2">Custom Integrations</h3>
                    <p className="text-sm text-gray-300">Connect with your existing systems</p>
                  </div>
                  
                  <div className="bg-gray-900 rounded-xl p-6 shadow-lg border border-gray-600 hover:border-purple-500 transition-all duration-300 hover:scale-105">
                    <div className="w-12 h-12 bg-gradient-to-br from-orange-500 to-red-500 rounded-lg flex items-center justify-center mb-4">
                      <BarChart3 className="w-6 h-6 text-white" />
                    </div>
                    <h3 className="font-semibold text-white mb-2">Advanced Analytics</h3>
                    <p className="text-sm text-gray-300">Detailed insights and reporting</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Enterprise Features */}
      <section className="py-20 bg-gray-900">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-4xl lg:text-5xl font-bold text-white mb-6 animate-fade-in-up">
              Built for enterprise scale and security
            </h2>
            <p className="text-xl text-gray-300 max-w-3xl mx-auto animate-fade-in-up" style={{ animationDelay: '0.1s' }}>
              Everything you need to deploy AI chatbots across your organization with confidence and control.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {[
              {
                icon: <Shield className="w-8 h-8" />,
                title: "Advanced Security",
                description: "SOC 2 Type II compliance, GDPR ready, and enterprise-grade encryption to protect your data."
              },
              {
                icon: <Users className="w-8 h-8" />,
                title: "Multi-team Management",
                description: "Organize teams, set permissions, and manage multiple chatbots across different departments."
              },
              {
                icon: <Database className="w-8 h-8" />,
                title: "Custom Integrations",
                description: "Connect with your CRM, helpdesk, and other business systems through custom APIs."
              },
              {
                icon: <Cloud className="w-8 h-8" />,
                title: "Flexible Deployment",
                description: "Choose from cloud, on-premise, or hybrid deployment options to meet your requirements."
              },
              {
                icon: <Headphones className="w-8 h-8" />,
                title: "Dedicated Support",
                description: "24/7 priority support with a dedicated customer success manager and technical team."
              },
              {
                icon: <BarChart3 className="w-8 h-8" />,
                title: "Advanced Analytics",
                description: "Comprehensive reporting and analytics with custom dashboards and data export options."
              },
              {
                icon: <Cpu className="w-8 h-8" />,
                title: "Custom AI Training",
                description: "Train AI models on your specific data and use cases for optimal performance."
              },
              {
                icon: <Globe className="w-8 h-8" />,
                title: "Global Scale",
                description: "Deploy across multiple regions with localized support and compliance requirements."
              }
            ].map((feature, index) => (
              <div key={index} className="bg-black rounded-2xl p-8 shadow-lg border border-gray-700 hover:border-purple-500 hover:shadow-2xl hover:shadow-purple-500/20 transition-all duration-300 hover:scale-105 animate-fade-in-up" style={{ animationDelay: `${index * 0.1}s` }}>
                <div className="w-16 h-16 bg-gradient-to-br from-purple-500 to-pink-500 rounded-2xl flex items-center justify-center text-white mb-6 group-hover:scale-110 transition-transform duration-300">
                  {feature.icon}
                </div>
                <h3 className="text-xl font-semibold text-white mb-3">{feature.title}</h3>
                <p className="text-gray-300 leading-relaxed">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Deployment Options */}
      <section className="bg-black py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-4xl lg:text-5xl font-bold text-white mb-6 animate-fade-in-up">
              Flexible deployment options
            </h2>
            <p className="text-xl text-gray-300 max-w-3xl mx-auto animate-fade-in-up" style={{ animationDelay: '0.1s' }}>
              Choose the deployment model that best fits your organization's security and compliance requirements.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {[
              {
                title: "Cloud Deployment",
                description: "Fully managed cloud solution with automatic updates and scaling",
                features: [
                  "Fastest time to deployment",
                  "Automatic updates and maintenance",
                  "Global CDN and edge locations",
                  "Built-in monitoring and alerts"
                ],
                icon: <Cloud className="w-8 h-8" />
              },
              {
                title: "On-Premise",
                description: "Deploy within your own infrastructure for maximum control and security",
                features: [
                  "Complete data control",
                  "Custom security configurations",
                  "Integration with existing systems",
                  "Compliance with internal policies"
                ],
                icon: <Building className="w-8 h-8" />
              },
              {
                title: "Hybrid Solution",
                description: "Combine cloud flexibility with on-premise security requirements",
                features: [
                  "Best of both worlds",
                  "Gradual migration path",
                  "Flexible data residency",
                  "Custom compliance requirements"
                ],
                icon: <Settings className="w-8 h-8" />
              }
            ].map((option, index) => (
              <div key={index} className="bg-gray-900 rounded-2xl p-8 border border-gray-700 hover:border-purple-500 hover:shadow-lg hover:shadow-purple-500/20 transition-all duration-300 hover:scale-105 animate-fade-in-up" style={{ animationDelay: `${index * 0.1}s` }}>
                <div className="w-16 h-16 bg-gradient-to-br from-purple-500 to-pink-500 rounded-2xl flex items-center justify-center text-white mb-6">
                  {option.icon}
                </div>
                <h3 className="text-2xl font-bold text-white mb-4">{option.title}</h3>
                <p className="text-gray-300 mb-6">{option.description}</p>
                <ul className="space-y-3">
                  {option.features.map((feature, featureIndex) => (
                    <li key={featureIndex} className="flex items-center space-x-3">
                      <Check className="w-5 h-5 text-purple-400 flex-shrink-0" />
                      <span className="text-gray-300">{feature}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Customer Success Stories */}
      <section className="py-20 bg-gray-900">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-4xl lg:text-5xl font-bold text-white mb-6 animate-fade-in-up">
              Trusted by enterprise customers
            </h2>
            <p className="text-xl text-gray-300 max-w-3xl mx-auto animate-fade-in-up" style={{ animationDelay: '0.1s' }}>
              See how leading organizations are transforming their customer support with our enterprise solutions.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-12">
            {[
              {
                quote: "The enterprise deployment was seamless, and the custom integrations with our existing systems exceeded our expectations. Our customer satisfaction scores improved by 45% within the first quarter.",
                author: "Sarah Johnson",
                role: "VP of Customer Operations",
                company: "TechCorp Global",
                metrics: [
                  { label: "Response Time", value: "85% faster" },
                  { label: "Customer Satisfaction", value: "+45%" },
                  { label: "Cost Reduction", value: "60%" }
                ]
              },
              {
                quote: "The dedicated support team and custom AI training helped us achieve our specific use case requirements. The security features give us complete confidence in handling sensitive customer data.",
                author: "Michael Chen",
                role: "Chief Technology Officer",
                company: "Financial Services Inc.",
                metrics: [
                  { label: "Security Compliance", value: "100%" },
                  { label: "Uptime", value: "99.99%" },
                  { label: "Team Efficiency", value: "+70%" }
                ]
              }
            ].map((story, index) => (
              <div key={index} className="bg-black rounded-2xl p-8 shadow-lg border border-gray-700 hover:border-purple-500 hover:shadow-2xl hover:shadow-purple-500/20 transition-all duration-300 hover:scale-105 animate-fade-in-up" style={{ animationDelay: `${index * 0.1}s` }}>
                <div className="flex mb-6">
                  {[...Array(5)].map((_, i) => (
                    <Star key={i} className="w-5 h-5 text-yellow-400 fill-current" />
                  ))}
                </div>
                
                <p className="text-gray-300 mb-8 leading-relaxed text-lg">"{story.quote}"</p>
                
                <div className="flex items-center mb-6">
                  <div className="w-12 h-12 bg-gradient-to-br from-purple-500 to-pink-500 rounded-full mr-4 flex items-center justify-center text-white font-semibold">
                    {story.author.split(' ').map(n => n[0]).join('')}
                  </div>
                  <div>
                    <div className="font-semibold text-white">{story.author}</div>
                    <div className="text-sm text-gray-300">{story.role}</div>
                    <div className="text-sm text-gray-400">{story.company}</div>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-4 pt-6 border-t border-gray-700">
                  {story.metrics.map((metric, metricIndex) => (
                    <div key={metricIndex} className="text-center">
                      <div className="text-2xl font-bold text-purple-400">{metric.value}</div>
                      <div className="text-sm text-gray-400">{metric.label}</div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Implementation Process */}
      <section className="bg-black py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-4xl lg:text-5xl font-bold text-white mb-6 animate-fade-in-up">
              Seamless implementation process
            </h2>
            <p className="text-xl text-gray-300 max-w-3xl mx-auto animate-fade-in-up" style={{ animationDelay: '0.1s' }}>
              Our proven implementation methodology ensures a smooth deployment with minimal disruption to your operations.
            </p>
          </div>

          <div className="grid md:grid-cols-4 gap-8">
            {[
              {
                step: "01",
                title: "Discovery & Planning",
                description: "We analyze your requirements, existing systems, and create a detailed implementation plan.",
                duration: "1-2 weeks"
              },
              {
                step: "02",
                title: "Custom Configuration",
                description: "Set up your chatbots, integrations, and security configurations based on your needs.",
                duration: "2-4 weeks"
              },
              {
                step: "03",
                title: "Testing & Training",
                description: "Comprehensive testing, team training, and AI model optimization for your use cases.",
                duration: "1-2 weeks"
              },
              {
                step: "04",
                title: "Go-Live & Support",
                description: "Smooth deployment with ongoing monitoring and dedicated support for continuous optimization.",
                duration: "Ongoing"
              }
            ].map((phase, index) => (
              <div key={index} className="relative animate-fade-in-up" style={{ animationDelay: `${index * 0.1}s` }}>
                <div className="bg-gray-900 rounded-2xl p-8 text-center border border-gray-700 hover:border-purple-500 transition-all duration-300 hover:scale-105">
                  <div className="w-16 h-16 bg-gradient-to-br from-purple-600 to-pink-600 rounded-full flex items-center justify-center text-white font-bold text-xl mx-auto mb-6 animate-pulse">
                    {phase.step}
                  </div>
                  <h3 className="text-xl font-semibold text-white mb-4">{phase.title}</h3>
                  <p className="text-gray-300 mb-4">{phase.description}</p>
                  <div className="inline-flex items-center space-x-2 bg-purple-900 text-purple-300 px-3 py-1 rounded-full text-sm font-medium">
                    <Calendar className="w-4 h-4" />
                    <span>{phase.duration}</span>
                  </div>
                </div>
                {index < 3 && (
                  <div className="hidden md:block absolute top-1/2 -right-4 transform -translate-y-1/2">
                    <ArrowRight className="w-8 h-8 text-purple-400" />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Contact Section */}
      <section className="bg-gradient-to-br from-purple-900 via-black to-pink-900 py-20 relative overflow-hidden">
        {/* Animated Background */}
        <div className="absolute inset-0">
          <div className="absolute top-0 left-0 w-full h-full bg-gradient-to-r from-purple-500/10 to-pink-500/10 animate-pulse"></div>
          <div className="absolute -top-40 -right-40 w-80 h-80 bg-gradient-to-br from-purple-500/20 to-pink-500/20 rounded-full blur-3xl animate-pulse"></div>
          <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-gradient-to-br from-cyan-500/20 to-blue-500/20 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }}></div>
        </div>
        
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-4xl lg:text-5xl font-bold text-white mb-6 animate-fade-in-up">
            Ready to transform your enterprise support?
          </h2>
          <p className="text-xl text-purple-100 mb-8 max-w-2xl mx-auto animate-fade-in-up" style={{ animationDelay: '0.1s' }}>
            Let's discuss how our enterprise solutions can meet your organization's specific needs and requirements.
          </p>
          
          <div className="grid md:grid-cols-3 gap-6 mb-12 animate-fade-in-up" style={{ animationDelay: '0.2s' }}>
            <div className="bg-purple-500 bg-opacity-20 rounded-2xl p-6 text-center border border-purple-500/30 hover:bg-opacity-30 transition-all duration-300 hover:scale-105">
              <Phone className="w-8 h-8 text-purple-100 mx-auto mb-4" />
              <h3 className="text-white font-semibold mb-2">Schedule a Call</h3>
              <p className="text-purple-100 text-sm">Book a personalized demo with our enterprise team</p>
            </div>
            <div className="bg-purple-500 bg-opacity-20 rounded-2xl p-6 text-center border border-purple-500/30 hover:bg-opacity-30 transition-all duration-300 hover:scale-105">
              <Mail className="w-8 h-8 text-purple-100 mx-auto mb-4" />
              <h3 className="text-white font-semibold mb-2">Email Us</h3>
              <p className="text-purple-100 text-sm">Get detailed information and custom proposals</p>
            </div>
            <div className="bg-purple-500 bg-opacity-20 rounded-2xl p-6 text-center border border-purple-500/30 hover:bg-opacity-30 transition-all duration-300 hover:scale-105">
              <MessageCircle className="w-8 h-8 text-purple-100 mx-auto mb-4" />
              <h3 className="text-white font-semibold mb-2">Live Chat</h3>
              <p className="text-purple-100 text-sm">Chat with our enterprise specialists now</p>
            </div>
          </div>
          
          <div className="flex flex-col sm:flex-row gap-4 justify-center items-center animate-fade-in-up" style={{ animationDelay: '0.3s' }}>
            <button className="group bg-white text-purple-600 px-8 py-4 rounded-lg font-semibold text-lg hover:bg-gray-50 transition-all duration-200 flex items-center space-x-2 transform hover:scale-105 shadow-lg hover:shadow-2xl">
              <span>Schedule Enterprise Demo</span>
              <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform duration-200" />
            </button>
            <button className="text-purple-100 hover:text-white transition-colors duration-200 flex items-center space-x-2 hover:scale-105 transform">
              <span>Download Enterprise Brochure</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </section>

      <Footer />

      {/* Chat Widget */}
      <div className="fixed bottom-6 right-6 z-50">
        <button className="w-14 h-14 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 rounded-full flex items-center justify-center shadow-lg hover:shadow-2xl hover:shadow-purple-500/50 transition-all duration-300 transform hover:scale-110 animate-bounce">
          <MessageCircle className="w-6 h-6 text-white" />
        </button>
      </div>
    </div>
  );
}