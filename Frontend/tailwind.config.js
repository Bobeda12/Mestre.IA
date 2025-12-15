/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        rpg: ['"Cinzel"', 'serif'],       // Para Títulos
        hand: ['"MedievalSharp"', 'cursive'], // Para textos de pergaminho
      },
      colors: {
        rpg: {
          dark: '#0f0e0b',        // Preto quase marrom
          darker: '#050505',
          gold: '#c5a059',        // Dourado envelhecido
          crimson: '#8a1c1c',     // Vermelho sangue seco
          parchment: '#d4c5a9',   // Cor de pergaminho
          leather: '#4a3b2a',     // Marrom couro
        }
      },
      backgroundImage: {
        'parchment-texture': "url('https://www.transparenttextures.com/patterns/aged-paper.png')",
        'stone-texture': "url('https://www.transparenttextures.com/patterns/black-scales.png')",
      }
    },
  },
  plugins: [],
}