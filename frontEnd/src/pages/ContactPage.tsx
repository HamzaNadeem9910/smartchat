import Header from '../components/Header';
import Footer from '../components/Footer';

export default function ContactPage() {
  return (
    <div className="min-h-screen bg-white">
      <Header />

      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <section className="text-center mb-12">
          <p className="text-sm font-semibold uppercase tracking-wide text-indigo-600">Contact Us</p>
          <h1 className="mt-4 text-4xl font-bold text-gray-900 sm:text-5xl">
            Need help or want to talk about your project?
          </h1>
          <p className="mt-6 text-lg text-gray-600 max-w-2xl mx-auto">
            Reach out to our team and we’ll get back to you with a plan that fits your business.
          </p>
        </section>

        <section className="rounded-3xl border border-gray-200 bg-slate-50 p-10 shadow-sm">
          <div className="grid gap-10 lg:grid-cols-2">
            <div>
              <h2 className="text-2xl font-semibold text-gray-900">Contact details</h2>
              <p className="mt-4 text-gray-600">
                Email us at <a href="mailto:hamzanadeemc@gmail.com" className="text-indigo-600 hover:text-indigo-700">hamzanadeemc@gmail.com</a>
                or call <a href="tel:+923107125676" className="text-indigo-600 hover:text-indigo-700">+92 310 7125676</a>.
              </p>
              <div className="mt-8 space-y-4">
                <div>
                  <p className="text-sm font-semibold text-gray-500">Office</p>
                  <p className="text-gray-700">GIFT UNIVERSITY Gujranwala PAKISTAN</p>
                </div>
                <div>
                  <p className="text-sm font-semibold text-gray-500">Support hours</p>
                  <p className="text-gray-700">Mon - Fri, 9 AM - 6 PM PT</p>
                </div>
              </div>
            </div>

            <form className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-gray-700">Name</label>
                <input type="text" className="mt-2 w-full rounded-2xl border border-gray-300 bg-white px-4 py-3 focus:border-indigo-500 focus:outline-none" placeholder="Your full name" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Email</label>
                <input type="email" className="mt-2 w-full rounded-2xl border border-gray-300 bg-white px-4 py-3 focus:border-indigo-500 focus:outline-none" placeholder="you@example.com" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Message</label>
                <textarea rows={5} className="mt-2 w-full rounded-2xl border border-gray-300 bg-white px-4 py-3 focus:border-indigo-500 focus:outline-none" placeholder="Tell us how we can help." />
              </div>
              <button type="submit" className="w-full rounded-2xl bg-indigo-600 px-6 py-3 text-white font-semibold hover:bg-indigo-700 transition-colors">
                Send Message
              </button>
            </form>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
