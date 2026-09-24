# SmartChat

A full-stack chatbot platform with authenticated user workflows, subscription plans, admin controls, document ingestion, and AI-driven chatbot management.

## 🚀 What this project includes

- **Multi-bot platform** with specialized chatbot categories and user-owned bots.
- **FastAPI backend** with JWT authentication, subscription payments, admin management, and content ingestion.
- **React + TypeScript frontend** with Tailwind UI, protected routes, and dashboard views.
- **Knowledge ingestion** from uploaded documents and website scraping.
- **Admin dashboard** and admin API for subscriber, payment, and notification management.
- **Payment plans** with free, standard, and premium tiers plus trial support.

## 📁 Current project structure

```
SmartChat/
├── backend/
│   ├── admin_dashboard.html    # Admin dashboard UI file
│   ├── config.py              # Configuration and environment variables
│   ├── database.py            # SQLAlchemy session + models setup
│   ├── main.py                # FastAPI application entrypoint
│   ├── models.py              # ORM models for users, bots, docs, payments
│   ├── schemas.py             # Pydantic request/response schemas
│   ├── init_db.py             # Database initializer
│   ├── pinecone_ingest.py     # Pinecone vector ingestion utilities
│   ├── crawlee_ingest.py      # Crawled data ingestion helpers
│   ├── crawlee_scrape.py      # Website scraping + ingestion pipeline
│   ├── requirements.txt       # Python dependencies
│   └── routers/
│       ├── auth.py            # User auth endpoints
│       ├── chatbots.py        # Chatbot and knowledge management
│       ├── payment.py         # Subscription and payment APIs
│       └── admin.py           # Admin panel endpoints
├── frontEnd/
│   ├── package.json           # Frontend dependencies and scripts
│   ├── tsconfig.json          # TypeScript config
│   ├── vite.config.ts         # Vite config
│   ├── src/
│   │   ├── App.tsx            # App routes and page layout
│   │   ├── main.tsx           # React entrypoint
│   │   ├── index.css          # Global styles
│   │   ├── components/        # Shared UI components
│   │   ├── pages/             # Page views and auth pages
│   │   └── services/          # API client services
└── Models/
    ├── restaurantBot/        # Restaurant chatbot implementation
    ├── unibot/               # University chatbot implementation
    ├── facultyBot/           # Faculty chatbot implementation
    ├── FYP/                  # FYP chatbot implementation
    └── general/              # General assistant implementation
```

## 🛠️ Tech stack

- Backend: FastAPI, SQLAlchemy, JWT auth, CORS, file uploads, Pinecone ingestion
- Frontend: React, TypeScript, Vite, Tailwind CSS, React Router
- AI: Vector knowledge ingestion, document upload, web scraping import

## 📦 Installation

### Prerequisites
- Python 3.8+
- Node.js 18+
- npm or yarn
- Git

### Backend setup

1. `cd backend`
2. `python -m venv venv`
3. Activate the virtual environment
   - Windows: `..\Scripts\activate`
   - macOS/Linux: `source venv/bin/activate`
4. `pip install -r requirements.txt`
5. `python init_db.py`

### Frontend setup

1. `cd frontEnd`
2. `npm install`

## 🚀 Running the app

### Backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Backend API: `http://localhost:8000`

API docs: `http://localhost:8000/docs`

### Frontend

```bash
cd frontEnd
npm run dev
```

Frontend: `http://localhost:5173`

### Admin panel

Open: `http://localhost:8000/admin`

### Optional bot services

**University Bot:**
```bash
cd Models/unibot/files
uvicorn main:app --reload --port 8001
```

**Restaurant Bot:**
```bash
cd Models/restaurantBot/files
uvicorn main:app --reload --port 8002
```

## 🔐 Environment variables

Create a `.env` in `backend/` with:

```env
DATABASE_URL=your_database_url
PINECONE_API_KEY=your_pinecone_api_key
JWT_SECRET=your_jwt_secret
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=your_secure_password
ADMIN_SECRET=your_admin_secret
GMAIL_USER=your_email@example.com
GMAIL_APP_PASSWORD=your_gmail_app_password
UPLOAD_DIR=uploads
```

## 📚 Core API endpoints

### Auth
- `POST /auth/signup` — register user
- `POST /auth/login` — login and receive JWT
- `POST /auth/verify-token` — validate token

### Chatbots
- `GET /chatbots?user_id=<id>` — list user chatbots
- `POST /chatbots?user_id=<id>` — create chatbot
- `GET /chatbots/{chatbot_id}?user_id=<id>` — chatbot detail
- `PUT /chatbots/{chatbot_id}?user_id=<id>` — update chatbot
- `DELETE /chatbots/{chatbot_id}?user_id=<id>` — delete chatbot
- `GET /chatbots/{chatbot_id}/stats?user_id=<id>` — usage stats
- `GET /chatbots/{chatbot_id}/conversations?user_id=<id>` — list conversations
- `POST /chatbots/{chatbot_id}/conversations?user_id=<id>` — create conversation
- `PATCH /chatbots/{chatbot_id}/conversations/{conv_id}?user_id=<id>` — update conversation
- `GET /chatbots/{chatbot_id}/conversations/{conv_id}/messages?user_id=<id>` — get messages
- `GET /chatbots/{chatbot_id}/documents?user_id=<id>` — list uploaded docs
- `POST /chatbots/{chatbot_id}/documents/upload?user_id=<id>` — upload document

### Payments
- `GET /payments/plans` — available plans
- `POST /payments/initiate` — record payment/trial
- `POST /payments/verify` — verify completed payment
- `GET /payments/my-plan` — current user plan
- `GET /payments/history` — payment history
- `GET /payments/limits` — plan limits

### Admin
- `POST /admin/login` — admin login
- `GET /admin/me` — verify admin session
- `GET /admin/subscribers` — list subscribers
- `PATCH /admin/subscribers/{id}` — update subscriber status
- `POST /admin/subscribers/{id}/extend` — extend subscription
- `GET /admin/payments` — list payments
- `PATCH /admin/payments/{id}` — update payment status
- `POST /admin/payments/{id}/confirm-extend` — complete payment + extend
- `POST /admin/notifications/send` — send email
- `POST /admin/notifications/bulk` — send bulk email
- `POST /admin/notifications/payment-email` — send payment email

## 💡 Usage flow

1. Sign up or log in using the frontend.
2. Create or choose a chatbot.
3. Upload documents or scrape web content to add knowledge.
4. Interact with the bot and monitor metrics.
5. Use the admin panel for subscriber and payment controls.

## 🐛 Troubleshooting

### Backend issues
- Confirm virtualenv is active.
- Run `pip install -r requirements.txt`.
- Verify `.env` values and `DATABASE_URL`.
- Set `PINECONE_API_KEY` for vector ingestion.

### Frontend issues
- Run `npm install` in `frontEnd`.
- Start with `npm run dev`.
- Check `5173` is available.

### Payment/plan problems
- Use `/payments/plans` and `/payments/my-plan` to validate state.
- Confirm admin endpoints are available for manual verification.

## 🤝 Contributing

1. Fork the repo.
2. Create a branch: `git checkout -b feature/name`
3. Commit changes: `git commit -m "Add feature"`
4. Push and open a PR.

## �️ Roadmap

- [ ] Multi-language support for chatbot conversations
- [ ] Advanced analytics dashboard for usage and retention
- [ ] Bot training interface with custom dataset upload
- [ ] Integration with external APIs (CRM, email, payment gateways)
- [ ] Lead generation and conversational sales workflows
- [ ] Mobile-responsive dashboard improvements
- [ ] Performance optimizations and scaling enhancements

## �📄 License

This project is released under the MIT License.
