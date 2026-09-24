import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Plus, Search, Upload, Globe, Zap, CheckCircle, Eye,
  Trash2, Copy, Code, Database, Bot, LogOut,
  FileText, Smartphone, ChevronLeft, X,
  AlertCircle, RefreshCw, Palette, BookOpen, Plug,
  LayoutDashboard, MessageCircle, GraduationCap,
  UtensilsCrossed, FlaskConical, Users, Edit3,
  Image as ImageIcon, Download, Check, Lightbulb,
} from 'lucide-react';
import Header from '../components/Header';
import AnalysisSidePanel from '../components/AnalysisSidePanel';
import WhatsAppConnect from '../components/WhatsAppConnect';
import smartchatLogo from '../assets/smartchat_logo.png';
import { API_BASE_URL } from '../services/apiService';

// ─────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────
type TabType = 'overview' | 'chatbots' | 'conversations' | 'knowledge' | 'integrations' | 'customization';

interface Chatbot {
  id: number; name: string; category: string;
  status: 'active' | 'inactive' | 'training';
  conversations: number; accuracy: number;
  response_time: number; success_rate: number;
  created_at: string;
}

interface Conversation {
  id: number; customer_name: string; customer_email?: string;
  topic: string; status: 'resolved' | 'active' | 'escalated';
  satisfaction: number | null; started_at: string;
}

interface KnowledgeDoc {
  id: number; name: string; type: string; size_label?: string;
  status: 'trained' | 'training' | 'failed' | 'pending';
  accuracy?: number; training_progress?: number; upload_date?: string;
  source_url?: string;
  scrape_job_id?: string;  // returned by POST /documents/scrape to open SSE stream
}

interface FAQ {
  id: number; question: string; answer: string;
  category: string; status: 'active' | 'training' | 'inactive';
}

interface Integration {
  id: number; type: string;
  status: 'connected' | 'disconnected' | 'pending';
  connected_at?: string;
}

// Pinecone ingest job state (all categories)
interface PineconeJob {
  jobId:        string;
  docId:        number;
  filename:     string;
  indexName:    string;
  status:       'uploading' | 'extracting' | 'chunking' | 'embedding' | 'done' | 'error';
  total:        number;
  done:         number;
  pct:          number;
  method:       string;
  stage_detail: string;
  items_count:  number;
  pipeline:     string;
  errors:       string[];
}

interface Customization {
  theme: string; theme_color: string; background_color: string;
  text_color: string; button_color: string; button_shape: string;
  font_family: string; font_size: number; header_title: string;
  logo_url: string | null; position: string; welcome_message: string;
}

// ─────────────────────────────────────────────
// Plan Constants
// ─────────────────────────────────────────────
type PlanType = 'free' | 'standard' | 'premium';

const PLAN_LIMITS: Record<PlanType, {
  maxBots: number;
  maxStorageMB: number;
  canCustomizeLogo: boolean;
  canCustomizeHeader: boolean;
  fixedHeaderTitle: string;
  fixedHeaderEmail: string;
}> = {
  free: {
    maxBots: 2,
    maxStorageMB: 300,
    canCustomizeLogo: false,
    canCustomizeHeader: false,
    fixedHeaderTitle: 'SmartChat',
    fixedHeaderEmail: 'Support@smartchat.com',
  },
  standard: {
    maxBots: 2,
    maxStorageMB: 300,
    canCustomizeLogo: false,
    canCustomizeHeader: false,
    fixedHeaderTitle: 'SmartChat',
    fixedHeaderEmail: 'Support@smartchat.com',
  },
  premium: {
    maxBots: 4,
    maxStorageMB: Infinity,
    canCustomizeLogo: true,
    canCustomizeHeader: true,
    fixedHeaderTitle: '',
    fixedHeaderEmail: '',
  },
};

// Fixed SmartChat logo for free/standard plans
const FIXED_LOGO_URL = smartchatLogo;

// ─────────────────────────────────────────────
// API
// ─────────────────────────────────────────────
const API_BASE = API_BASE_URL;
const WIDGET_URL_TEMPLATE = (import.meta as any).env?.VITE_WIDGET_URL_TEMPLATE
  || (import.meta.env.DEV ? 'http://localhost:{port}/{botId}' : '');

function getAuth() {
  try {
    const raw = localStorage.getItem('auth');
    if (!raw) return null;
    return JSON.parse(raw) as { user_id: number; token: string };
  } catch { return null; }
}

async function apiFetch<T>(
  path: string,
  options?: RequestInit & { params?: Record<string, any> }
): Promise<T> {
  const auth = getAuth();
  if (!auth) throw new Error('Not authenticated');

  const params = new URLSearchParams({
    user_id: String(auth.user_id),
    token: auth.token,
    ...(options?.params || {}),
  });
  const url = `${API_BASE}${path}?${params}`;

  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${auth.token}`,
      ...(options?.headers || {}),
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(err.detail || JSON.stringify(err));
  }
  return res.json();
}

async function apiUpload<T>(path: string, formData: FormData): Promise<T> {
  const auth = getAuth();
  if (!auth) throw new Error('Not authenticated');
  const params = new URLSearchParams({ user_id: String(auth.user_id), token: auth.token });
  const res = await fetch(`${API_BASE}${path}?${params}`, {
    method: 'POST',
    body: formData,
    headers: { 'Authorization': `Bearer ${auth.token}` },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(err.detail || 'Upload failed');
  }
  return res.json();
}

// ─────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────
const CATEGORY_META: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
  university:  { label: 'University',  icon: <GraduationCap className="w-5 h-5" />, color: 'from-blue-500 to-indigo-600' },
  faculty:     { label: 'Faculty',     icon: <Users className="w-5 h-5" />,         color: 'from-purple-500 to-violet-600' },
  fyp:         { label: 'FYP',         icon: <FlaskConical className="w-5 h-5" />,  color: 'from-green-500 to-emerald-600' },
  restaurant:  { label: 'Restaurant',  icon: <UtensilsCrossed className="w-5 h-5" />, color: 'from-orange-500 to-red-500' },
  general:     { label: 'General',     icon: <Bot className="w-5 h-5" />,           color: 'from-gray-500 to-gray-700' },
};

const StatusBadge = ({ status }: { status: string }) => {
  const map: Record<string, string> = {
    active: 'bg-green-100 text-green-700', training: 'bg-yellow-100 text-yellow-700',
    inactive: 'bg-gray-100 text-gray-600', resolved: 'bg-blue-100 text-blue-700',
    escalated: 'bg-red-100 text-red-700',  trained: 'bg-green-100 text-green-700',
    pending: 'bg-gray-100 text-gray-600',  failed: 'bg-red-100 text-red-700',
    connected: 'bg-green-100 text-green-700', disconnected: 'bg-gray-100 text-gray-600',
  };
  return (
    <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${map[status] ?? 'bg-gray-100 text-gray-600'}`}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
};

const NAV_ITEMS: { tab: TabType; label: string; icon: React.ReactNode }[] = [
  { tab: 'overview',      label: 'Overview',       icon: <LayoutDashboard className="w-4 h-4" /> },
  { tab: 'chatbots',      label: 'Manage Bot',     icon: <Bot className="w-4 h-4" /> },
  { tab: 'conversations', label: 'Conversations',  icon: <MessageCircle className="w-4 h-4" /> },
  { tab: 'knowledge',     label: 'Knowledge Base', icon: <BookOpen className="w-4 h-4" /> },
  { tab: 'integrations',  label: 'Integrations',   icon: <Plug className="w-4 h-4" /> },
  { tab: 'customization', label: 'Customization',  icon: <Palette className="w-4 h-4" /> },
];

// Simulate polling progress bar for training docs
function useDocProgress(
  docId: number | null,
  onComplete: (id: number) => void
) {
  const [progress, setProgress] = useState(0);
  useEffect(() => {
    if (docId === null) { setProgress(0); return; }
    setProgress(5);
    const interval = setInterval(() => {
      setProgress(prev => {
        if (prev >= 100) { clearInterval(interval); onComplete(docId); return 100; }
        return prev + Math.random() * 12;
      });
    }, 400);
    return () => clearInterval(interval);
  }, [docId]);
  return Math.min(100, Math.round(progress));
}

// ─────────────────────────────────────────────
// MAIN COMPONENT
// ─────────────────────────────────────────────
export default function DashboardPage() {
  const navigate = useNavigate();

  const authGuard = useCallback(() => {
    const auth = getAuth();
    if (!auth) { navigate('/login'); return false; }
    return true;
  }, [navigate]);

  // ── global state ──
  const [chatbots, setChatbots] = useState<Chatbot[]>([]);
  const [selectedBot, setSelectedBot] = useState<Chatbot | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [loading, setLoading] = useState(true);
  const [botLoading, setBotLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');

  // ── subscriber plan ──
  const [userPlan, setUserPlan] = useState<PlanType>('free');
  const planLimits = PLAN_LIMITS[userPlan];

  // ── bot-specific data ──
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [docs, setDocs] = useState<KnowledgeDoc[]>([]);
  const [faqs, setFaqs] = useState<FAQ[]>([]);
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [customization, setCustomization] = useState<Customization>({
    theme: 'light', theme_color: '#4285F4', background_color: '#ffffff',
    text_color: '#333333', button_color: '#34A853', button_shape: 'rounded',
    font_family: 'Inter', font_size: 14, header_title: 'Chat Support',
    logo_url: null, position: 'bottom-right', welcome_message: 'Hi! How can I help you today?',
  });

  // ── modals & forms ──
  const [showNewBotModal, setShowNewBotModal] = useState(false);
  const [showWhatsAppModal, setShowWhatsAppModal] = useState(false);
  const [showWebsiteModal, setShowWebsiteModal] = useState(false);
  const [newBotName, setNewBotName] = useState('');
  const [newBotCategory, setNewBotCategory] = useState<string>('general');
  const [isCreating, setIsCreating] = useState(false);
  const [showAddFaq, setShowAddFaq] = useState(false);
  const [newFaq, setNewFaq] = useState({ question: '', answer: '', category: '' });
  const [websiteUrl, setWebsiteUrl] = useState('');
  const [isScraping, setIsScraping] = useState(false);
  const [editBot, setEditBot] = useState<{ name: string; status: string }>({ name: '', status: '' });
  const [savingBot, setSavingBot] = useState(false);
  const [savingCust, setSavingCust] = useState(false);
  const [previewRefreshKey, setPreviewRefreshKey] = useState(0);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [uploadingDoc, setUploadingDoc] = useState(false);
  const [trainingDocId, setTrainingDocId] = useState<number | null>(null);
  const [pineconeJobs, setPineconeJobs] = useState<Record<number, PineconeJob>>({});
  const pineconeEsRef = useRef<Record<number, EventSource>>({});

  // ── Crawlee JSON upload state ──
  const [uploadingCrawlee, setUploadingCrawlee]   = useState(false);
  const [crawleeSourceType, setCrawleeSourceType] = useState<'food_items' | 'page_data'>('food_items');
  const crawleeInputRef = useRef<HTMLInputElement>(null);

  const [convSearch, setConvSearch] = useState('');
  const [selectedConv, setSelectedConv] = useState<Conversation | null>(null);
  const [convMessages, setConvMessages] = useState<any[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const logoInputRef = useRef<HTMLInputElement>(null);

  // ── Analysis panel state ──
  const [showAnalysisPanel, setShowAnalysisPanel] = useState(false);
  const [analysisData, setAnalysisData] = useState<any>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(null), 3000); };

  // Training progress for just-uploaded doc
  const trainingProgress = useDocProgress(trainingDocId, (id) => {
    setDocs(prev => prev.map(d => d.id === id ? { ...d, status: 'trained', training_progress: 100, accuracy: 90 } : d));
    setTrainingDocId(null);
    showToast('Document training complete!');
  });

  // ─── Load chatbots & plan from payments table ───
  useEffect(() => {
    if (!authGuard()) return;
    setLoading(true);
    Promise.allSettled([
      apiFetch<Chatbot[]>('/chatbots/'),
      // Backend: SELECT plan FROM payments
      //   WHERE subscriber_id = <auth.user_id> AND status = 'completed'
      //   ORDER BY plan_starts_at DESC LIMIT 1
      apiFetch<{ plan: string }>('/payments/my-plan'),
    ]).then(([botsRes, planRes]) => {
      if (botsRes.status === 'fulfilled') setChatbots(botsRes.value);
      else setError((botsRes.reason as Error).message);

      if (planRes.status === 'fulfilled') {
        const p = planRes.value.plan?.toLowerCase() as PlanType;
        if (p === 'premium') setUserPlan('premium');
        else if (p === 'standard') setUserPlan('standard');
        else setUserPlan('free');
      } else {
        // Payment lookup failed — treat as free plan
        setUserPlan('free');
      }
    }).finally(() => setLoading(false));
  }, [authGuard]);

  // ─── Load bot data when bot selected ───
  useEffect(() => {
    if (!selectedBot) return;
    setBotLoading(true);
    setEditBot({ name: selectedBot.name, status: selectedBot.status });
    Promise.allSettled([
      apiFetch<Chatbot>(`/chatbots/${selectedBot.id}`),
      apiFetch<Conversation[]>(`/chatbots/${selectedBot.id}/conversations`),
      apiFetch<KnowledgeDoc[]>(`/chatbots/${selectedBot.id}/documents`),
      apiFetch<FAQ[]>(`/chatbots/${selectedBot.id}/faqs`),
      apiFetch<Integration[]>(`/chatbots/${selectedBot.id}/integrations`),
      apiFetch<Customization>(`/chatbots/${selectedBot.id}/customization`),
    ]).then(([bot, conv, doc, faq, intg, cust]) => {
      // Refresh selectedBot with latest stats from the server
      if (bot.status === 'fulfilled') {
        setSelectedBot(bot.value);
        setEditBot({ name: bot.value.name, status: bot.value.status });
      }
      if (conv.status === 'fulfilled') setConversations(conv.value);
      if (doc.status === 'fulfilled') setDocs(doc.value);
      if (faq.status === 'fulfilled') setFaqs(faq.value);
      if (intg.status === 'fulfilled') setIntegrations(intg.value);
      if (cust.status === 'fulfilled') setCustomization(cust.value as Customization);
    }).finally(() => setBotLoading(false));
  }, [selectedBot?.id]);

  // ─── Actions ───
  const handleCreateBot = async () => {
    if (!newBotName.trim()) return;
    // ── Plan limit: max bots ──
    if (chatbots.length >= planLimits.maxBots) {
      setError(
        userPlan === 'premium'
          ? `Premium plan allows a maximum of ${planLimits.maxBots} chatbots.`
          : `Your ${userPlan} plan allows a maximum of ${planLimits.maxBots} chatbots. Upgrade to Premium to create more.`
      );
      return;
    }
    setIsCreating(true);
    try {
      const bot = await apiFetch<Chatbot>('/chatbots/', {
        method: 'POST',
        body: JSON.stringify({ name: newBotName, category: newBotCategory, status: 'inactive' }),
      });
      setChatbots(prev => [bot, ...prev]);
      setNewBotName(''); setNewBotCategory('general'); setShowNewBotModal(false);
      showToast('Chatbot created!');
    } catch (e: any) { setError(e.message); }
    finally { setIsCreating(false); }
  };

  const handleDeleteBot = async (id: number, e?: React.MouseEvent) => {
    e?.stopPropagation();
    if (!window.confirm('Delete this chatbot permanently?')) return;
    try {
      await apiFetch(`/chatbots/${id}`, { method: 'DELETE' });
      setChatbots(prev => prev.filter(b => b.id !== id));
      if (selectedBot?.id === id) setSelectedBot(null);
      showToast('Chatbot deleted');
    } catch (e: any) { setError(e.message); }
  };

  const handleSaveBot = async () => {
    if (!selectedBot) return;
    setSavingBot(true);
    try {
      const updated = await apiFetch<Chatbot>(`/chatbots/${selectedBot.id}`, {
        method: 'PUT', body: JSON.stringify(editBot),
      });
      setSelectedBot(updated);
      setChatbots(prev => prev.map(b => b.id === updated.id ? updated : b));
      showToast('Bot updated!');
    } catch (e: any) { setError(e.message); }
    finally { setSavingBot(false); }
  };

  const handleUploadFile = async (file: File) => {
    if (!selectedBot) return;

    // ── Plan limit: total document storage ──
    if (planLimits.maxStorageMB !== Infinity) {
      // Calculate approximate current usage from docs (size_label may be e.g. "1.2 MB")
      const parseSizeMB = (label?: string): number => {
        if (!label) return 0;
        const m = label.match(/([\d.]+)\s*(MB|KB|GB)/i);
        if (!m) return 0;
        const val = parseFloat(m[1]);
        const unit = m[2].toUpperCase();
        if (unit === 'KB') return val / 1024;
        if (unit === 'GB') return val * 1024;
        return val;
      };
      const usedMB = docs.reduce((sum, d) => sum + parseSizeMB(d.size_label), 0);
      const newFileMB = file.size / (1024 * 1024);
      if (usedMB + newFileMB > planLimits.maxStorageMB) {
        setError(
          `Storage limit reached. Your ${userPlan} plan allows up to ${planLimits.maxStorageMB} MB of documents. ` +
          `Upgrade to Premium for unlimited storage.`
        );
        return;
      }
    }

    setUploadingDoc(true);
    const fd = new FormData();
    fd.append('file', file);
    try {
      const doc = await apiUpload<KnowledgeDoc>(`/chatbots/${selectedBot.id}/documents/upload`, fd);
      setDocs(prev => [doc, ...prev]);
      setTrainingDocId(doc.id);
      showToast('File uploaded — training started');

      // ── Pinecone ingestion for ALL bot categories that use vector search ──
      const pineconeCategories = ['university', 'restaurant', 'faculty', 'fyp', 'general'];
      if (pineconeCategories.includes(selectedBot.category) && file.name.toLowerCase().endsWith('.pdf')) {
        await startPineconeIngest(doc, file);
      }
    } catch (e: any) { setError(e.message); }
    finally { setUploadingDoc(false); }
  };

  // ── Pinecone helpers ─────────────────────────────────────────────────────────
  //  Works for ALL categories: restaurant, university, faculty, fyp, general
  //  Each category ingests into its own dedicated Pinecone index with namespace isolation

  // Determine which Pinecone index a category maps to
  // Each category gets its own dedicated index with namespace isolation
  const pineconeCategory = (cat: string): string => {
    if (cat === 'restaurant') return 'restaurant';
    if (cat === 'faculty')    return 'faculty';
    if (cat === 'fyp')        return 'fyp';
    if (cat === 'general')    return 'general';
    // Default: university
    return 'university';
  };

  // ── Live bot URL (used by both Integrations preview and Customization preview) ──
  const BOT_PORT_MAP: Record<string, number> = {
    university: 8001, restaurant: 8002, faculty: 8003, fyp: 8004, general: 8005,
  };
  const getBotEmbedUrl = (bot: Chatbot): string => {
    const port = BOT_PORT_MAP[bot.category] ?? 8001;
    return WIDGET_URL_TEMPLATE.replace('{port}', String(port)).replace('{botId}', String(bot.id));
  };

  const startPineconeIngest = async (doc: KnowledgeDoc, file: File) => {
    const auth = getAuth();
    if (!auth || !selectedBot) return;

    const pcat = pineconeCategory(selectedBot.category);
    const fd = new FormData();
    fd.append('file', file);
    const params = new URLSearchParams({
      user_id:  String(auth.user_id),
      token:    auth.token,
      doc_id:   String(doc.id),
      category: pcat,
    });

    let jobId = '';
    let indexName = '';
    try {
      const res = await fetch(
        `${API_BASE}/chatbots/${selectedBot.id}/pinecone/ingest?${params}`,
        { method: 'POST', body: fd, headers: { 'Authorization': `Bearer ${auth.token}` } }
      );
      if (!res.ok) throw new Error('Failed to start Pinecone ingest');
      const data = await res.json();
      jobId     = data.job_id;
      indexName = data.index_name;
    } catch (e: any) {
      setError(`Pinecone ingest failed: ${e.message}`);
      return;
    }

    const initialJob: PineconeJob = {
      jobId, docId: doc.id, filename: file.name, indexName,
      status: 'uploading', total: 0, done: 0, pct: 0,
      method: 'unknown', stage_detail: '', items_count: 0, pipeline: pcat, errors: [],
    };
    setPineconeJobs(prev => ({ ...prev, [doc.id]: initialJob }));

    const sseUrl = `${API_BASE}/chatbots/${selectedBot.id}/pinecone/ingest/${jobId}/progress?${params}`;
    const es = new EventSource(sseUrl);
    pineconeEsRef.current[doc.id] = es;

    es.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        setPineconeJobs(prev => ({
          ...prev,
          [doc.id]: { ...prev[doc.id], ...payload, jobId, docId: doc.id, indexName },
        }));
        if (payload.status === 'done') {
          es.close();
          delete pineconeEsRef.current[doc.id];
          showToast(`✅ Pinecone [${indexName}] ready — ${payload.done} chunks embedded`);
          setDocs(prev => prev.map(d =>
            d.id === doc.id ? { ...d, status: 'trained', training_progress: 100, accuracy: 92 } : d
          ));
          setTrainingDocId(null);
        }
        if (payload.status === 'error') {
          es.close();
          delete pineconeEsRef.current[doc.id];
          setError(`Pinecone error: ${payload.errors?.[0] || 'Unknown error'}`);
        }
      } catch { /* ignore malformed events */ }
    };
    es.onerror = () => { es.close(); delete pineconeEsRef.current[doc.id]; };
  };

  // ── Crawlee JSON upload → /crawlee/ingest ─────────────────────────────────
  //  Uploads food-items.json or page-data.json produced by the Crawlee scraper.
  //  Works for ALL categories — backend picks the right parser automatically.

  const handleCrawleeUpload = async (file: File) => {
    if (!selectedBot) return;
    setUploadingCrawlee(true);

    const auth = getAuth();
    if (!auth) { setError('Not authenticated'); setUploadingCrawlee(false); return; }

    // Create a placeholder doc record so progress appears in the list
    const placeholderDoc: KnowledgeDoc = {
      id: Date.now(),           // temp id — replaced after backend responds
      name: file.name,
      type: 'crawlee_json',
      size_label: `${(file.size / 1024).toFixed(1)} KB`,
      status: 'training',
      training_progress: 0,
      upload_date: new Date().toLocaleDateString(),
    };
    setDocs(prev => [placeholderDoc, ...prev]);

    const pcat = pineconeCategory(selectedBot.category);
    const fd   = new FormData();
    fd.append('file', file);

    const params = new URLSearchParams({
      user_id:     String(auth.user_id),
      token:       auth.token,
      doc_id:      String(placeholderDoc.id),
      source_type: crawleeSourceType,
      category:    pcat,
    });

    let jobId     = '';
    let indexName = '';
    try {
      const res = await fetch(
        `${API_BASE}/chatbots/${selectedBot.id}/crawlee/ingest?${params}`,
        { method: 'POST', body: fd, headers: { 'Authorization': `Bearer ${auth.token}` } }
      );
      if (!res.ok) throw new Error('Crawlee ingest failed to start');
      const data = await res.json();
      jobId     = data.job_id;
      indexName = data.index_name;
    } catch (e: any) {
      setError(`Crawlee ingest failed: ${e.message}`);
      setDocs(prev => prev.filter(d => d.id !== placeholderDoc.id));
      setUploadingCrawlee(false);
      return;
    }

    // Register a Pinecone job so the same progress UI renders
    const crawleeJob: PineconeJob = {
      jobId,
      docId:        placeholderDoc.id,
      filename:     file.name,
      indexName,
      status:       'uploading',
      total:        0,
      done:         0,
      pct:          0,
      method:       'json',
      stage_detail: '',
      items_count:  0,
      pipeline:     `crawlee_${pcat}_${crawleeSourceType}`,
      errors:       [],
    };
    setPineconeJobs(prev => ({ ...prev, [placeholderDoc.id]: crawleeJob }));

    // SSE progress stream — same endpoint shape as PDF pipeline
    const sseUrl = `${API_BASE}/chatbots/${selectedBot.id}/crawlee/ingest/${jobId}/progress?user_id=${auth.user_id}&token=${auth.token}`;
    const es = new EventSource(sseUrl);
    pineconeEsRef.current[placeholderDoc.id] = es;

    es.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        setPineconeJobs(prev => ({
          ...prev,
          [placeholderDoc.id]: { ...prev[placeholderDoc.id], ...payload, jobId, docId: placeholderDoc.id, indexName },
        }));
        if (payload.status === 'done') {
          es.close();
          delete pineconeEsRef.current[placeholderDoc.id];
          showToast(`✅ Crawlee data indexed — ${payload.done} vectors in [${indexName}]`);
          setDocs(prev => prev.map(d =>
            d.id === placeholderDoc.id
              ? { ...d, status: 'trained', training_progress: 100, accuracy: 92 }
              : d
          ));
        }
        if (payload.status === 'error') {
          es.close();
          delete pineconeEsRef.current[placeholderDoc.id];
          setError(`Crawlee ingest error: ${payload.errors?.[0] || 'Unknown error'}`);
          setDocs(prev => prev.map(d =>
            d.id === placeholderDoc.id ? { ...d, status: 'failed' } : d
          ));
        }
      } catch { /* ignore */ }
    };
    es.onerror = () => { es.close(); delete pineconeEsRef.current[placeholderDoc.id]; };

    setUploadingCrawlee(false);
    showToast('Crawlee JSON upload started — indexing into Pinecone…');
  };

  // ── Polling fallback when SSE fails (CORS / proxy issues) ──────────────────
  // Polls /scrape/{job_id}/status every 2s and updates UI the same way SSE does.
  const _pollScrapeStatus = (
    docId: number,
    jobId: string,
    botId: number,
    auth: { user_id: number; token: string },
  ) => {
    const statusMap: Record<string, PineconeJob['status']> = {
      queued: 'uploading', scraping: 'extracting',
      ingesting_food: 'chunking', ingesting_pages: 'embedding',
      done: 'done', done_with_errors: 'done', error: 'error',
    };
    const stagePct: Record<string, number> = {
      queued: 5, scraping: 30, ingesting_food: 60, ingesting_pages: 80, done: 100,
    };

    const poll = async () => {
      try {
        const params = new URLSearchParams({ user_id: String(auth.user_id), token: auth.token });
        const res = await fetch(
          `${API_BASE}/chatbots/${botId}/documents/scrape/${jobId}/status?${params}`
        );
        if (!res.ok) return;  // server not ready yet, retry next tick
        const payload = await res.json();
        const mappedStatus = statusMap[payload.status] ?? 'uploading';
        const pct = stagePct[payload.status] ?? 0;

        setPineconeJobs(prev => ({
          ...prev,
          [docId]: {
            ...prev[docId],
            status: mappedStatus, pct,
            done: payload.total_vectors ?? 0,
            total: payload.total_vectors ?? 0,
            stage_detail: payload.stage_detail ?? '',
            errors: payload.errors ?? [],
            items_count: payload.food_count ?? 0,
          },
        }));

        if (payload.status === 'done' || payload.status === 'done_with_errors') {
          showToast(`✅ Scraped ${payload.page_count ?? 0} pages, ${payload.food_count ?? 0} items → ${payload.total_vectors ?? 0} vectors`);
          setDocs(prev => prev.map(d =>
            d.id === docId ? { ...d, status: 'trained', training_progress: 100, accuracy: 92 } : d
          ));
          return; // stop polling
        }
        if (payload.status === 'error') {
          setError(`Scrape failed: ${payload.errors?.[0] ?? 'Unknown error'}`);
          setDocs(prev => prev.map(d => d.id === docId ? { ...d, status: 'failed' } : d));
          return; // stop polling
        }
      } catch { /* network error, try again next tick */ }
      setTimeout(poll, 2000);
    };

    setTimeout(poll, 2000); // start polling after 2s
  };

  const handleScrape = async () => {
    if (!selectedBot || !websiteUrl.trim()) return;
    setIsScraping(true);
    const auth = getAuth();
    if (!auth) { setError('Not authenticated'); setIsScraping(false); return; }

    try {
      const doc = await apiFetch<KnowledgeDoc>(
        `/chatbots/${selectedBot.id}/documents/scrape`,
        { method: 'POST', body: JSON.stringify({ url: websiteUrl, max_pages: 30 }) }
      );
      setDocs(prev => [doc, ...prev]);
      setWebsiteUrl('');
      showToast('Scraping started — Crawlee is running…');

      // ── Open SSE stream for this scrape job ──────────────────────────────
      if (doc.scrape_job_id) {
        const scrapeJobId = doc.scrape_job_id;

        // Seed a pinecone job so the progress panel renders immediately
        const seedJob: PineconeJob = {
          jobId: scrapeJobId, docId: doc.id, filename: doc.name,
          indexName: '', status: 'uploading', total: 0, done: 0, pct: 0,
          method: 'crawlee', stage_detail: 'Crawlee is crawling the site…',
          items_count: 0, pipeline: `crawlee_${selectedBot.category}_scrape`, errors: [],
        };
        setPineconeJobs(prev => ({ ...prev, [doc.id]: seedJob }));

        const params = new URLSearchParams({ user_id: String(auth.user_id), token: auth.token });
        const sseUrl = `${API_BASE}/chatbots/${selectedBot.id}/documents/scrape/${scrapeJobId}/progress?${params}`;
        const es = new EventSource(sseUrl);
        pineconeEsRef.current[doc.id] = es;

        es.onmessage = (event) => {
          try {
            const payload = JSON.parse(event.data);

            // Map scrape status → PineconeJob status for the shared progress UI
            const statusMap: Record<string, PineconeJob['status']> = {
              queued:           'uploading',
              scraping:         'extracting',
              ingesting_food:   'chunking',
              ingesting_pages:  'embedding',
              done:             'done',
              done_with_errors: 'done',
              error:            'error',
            };

            // Compute a synthetic pct from stage
            const stagePct: Record<string, number> = {
              queued: 5, scraping: 30, ingesting_food: 60, ingesting_pages: 80, done: 100,
            };

            const mappedStatus = statusMap[payload.status] ?? 'uploading';
            const pct = stagePct[payload.status] ?? 0;

            setPineconeJobs(prev => ({
              ...prev,
              [doc.id]: {
                ...prev[doc.id],
                status:       mappedStatus,
                pct,
                done:         payload.total_vectors ?? 0,
                total:        payload.total_vectors ?? 0,
                stage_detail: payload.stage_detail ?? '',
                indexName:    payload.index ?? prev[doc.id]?.indexName ?? '',
                errors:       payload.errors ?? [],
                items_count:  payload.food_count ?? 0,
              },
            }));

            if (payload.status === 'done' || payload.status === 'done_with_errors') {
              es.close();
              delete pineconeEsRef.current[doc.id];
              const tv = payload.total_vectors ?? 0;
              const fc = payload.food_count ?? 0;
              const pc = payload.page_count ?? 0;
              showToast(`✅ Scraped ${pc} pages, ${fc} items → ${tv} vectors indexed`);
              setDocs(prev => prev.map(d =>
                d.id === doc.id ? { ...d, status: 'trained', training_progress: 100, accuracy: 92 } : d
              ));
            }
            if (payload.status === 'error') {
              es.close();
              delete pineconeEsRef.current[doc.id];
              setError(`Scrape failed: ${payload.errors?.[0] ?? 'Unknown error'}`);
              setDocs(prev => prev.map(d => d.id === doc.id ? { ...d, status: 'failed' } : d));
            }
          } catch { /* ignore */ }
        };
        es.onerror = () => {
          es.close();
          delete pineconeEsRef.current[doc.id];
          // SSE failed (CORS, network, or server error) — fall back to polling
          _pollScrapeStatus(doc.id, scrapeJobId, selectedBot.id, auth);
        };
      }
    } catch (e: any) { setError(e.message); }
    finally { setIsScraping(false); }
  };

  const handleDeleteDoc = async (docId: number) => {
    if (!selectedBot) return;
    try {
      await apiFetch(`/chatbots/${selectedBot.id}/documents/${docId}`, { method: 'DELETE' });
      setDocs(prev => prev.filter(d => d.id !== docId));
      showToast('Document removed');
    } catch (e: any) { setError(e.message); }
  };

  const handleAddFaq = async () => {
    if (!selectedBot || !newFaq.question.trim() || !newFaq.answer.trim()) return;
    try {
      const created = await apiFetch<FAQ>(`/chatbots/${selectedBot.id}/faqs`, {
        method: 'POST', body: JSON.stringify(newFaq),
      });
      setFaqs(prev => [created, ...prev]);
      setNewFaq({ question: '', answer: '', category: '' });
      setShowAddFaq(false);
      showToast('FAQ added!');
    } catch (e: any) { setError(e.message); }
  };

  const handleDeleteFaq = async (faqId: number) => {
    if (!selectedBot) return;
    try {
      await apiFetch(`/chatbots/${selectedBot.id}/faqs/${faqId}`, { method: 'DELETE' });
      setFaqs(prev => prev.filter(f => f.id !== faqId));
      showToast('FAQ removed');
    } catch (e: any) { setError(e.message); }
  };

  const handleToggleIntegration = async (type: string) => {
    if (!selectedBot) return;
    try {
      const updated = await apiFetch<Integration>(
        `/chatbots/${selectedBot.id}/integrations/${type}/connect`,
        { method: 'POST' }
      );
      setIntegrations(prev => prev.map(i => i.type === type ? updated : i));
      showToast(updated.status === 'connected' ? `${type} connected!` : `${type} disconnected`);
    } catch (e: any) { setError(e.message); }
  };

  const refreshIntegrations = async () => {
    if (!selectedBot) return;
    try {
      const data = await apiFetch<Integration[]>(`/chatbots/${selectedBot.id}/integrations`);
      setIntegrations(data);
    } catch (e: any) { setError(e.message); }
  };

  const handleSaveCustomization = async () => {
    if (!selectedBot) return;
    setSavingCust(true);

    // ── For free/standard plans, always lock header_title and logo_url ──
    const custToSave: Customization = planLimits.canCustomizeHeader
      ? customization
      : {
          ...customization,
          header_title: planLimits.fixedHeaderTitle,
          logo_url: FIXED_LOGO_URL,
        };

    try {
      const updated = await apiFetch<Customization>(`/chatbots/${selectedBot.id}/customization`, {
        method: 'PUT', body: JSON.stringify(custToSave),
      });
      setCustomization(updated);
      setPreviewRefreshKey(k => k + 1);
      showToast('Customization saved!');
    } catch (e: any) { setError(e.message); }
    finally { setSavingCust(false); }
  };

  const handleLogoUpload = async (file: File) => {
    if (!selectedBot) return;
    setUploadingLogo(true);
    const fd = new FormData();
    fd.append('file', file);
    try {
      const res = await apiUpload<{ logo_url: string }>(
        `/chatbots/${selectedBot.id}/customization/logo`, fd
      );
      setCustomization(prev => ({ ...prev, logo_url: `${API_BASE}${res.logo_url}` }));
      showToast('Logo uploaded!');
    } catch (e: any) { setError(e.message); }
    finally { setUploadingLogo(false); }
  };

  const handleViewConversation = async (conv: Conversation) => {
    setSelectedConv(conv);
    if (!selectedBot) return;
    try {
      const msgs = await apiFetch<any[]>(
        `/chatbots/${selectedBot.id}/conversations/${conv.id}/messages`
      );
      setConvMessages(msgs);
    } catch { setConvMessages([]); }
  };

  const handleAnalyzeBot = async () => {
    if (!selectedBot) return;
    setAnalysisError(null);
    setAnalysisLoading(true);
    // Open the panel right away so the loading spinner inside it is visible
    // while the request is in flight, instead of only appearing once data
    // has already come back (which made the click look like it did nothing).
    setShowAnalysisPanel(true);
    try {
      const data = await apiFetch<any>(
        `/chatbots/${selectedBot.id}/analyze`,
        { method: 'POST', params: { days: 30, refresh: true } }
      );
      setAnalysisData(data);
      showToast('Analysis complete!');
    } catch (e: any) {
      setAnalysisError(e.message || 'Failed to analyze conversations');
    } finally {
      setAnalysisLoading(false);
    }
  };

  // "Ask AI" — chat with your data, from inside the Analysis panel
  const handleAskAI = async (
    question: string,
    history: { role: 'user' | 'assistant'; content: string }[]
  ): Promise<string> => {
    if (!selectedBot) throw new Error('No chatbot selected');
    const res = await apiFetch<{ answer: string }>(
      `/chatbots/${selectedBot.id}/analyze/chat`,
      {
        method: 'POST',
        params: { days: 30 },
        body: JSON.stringify({ question, chat_history: history }),
      }
    );
    return res.answer;
  };

  const handleLogout = () => { localStorage.removeItem('auth'); navigate('/login'); };

  // ─────────────────────────────────────────────
  // BOT SELECTOR
  // ─────────────────────────────────────────────
  const renderSelector = () => {
    const filtered = chatbots.filter(b =>
      b.name.toLowerCase().includes(searchTerm.toLowerCase())
    );

    return (
      <div className="min-h-screen bg-gray-50">
        <Header />

        {/* Toast */}
        {toast && (
          <div className="fixed top-4 right-4 z-50 bg-gray-900 text-white px-4 py-2 rounded-lg shadow-lg flex items-center gap-2 text-sm animate-fade-in">
            <Check className="w-4 h-4 text-green-400" /> {toast}
          </div>
        )}

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-10">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">My Chatbots</h1>
              <p className="text-gray-500 mt-1">Select a chatbot to manage or create a new one</p>
              {/* Plan badge */}
              <div className="flex items-center gap-2 mt-2">
                <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${
                  userPlan === 'premium'
                    ? 'bg-yellow-100 text-yellow-700 border border-yellow-200'
                    : 'bg-gray-100 text-gray-600 border border-gray-200'
                }`}>
                  {userPlan === 'premium' ? '⭐ Premium' : userPlan === 'standard' ? '📦 Standard' : '🆓 Free'}
                </span>
                <span className="text-xs text-gray-400">
                  {chatbots.length} / {planLimits.maxBots} bots
                  {planLimits.maxStorageMB !== Infinity && ` • ${planLimits.maxStorageMB} MB storage`}
                </span>
              </div>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => {
                  if (chatbots.length >= planLimits.maxBots) {
                    setError(
                      userPlan === 'premium'
                        ? `Premium plan allows a maximum of ${planLimits.maxBots} chatbots.`
                        : `Your ${userPlan} plan allows a maximum of ${planLimits.maxBots} chatbots. Upgrade to Premium for up to 4 bots.`
                    );
                    return;
                  }
                  setShowNewBotModal(true);
                }}
                className={`flex items-center gap-2 text-white px-5 py-2.5 rounded-lg font-medium transition shadow ${
                  chatbots.length >= planLimits.maxBots
                    ? 'bg-gray-400 cursor-not-allowed'
                    : 'bg-blue-600 hover:bg-blue-700'
                }`}>
                <Plus className="w-5 h-5" /> New Chatbot
                {chatbots.length >= planLimits.maxBots && <span className="text-xs opacity-75">(Limit reached)</span>}
              </button>
              <button onClick={handleLogout}
                className="flex items-center gap-2 bg-white border border-gray-200 hover:bg-gray-50 text-gray-700 px-5 py-2.5 rounded-lg font-medium transition">
                <LogOut className="w-4 h-4" /> Logout
              </button>
            </div>
          </div>

          {error && (
            <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6 text-sm">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span className="flex-1">{error}</span>
              <button onClick={() => setError(null)}><X className="w-4 h-4" /></button>
            </div>
          )}

          <div className="relative mb-8 max-w-sm">
            <Search className="absolute left-3 top-3 w-4 h-4 text-gray-400" />
            <input type="text" placeholder="Search chatbots..."
              value={searchTerm} onChange={e => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white text-sm" />
          </div>

          {loading ? (
            <div className="flex flex-col items-center py-24 gap-3 text-gray-400">
              <RefreshCw className="w-8 h-8 animate-spin" />
              <p>Loading chatbots...</p>
            </div>
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center py-24 gap-4 text-gray-400">
              <Bot className="w-16 h-16 text-gray-200" />
              <p className="text-lg font-medium text-gray-500">
                {chatbots.length === 0 ? 'No chatbots yet — create your first one!' : 'No results'}
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
              {filtered.map(bot => {
                const meta = CATEGORY_META[bot.category] ?? CATEGORY_META.general;
                return (
                  <div key={bot.id}
                    className="group bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-all duration-200 overflow-hidden cursor-pointer"
                    onClick={() => { setSelectedBot(bot); setActiveTab('overview'); }}>
                    <div className={`h-1.5 w-full bg-gradient-to-r ${meta.color}`} />
                    <div className="p-6">
                      <div className="flex items-start justify-between mb-4">
                        <div className={`w-12 h-12 bg-gradient-to-br ${meta.color} rounded-xl flex items-center justify-center shadow-sm text-white`}>
                          {meta.icon}
                        </div>
                        <div className="flex items-center gap-2">
                          <StatusBadge status={bot.status} />
                          <button onClick={e => handleDeleteBot(bot.id, e)}
                            className="opacity-0 group-hover:opacity-100 text-gray-300 hover:text-red-500 transition-all">
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                      <h3 className="font-semibold text-gray-900 text-lg mb-1 truncate">{bot.name}</h3>
                      <span className="text-xs text-gray-400 bg-gray-50 px-2 py-0.5 rounded-full mb-4 inline-block">
                        {meta.label}
                      </span>
                      <div className="grid grid-cols-2 gap-2 mt-3">
                        {[
                          { label: 'Conversations', value: bot.conversations.toLocaleString(), c: 'text-blue-600' },
                          { label: 'Accuracy', value: `${bot.accuracy}%`, c: 'text-green-600' },
                          { label: 'Response', value: `${bot.response_time}s`, c: 'text-yellow-600' },
                          { label: 'Success', value: `${bot.success_rate}%`, c: 'text-purple-600' },
                        ].map(m => (
                          <div key={m.label} className="bg-gray-50 rounded-lg p-2">
                            <p className="text-gray-400 text-xs">{m.label}</p>
                            <p className={`font-bold text-sm ${m.c}`}>{m.value}</p>
                          </div>
                        ))}
                      </div>
                      <div className="mt-4 pt-4 border-t border-gray-100">
                        <button className="w-full flex items-center justify-center gap-2 bg-blue-50 hover:bg-blue-100 text-blue-600 py-2 rounded-lg font-medium transition text-sm">
                          <Eye className="w-4 h-4" /> Open Dashboard
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Create Bot Modal */}
        {showNewBotModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-white rounded-2xl shadow-2xl p-6 w-full max-w-md mx-4">
              <div className="flex items-center justify-between mb-5">
                <h2 className="text-xl font-bold text-gray-900">Create New Chatbot</h2>
                <button onClick={() => setShowNewBotModal(false)}><X className="w-5 h-5 text-gray-400" /></button>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-600 mb-1">Bot Name</label>
                  <input type="text" placeholder="e.g. GIFT University Bot"
                    value={newBotName} onChange={e => setNewBotName(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleCreateBot()}
                    className="w-full border border-gray-300 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm" autoFocus />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-600 mb-2">Category</label>
                  <div className="grid grid-cols-2 gap-2">
                    {Object.entries(CATEGORY_META).map(([key, meta]) => (
                      <button key={key} onClick={() => setNewBotCategory(key)}
                        className={`flex items-center gap-2 px-3 py-2.5 rounded-lg border text-sm font-medium transition ${
                          newBotCategory === key
                            ? 'border-blue-500 bg-blue-50 text-blue-700'
                            : 'border-gray-200 hover:border-gray-300 text-gray-600'
                        }`}>
                        <span className={`w-7 h-7 rounded-lg bg-gradient-to-br ${meta.color} flex items-center justify-center text-white`}>
                          {meta.icon}
                        </span>
                        {meta.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <div className="flex gap-3 mt-5">
                <button onClick={() => setShowNewBotModal(false)}
                  className="flex-1 py-2.5 bg-gray-100 rounded-lg text-gray-700 font-medium hover:bg-gray-200 transition text-sm">
                  Cancel
                </button>
                <button onClick={handleCreateBot} disabled={isCreating || !newBotName.trim()}
                  className="flex-1 py-2.5 bg-blue-600 rounded-lg text-white font-medium hover:bg-blue-700 transition text-sm disabled:opacity-50">
                  {isCreating ? 'Creating...' : 'Create Chatbot'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  };

  // ─────────────────────────────────────────────
  // If no bot selected, show selector
  // ─────────────────────────────────────────────
  if (!selectedBot) return renderSelector();

  const meta = CATEGORY_META[selectedBot.category] ?? CATEGORY_META.general;

  // ─────────────────────────────────────────────
  // TAB: Overview
  // ─────────────────────────────────────────────
  const renderOverview = () => (
    <div className="space-y-6">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Total Conversations', value: selectedBot.conversations.toLocaleString(), icon: <MessageCircle className="w-5 h-5 text-white" />, color: 'from-blue-500 to-blue-600' },
          { label: 'Accuracy',            value: `${selectedBot.accuracy}%`,          icon: <CheckCircle className="w-5 h-5 text-white" />, color: 'from-green-500 to-green-600' },
          { label: 'Avg Response',        value: `${selectedBot.response_time}s`,     icon: <Zap className="w-5 h-5 text-white" />,         color: 'from-yellow-500 to-yellow-600' },
          { label: 'Success Rate',        value: `${selectedBot.success_rate}%`,      icon: <CheckCircle className="w-5 h-5 text-white" />, color: 'from-purple-500 to-purple-600' },
        ].map(s => (
          <div key={s.label} className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm hover:shadow-md transition">
            <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${s.color} flex items-center justify-center shadow mb-4`}>
              {s.icon}
            </div>
            <p className="text-2xl font-bold text-gray-900">{s.value}</p>
            <p className="text-sm text-gray-500 mt-1">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <p className="text-sm font-medium text-gray-500 mb-1">Documents Trained</p>
          <p className="text-3xl font-bold text-gray-900">{docs.filter(d => d.status === 'trained').length}</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <p className="text-sm font-medium text-gray-500 mb-1">FAQ Entries</p>
          <p className="text-3xl font-bold text-gray-900">{faqs.length}</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <p className="text-sm font-medium text-gray-500 mb-1">Integrations Active</p>
          <p className="text-3xl font-bold text-gray-900">{integrations.filter(i => i.status === 'connected').length}</p>
        </div>
      </div>

      {/* Recent conversations */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h3 className="font-semibold text-gray-900">Recent Conversations</h3>
          <button onClick={() => setActiveTab('conversations')} className="text-sm text-blue-600 hover:underline">View all</button>
        </div>
        {conversations.length === 0 ? (
          <p className="text-gray-400 text-sm text-center py-10">No conversations yet</p>
        ) : (
          <div className="divide-y divide-gray-50">
            {conversations.slice(0, 5).map(c => (
              <div key={c.id} className="px-6 py-3 flex items-center justify-between hover:bg-gray-50">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-full bg-gradient-to-br from-blue-400 to-indigo-500 flex items-center justify-center text-white text-sm font-semibold">
                    {c.customer_name?.charAt(0) ?? '?'}
                  </div>
                  <div>
                    <p className="font-medium text-gray-900 text-sm">{c.customer_name}</p>
                    <p className="text-xs text-gray-400">{c.topic}</p>
                  </div>
                </div>
                <StatusBadge status={c.status} />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );

  // ─────────────────────────────────────────────
  // TAB: Manage Bot
  // ─────────────────────────────────────────────
  const renderChatbots = () => (
    <div className="space-y-6">
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
        <h3 className="font-semibold text-gray-900 mb-5">Bot Configuration</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">Bot Name</label>
            <input value={editBot.name} onChange={e => setEditBot(p => ({ ...p, name: e.target.value }))}
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">Status</label>
            <select value={editBot.status} onChange={e => setEditBot(p => ({ ...p, status: e.target.value }))}
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
              <option value="training">Training</option>
            </select>
          </div>
        </div>
        <button onClick={handleSaveBot} disabled={savingBot}
          className="mt-4 flex items-center gap-2 bg-blue-600 text-white px-5 py-2 rounded-lg hover:bg-blue-700 transition font-medium text-sm disabled:opacity-50">
          {savingBot ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Edit3 className="w-4 h-4" />}
          {savingBot ? 'Saving...' : 'Save Changes'}
        </button>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
        <h3 className="font-semibold text-gray-900 mb-5">Performance Metrics</h3>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: 'Conversations', value: selectedBot.conversations.toLocaleString() },
            { label: 'Accuracy', value: `${selectedBot.accuracy}%` },
            { label: 'Response Time', value: `${selectedBot.response_time}s` },
            { label: 'Success Rate', value: `${selectedBot.success_rate}%` },
          ].map(m => (
            <div key={m.label} className="bg-gray-50 rounded-lg p-4 text-center">
              <p className="text-2xl font-bold text-gray-900">{m.value}</p>
              <p className="text-xs text-gray-400 mt-1">{m.label}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-red-50 rounded-xl border border-red-200 p-6">
        <h3 className="font-semibold text-red-700 mb-2">Danger Zone</h3>
        <p className="text-sm text-red-500 mb-4">Permanently delete this chatbot and all its data.</p>
        <button onClick={() => handleDeleteBot(selectedBot.id)}
          className="flex items-center gap-2 bg-red-600 text-white px-5 py-2 rounded-lg hover:bg-red-700 transition font-medium text-sm">
          <Trash2 className="w-4 h-4" /> Delete Chatbot
        </button>
      </div>
    </div>
  );

  // ─────────────────────────────────────────────
  // TAB: Conversations
  // ─────────────────────────────────────────────
  const renderConversations = () => {
    const filtered = conversations.filter(c =>
      (c.customer_name || '').toLowerCase().includes(convSearch.toLowerCase()) ||
      (c.topic || '').toLowerCase().includes(convSearch.toLowerCase())
    );
    return (
      <div className="space-y-6">
        {selectedConv ? (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-3">
              <button onClick={() => setSelectedConv(null)} className="text-gray-400 hover:text-gray-700">
                <ChevronLeft className="w-5 h-5" />
              </button>
              <div>
                <p className="font-semibold text-gray-900">{selectedConv.customer_name}</p>
                <p className="text-xs text-gray-400">{selectedConv.topic}</p>
              </div>
              <div className="ml-auto"><StatusBadge status={selectedConv.status} /></div>
            </div>
            <div className="p-6 space-y-3 min-h-[200px]">
              {convMessages.length === 0 ? (
                <p className="text-center text-gray-400 text-sm py-8">No messages recorded</p>
              ) : convMessages.map(m => (
                <div key={m.id} className={`flex ${m.role === 'bot' ? 'justify-start' : 'justify-end'}`}>
                  <div className={`px-4 py-2 rounded-xl text-sm max-w-[70%] ${
                    m.role === 'bot' ? 'bg-gray-100 text-gray-800' : 'bg-blue-600 text-white'
                  }`}>{m.content}</div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between gap-4">
              <h3 className="font-semibold text-gray-900">All Conversations ({conversations.length})</h3>
              <div className="flex items-center gap-3">
                <button
                  onClick={handleAnalyzeBot}
                  disabled={analysisLoading || conversations.length === 0}
                  className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition font-medium text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {analysisLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Lightbulb className="w-4 h-4" />}
                  {analysisLoading ? 'Analyzing...' : 'AI Analysis'}
                </button>
                <div className="relative">
                  <Search className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
                  <input placeholder="Search..." value={convSearch} onChange={e => setConvSearch(e.target.value)}
                    className="pl-9 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
              </div>
            </div>
            {filtered.length === 0 ? (
              <p className="text-center text-gray-400 py-12 text-sm">No conversations yet</p>
            ) : (
              <div className="divide-y divide-gray-50">
                {filtered.map(c => (
                  <div key={c.id} className="px-6 py-4 hover:bg-gray-50 flex items-center justify-between group">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-400 to-indigo-500 flex items-center justify-center text-white font-semibold">
                        {c.customer_name?.charAt(0) ?? '?'}
                      </div>
                      <div>
                        <p className="font-medium text-gray-900 text-sm">{c.customer_name}</p>
                        <p className="text-xs text-gray-400">{c.topic}</p>
                        <p className="text-xs text-gray-300 mt-0.5">{new Date(c.started_at).toLocaleDateString()}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      {c.satisfaction && (
                        <span className="text-xs text-yellow-500">{'★'.repeat(c.satisfaction)}{'☆'.repeat(5 - c.satisfaction)}</span>
                      )}
                      <StatusBadge status={c.status} />
                      <button onClick={() => handleViewConversation(c)}
                        className="text-gray-400 hover:text-blue-600 transition opacity-0 group-hover:opacity-100">
                        <Eye className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  // ─────────────────────────────────────────────
  // TAB: Knowledge Base
  // ─────────────────────────────────────────────
  const renderKnowledge = () => {
    // All categories support Pinecone vector indexing
    const isUniversityBot = true;
    const isRestaurant = selectedBot?.category === 'restaurant';
    const isFaculty    = selectedBot?.category === 'faculty';
    const isFyp        = selectedBot?.category === 'fyp';
    const cat          = selectedBot?.category ?? 'general';

    // Helper: detect whether a job came from a website scrape or a PDF upload
    const isWebScrapeJob = (job: PineconeJob) =>
      job.pipeline?.includes('scrape') || job.method === 'crawlee';

    // Step bar labels — 5 steps, differ by category AND by PDF-vs-website source
    const getStepLabels = (job: PineconeJob): string[] => {
      const isWeb = isWebScrapeJob(job);
      if (isRestaurant) {
        return isWeb
          ? ['Queue', 'Scrape', 'Menu Items', 'Embed', 'Done']   // website → no GPT-4o
          : ['Upload', 'GPT-4o', 'Build Docs', 'Embed', 'Done']; // PDF    → GPT-4o vision
      }
      if (isFaculty) {
        return isWeb
          ? ['Queue', 'Scrape', 'Profiles', 'Embed', 'Done']
          : ['Upload', 'Text', 'Photos', 'Embed', 'Done'];
      }
      if (isFyp) {
        return isWeb
          ? ['Queue', 'Scrape', 'Projects', 'Embed', 'Done']
          : ['Upload', 'Extract', 'Chunk', 'Embed', 'Done'];
      }
      // university / general
      return isWeb
        ? ['Queue', 'Scrape', 'Pages', 'Embed', 'Done']
        : ['Upload', 'Extract', 'Chunk', 'Embed', 'Done'];
    };

    // Status badge text — shown above the bar, differ by category AND source
    const getPineconeStepLabel = (job: PineconeJob): Record<string, string> => {
      const isWeb = isWebScrapeJob(job);
      if (isRestaurant && isWeb) return {
        uploading:  '📤 Queued — waiting to start…',
        extracting: '🕷️ Crawlee scraping the menu site…',
        chunking:   '🍕 Parsing & indexing menu items…',
        embedding:  '📄 Indexing page content into Pinecone…',
        parsing:    '🔍 Parsing scraped JSON…',
        done:       '✅ Menu site scraped & indexed!',
        error:      '❌ Scrape failed',
      };
      if (isRestaurant && !isWeb) return {
        uploading:  '📤 Uploading PDF…',
        extracting: '🤖 GPT-4o reading menu pages…',
        chunking:   '🍕 Building menu item documents…',
        embedding:  '🧠 Embedding items into Pinecone…',
        parsing:    '🔍 Parsing extracted data…',
        done:       '✅ Menu PDF indexed!',
        error:      '❌ Ingest failed',
      };
      if (isFaculty && isWeb) return {
        uploading:  '📤 Queued — waiting to start…',
        extracting: '🕷️ Crawlee scraping faculty pages…',
        chunking:   '👤 Parsing & indexing faculty profiles…',
        embedding:  '📄 Indexing page content into Pinecone…',
        parsing:    '🔍 Parsing scraped JSON…',
        done:       '✅ Faculty site scraped & indexed!',
        error:      '❌ Scrape failed',
      };
      if (isFaculty && !isWeb) return {
        uploading:  '📤 Uploading PDF…',
        extracting: '🤖 GPT-4o extracting faculty text…',
        chunking:   '📸 GPT-4o identifying faculty photos…',
        embedding:  '🧠 Embedding profiles into Pinecone…',
        parsing:    '🔍 Parsing extracted data…',
        done:       '✅ Faculty directory indexed!',
        error:      '❌ Ingest failed',
      };
      if (isFyp && isWeb) return {
        uploading:  '📤 Queued — waiting to start…',
        extracting: '🕷️ Crawlee scraping FYP pages…',
        chunking:   '🎓 Parsing & indexing FYP projects…',
        embedding:  '🧠 Embedding into Pinecone…',
        parsing:    '🔍 Parsing scraped JSON…',
        done:       '✅ FYP site scraped & indexed!',
        error:      '❌ Scrape failed',
      };
      if (isFyp && !isWeb) return {
        uploading:  '📤 Uploading PDF…',
        extracting: '📖 Extracting FYP content…',
        chunking:   '✂️ Chunking project text…',
        embedding:  '🧠 Embedding into Pinecone…',
        parsing:    '🔍 Parsing extracted data…',
        done:       '✅ FYP documents indexed!',
        error:      '❌ Ingest failed',
      };
      // university / general — web
      if (isWeb) return {
        uploading:  '📤 Queued — waiting to start…',
        extracting: '🕷️ Crawlee scraping the site…',
        chunking:   '📄 Parsing & indexing pages…',
        embedding:  '🧠 Embedding content into Pinecone…',
        parsing:    '🔍 Parsing scraped JSON…',
        done:       '✅ Site scraped & indexed!',
        error:      '❌ Scrape failed',
      };
      // university / general — PDF
      return {
        uploading:  '📤 Uploading PDF…',
        extracting: '📖 Extracting text from PDF…',
        chunking:   '✂️ Chunking document text…',
        embedding:  '🧠 Embedding into Pinecone…',
        parsing:    '🔍 Parsing extracted data…',
        done:       '✅ Document indexed!',
        error:      '❌ Ingest failed',
      };
    };

    const activePineconeJobs = Object.values(pineconeJobs).filter(
      j => j.status !== 'done' && j.status !== 'error'
    );

    return (
    <div className="space-y-6">

      {/* ── Pinecone live progress panel ── */}
      {activePineconeJobs.length > 0 && (
        <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-5 space-y-4">
          <div className="flex items-center gap-2 text-indigo-800 font-semibold text-sm">
            <Database className="w-4 h-4" />
            Pinecone Vector Index — Building Embeddings
          </div>
          {activePineconeJobs.map(job => (
            <div key={job.jobId} className="space-y-2">
              <div className="flex items-center justify-between text-xs text-indigo-700">
                <span className="font-medium truncate max-w-xs">{job.filename}</span>
                <span className="text-indigo-500 font-mono">{job.indexName}</span>
              </div>
              <p className="text-xs text-indigo-600">{getPineconeStepLabel(job)[job.status] ?? job.status}</p>
              {/* Main progress bar */}
              <div className="w-full bg-indigo-100 rounded-full h-2.5 overflow-hidden">
                <div
                  className={`h-2.5 rounded-full transition-all duration-500 ${
                    job.status === 'embedding'
                      ? 'bg-gradient-to-r from-indigo-400 to-purple-500'
                      : 'bg-indigo-300'
                  }`}
                  style={{ width: job.status === 'done' ? '100%' : job.status === 'embedding' ? `${job.pct}%` : '15%' }}
                />
              </div>
              {/* Step indicators */}
              <div className="flex gap-1 mt-1">
                {(['uploading', 'extracting', 'chunking', 'embedding', 'done'] as const).map((step, idx) => {
                  const stepOrder = ['uploading', 'extracting', 'chunking', 'embedding', 'done'];
                  const stepLabels = getStepLabels(job);
                  const currentIdx = stepOrder.indexOf(job.status);
                  const isComplete = idx < currentIdx;
                  const isCurrent  = idx === currentIdx;
                  return (
                    <div key={step} className="flex-1 text-center">
                      <div className={`h-1 rounded-full mb-1 ${
                        isComplete ? 'bg-indigo-500' : isCurrent ? 'bg-purple-400 animate-pulse' : 'bg-indigo-100'
                      }`} />
                      <span className={`text-[10px] ${
                        isComplete || isCurrent ? 'text-indigo-600 font-medium' : 'text-indigo-300'
                      }`}>
                        {stepLabels[idx]}
                      </span>
                    </div>
                  );
                })}
              </div>
              {job.status === 'embedding' && job.total > 0 && (
                <p className="text-xs text-indigo-500">
                  {job.done} / {job.total} documents embedded ({job.pct}%)
                  {!isWebScrapeJob(job) && job.method !== 'unknown' && <span className="ml-2 text-indigo-400">via {job.method}</span>}
                </p>
              )}
              {(job as any).stage_detail && job.status !== 'done' && job.status !== 'error' && (
                <p className="text-xs text-indigo-400 italic">{(job as any).stage_detail}</p>
              )}
            </div>
          ))}
        </div>
      )}

      {/* ── Completed Pinecone indexes summary ── */}
      {isUniversityBot && Object.values(pineconeJobs).some(j => j.status === 'done') && (
        <div className="bg-green-50 border border-green-200 rounded-xl px-5 py-3 flex items-center gap-3 text-sm text-green-800">
          <CheckCircle className="w-4 h-4 text-green-600 flex-shrink-0" />
          <span>
            Pinecone index active —{' '}
            {isRestaurant
              ? `${Object.values(pineconeJobs).filter(j => j.status === 'done').reduce((a, j) => a + ((j as any).items_count || j.total), 0)} menu items indexed.`
              : isFaculty
              ? `${Object.values(pineconeJobs).filter(j => j.status === 'done').reduce((a, j) => a + ((j as any).items_count || j.total), 0)} faculty profiles indexed.`
              : `${Object.values(pineconeJobs).filter(j => j.status === 'done').reduce((a, j) => a + j.total, 0)} chunks embedded.`
            }{' '}
            {isRestaurant
              ? 'RestaurantBot will use this index for menu queries.'
              : isFaculty
              ? 'FacultyBot will use this index for staff directory queries.'
              : 'UniBot will use this index for RAG answers.'}
          </span>
        </div>
      )}

      {/* ── Upload area ── */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-gray-900">Training Documents ({docs.length})</h3>
            {isUniversityBot && (
              <p className="text-xs text-indigo-600 mt-0.5 flex items-center gap-1">
                <Database className="w-3 h-3" />
                {isFaculty
                  ? 'PDF uploads auto-extract faculty profiles + photos into Pinecone'
                  : isRestaurant
                  ? 'PDF uploads auto-extract menu items + images into Pinecone'
                  : 'PDF uploads auto-index into Pinecone'}
              </p>
            )}
            {/* ── Storage usage bar (free/standard only) ── */}
            {planLimits.maxStorageMB !== Infinity && (() => {
              const parseSizeMB = (label?: string): number => {
                if (!label) return 0;
                const m = label.match(/([\d.]+)\s*(MB|KB|GB)/i);
                if (!m) return 0;
                const val = parseFloat(m[1]);
                const unit = m[2].toUpperCase();
                if (unit === 'KB') return val / 1024;
                if (unit === 'GB') return val * 1024;
                return val;
              };
              const usedMB = docs.reduce((sum, d) => sum + parseSizeMB(d.size_label), 0);
              const pct = Math.min(100, (usedMB / planLimits.maxStorageMB) * 100);
              const isNearLimit = pct >= 80;
              return (
                <div className="mt-2 w-48">
                  <div className="flex justify-between text-[10px] text-gray-400 mb-0.5">
                    <span>{usedMB.toFixed(1)} MB used</span>
                    <span>{planLimits.maxStorageMB} MB limit</span>
                  </div>
                  <div className="w-full bg-gray-100 rounded-full h-1.5 overflow-hidden">
                    <div className={`h-1.5 rounded-full transition-all duration-500 ${isNearLimit ? 'bg-red-400' : 'bg-blue-400'}`}
                      style={{ width: `${pct}%` }} />
                  </div>
                  {isNearLimit && (
                    <p className="text-[10px] text-red-500 mt-0.5">
                      {pct >= 100 ? 'Storage full — upgrade to Premium for unlimited storage' : 'Approaching storage limit'}
                    </p>
                  )}
                </div>
              );
            })()}
          </div>
          <button onClick={() => fileInputRef.current?.click()}
            disabled={uploadingDoc}
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition disabled:opacity-50">
            {uploadingDoc ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
            {uploadingDoc ? 'Uploading...' : 'Upload File'}
          </button>
        </div>
        <input ref={fileInputRef} type="file"
          accept={isUniversityBot ? '.pdf' : '.pdf,.docx,.txt'}
          className="hidden"
          onChange={e => { if (e.target.files?.[0]) handleUploadFile(e.target.files[0]); e.target.value = ''; }} />

        {docs.length === 0 && !uploadingDoc ? (
          <div
            className="m-6 border-2 border-dashed border-gray-200 rounded-xl p-12 text-center cursor-pointer hover:border-blue-300 hover:bg-blue-50 transition"
            onClick={() => fileInputRef.current?.click()}
            onDragOver={e => e.preventDefault()}
            onDrop={e => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) handleUploadFile(f); }}>
            <Database className="w-10 h-10 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500 font-medium">Drop files here or click to upload</p>
            <p className="text-xs text-gray-400 mt-1">
              {isUniversityBot
                ? 'PDF only • Max 20 MB • Auto-indexed into Pinecone for UniBot RAG'
                : 'Supports PDF, DOCX, TXT • Max 20 MB'}
            </p>
          </div>
        ) : (
          <div className="divide-y divide-gray-50">
            {docs.map(doc => {
              const isThisTraining = trainingDocId === doc.id && doc.status === 'training';
              const progress = isThisTraining ? trainingProgress : (doc.training_progress ?? 0);
              const pJob = pineconeJobs[doc.id];

              return (
                <div key={doc.id} className="px-6 py-4 hover:bg-gray-50">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      <div className="w-9 h-9 rounded-lg bg-gray-100 flex items-center justify-center flex-shrink-0">
                        {doc.type === 'website' ? <Globe className="w-4 h-4 text-blue-500" /> : <FileText className="w-4 h-4 text-gray-500" />}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="font-medium text-gray-900 text-sm truncate">{doc.name}</p>
                        <p className="text-xs text-gray-400">{doc.size_label} • {doc.upload_date}</p>
                        {(doc.status === 'training' || isThisTraining) && !pJob && (
                          <div className="mt-1.5 w-48">
                            <div className="w-full bg-gray-100 rounded-full h-1.5">
                              <div className="bg-yellow-400 h-1.5 rounded-full transition-all duration-300"
                                style={{ width: `${progress}%` }} />
                            </div>
                            <p className="text-xs text-gray-400 mt-0.5">{Math.round(progress)}% trained</p>
                          </div>
                        )}
                        {/* Pinecone / scrape mini-progress inline */}
                        {pJob && pJob.status !== 'done' && pJob.status !== 'error' && (
                          <div className="mt-1.5">
                            <div className="flex items-center gap-2">
                              <div className="w-36 bg-indigo-100 rounded-full h-1.5 overflow-hidden">
                                <div className="bg-indigo-500 h-1.5 rounded-full transition-all duration-500"
                                  style={{ width: `${pJob.pct > 0 ? pJob.pct : 15}%` }} />
                              </div>
                              <span className="text-xs text-indigo-500">
                                {pJob.pct > 0 ? `${pJob.pct}%` : pJob.status + '…'}
                              </span>
                            </div>
                            {pJob.stage_detail && (
                              <p className="text-[10px] text-gray-400 mt-0.5 truncate max-w-xs">{pJob.stage_detail}</p>
                            )}
                          </div>
                        )}
                        {/* Done badge */}
                        {pJob && pJob.status === 'done' && (
                          <p className="text-xs text-green-600 mt-1 flex items-center gap-1">
                            <CheckCircle className="w-3 h-3" /> {pJob.total} chunks in Pinecone
                          </p>
                        )}
                        {pJob && pJob.status === 'error' && (
                          <p className="text-xs text-red-500 mt-1">{pJob.errors[0]}</p>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-3 flex-shrink-0 ml-4">
                      {doc.accuracy != null && <span className="text-xs text-green-600 font-medium">{doc.accuracy}%</span>}
                      <StatusBadge status={doc.status} />
                      <button onClick={() => handleDeleteDoc(doc.id)} className="text-gray-300 hover:text-red-500 transition">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── Import from Website ── */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
        <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Globe className="w-4 h-4 text-blue-500" /> Import from Website
        </h3>
        <div className="flex gap-3">
          <div className="relative flex-1">
            <Globe className="w-4 h-4 text-gray-400 absolute left-3 top-3" />
            <input type="url" placeholder="https://yoursite.com/help-center"
              value={websiteUrl} onChange={e => setWebsiteUrl(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleScrape()}
              className="w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <button onClick={handleScrape} disabled={isScraping || !websiteUrl.trim()}
            className="flex items-center gap-2 bg-blue-600 text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-blue-700 transition disabled:opacity-50">
            {isScraping ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
            {isScraping ? 'Scraping...' : 'Scrape'}
          </button>
        </div>
        <p className="text-xs text-gray-400 mt-2">We'll crawl the page and extract text as training data.</p>
      </div>

      {/* FAQs */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h3 className="font-semibold text-gray-900">FAQ Entries ({faqs.length})</h3>
          <button onClick={() => setShowAddFaq(true)}
            className="flex items-center gap-2 bg-green-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-green-700 transition">
            <Plus className="w-4 h-4" /> Add FAQ
          </button>
        </div>
        {faqs.length === 0 ? (
          <p className="text-center text-gray-400 py-10 text-sm">No FAQs added yet</p>
        ) : (
          <div className="divide-y divide-gray-50">
            {faqs.map(faq => (
              <div key={faq.id} className="px-6 py-4 hover:bg-gray-50">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-gray-900 text-sm">{faq.question}</p>
                    <p className="text-xs text-gray-400 mt-1 line-clamp-2">{faq.answer}</p>
                    {faq.category && (
                      <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded mt-2 inline-block">
                        {faq.category}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <StatusBadge status={faq.status} />
                    <button onClick={() => handleDeleteFaq(faq.id)} className="text-gray-300 hover:text-red-500 transition">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Add FAQ modal */}
      {showAddFaq && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl shadow-2xl p-6 w-full max-w-lg mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-gray-900">Add FAQ</h3>
              <button onClick={() => setShowAddFaq(false)}><X className="w-5 h-5 text-gray-400" /></button>
            </div>
            <div className="space-y-3">
              <input placeholder="Question" value={newFaq.question}
                onChange={e => setNewFaq(p => ({ ...p, question: e.target.value }))}
                className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              <textarea placeholder="Answer" value={newFaq.answer}
                onChange={e => setNewFaq(p => ({ ...p, answer: e.target.value }))}
                rows={4} className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none" />
              <input placeholder="Category (e.g. Admission, Billing)" value={newFaq.category}
                onChange={e => setNewFaq(p => ({ ...p, category: e.target.value }))}
                className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div className="flex gap-3 mt-4">
              <button onClick={() => setShowAddFaq(false)}
                className="flex-1 py-2.5 bg-gray-100 rounded-lg text-gray-700 font-medium hover:bg-gray-200 transition text-sm">Cancel</button>
              <button onClick={handleAddFaq} disabled={!newFaq.question.trim() || !newFaq.answer.trim()}
                className="flex-1 py-2.5 bg-green-600 rounded-lg text-white font-medium hover:bg-green-700 transition text-sm disabled:opacity-50">Save FAQ</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
  };

  // ─────────────────────────────────────────────
  // TAB: Integrations
  // ─────────────────────────────────────────────
  const renderIntegrations = () => {
    const ALL = [
      { type: 'whatsapp', label: 'WhatsApp', desc: 'Link a number via QR code — no Meta verification needed', icon: <Smartphone className="w-5 h-5" /> },
      { type: 'website',  label: 'Website',  desc: 'Embed chat widget on your site', icon: <Globe className="w-5 h-5" /> },
    ];

    // Shared by both the "Bot Embed Code" card and the website-connect modal.
    const getEmbedInfo = () => {
      const port    = BOT_PORT_MAP[selectedBot.category] ?? 8001;
      const botUrl  = getBotEmbedUrl(selectedBot);
      const pos     = customization.position ?? 'bottom-right';
      const [vPos, hPos] = pos.includes('top') ? ['top:20px', ''] : ['bottom:20px', ''];
      const hStyle  = pos.includes('left') ? 'left:20px' : 'right:20px';
      const snippet = [
        `<!-- SmartChat · ${selectedBot.name} (${selectedBot.category}) -->`,
        `<iframe`,
        `  src="${botUrl}"`,
        `  style="position:fixed;${vPos};${hStyle};width:480px;height:500px;`,
        `         border:none;border-radius:16px;box-shadow:0 8px 40px rgba(0,0,0,0.18);z-index:9999"`,
        `  allow="microphone"`,
        `></iframe>`,
      ].join('\n');
      return { port, botUrl, snippet };
    };

    return (
      <div className="space-y-4">
        {ALL.map(intg => {
          const current = integrations.find(i => i.type === intg.type);
          const st = current?.status ?? 'disconnected';
          return (
            <div key={intg.type} className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 flex items-center justify-between hover:shadow-md transition">
              <div className="flex items-center gap-4">
                <div className="w-11 h-11 rounded-xl bg-gray-100 flex items-center justify-center text-gray-600">
                  {intg.icon}
                </div>
                <div>
                  <p className="font-semibold text-gray-900">{intg.label}</p>
                  <p className="text-sm text-gray-400">{intg.desc}</p>
                  {current?.connected_at && st === 'connected' && (
                    <p className="text-xs text-green-600 mt-0.5">Connected {new Date(current.connected_at).toLocaleDateString()}</p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-3">
                <StatusBadge status={st} />
                <button
                  onClick={() => {
                    if (intg.type === 'whatsapp') { setShowWhatsAppModal(true); return; }
                    if (intg.type === 'website' && st !== 'connected') { setShowWebsiteModal(true); return; }
                    handleToggleIntegration(intg.type);
                  }}
                  className={`px-4 py-1.5 rounded-lg text-sm font-medium transition ${
                    intg.type !== 'whatsapp' && st === 'connected'
                      ? 'bg-red-50 text-red-600 hover:bg-red-100'
                      : 'bg-blue-600 text-white hover:bg-blue-700'
                  }`}>
                  {intg.type === 'whatsapp'
                    ? (st === 'connected' ? 'Manage' : 'Connect')
                    : (st === 'connected' ? 'Disconnect' : 'Connect')}
                </button>
              </div>
            </div>
          );
        })}

        {/* Embed snippet */}
        {(() => {
          const { port, botUrl, snippet } = getEmbedInfo();
          return (
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
              <h3 className="font-semibold text-gray-900 mb-1 flex items-center gap-2">
                <Code className="w-4 h-4" /> Bot Embed Code
              </h3>
              <p className="text-xs text-gray-400 mb-3">
                Paste this into any webpage to embed your {selectedBot.category} bot.
                Make sure <code className="bg-gray-100 px-1 rounded">uvicorn main:app --port {port}</code> is running in <code className="bg-gray-100 px-1 rounded">Models/{selectedBot.category}Bot/</code> — the bot ID in the URL tells that server which bot ({selectedBot.name}) to load.
              </p>
              <div className="bg-gray-900 rounded-lg p-4 font-mono text-xs text-green-400 overflow-x-auto whitespace-pre">
                {snippet}
              </div>
              <div className="flex items-center gap-4 mt-3">
                <button onClick={() => { navigator.clipboard.writeText(snippet); showToast('Copied!'); }}
                  className="flex items-center gap-2 text-sm text-gray-500 hover:text-blue-600 transition">
                  <Copy className="w-4 h-4" /> Copy code
                </button>
                <a href={botUrl} target="_blank" rel="noreferrer"
                  className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-700 transition">
                  <Eye className="w-4 h-4" /> Open bot (port {port})
                </a>
              </div>
            </div>
          );
        })()}

        {/* WhatsApp QR-connect modal */}
        {showWhatsAppModal && (
          <div className="fixed inset-0 bg-black/40 z-50 overflow-y-auto">
            <div className="min-h-full flex items-center justify-center p-4">
            <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 relative my-8 max-h-[90vh] overflow-y-auto">
              <button
                onClick={() => { setShowWhatsAppModal(false); refreshIntegrations(); }}
                className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
              <h3 className="font-semibold text-gray-900 mb-1 flex items-center gap-2">
                <Smartphone className="w-4 h-4" /> Connect WhatsApp
              </h3>
              <p className="text-xs text-gray-400 mb-4">
                Scan the QR code with the WhatsApp account you want {selectedBot.name} to reply from.
              </p>
              <WhatsAppConnect botId={selectedBot.id} apiBaseUrl={API_BASE} />
            </div>
            </div>
          </div>
        )}

        {/* Website connect modal */}
        {showWebsiteModal && (() => {
          const { botUrl, snippet } = getEmbedInfo();
          return (
            <div className="fixed inset-0 bg-black/40 z-50 overflow-y-auto">
              <div className="min-h-full flex items-center justify-center p-4">
              <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full p-6 relative my-8 max-h-[90vh] overflow-y-auto">
                <button
                  onClick={() => setShowWebsiteModal(false)}
                  className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
                >
                  <X className="w-5 h-5" />
                </button>
                <h3 className="font-semibold text-gray-900 mb-1 flex items-center gap-2">
                  <Globe className="w-4 h-4" /> Connect Website
                </h3>
                <p className="text-xs text-gray-400 mb-4">
                  Here's a live preview of {selectedBot.name} — this is exactly what your visitors will see.
                </p>

                <div className="rounded-lg border border-gray-200 bg-gray-50 h-[640px] max-h-[70vh] mb-4 overflow-hidden flex items-center justify-center">
                  <iframe
                    src={botUrl}
                    title="Bot preview"
                    className="w-full h-full"
                    style={{ border: 'none' }}
                    allow="microphone"
                  />
                </div>

                <p className="text-sm font-medium text-gray-700 mb-2">
                  Enter this iframe in your site to connect
                </p>
                <div className="bg-gray-900 rounded-lg p-4 font-mono text-xs text-green-400 overflow-x-auto whitespace-pre mb-3">
                  {snippet}
                </div>
                <button
                  onClick={() => { navigator.clipboard.writeText(snippet); showToast('Copied!'); }}
                  className="flex items-center gap-2 text-sm text-gray-500 hover:text-blue-600 transition mb-5"
                >
                  <Copy className="w-4 h-4" /> Copy code
                </button>

                <button
                  onClick={async () => {
                    await handleToggleIntegration('website');
                    setShowWebsiteModal(false);
                  }}
                  className="w-full flex items-center justify-center gap-2 bg-blue-600 text-white rounded-lg py-2.5 font-medium hover:bg-blue-700 transition"
                >
                  <Check className="w-4 h-4" /> Yes, I added this to my website
                </button>
              </div>
              </div>
            </div>
          );
        })()}
      </div>
    );
  };

  // ─────────────────────────────────────────────
  // TAB: Customization
  // ─────────────────────────────────────────────
  const renderCustomization = () => (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 lg:h-[calc(100vh-180px)]">
      {/* Controls */}
      <div className="space-y-4 overflow-y-auto pr-1">

        {/* ── Plan upgrade banner for free/standard ── */}
        {!planLimits.canCustomizeLogo && (
          <div className="bg-gradient-to-r from-yellow-50 to-amber-50 border border-yellow-200 rounded-xl p-4 flex items-start gap-3">
            <span className="text-2xl">⭐</span>
            <div>
              <p className="font-semibold text-yellow-800 text-sm">Unlock Full Customization with Premium</p>
              <p className="text-xs text-yellow-700 mt-0.5">
                Your <span className="font-medium capitalize">{userPlan}</span> plan includes fixed branding (SmartChat logo & header). Upgrade to Premium to use your own logo, custom header title, and support email.
              </p>
            </div>
          </div>
        )}

        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
          <h3 className="font-semibold text-gray-900 mb-5">Appearance Settings</h3>
          <div className="space-y-4">

            {/* Logo upload — locked for free/standard plans */}
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-2 flex items-center gap-2">
                Bot Logo
                {!planLimits.canCustomizeLogo && (
                  <span className="inline-flex items-center gap-1 text-xs text-yellow-600 bg-yellow-50 border border-yellow-200 px-2 py-0.5 rounded-full">
                    🔒 Premium only
                  </span>
                )}
              </label>
              {planLimits.canCustomizeLogo ? (
                // ── Premium: full logo upload ──
                <div className="flex items-center gap-4">
                  {customization.logo_url ? (
                    <img src={customization.logo_url} alt="logo"
                      className="w-14 h-14 rounded-xl object-cover border border-gray-200 shadow-sm" />
                  ) : (
                    <div className="w-14 h-14 rounded-xl bg-gray-100 border border-dashed border-gray-300 flex items-center justify-center">
                      <ImageIcon className="w-5 h-5 text-gray-400" />
                    </div>
                  )}
                  <div>
                    <button onClick={() => logoInputRef.current?.click()} disabled={uploadingLogo}
                      className="flex items-center gap-2 text-sm bg-gray-100 hover:bg-gray-200 text-gray-700 px-3 py-2 rounded-lg transition disabled:opacity-50">
                      {uploadingLogo ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                      {uploadingLogo ? 'Uploading...' : 'Upload Logo'}
                    </button>
                    <p className="text-xs text-gray-400 mt-1">PNG, JPG, SVG • Max 5 MB</p>
                    {customization.logo_url && customization.logo_url !== FIXED_LOGO_URL && (
                      <button onClick={() => setCustomization(p => ({ ...p, logo_url: null }))}
                        className="text-xs text-red-500 hover:underline mt-0.5">Remove</button>
                    )}
                  </div>
                </div>
              ) : (
                // ── Free/Standard: fixed SmartChat logo, locked ──
                <div className="flex items-center gap-4">
                  <div className="relative">
                    <img src={FIXED_LOGO_URL} alt="SmartChat logo"
                      className="w-14 h-14 rounded-xl object-cover border border-gray-200 shadow-sm opacity-80" />
                    <div className="absolute -top-1 -right-1 w-5 h-5 bg-yellow-400 rounded-full flex items-center justify-center text-[10px]">🔒</div>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-700">SmartChat Logo</p>
                    <p className="text-xs text-gray-400 mt-0.5">Fixed for free & standard plans</p>
                    <button
                      onClick={() => setError('Logo customization is available on the Premium plan. Please upgrade to use your own logo.')}
                      className="mt-1.5 flex items-center gap-1.5 text-xs text-yellow-600 bg-yellow-50 border border-yellow-200 px-2.5 py-1 rounded-lg hover:bg-yellow-100 transition">
                      ⭐ Upgrade to Premium to unlock
                    </button>
                  </div>
                </div>
              )}
              <input ref={logoInputRef} type="file" accept="image/*" className="hidden"
                onChange={e => { if (e.target.files?.[0]) handleLogoUpload(e.target.files[0]); e.target.value = ''; }} />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1 flex items-center gap-2">
                Header Title
                {!planLimits.canCustomizeHeader && (
                  <span className="inline-flex items-center gap-1 text-xs text-yellow-600 bg-yellow-50 border border-yellow-200 px-2 py-0.5 rounded-full">
                    🔒 Premium only
                  </span>
                )}
              </label>
              {planLimits.canCustomizeHeader ? (
                <input value={customization.header_title}
                  onChange={e => setCustomization(p => ({ ...p, header_title: e.target.value }))}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              ) : (
                <div className="space-y-2">
                  <div className="relative">
                    <input value={planLimits.fixedHeaderTitle} readOnly
                      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-gray-50 text-gray-500 cursor-not-allowed" />
                    <span className="absolute right-3 top-2.5 text-gray-400 text-xs">🔒</span>
                  </div>
                  <div className="relative">
                    <input value={planLimits.fixedHeaderEmail} readOnly
                      placeholder="Support email"
                      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-gray-50 text-gray-500 cursor-not-allowed" />
                    <span className="absolute right-3 top-2.5 text-gray-400 text-xs">🔒</span>
                  </div>
                  <p className="text-xs text-gray-400">Header title and support email are fixed for free & standard plans.</p>
                </div>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">Welcome Message</label>
              <textarea value={customization.welcome_message}
                onChange={e => setCustomization(p => ({ ...p, welcome_message: e.target.value }))}
                rows={2} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none" />
            </div>

            <div className="grid grid-cols-2 gap-3">
              {[
                { key: 'theme_color', label: 'Theme Color' },
                { key: 'button_color', label: 'Button Color' },
                { key: 'background_color', label: 'Background' },
                { key: 'text_color', label: 'Text Color' },
              ].map(c => (
                <div key={c.key}>
                  <label className="block text-sm font-medium text-gray-600 mb-1">{c.label}</label>
                  <div className="flex items-center gap-2">
                    <input type="color" value={(customization as any)[c.key]}
                      onChange={e => setCustomization(p => ({ ...p, [c.key]: e.target.value }))}
                      className="w-9 h-9 rounded border border-gray-200 cursor-pointer p-0.5" />
                    <input value={(customization as any)[c.key]}
                      onChange={e => setCustomization(p => ({ ...p, [c.key]: e.target.value }))}
                      className="flex-1 border border-gray-200 rounded-lg px-2 py-1.5 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-blue-500" />
                  </div>
                </div>
              ))}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">Theme</label>
              <div className="flex gap-2">
                {['light', 'dark'].map(t => (
                  <button key={t} onClick={() => setCustomization(p => ({ ...p, theme: t }))}
                    className={`flex-1 py-2 rounded-lg text-sm font-medium border transition ${
                      customization.theme === t ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'
                    }`}>
                    {t.charAt(0).toUpperCase() + t.slice(1)}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">Button Shape</label>
              <div className="flex gap-2">
                {['rounded', 'square', 'pill'].map(s => (
                  <button key={s} onClick={() => setCustomization(p => ({ ...p, button_shape: s }))}
                    className={`flex-1 py-2 rounded-lg text-sm font-medium border transition ${
                      customization.button_shape === s ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'
                    }`}>
                    {s.charAt(0).toUpperCase() + s.slice(1)}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">Widget Position</label>
              <select value={customization.position}
                onChange={e => setCustomization(p => ({ ...p, position: e.target.value }))}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                <option value="bottom-right">Bottom Right</option>
                <option value="bottom-left">Bottom Left</option>
                <option value="top-right">Top Right</option>
                <option value="top-left">Top Left</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">
                Font Size <span className="text-gray-400">({customization.font_size}px)</span>
              </label>
              <input type="range" min={12} max={18}
                value={customization.font_size}
                onChange={e => setCustomization(p => ({ ...p, font_size: Number(e.target.value) }))}
                className="w-full accent-blue-600" />
            </div>
          </div>

          <button onClick={handleSaveCustomization} disabled={savingCust}
            className="mt-5 w-full flex items-center justify-center gap-2 bg-blue-600 text-white py-2.5 rounded-lg font-medium hover:bg-blue-700 transition text-sm disabled:opacity-50">
            {savingCust ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
            {savingCust ? 'Saving...' : 'Save Customization'}
          </button>
        </div>
      </div>

      {/* Live preview */}
      <div className="flex flex-col h-full">
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 flex flex-col flex-1 min-h-0">
        <div className="flex items-center justify-between mb-1">
          <h3 className="font-semibold text-gray-900">Live Preview</h3>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setPreviewRefreshKey(k => k + 1)}
              className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-blue-600 transition"
              title="Reload preview"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Refresh
            </button>
            <a href={getBotEmbedUrl(selectedBot)} target="_blank" rel="noreferrer"
              className="flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-700 transition">
              <Eye className="w-3.5 h-3.5" /> Open
            </a>
          </div>
        </div>
        <p className="text-xs text-gray-400 mb-4">
          This is the real, live {selectedBot.name} chatbot. Save your changes below, then Refresh to see them reflected here.
        </p>
        {/* Real bot iframe */}
        <div className={`relative rounded-xl flex-1 min-h-0 overflow-hidden border border-gray-200 ${customization.theme === 'dark' ? 'bg-gray-800' : 'bg-gray-100'}`}>
          <iframe
            key={previewRefreshKey}
            src={getBotEmbedUrl(selectedBot)}
            title="Live chatbot preview"
            className="w-full h-full"
            style={{ border: 'none', minHeight: 520 }}
            allow="microphone"
          />
        </div>
        </div>
      </div>
    </div>
  );

  // ─────────────────────────────────────────────
  // MAIN LAYOUT
  // ─────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Header />

      {/* Toast */}
      {toast && (
        <div className="fixed top-4 right-4 z-50 bg-gray-900 text-white px-4 py-2 rounded-lg shadow-lg flex items-center gap-2 text-sm">
          <Check className="w-4 h-4 text-green-400" /> {toast}
        </div>
      )}

      {/* Error banner */}
      {error && (
        <div className="flex items-center gap-2 bg-red-50 border-b border-red-200 text-red-700 px-6 py-3 text-sm">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span className="flex-1">{error}</span>
          <button onClick={() => setError(null)}><X className="w-4 h-4" /></button>
        </div>
      )}

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside className="w-56 bg-white border-r border-gray-200 flex flex-col py-4 px-3 flex-shrink-0">
          <button onClick={() => setSelectedBot(null)}
            className="flex items-center gap-2 text-sm text-gray-500 hover:text-blue-600 transition mb-4 px-2 py-1.5 rounded-lg hover:bg-blue-50">
            <ChevronLeft className="w-4 h-4" /> All Chatbots
          </button>

          <div className="px-2 mb-5 pb-4 border-b border-gray-100">
            <div className="flex items-center gap-2">
              <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${meta.color} flex items-center justify-center flex-shrink-0 text-white`}>
                {meta.icon}
              </div>
              <div className="min-w-0">
                <p className="font-semibold text-gray-900 text-sm truncate">{selectedBot.name}</p>
                <StatusBadge status={selectedBot.status} />
              </div>
            </div>
            <p className="text-xs text-gray-400 mt-1 ml-10">{meta.label}</p>
          </div>

          <nav className="space-y-1 flex-1">
            {NAV_ITEMS.map(item => (
              <button key={item.tab} onClick={() => setActiveTab(item.tab)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  activeTab === item.tab ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`}>
                <span className={activeTab === item.tab ? 'text-blue-600' : 'text-gray-400'}>{item.icon}</span>
                {item.label}
              </button>
            ))}
          </nav>

          <button onClick={handleLogout}
            className="flex items-center gap-2 text-sm text-gray-400 hover:text-red-600 transition px-3 py-2 rounded-lg hover:bg-red-50 mt-2">
            <LogOut className="w-4 h-4" /> Logout
          </button>
        </aside>

        {/* Main */}
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-5xl mx-auto px-6 py-8">
            <div className="mb-6">
              <h2 className="text-2xl font-bold text-gray-900">
                {NAV_ITEMS.find(n => n.tab === activeTab)?.label}
              </h2>
              <p className="text-gray-400 text-sm mt-0.5">{selectedBot.name}</p>
            </div>

            {botLoading ? (
              <div className="flex flex-col items-center py-24 gap-3 text-gray-400">
                <RefreshCw className="w-8 h-8 animate-spin" />
                <p>Loading data...</p>
              </div>
            ) : (
              <>
                {activeTab === 'overview'      && renderOverview()}
                {activeTab === 'chatbots'      && renderChatbots()}
                {activeTab === 'conversations' && renderConversations()}
                {activeTab === 'knowledge'     && renderKnowledge()}
                {activeTab === 'integrations'  && renderIntegrations()}
                {activeTab === 'customization' && renderCustomization()}
              </>
            )}
          </div>
        </main>
      </div>

      {/* Analysis Side Panel */}
      <AnalysisSidePanel
        isOpen={showAnalysisPanel}
        onClose={() => setShowAnalysisPanel(false)}
        data={analysisData}
        isLoading={analysisLoading}
        error={analysisError}
        onAskAI={handleAskAI}
      />
    </div>
  );
}
