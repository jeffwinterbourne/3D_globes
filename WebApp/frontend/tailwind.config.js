/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        studio: {
          bg: '#0b0f17',
          panel: '#111827',
          card: '#1e293b',
          border: '#334155',
          accent: '#38bdf8',
          emerald: '#10b981',
        },
      },
    },
  },
  plugins: [],
};
