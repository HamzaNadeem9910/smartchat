export const API_BASE_URL = (
  import.meta.env.VITE_API_URL || (import.meta.env.DEV ? "http://localhost:8000" : "")
).replace(/\/$/, "");

interface LoginCredentials {
  email: string;
  password: string;
}

interface SignupData {
  name: string;
  email: string;
  password: string;
  plan?: "free" | "pro" | "enterprise";
}

interface Chatbot {
  id: number;
  subscriber_id: number;
  name: string;
  status: "active" | "inactive" | "training";
  conversations: number;
  accuracy: number;
  response_time: number;
  success_rate: number;
  last_updated: string;
  created_at: string;
}

interface CreateChatbotData {
  name: string;
  status?: "active" | "inactive" | "training";
}

interface UpdateChatbotData {
  name?: string;
  status?: "active" | "inactive" | "training";
  conversations?: number;
  accuracy?: number;
  response_time?: number;
  success_rate?: number;
}

interface UsageStats {
  id: number;
  chatbot_id: number;
  date: string;
  messages_count: number;
  created_at: string;
}

// Auth API calls
export const authAPI = {
  signup: async (data: SignupData) => {
    const response = await fetch(`${API_BASE_URL}/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error("Signup failed");
    return response.json();
  },

  login: async (credentials: LoginCredentials) => {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(credentials),
    });
    if (!response.ok) throw new Error("Login failed");
    return response.json();
  },

  verifyToken: async (token: string) => {
    const response = await fetch(`${API_BASE_URL}/auth/verify-token?token=${token}`, {
      headers: { "Content-Type": "application/json" },
    });
    if (!response.ok) throw new Error("Token verification failed");
    return response.json();
  },
};

// Chatbots API calls
export const chatbotsAPI = {
  create: async (userId: number, data: CreateChatbotData, token: string) => {
    const response = await fetch(`${API_BASE_URL}/chatbots/?user_id=${userId}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error("Failed to create chatbot");
    return response.json();
  },

  getAll: async (userId: number, token: string): Promise<Chatbot[]> => {
    const response = await fetch(`${API_BASE_URL}/chatbots/?user_id=${userId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) throw new Error("Failed to fetch chatbots");
    return response.json();
  },

  getDetail: async (chatbotId: number, userId: number, token: string) => {
    const response = await fetch(
      `${API_BASE_URL}/chatbots/${chatbotId}?user_id=${userId}`,
      {
        headers: { Authorization: `Bearer ${token}` },
      }
    );
    if (!response.ok) throw new Error("Failed to fetch chatbot details");
    return response.json();
  },

  update: async (
    chatbotId: number,
    userId: number,
    data: UpdateChatbotData,
    token: string
  ) => {
    const response = await fetch(
      `${API_BASE_URL}/chatbots/${chatbotId}?user_id=${userId}`,
      {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(data),
      }
    );
    if (!response.ok) throw new Error("Failed to update chatbot");
    return response.json();
  },

  delete: async (chatbotId: number, userId: number, token: string) => {
    const response = await fetch(
      `${API_BASE_URL}/chatbots/${chatbotId}?user_id=${userId}`,
      {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      }
    );
    if (!response.ok) throw new Error("Failed to delete chatbot");
    return response.json();
  },

  getStats: async (
    chatbotId: number,
    userId: number,
    days: number = 7,
    token: string
  ): Promise<UsageStats[]> => {
    const response = await fetch(
      `${API_BASE_URL}/chatbots/${chatbotId}/stats?user_id=${userId}&days=${days}`,
      {
        headers: { Authorization: `Bearer ${token}` },
      }
    );
    if (!response.ok) throw new Error("Failed to fetch stats");
    return response.json();
  },

  recordStat: async (
    chatbotId: number,
    userId: number,
    messagesCount: number,
    token: string
  ) => {
    const response = await fetch(
      `${API_BASE_URL}/chatbots/${chatbotId}/stats?user_id=${userId}&messages_count=${messagesCount}`,
      {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      }
    );
    if (!response.ok) throw new Error("Failed to record stats");
    return response.json();
  },
};
