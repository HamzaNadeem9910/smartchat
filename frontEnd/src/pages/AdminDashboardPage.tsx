import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  BarChart3, 
  Users, 
  Settings, 
  Search, 
  Download, 
  Edit, 
  Trash2, 
  CheckCircle,
  DollarSign,
  TrendingUp,
  Activity,
  AlertCircle,
  Shield,
  Eye,
  LogOut,
  User
} from 'lucide-react';

// Interactive Cursor Snake Trail Effect Component
const InteractiveCursorEffect = () => {
  const [trail, setTrail] = useState<Array<{id: number, x: number, y: number, timestamp: number}>>([]);

  useEffect(() => {
    let frameId: number;
    const handleMouseMove = (e: MouseEvent) => {
      const newPoint = {
        id: Date.now(),
        x: e.clientX,
        y: e.clientY,
        timestamp: Date.now()
      };
      
      setTrail(prev => [...prev.slice(-7), newPoint]);
    };

    const animate = () => {
      setTrail(prev => prev.filter(point => Date.now() - point.timestamp < 800));
      frameId = requestAnimationFrame(animate);
    };

    const cleanupInterval = setInterval(() => {
      setTrail(prev => prev.filter(point => Date.now() - point.timestamp < 800));
    }, 30);

    window.addEventListener('mousemove', handleMouseMove);
    frameId = requestAnimationFrame(animate);

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      cancelAnimationFrame(frameId);
      clearInterval(cleanupInterval);
    };
  }, []);

  return (
    <>
      {trail.map((point, index) => {
        const age = Date.now() - point.timestamp;
        const opacity = Math.max(0, 1 - age / 800);
        const scale = 0.3 + (index / trail.length) * 0.7;
        const hue = 200 + (index / trail.length) * 60;
        
        return (
          <div
            key={point.id}
            className="fixed pointer-events-none z-50"
            style={{
              left: point.x,
              top: point.y,
              transform: `translate(-50%, -50%) scale(${scale})`,
              opacity: opacity * 0.6,
              transition: 'opacity 0.1s ease-out, transform 0.1s ease-out'
            }}
          >
            <div 
              className="w-4 h-4 rounded-full"
              style={{
                background: `hsl(${hue}, 70%, 60%)`,
                boxShadow: `0 0 ${10 + index * 2}px hsl(${hue}, 70%, 60%)`,
              }}
            />
          </div>
        );
      })}
    </>
  );
};

// Hook to initialize interactive effects
const useInteractiveEffects = () => {
  useEffect(() => {
    const style = document.createElement('style');
    style.textContent = `
      .interactive-hover {
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      }
      .interactive-hover:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 24px -10px rgba(66, 133, 244, 0.3);
      }
      .cursor-glow {
        position: relative;
        overflow: hidden;
      }
      .cursor-glow::before {
        content: '';
        position: absolute;
        width: 100px;
        height: 100px;
        background: radial-gradient(circle, rgba(66, 133, 244, 0.15) 0%, transparent 70%);
        pointer-events: none;
        opacity: 0;
        transition: opacity 0.3s;
      }
      .cursor-glow:hover::before {
        opacity: 1;
      }
    `;
    document.head.appendChild(style);
    return () => {
      document.head.removeChild(style);
    };
  }, []);
};

type TabType = 'overview' | 'subscribers' | 'payments' | 'analytics' | 'settings';

interface Subscriber {
  id: number;
  name: string;
  email: string;
  package: 'Free' | 'Professional' | 'Enterprise';
  subscriptionStart: string;
  subscriptionEnd: string;
  status: 'active' | 'expired' | 'cancelled';
  paymentStatus: 'paid' | 'pending' | 'failed';
  totalChatbots: number;
  monthlyMessages: number;
}

interface Payment {
  id: number;
  transactionId: string;
  userName: string;
  userEmail: string;
  planName: 'Free' | 'Professional' | 'Enterprise';
  amount: number;
  paymentStatus: 'completed' | 'pending' | 'failed';
  transactionDate: string;
  paymentMethod: string;
}

export default function AdminDashboardPage() {
  const [activeTab, setActiveTab] = useState<TabType>('subscribers');
  const [searchTerm, setSearchTerm] = useState('');
  const [searchField, setSearchField] = useState<string>('all');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [filterPackage, setFilterPackage] = useState<string>('all');
  const [filterPayment, setFilterPayment] = useState<string>('all');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  
  // Payment states
  const [paymentSearchTerm, setPaymentSearchTerm] = useState('');
  const [paymentSearchField, setPaymentSearchField] = useState<string>('all');
  const [paymentFilterStatus, setPaymentFilterStatus] = useState<string>('all');
  const [paymentFilterPlan, setPaymentFilterPlan] = useState<string>('all');
  const [paymentStartDate, setPaymentStartDate] = useState('');
  const [paymentEndDate, setPaymentEndDate] = useState('');
  const [sortBy, setSortBy] = useState<string>('date');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  
  const navigate = useNavigate();
  
  useInteractiveEffects();

  // Get admin info
  const adminAuthRaw = localStorage.getItem('adminAuth');
  let adminEmail = 'Admin';
  if (adminAuthRaw) {
    try {
      const adminAuth = JSON.parse(adminAuthRaw);
      adminEmail = adminAuth.email;
    } catch {}
  }

  const handleLogout = () => {
    localStorage.removeItem('adminAuth');
    navigate('/admin/login', { replace: true });
  };

  // Sample subscribers data
  const subscribers: Subscriber[] = [
    { 
      id: 1, 
      name: 'John Smith', 
      email: 'john@company.com',
      package: 'Professional',
      subscriptionStart: '2024-01-15',
      subscriptionEnd: '2024-12-15',
      status: 'active',
      paymentStatus: 'paid',
      totalChatbots: 3,
      monthlyMessages: 2450
    },
    { 
      id: 2, 
      name: 'Sarah Johnson', 
      email: 'sarah@startup.io',
      package: 'Enterprise',
      subscriptionStart: '2023-11-01',
      subscriptionEnd: '2024-11-01',
      status: 'active',
      paymentStatus: 'paid',
      totalChatbots: 8,
      monthlyMessages: 12500
    },
    { 
      id: 3, 
      name: 'Mike Chen', 
      email: 'mike@tech.com',
      package: 'Free',
      subscriptionStart: '2024-02-10',
      subscriptionEnd: '2025-02-10',
      status: 'active',
      paymentStatus: 'paid',
      totalChatbots: 1,
      monthlyMessages: 450
    },
    { 
      id: 4, 
      name: 'Emma Wilson', 
      email: 'emma@bizco.com',
      package: 'Professional',
      subscriptionStart: '2023-12-05',
      subscriptionEnd: '2024-01-05',
      status: 'expired',
      paymentStatus: 'pending',
      totalChatbots: 2,
      monthlyMessages: 0
    },
    { 
      id: 5, 
      name: 'David Brown', 
      email: 'david@enterprise.net',
      package: 'Enterprise',
      subscriptionStart: '2024-01-20',
      subscriptionEnd: '2025-01-20',
      status: 'active',
      paymentStatus: 'paid',
      totalChatbots: 15,
      monthlyMessages: 25000
    },
    { 
      id: 6, 
      name: 'Lisa Anderson', 
      email: 'lisa@shop.com',
      package: 'Professional',
      subscriptionStart: '2024-02-01',
      subscriptionEnd: '2024-03-01',
      status: 'cancelled',
      paymentStatus: 'failed',
      totalChatbots: 0,
      monthlyMessages: 0
    }
  ];

  // Sample payment transactions data
  const payments: Payment[] = [
    {
      id: 1,
      transactionId: 'TXN-2024-001234',
      userName: 'John Smith',
      userEmail: 'john@company.com',
      planName: 'Professional',
      amount: 49,
      paymentStatus: 'completed',
      transactionDate: '2024-01-15',
      paymentMethod: 'Credit Card'
    },
    {
      id: 2,
      transactionId: 'TXN-2024-001235',
      userName: 'Sarah Johnson',
      userEmail: 'sarah@startup.io',
      planName: 'Enterprise',
      amount: 199,
      paymentStatus: 'completed',
      transactionDate: '2023-11-01',
      paymentMethod: 'PayPal'
    },
    {
      id: 3,
      transactionId: 'TXN-2024-001236',
      userName: 'Mike Chen',
      userEmail: 'mike@tech.com',
      planName: 'Free',
      amount: 0,
      paymentStatus: 'completed',
      transactionDate: '2024-02-10',
      paymentMethod: 'N/A'
    },
    {
      id: 4,
      transactionId: 'TXN-2024-001237',
      userName: 'Emma Wilson',
      userEmail: 'emma@bizco.com',
      planName: 'Professional',
      amount: 49,
      paymentStatus: 'pending',
      transactionDate: '2024-01-18',
      paymentMethod: 'Bank Transfer'
    },
    {
      id: 5,
      transactionId: 'TXN-2024-001238',
      userName: 'David Brown',
      userEmail: 'david@enterprise.net',
      planName: 'Enterprise',
      amount: 199,
      paymentStatus: 'completed',
      transactionDate: '2024-01-20',
      paymentMethod: 'Credit Card'
    },
    {
      id: 6,
      transactionId: 'TXN-2024-001239',
      userName: 'Lisa Anderson',
      userEmail: 'lisa@shop.com',
      planName: 'Professional',
      amount: 49,
      paymentStatus: 'failed',
      transactionDate: '2024-02-01',
      paymentMethod: 'Credit Card'
    },
    {
      id: 7,
      transactionId: 'TXN-2024-001240',
      userName: 'Robert Martinez',
      userEmail: 'robert@startup.com',
      planName: 'Enterprise',
      amount: 199,
      paymentStatus: 'completed',
      transactionDate: '2024-01-25',
      paymentMethod: 'PayPal'
    },
    {
      id: 8,
      transactionId: 'TXN-2024-001241',
      userName: 'Jennifer Lee',
      userEmail: 'jennifer@business.io',
      planName: 'Professional',
      amount: 49,
      paymentStatus: 'completed',
      transactionDate: '2024-02-05',
      paymentMethod: 'Credit Card'
    }
  ];

  const filteredSubscribers = subscribers.filter(sub => {
    // Search logic based on selected field
    let matchesSearch = true;
    if (searchTerm) {
      const searchLower = searchTerm.toLowerCase();
      switch (searchField) {
        case 'name':
          matchesSearch = sub.name.toLowerCase().includes(searchLower);
          break;
        case 'email':
          matchesSearch = sub.email.toLowerCase().includes(searchLower);
          break;
        case 'id':
          matchesSearch = sub.id.toString().includes(searchTerm);
          break;
        case 'package':
          matchesSearch = sub.package.toLowerCase().includes(searchLower);
          break;
        case 'all':
        default:
          matchesSearch = 
            sub.name.toLowerCase().includes(searchLower) ||
            sub.email.toLowerCase().includes(searchLower) ||
            sub.id.toString().includes(searchTerm) ||
            sub.package.toLowerCase().includes(searchLower);
          break;
      }
    }
    
    // Filter by status
    const matchesStatus = filterStatus === 'all' || sub.status === filterStatus;
    
    // Filter by package
    const matchesPackage = filterPackage === 'all' || sub.package === filterPackage;
    
    // Filter by payment status
    const matchesPayment = filterPayment === 'all' || sub.paymentStatus === filterPayment;
    
    // Filter by date range
    let matchesDateRange = true;
    if (startDate || endDate) {
      const subStartDate = new Date(sub.subscriptionStart);
      const subEndDate = new Date(sub.subscriptionEnd);
      
      if (startDate && endDate) {
        const filterStart = new Date(startDate);
        const filterEnd = new Date(endDate);
        matchesDateRange = (subStartDate >= filterStart && subStartDate <= filterEnd) ||
                          (subEndDate >= filterStart && subEndDate <= filterEnd) ||
                          (subStartDate <= filterStart && subEndDate >= filterEnd);
      } else if (startDate) {
        const filterStart = new Date(startDate);
        matchesDateRange = subEndDate >= filterStart;
      } else if (endDate) {
        const filterEnd = new Date(endDate);
        matchesDateRange = subStartDate <= filterEnd;
      }
    }
    
    return matchesSearch && matchesStatus && matchesPackage && matchesPayment && matchesDateRange;
  });

  // Filter and sort payments
  const filteredPayments = payments.filter(payment => {
    // Search logic
    let matchesSearch = true;
    if (paymentSearchTerm) {
      const searchLower = paymentSearchTerm.toLowerCase();
      switch (paymentSearchField) {
        case 'transactionId':
          matchesSearch = payment.transactionId.toLowerCase().includes(searchLower);
          break;
        case 'userName':
          matchesSearch = payment.userName.toLowerCase().includes(searchLower);
          break;
        case 'all':
        default:
          matchesSearch = 
            payment.transactionId.toLowerCase().includes(searchLower) ||
            payment.userName.toLowerCase().includes(searchLower) ||
            payment.userEmail.toLowerCase().includes(searchLower);
          break;
      }
    }

    // Filter by payment status
    const matchesStatus = paymentFilterStatus === 'all' || payment.paymentStatus === paymentFilterStatus;

    // Filter by plan
    const matchesPlan = paymentFilterPlan === 'all' || payment.planName === paymentFilterPlan;

    // Filter by date range
    let matchesDateRange = true;
    if (paymentStartDate || paymentEndDate) {
      const transactionDate = new Date(payment.transactionDate);
      
      if (paymentStartDate && paymentEndDate) {
        const filterStart = new Date(paymentStartDate);
        const filterEnd = new Date(paymentEndDate);
        matchesDateRange = transactionDate >= filterStart && transactionDate <= filterEnd;
      } else if (paymentStartDate) {
        const filterStart = new Date(paymentStartDate);
        matchesDateRange = transactionDate >= filterStart;
      } else if (paymentEndDate) {
        const filterEnd = new Date(paymentEndDate);
        matchesDateRange = transactionDate <= filterEnd;
      }
    }

    return matchesSearch && matchesStatus && matchesPlan && matchesDateRange;
  }).sort((a, b) => {
    let comparison = 0;
    
    switch (sortBy) {
      case 'date':
        comparison = new Date(a.transactionDate).getTime() - new Date(b.transactionDate).getTime();
        break;
      case 'userName':
        comparison = a.userName.localeCompare(b.userName);
        break;
      case 'planName':
        comparison = a.planName.localeCompare(b.planName);
        break;
      case 'amount':
        comparison = a.amount - b.amount;
        break;
      default:
        comparison = 0;
    }
    
    return sortOrder === 'asc' ? comparison : -comparison;
  });

  // Stats calculations
  const stats = {
    totalSubscribers: subscribers.length,
    activeSubscribers: subscribers.filter(s => s.status === 'active').length,
    totalRevenue: subscribers.reduce((acc, s) => {
      if (s.paymentStatus === 'paid') {
        if (s.package === 'Professional') return acc + 49;
        if (s.package === 'Enterprise') return acc + 199;
      }
      return acc;
    }, 0),
    pendingPayments: subscribers.filter(s => s.paymentStatus === 'pending').length
  };

  const renderOverview = () => (
    <div className="space-y-8">
      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-white rounded-xl p-6 border border-gray-200 shadow-sm interactive-hover cursor-glow">
          <div className="flex items-center justify-between mb-4">
            <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg flex items-center justify-center shadow-md">
              <Users className="w-6 h-6 text-white" />
            </div>
            <span className="text-green-600 text-sm font-medium flex items-center">
              <TrendingUp className="w-4 h-4 mr-1" />
              +12%
            </span>
          </div>
          <div className="text-3xl font-bold text-gray-900 mb-1">{stats.totalSubscribers}</div>
          <div className="text-gray-600 text-sm font-medium">Total Subscribers</div>
        </div>

        <div className="bg-white rounded-xl p-6 border border-gray-200 shadow-sm interactive-hover cursor-glow">
          <div className="flex items-center justify-between mb-4">
            <div className="w-12 h-12 bg-gradient-to-br from-green-500 to-green-600 rounded-lg flex items-center justify-center shadow-md">
              <CheckCircle className="w-6 h-6 text-white" />
            </div>
            <span className="text-green-600 text-sm font-medium flex items-center">
              <TrendingUp className="w-4 h-4 mr-1" />
              +8%
            </span>
          </div>
          <div className="text-3xl font-bold text-gray-900 mb-1">{stats.activeSubscribers}</div>
          <div className="text-gray-600 text-sm font-medium">Active Subscribers</div>
        </div>

        <div className="bg-white rounded-xl p-6 border border-gray-200 shadow-sm interactive-hover cursor-glow">
          <div className="flex items-center justify-between mb-4">
            <div className="w-12 h-12 bg-gradient-to-br from-purple-500 to-purple-600 rounded-lg flex items-center justify-center shadow-md">
              <DollarSign className="w-6 h-6 text-white" />
            </div>
            <span className="text-green-600 text-sm font-medium flex items-center">
              <TrendingUp className="w-4 h-4 mr-1" />
              +15%
            </span>
          </div>
          <div className="text-3xl font-bold text-gray-900 mb-1">${stats.totalRevenue.toLocaleString()}</div>
          <div className="text-gray-600 text-sm font-medium">Monthly Revenue</div>
        </div>

        <div className="bg-white rounded-xl p-6 border border-gray-200 shadow-sm interactive-hover cursor-glow">
          <div className="flex items-center justify-between mb-4">
            <div className="w-12 h-12 bg-gradient-to-br from-orange-500 to-orange-600 rounded-lg flex items-center justify-center shadow-md">
              <AlertCircle className="w-6 h-6 text-white" />
            </div>
          </div>
          <div className="text-3xl font-bold text-gray-900 mb-1">{stats.pendingPayments}</div>
          <div className="text-gray-600 text-sm font-medium">Pending Payments</div>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl p-6 border border-gray-200 shadow-sm interactive-hover cursor-glow">
          <h3 className="text-lg font-medium text-gray-900 mb-6">Subscription Distribution</h3>
          <div className="space-y-4">
            {[
              { name: 'Enterprise', count: 2, color: 'bg-blue-500', percentage: 33 },
              { name: 'Professional', count: 3, color: 'bg-green-500', percentage: 50 },
              { name: 'Free', count: 1, color: 'bg-gray-500', percentage: 17 }
            ].map((item) => (
              <div key={item.name}>
                <div className="flex justify-between mb-2">
                  <span className="text-gray-700 font-medium">{item.name}</span>
                  <span className="text-gray-600">{item.count} users</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-3">
                  <div 
                    className={`${item.color} h-3 rounded-full transition-all duration-500`}
                    style={{ width: `${item.percentage}%` }}
                  ></div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-xl p-6 border border-gray-200 shadow-sm interactive-hover cursor-glow">
          <h3 className="text-lg font-medium text-gray-900 mb-6">Recent Activity</h3>
          <div className="space-y-4">
            <div className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
              <div className="w-10 h-10 bg-green-100 rounded-full flex items-center justify-center">
                <CheckCircle className="w-5 h-5 text-green-600" />
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium text-gray-900">New subscription</p>
                <p className="text-xs text-gray-500">David Brown - Enterprise plan</p>
              </div>
              <span className="text-xs text-gray-400">2h ago</span>
            </div>
            <div className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
              <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
                <DollarSign className="w-5 h-5 text-blue-600" />
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium text-gray-900">Payment received</p>
                <p className="text-xs text-gray-500">John Smith - $49.00</p>
              </div>
              <span className="text-xs text-gray-400">5h ago</span>
            </div>
            <div className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
              <div className="w-10 h-10 bg-orange-100 rounded-full flex items-center justify-center">
                <AlertCircle className="w-5 h-5 text-orange-600" />
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium text-gray-900">Subscription expired</p>
                <p className="text-xs text-gray-500">Emma Wilson - Professional</p>
              </div>
              <span className="text-xs text-gray-400">1d ago</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const renderSubscribers = () => (
    <div className="space-y-6">
      {/* Advanced Search and Filters */}
      <div className="bg-white rounded-xl p-6 border border-gray-200 shadow-sm space-y-4">
        {/* Search Section */}
        <div className="flex flex-col lg:flex-row gap-4">
          <div className="flex-1 flex gap-3">
            <select
              value={searchField}
              onChange={(e) => setSearchField(e.target.value)}
              className="bg-gray-50 border border-gray-300 text-gray-900 px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 min-w-[140px]"
            >
              <option value="all">All Fields</option>
              <option value="name">Username</option>
              <option value="email">Email</option>
              <option value="id">User ID</option>
              <option value="package">Package</option>
            </select>
            <div className="flex-1 relative">
              <Search className="w-5 h-5 text-gray-400 absolute left-3 top-1/2 transform -translate-y-1/2" />
              <input
                type="text"
                placeholder={`Search by ${searchField === 'all' ? 'any field' : searchField}...`}
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full bg-gray-50 border border-gray-300 text-gray-900 pl-10 pr-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>
          
          <button 
            onClick={() => {
              setSearchTerm('');
              setSearchField('all');
              setFilterStatus('all');
              setFilterPackage('all');
              setFilterPayment('all');
              setStartDate('');
              setEndDate('');
            }}
            className="bg-gray-100 text-gray-700 px-6 py-3 rounded-lg hover:bg-gray-200 transition-colors font-medium whitespace-nowrap"
          >
            Clear All
          </button>
        </div>

        {/* Filters Section */}
        <div className="flex flex-wrap gap-3">
          <div className="flex items-center space-x-2">
            <span className="text-sm font-medium text-gray-700">Filters:</span>
          </div>
          
          <select
            value={filterPackage}
            onChange={(e) => setFilterPackage(e.target.value)}
            className="bg-gray-50 border border-gray-300 text-gray-900 px-4 py-2.5 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
          >
            <option value="all">All Packages</option>
            <option value="Free">Free</option>
            <option value="Professional">Professional</option>
            <option value="Enterprise">Enterprise</option>
          </select>
          
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="bg-gray-50 border border-gray-300 text-gray-900 px-4 py-2.5 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
          >
            <option value="all">All Subscription Status</option>
            <option value="active">Active</option>
            <option value="expired">Expired</option>
            <option value="cancelled">Cancelled</option>
          </select>
          
          <select
            value={filterPayment}
            onChange={(e) => setFilterPayment(e.target.value)}
            className="bg-gray-50 border border-gray-300 text-gray-900 px-4 py-2.5 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
          >
            <option value="all">All Payment Status</option>
            <option value="paid">Paid</option>
            <option value="pending">Pending</option>
            <option value="failed">Failed</option>
          </select>
          
          <div className="flex items-center space-x-2">
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="bg-gray-50 border border-gray-300 text-gray-900 px-4 py-2.5 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
              placeholder="Start Date"
            />
            <span className="text-gray-500 text-sm">to</span>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="bg-gray-50 border border-gray-300 text-gray-900 px-4 py-2.5 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
              placeholder="End Date"
            />
          </div>
          
          <button className="bg-blue-600 text-white px-4 py-2.5 rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2 text-sm font-medium ml-auto">
            <Download className="w-4 h-4" />
            <span>Export</span>
          </button>
        </div>

        {/* Active Filters Display */}
        {(searchTerm || filterStatus !== 'all' || filterPackage !== 'all' || filterPayment !== 'all' || startDate || endDate) && (
          <div className="flex items-center gap-2 pt-2 border-t border-gray-200">
            <span className="text-sm font-medium text-gray-600">Active Filters:</span>
            <div className="flex flex-wrap gap-2">
              {searchTerm && (
                <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                  Search: {searchTerm}
                </span>
              )}
              {filterPackage !== 'all' && (
                <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                  Package: {filterPackage}
                </span>
              )}
              {filterStatus !== 'all' && (
                <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                  Status: {filterStatus}
                </span>
              )}
              {filterPayment !== 'all' && (
                <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-orange-100 text-orange-800">
                  Payment: {filterPayment}
                </span>
              )}
              {(startDate || endDate) && (
                <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-indigo-100 text-indigo-800">
                  Date: {startDate || '...'} → {endDate || '...'}
                </span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Subscribers Table */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-2 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
                  ID
                </th>
                <th className="px-2 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
                  Subscriber
                </th>
                <th className="px-2 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
                  Package
                </th>
                <th className="px-2 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
                  Start
                </th>
                <th className="px-2 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
                  End
                </th>
                <th className="px-2 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-2 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
                  Payment
                </th>
                <th className="px-2 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
                  Usage
                </th>
                <th className="px-2 py-3 text-right text-xs font-semibold text-gray-700 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {filteredSubscribers.map((subscriber) => (
                <tr key={subscriber.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-2 py-3 whitespace-nowrap">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium bg-gray-100 text-gray-800">
                      #{subscriber.id}
                    </span>
                  </td>
                  <td className="px-2 py-3">
                    <div className="min-w-[140px] max-w-[180px]">
                      <div className="text-sm font-medium text-gray-900 truncate">{subscriber.name}</div>
                      <div className="text-xs text-gray-500 truncate">{subscriber.email}</div>
                    </div>
                  </td>
                  <td className="px-2 py-3 whitespace-nowrap">
                    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${
                      subscriber.package === 'Enterprise' ? 'bg-blue-100 text-blue-800' :
                      subscriber.package === 'Professional' ? 'bg-green-100 text-green-800' :
                      'bg-gray-100 text-gray-800'
                    }`}>
                      {subscriber.package === 'Professional' ? 'Pro' : subscriber.package === 'Enterprise' ? 'Ent' : 'Free'}
                    </span>
                  </td>
                  <td className="px-2 py-3 whitespace-nowrap text-sm text-gray-600">
                    {new Date(subscriber.subscriptionStart).toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: '2-digit' })}
                  </td>
                  <td className="px-2 py-3 whitespace-nowrap text-sm text-gray-600">
                    {new Date(subscriber.subscriptionEnd).toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: '2-digit' })}
                  </td>
                  <td className="px-2 py-3 whitespace-nowrap">
                    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${
                      subscriber.status === 'active' ? 'bg-green-100 text-green-800' :
                      subscriber.status === 'expired' ? 'bg-orange-100 text-orange-800' :
                      'bg-red-100 text-red-800'
                    }`}>
                      {subscriber.status === 'active' ? 'Active' : subscriber.status === 'expired' ? 'Expired' : 'Cancelled'}
                    </span>
                  </td>
                  <td className="px-2 py-3 whitespace-nowrap">
                    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${
                      subscriber.paymentStatus === 'paid' ? 'bg-green-100 text-green-800' :
                      subscriber.paymentStatus === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                      'bg-red-100 text-red-800'
                    }`}>
                      {subscriber.paymentStatus === 'paid' ? 'Paid' : subscriber.paymentStatus === 'pending' ? 'Pending' : 'Failed'}
                    </span>
                  </td>
                  <td className="px-2 py-3 whitespace-nowrap">
                    <div className="text-sm text-gray-900">{subscriber.totalChatbots} bots</div>
                    <div className="text-xs text-gray-500">{(subscriber.monthlyMessages / 1000).toFixed(1)}k</div>
                  </td>
                  <td className="px-2 py-3 whitespace-nowrap text-right">
                    <div className="flex items-center justify-end space-x-1">
                      <button className="text-blue-600 hover:text-blue-900 p-1.5 hover:bg-blue-50 rounded transition-colors" title="View">
                        <Eye className="w-4 h-4" />
                      </button>
                      <button className="text-green-600 hover:text-green-900 p-1.5 hover:bg-green-50 rounded transition-colors" title="Edit">
                        <Edit className="w-4 h-4" />
                      </button>
                      <button className="text-red-600 hover:text-red-900 p-1.5 hover:bg-red-50 rounded transition-colors" title="Delete">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        
        {/* Pagination */}
        <div className="bg-gray-50 px-4 py-3 flex items-center justify-between border-t border-gray-200">
          <div className="text-sm text-gray-600">
            Showing <span className="font-medium">{filteredSubscribers.length}</span> of{' '}
            <span className="font-medium">{subscribers.length}</span> subscribers
          </div>
          <div className="flex space-x-1">
            <button className="px-3 py-1.5 border border-gray-300 rounded text-sm font-medium text-gray-700 hover:bg-gray-100 transition-colors">
              Prev
            </button>
            <button className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700 transition-colors">
              1
            </button>
            <button className="px-3 py-1.5 border border-gray-300 rounded text-sm font-medium text-gray-700 hover:bg-gray-100 transition-colors">
              2
            </button>
            <button className="px-3 py-1.5 border border-gray-300 rounded text-sm font-medium text-gray-700 hover:bg-gray-100 transition-colors">
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  const renderPayments = () => (
    <div className="space-y-6">
      {/* Search and Filters */}
      <div className="bg-white rounded-xl p-6 border border-gray-200 shadow-sm space-y-4">
        {/* Search Section */}
        <div className="flex flex-col lg:flex-row gap-4">
          <div className="flex-1 flex gap-3">
            <select
              value={paymentSearchField}
              onChange={(e) => setPaymentSearchField(e.target.value)}
              className="bg-gray-50 border border-gray-300 text-gray-900 px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 min-w-[140px]"
            >
              <option value="all">All Fields</option>
              <option value="transactionId">Transaction ID</option>
              <option value="userName">Username</option>
            </select>
            <div className="flex-1 relative">
              <Search className="w-5 h-5 text-gray-400 absolute left-3 top-1/2 transform -translate-y-1/2" />
              <input
                type="text"
                placeholder={`Search by ${paymentSearchField === 'all' ? 'any field' : paymentSearchField}...`}
                value={paymentSearchTerm}
                onChange={(e) => setPaymentSearchTerm(e.target.value)}
                className="w-full bg-gray-50 border border-gray-300 text-gray-900 pl-10 pr-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>
          
          <button 
            onClick={() => {
              setPaymentSearchTerm('');
              setPaymentSearchField('all');
              setPaymentFilterStatus('all');
              setPaymentFilterPlan('all');
              setPaymentStartDate('');
              setPaymentEndDate('');
              setSortBy('date');
              setSortOrder('desc');
            }}
            className="bg-gray-100 text-gray-700 px-6 py-3 rounded-lg hover:bg-gray-200 transition-colors font-medium whitespace-nowrap"
          >
            Clear All
          </button>
        </div>

        {/* Filters and Sort Section */}
        <div className="flex flex-wrap gap-3">
          <div className="flex items-center space-x-2">
            <span className="text-sm font-medium text-gray-700">Sort by:</span>
          </div>
          
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="bg-gray-50 border border-gray-300 text-gray-900 px-4 py-2.5 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
          >
            <option value="date">Date</option>
            <option value="userName">Username</option>
            <option value="planName">Plan Name</option>
            <option value="amount">Amount</option>
          </select>
          
          <button
            onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
            className="bg-gray-50 border border-gray-300 text-gray-900 px-4 py-2.5 rounded-lg hover:bg-gray-100 transition-colors text-sm font-medium"
          >
            {sortOrder === 'asc' ? '↑ Ascending' : '↓ Descending'}
          </button>

          <div className="border-l border-gray-300 mx-2"></div>
          
          <div className="flex items-center space-x-2">
            <span className="text-sm font-medium text-gray-700">Filters:</span>
          </div>
          
          <select
            value={paymentFilterPlan}
            onChange={(e) => setPaymentFilterPlan(e.target.value)}
            className="bg-gray-50 border border-gray-300 text-gray-900 px-4 py-2.5 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
          >
            <option value="all">All Plans</option>
            <option value="Free">Free</option>
            <option value="Professional">Professional</option>
            <option value="Enterprise">Enterprise</option>
          </select>
          
          <select
            value={paymentFilterStatus}
            onChange={(e) => setPaymentFilterStatus(e.target.value)}
            className="bg-gray-50 border border-gray-300 text-gray-900 px-4 py-2.5 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
          >
            <option value="all">All Status</option>
            <option value="completed">Completed</option>
            <option value="pending">Pending</option>
            <option value="failed">Failed</option>
          </select>
          
          <div className="flex items-center space-x-2">
            <input
              type="date"
              value={paymentStartDate}
              onChange={(e) => setPaymentStartDate(e.target.value)}
              className="bg-gray-50 border border-gray-300 text-gray-900 px-4 py-2.5 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            />
            <span className="text-gray-500 text-sm">to</span>
            <input
              type="date"
              value={paymentEndDate}
              onChange={(e) => setPaymentEndDate(e.target.value)}
              className="bg-gray-50 border border-gray-300 text-gray-900 px-4 py-2.5 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            />
          </div>
          
          <button className="bg-blue-600 text-white px-4 py-2.5 rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2 text-sm font-medium ml-auto">
            <Download className="w-4 h-4" />
            <span>Export</span>
          </button>
        </div>

        {/* Active Filters Display */}
        {(paymentSearchTerm || paymentFilterStatus !== 'all' || paymentFilterPlan !== 'all' || paymentStartDate || paymentEndDate) && (
          <div className="flex items-center gap-2 pt-2 border-t border-gray-200">
            <span className="text-sm font-medium text-gray-600">Active Filters:</span>
            <div className="flex flex-wrap gap-2">
              {paymentSearchTerm && (
                <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                  Search: {paymentSearchTerm}
                </span>
              )}
              {paymentFilterPlan !== 'all' && (
                <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                  Plan: {paymentFilterPlan}
                </span>
              )}
              {paymentFilterStatus !== 'all' && (
                <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                  Status: {paymentFilterStatus}
                </span>
              )}
              {(paymentStartDate || paymentEndDate) && (
                <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-indigo-100 text-indigo-800">
                  Date: {paymentStartDate || '...'} → {paymentEndDate || '...'}
                </span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Payments Table */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-2 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
                  Transaction ID
                </th>
                <th className="px-2 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
                  User
                </th>
                <th className="px-2 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
                  Plan
                </th>
                <th className="px-2 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
                  Amount
                </th>
                <th className="px-2 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
                  Date
                </th>
                <th className="px-2 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-2 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
                  Method
                </th>
                <th className="px-2 py-3 text-right text-xs font-semibold text-gray-700 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {filteredPayments.map((payment) => (
                <tr key={payment.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-2 py-3 whitespace-nowrap">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium bg-blue-100 text-blue-800">
                      {payment.transactionId}
                    </span>
                  </td>
                  <td className="px-2 py-3">
                    <div className="min-w-[140px] max-w-[180px]">
                      <div className="text-sm font-medium text-gray-900 truncate">{payment.userName}</div>
                      <div className="text-xs text-gray-500 truncate">{payment.userEmail}</div>
                    </div>
                  </td>
                  <td className="px-2 py-3 whitespace-nowrap">
                    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${
                      payment.planName === 'Enterprise' ? 'bg-blue-100 text-blue-800' :
                      payment.planName === 'Professional' ? 'bg-green-100 text-green-800' :
                      'bg-gray-100 text-gray-800'
                    }`}>
                      {payment.planName === 'Professional' ? 'Pro' : payment.planName === 'Enterprise' ? 'Ent' : 'Free'}
                    </span>
                  </td>
                  <td className="px-2 py-3 whitespace-nowrap">
                    <div className="text-sm font-semibold text-gray-900">
                      ${payment.amount.toFixed(2)}
                    </div>
                  </td>
                  <td className="px-2 py-3 whitespace-nowrap text-sm text-gray-600">
                    {new Date(payment.transactionDate).toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: '2-digit' })}
                  </td>
                  <td className="px-2 py-3 whitespace-nowrap">
                    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${
                      payment.paymentStatus === 'completed' ? 'bg-green-100 text-green-800' :
                      payment.paymentStatus === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                      'bg-red-100 text-red-800'
                    }`}>
                      {payment.paymentStatus === 'completed' ? 'Completed' : payment.paymentStatus === 'pending' ? 'Pending' : 'Failed'}
                    </span>
                  </td>
                  <td className="px-2 py-3 whitespace-nowrap text-sm text-gray-600">
                    {payment.paymentMethod}
                  </td>
                  <td className="px-2 py-3 whitespace-nowrap text-right">
                    <div className="flex items-center justify-end space-x-1">
                      <button className="text-blue-600 hover:text-blue-900 p-1.5 hover:bg-blue-50 rounded transition-colors" title="View">
                        <Eye className="w-4 h-4" />
                      </button>
                      <button className="text-green-600 hover:text-green-900 p-1.5 hover:bg-green-50 rounded transition-colors" title="Download">
                        <Download className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        
        {/* Pagination */}
        <div className="bg-gray-50 px-4 py-3 flex items-center justify-between border-t border-gray-200">
          <div className="text-sm text-gray-600">
            Showing <span className="font-medium">{filteredPayments.length}</span> of{' '}
            <span className="font-medium">{payments.length}</span> transactions
          </div>
          <div className="flex space-x-1">
            <button className="px-3 py-1.5 border border-gray-300 rounded text-sm font-medium text-gray-700 hover:bg-gray-100 transition-colors">
              Prev
            </button>
            <button className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700 transition-colors">
              1
            </button>
            <button className="px-3 py-1.5 border border-gray-300 rounded text-sm font-medium text-gray-700 hover:bg-gray-100 transition-colors">
              2
            </button>
            <button className="px-3 py-1.5 border border-gray-300 rounded text-sm font-medium text-gray-700 hover:bg-gray-100 transition-colors">
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50 relative">
      <InteractiveCursorEffect />
      
      <div className="flex">
        {/* Sidebar */}
        <div className="w-64 flex-shrink-0 bg-white border-r border-gray-200 min-h-screen sticky top-0 overflow-y-auto shadow-sm">
          <div className="p-6">
            <div className="mb-8">
              <div className="flex items-center space-x-2 mb-2">
                <Shield className="w-6 h-6 text-blue-600" />
                <h2 className="text-xl font-medium text-gray-900">Admin Panel</h2>
              </div>
              <div className="flex items-center space-x-2 text-sm text-gray-600 mb-3">
                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                <span>System operational</span>
              </div>
              <div className="bg-gray-50 rounded-lg p-3 border border-gray-200">
                <div className="flex items-center space-x-2 mb-1">
                  <User className="w-4 h-4 text-gray-600" />
                  <span className="text-xs font-medium text-gray-700">Logged in as:</span>
                </div>
                <p className="text-sm text-gray-900 font-medium truncate">{adminEmail}</p>
              </div>
            </div>
            <nav className="space-y-2">
              {[
                { id: 'overview', label: 'Overview', icon: <BarChart3 className="w-5 h-5" /> },
                { id: 'subscribers', label: 'Subscribers', icon: <Users className="w-5 h-5" /> },
                { id: 'payments', label: 'Payments', icon: <DollarSign className="w-5 h-5" /> },
                { id: 'analytics', label: 'Analytics', icon: <Activity className="w-5 h-5" /> },
                { id: 'settings', label: 'Settings', icon: <Settings className="w-5 h-5" /> }
              ].map((item) => (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id as TabType)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 font-medium text-left ${
                    activeTab === item.id
                      ? 'bg-blue-600 text-white shadow-md'
                      : 'text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  <div className="flex-shrink-0">{item.icon}</div>
                  <div className="flex-1 min-w-0">
                    <span className="text-sm">{item.label}</span>
                  </div>
                </button>
              ))}
            </nav>
            
            {/* Logout Button */}
            <div className="mt-8 pt-8 border-t border-gray-200">
              <button
                onClick={handleLogout}
                className="w-full flex items-center space-x-3 px-4 py-3 rounded-lg text-red-600 hover:bg-red-50 transition-all duration-200 font-medium"
              >
                <LogOut className="w-5 h-5" />
                <span>Logout</span>
              </button>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 p-8">
          <div className="max-w-7xl mx-auto">
            <div className="mb-8">
              <h1 className="text-3xl font-medium text-gray-900 mb-2">
                {activeTab === 'overview' && 'Dashboard Overview'}
                {activeTab === 'subscribers' && 'Manage Subscribers'}
                {activeTab === 'payments' && 'Payment Transactions'}
                {activeTab === 'analytics' && 'Analytics'}
                {activeTab === 'settings' && 'System Settings'}
              </h1>
              <p className="text-gray-600">
                {activeTab === 'overview' && 'Monitor system performance and key metrics'}
                {activeTab === 'subscribers' && 'View and manage all system subscribers'}
                {activeTab === 'payments' && 'View and manage all payment transactions'}
                {activeTab === 'analytics' && 'Detailed analytics and reporting'}
                {activeTab === 'settings' && 'Configure system settings'}
              </p>
            </div>

            {activeTab === 'overview' && renderOverview()}
            {activeTab === 'subscribers' && renderSubscribers()}
            {activeTab === 'payments' && renderPayments()}
            {activeTab === 'analytics' && (
              <div className="bg-white rounded-xl p-12 border border-gray-200 shadow-sm text-center">
                <Activity className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                <h3 className="text-xl font-medium text-gray-900 mb-2">Analytics Dashboard</h3>
                <p className="text-gray-600">Advanced analytics and reporting coming soon</p>
              </div>
            )}
            {activeTab === 'settings' && (
              <div className="bg-white rounded-xl p-12 border border-gray-200 shadow-sm text-center">
                <Settings className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                <h3 className="text-xl font-medium text-gray-900 mb-2">System Settings</h3>
                <p className="text-gray-600">System configuration options coming soon</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
