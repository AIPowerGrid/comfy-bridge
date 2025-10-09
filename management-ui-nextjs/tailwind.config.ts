import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        aipg: {
          orange: '#FF6B35',
          gold: '#FFD700',
          dark: '#000000',
          darkGray: '#1a1a1a',
          gray: '#2a2a2a',
        },
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'aipg-glow': 'radial-gradient(ellipse at top, rgba(255, 107, 53, 0.1), transparent 50%), radial-gradient(ellipse at bottom, rgba(255, 215, 0, 0.05), transparent 50%)',
      },
    },
  },
  plugins: [],
};

export default config;

