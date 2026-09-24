import Header from '../components/Header';
import Footer from '../components/Footer';

// Processed headshots — background-removed and composited onto a shared
// studio backdrop so all five read as one consistent set. Drop the `team`
// folder into this same directory (src/pages/team/).
import supervisorImg from './team/zuhaib.jpg';
import hamzaImg from './team/hamza.jpg';
import hassanImg from './team/hassan.jpg';
import shamsImg from './team/shams.jpg';
import shawaizImg from './team/shawaiz.jpg';

type TeamMember = {
  name: string;
  role: string;
  image: string;
};

const supervisor: TeamMember = {
  name: 'Zuhaib', // TODO: confirm full name/title to display here
  role: 'Project Founder & CEO',
  image: supervisorImg,
};

const team: TeamMember[] = [
  { name: 'Hamza Nadeem', role: 'AI & Backend Developer', image: hamzaImg },
  { name: 'Hassan Arif', role: 'Frontend Developer', image: hassanImg },
  { name: 'Shams Irfan', role: 'Tester', image: shamsImg },
  { name: 'Shawaiz Hussain', role: 'Project Manager', image: shawaizImg },
];

export default function AboutPage() {
  return (
    <div className="min-h-screen bg-white">
      <Header />

      <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <section className="text-center mb-16">
          <p className="text-sm font-semibold uppercase tracking-wide text-indigo-600">About Us</p>
          <h1 className="mt-4 text-4xl font-bold text-gray-900 sm:text-5xl">
            AI chatbots that actually know your business
          </h1>
          <p className="mt-6 text-lg text-gray-600 max-w-3xl mx-auto">
            SmartChat turns your menus, prospectuses, and support documents into AI assistants that answer
            accurately — for restaurants, universities, faculties, and support teams alike. Deploy on your
            website and WhatsApp, and see every conversation in one admin dashboard.
          </p>
        </section>

        <section className="grid gap-8 lg:grid-cols-3 mb-20">
          <div className="rounded-3xl border border-gray-200 p-8 shadow-sm bg-slate-50">
            <h2 className="text-2xl font-semibold text-gray-900">Our mission</h2>
            <p className="mt-4 text-gray-600">
              To give every organization — from a single restaurant to a university faculty — an AI assistant
              that knows their content inside out, powered by retrieval-augmented generation instead of
              guesswork.
            </p>
          </div>
          <div className="rounded-3xl border border-gray-200 p-8 shadow-sm bg-slate-50">
            <h2 className="text-2xl font-semibold text-gray-900">Our values</h2>
            <p className="mt-4 text-gray-600">
              Answers should come from real data, not hallucination. Every bot is grounded in the business's
              own documents, and reaches customers wherever they already are — web chat or WhatsApp.
            </p>
          </div>
          <div className="rounded-3xl border border-gray-200 p-8 shadow-sm bg-slate-50">
            <h2 className="text-2xl font-semibold text-gray-900">Our promise</h2>
            <p className="mt-4 text-gray-600">
              Simple onboarding, transparent plans, and an admin dashboard that turns every conversation into
              a clear, actionable insight.
            </p>
          </div>
        </section>

        <section>
          <div className="text-center mb-10">
            <p className="text-sm font-semibold uppercase tracking-wide text-indigo-600">The People Behind SmartChat</p>
            <h2 className="mt-2 text-3xl font-bold text-gray-900">Meet the Team</h2>
          </div>

          {/* Supervisor — featured card */}
          <div className="flex justify-center mb-10">
            <div className="flex flex-col items-center rounded-3xl border border-indigo-100 bg-indigo-50 px-10 py-8 shadow-sm w-full max-w-sm">
              <img
                src={supervisor.image}
                alt={supervisor.name}
                className="h-28 w-28 rounded-full object-cover ring-4 ring-white shadow-md"
              />
              <h3 className="mt-4 text-xl font-semibold text-gray-900">{supervisor.name}</h3>
              <p className="mt-1 text-sm font-medium text-indigo-600">{supervisor.role}</p>
            </div>
          </div>

          {/* Team members */}
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {team.map((member) => (
              <div
                key={member.name}
                className="flex flex-col items-center text-center rounded-3xl border border-gray-200 bg-slate-50 px-6 py-8 shadow-sm"
              >
                <img
                  src={member.image}
                  alt={member.name}
                  className="h-20 w-20 rounded-full object-cover ring-4 ring-white shadow-sm"
                />
                <h3 className="mt-4 text-base font-semibold text-gray-900">{member.name}</h3>
                <p className="mt-1 text-sm text-indigo-600">{member.role}</p>
              </div>
            ))}
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}