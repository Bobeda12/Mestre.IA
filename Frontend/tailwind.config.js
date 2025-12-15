/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        rpg: {
          dark: '#1a1a1a',
          darker: '#121212',
          accent: '#8b0000',
          text: '#e0e0e0',
        }
      }
    },
  },
  plugins: [],
}