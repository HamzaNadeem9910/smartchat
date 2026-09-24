import { useState, useEffect, type ReactNode } from 'react';
import { X, MessageSquare, AlertCircle, Lightbulb, HelpCircle, AlertTriangle, Sparkles, Send } from 'lucide-react';

interface AnalysisData {
  chatbot_name: string;
  analysis_period_days: number;
  generated_at: string;
  /** true when there was no data in the requested window and the backend fell back to full history */
  used_all_time?: boolean;
  overview: {
    total_conversations: number;
    resolved?: number;
    escalated?: number;
  };
  executive_summary: string;
  top_topics?: Array<{
    topic: string;
    frequency: number;
    description: string;
  }>;
  faq?: Array<{
    question: string;
    answer: string;
  }>;
  complaints?: Array<{
    issue: string;
    frequency: string;
    impact: string;
  }>;
  unanswered_questions?: Array<{
    question: string;
    frequency: string;
    importance: string;
  }>;
  ai_recommendations?: Array<{
    recommendation: string;
    priority: string;
    expected_impact: string;
  }>;
}

interface AskAIMessage {
  role: 'user' | 'assistant';
  content: string;
}

interface AnalysisSidePanelProps {
  isOpen: boolean;
  onClose: () => void;
  data: AnalysisData | null;
  isLoading: boolean;
  error: string | null;
  /** "Ask AI" — sends a question (plus prior turns) and resolves with the assistant's reply. */
  onAskAI?: (question: string, history: AskAIMessage[]) => Promise<string>;
}

export default function AnalysisSidePanel({
  isOpen,
  onClose,
  data,
  isLoading,
  error,
  onAskAI,
}: AnalysisSidePanelProps) {
  const [askMessages, setAskMessages] = useState<AskAIMessage[]>([]);
  const [askInput, setAskInput] = useState('');
  const [askLoading, setAskLoading] = useState(false);
  const [askError, setAskError] = useState<string | null>(null);

  // Start a fresh chat whenever a new analysis is loaded
  useEffect(() => {
    setAskMessages([]);
    setAskInput('');
    setAskError(null);
  }, [data?.generated_at, data?.chatbot_name]);

  if (!isOpen) return null;

  const handleAsk = async () => {
    const question = askInput.trim();
    if (!question || askLoading || !onAskAI) return;

    const history = askMessages;
    setAskMessages(prev => [...prev, { role: 'user', content: question }]);
    setAskInput('');
    setAskError(null);
    setAskLoading(true);
    try {
      const answer = await onAskAI(question, history);
      setAskMessages(prev => [...prev, { role: 'assistant', content: answer }]);
    } catch (e: any) {
      setAskError(e?.message || 'Failed to get a response. Please try again.');
    } finally {
      setAskLoading(false);
    }
  };

  // Lightweight Markdown renderer for Ask AI replies (## headings, - bullets,
  // **bold**). Keeps things dependency-free while letting structured answers
  // (e.g. lead/customer info) actually render as headings instead of raw "##" text.
  const renderInlineBold = (text: string) => {
    const parts = text.split(/(\*\*[^*]+\*\*)/g);
    return parts.map((part, i) =>
      part.startsWith('**') && part.endsWith('**')
        ? <strong key={i}>{part.slice(2, -2)}</strong>
        : <span key={i}>{part}</span>
    );
  };

  const renderAssistantContent = (content: string) => {
    const lines = content.split('\n');
    const elements: ReactNode[] = [];
    let bulletBuffer: string[] = [];

    const flushBullets = () => {
      if (bulletBuffer.length > 0) {
        elements.push(
          <ul key={`ul-${elements.length}`} className="list-disc pl-4 space-y-0.5">
            {bulletBuffer.map((b, i) => <li key={i}>{renderInlineBold(b)}</li>)}
          </ul>
        );
        bulletBuffer = [];
      }
    };

    lines.forEach((line, idx) => {
      const trimmed = line.trim();
      if (/^#{1,3}\s+/.test(trimmed)) {
        flushBullets();
        elements.push(
          <p key={idx} className="font-semibold mt-2 first:mt-0">
            {renderInlineBold(trimmed.replace(/^#{1,3}\s+/, ''))}
          </p>
        );
      } else if (/^[-*]\s+/.test(trimmed)) {
        bulletBuffer.push(trimmed.replace(/^[-*]\s+/, ''));
      } else if (trimmed === '') {
        flushBullets();
      } else {
        flushBullets();
        elements.push(<p key={idx}>{renderInlineBold(trimmed)}</p>);
      }
    });
    flushBullets();
    return elements;
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Overlay */}
      <div
        className="absolute inset-0 bg-black/30 transition-opacity"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="relative ml-auto w-full max-w-md bg-white shadow-xl flex flex-col h-screen overflow-hidden animate-in slide-in-from-right">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 flex-shrink-0">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">AI Bot Analysis</h2>
            {data && (
              <p className="text-xs text-gray-400 mt-1">
                {data.used_all_time
                  ? 'All-time history'
                  : `Last ${data.analysis_period_days} days`} • {formatDate(data.generated_at)}
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition"
          >
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
          {isLoading && (
            <div className="flex flex-col items-center justify-center py-12 gap-3 text-gray-400">
              <div className="w-8 h-8 border-2 border-gray-300 border-t-blue-600 rounded-full animate-spin" />
              <p className="text-sm">AI is analyzing your conversations...</p>
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex gap-3">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium text-red-900 text-sm">Analysis Error</p>
                <p className="text-red-700 text-xs mt-1">{error}</p>
              </div>
            </div>
          )}

          {data && !isLoading && (
            <>
              {/* Executive Summary */}
              <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200 rounded-lg p-4 space-y-2">
                <div className="flex items-center gap-2">
                  <Lightbulb className="w-5 h-5 text-blue-500" />
                  <h3 className="font-semibold text-gray-900">Executive Summary</h3>
                </div>
                <p className="text-sm text-gray-700 leading-relaxed">{data.executive_summary}</p>
              </div>

              {/* Quick Stats */}
              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="font-semibold text-gray-900 text-sm mb-3">Quick Stats</h3>
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-white rounded p-3 border border-gray-200">
                    <p className="text-xs text-gray-600">Total Conversations</p>
                    <p className="text-lg font-bold text-gray-900">{data.overview.total_conversations}</p>
                  </div>
                  {data.overview.resolved !== undefined && (
                    <div className="bg-white rounded p-3 border border-gray-200">
                      <p className="text-xs text-gray-600">Resolved</p>
                      <p className="text-lg font-bold text-green-600">{data.overview.resolved}</p>
                    </div>
                  )}
                  {data.overview.escalated !== undefined && (
                    <div className="bg-white rounded p-3 border border-gray-200">
                      <p className="text-xs text-gray-600">Escalated</p>
                      <p className="text-lg font-bold text-orange-600">{data.overview.escalated}</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Top Discussion Topics */}
              {data.top_topics && data.top_topics.length > 0 && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 space-y-3">
                  <h3 className="font-semibold text-gray-900 text-sm flex items-center gap-2">
                    <MessageSquare className="w-4 h-4 text-blue-600" />
                    Top Discussion Topics
                  </h3>
                  <div className="space-y-2">
                    {data.top_topics.slice(0, 5).map((topic, idx) => (
                      <div key={idx} className="bg-white rounded p-3 border border-blue-100">
                        <div className="flex justify-between items-start gap-2 mb-1">
                          <p className="font-medium text-gray-900 text-sm">{topic.topic}</p>
                          <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">
                            {topic.frequency}%
                          </span>
                        </div>
                        <p className="text-xs text-gray-600">{topic.description}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* FAQ */}
              {data.faq && data.faq.length > 0 && (
                <div className="bg-green-50 border border-green-200 rounded-lg p-4 space-y-3">
                  <h3 className="font-semibold text-gray-900 text-sm flex items-center gap-2">
                    <HelpCircle className="w-4 h-4 text-green-600" />
                    Frequently Asked Questions
                  </h3>
                  <div className="space-y-2">
                    {data.faq.slice(0, 5).map((item, idx) => (
                      <div key={idx} className="bg-white rounded p-3 border border-green-100">
                        <p className="font-medium text-gray-900 text-sm mb-1">{item.question}</p>
                        <p className="text-xs text-gray-600">{item.answer}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Complaints Detection */}
              {data.complaints && data.complaints.length > 0 && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4 space-y-3">
                  <h3 className="font-semibold text-gray-900 text-sm flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-red-600" />
                    Complaints Detection
                  </h3>
                  <div className="space-y-2">
                    {data.complaints.slice(0, 5).map((complaint, idx) => (
                      <div key={idx} className="bg-white rounded p-3 border border-red-100">
                        <div className="flex justify-between items-start gap-2 mb-1">
                          <p className="font-medium text-gray-900 text-sm">{complaint.issue}</p>
                          <span className={`text-xs px-2 py-1 rounded font-medium ${
                            complaint.impact === 'high' ? 'bg-red-100 text-red-700' :
                            complaint.impact === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                            'bg-blue-100 text-blue-700'
                          }`}>
                            {complaint.impact}
                          </span>
                        </div>
                        <p className="text-xs text-gray-600">Frequency: {complaint.frequency}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Unanswered Questions */}
              {data.unanswered_questions && data.unanswered_questions.length > 0 && (
                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 space-y-3">
                  <h3 className="font-semibold text-gray-900 text-sm flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 text-yellow-600" />
                    Unanswered Questions
                  </h3>
                  <div className="space-y-2">
                    {data.unanswered_questions.slice(0, 5).map((question, idx) => (
                      <div key={idx} className="bg-white rounded p-3 border border-yellow-100">
                        <p className="font-medium text-gray-900 text-sm mb-1">{question.question}</p>
                        <div className="flex justify-between items-center">
                          <span className="text-xs text-gray-600">Asked {question.frequency}</span>
                          <span className={`text-xs px-2 py-1 rounded font-medium ${
                            question.importance === 'high' ? 'bg-red-100 text-red-700' :
                            question.importance === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                            'bg-blue-100 text-blue-700'
                          }`}>
                            {question.importance} priority
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* AI Recommendations */}
              {data.ai_recommendations && data.ai_recommendations.length > 0 && (
                <div className="bg-gradient-to-br from-indigo-50 to-blue-50 border border-indigo-200 rounded-lg p-4 space-y-3">
                  <h3 className="font-semibold text-gray-900 text-sm flex items-center gap-2">
                    <Lightbulb className="w-4 h-4 text-indigo-600" />
                    AI Recommendations
                  </h3>
                  <div className="space-y-2">
                    {data.ai_recommendations.map((rec, idx) => (
                      <div key={idx} className="bg-white rounded p-3 border border-indigo-100">
                        <div className="flex justify-between items-start gap-2 mb-1">
                          <p className="font-medium text-gray-900 text-sm">{rec.recommendation}</p>
                          <span className={`text-xs px-2 py-1 rounded font-medium whitespace-nowrap ${
                            rec.priority === 'high' ? 'bg-red-100 text-red-700' :
                            rec.priority === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                            'bg-blue-100 text-blue-700'
                          }`}>
                            {rec.priority}
                          </span>
                        </div>
                        <p className="text-xs text-gray-600">{rec.expected_impact}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Ask AI — Chat with your data */}
        {data && !isLoading && onAskAI && (
          <div className="flex-shrink-0 border-t border-gray-200 bg-white">
            <div className="px-6 pt-3 pb-1 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-indigo-600" />
              <h3 className="font-semibold text-gray-900 text-sm">Ask AI</h3>
              <span className="text-xs text-gray-400">Chat with your data</span>
            </div>

            {askMessages.length > 0 && (
              <div className="max-h-40 overflow-y-auto px-6 py-2 space-y-2">
                {askMessages.map((m, idx) => (
                  <div key={idx} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div
                      className={`px-3 py-1.5 rounded-lg text-xs max-w-[85%] leading-relaxed space-y-1 ${
                        m.role === 'user' ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-800'
                      }`}
                    >
                      {m.role === 'assistant' ? renderAssistantContent(m.content) : m.content}
                    </div>
                  </div>
                ))}
                {askLoading && (
                  <div className="flex justify-start">
                    <div className="px-3 py-2 rounded-lg bg-gray-100 flex items-center gap-1">
                      <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.2s]" />
                      <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.1s]" />
                      <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" />
                    </div>
                  </div>
                )}
              </div>
            )}

            {askError && <p className="px-6 pb-1 text-xs text-red-600">{askError}</p>}

            <form
              onSubmit={(e) => { e.preventDefault(); handleAsk(); }}
              className="flex items-center gap-2 px-6 py-3"
            >
              <input
                value={askInput}
                onChange={(e) => setAskInput(e.target.value)}
                placeholder="Ask about your conversations..."
                disabled={askLoading}
                className="flex-1 text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-gray-50"
              />
              <button
                type="submit"
                disabled={askLoading || !askInput.trim()}
                className="p-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0"
                aria-label="Send"
              >
                <Send className="w-4 h-4" />
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}