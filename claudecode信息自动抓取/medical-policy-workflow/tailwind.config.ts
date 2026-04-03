import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: 'class',
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'PingFang SC', 'Microsoft YaHei', 'sans-serif'],
      },
      colors: {
        sidebar: {
          bg:     '#ffffff',
          border: '#e8eaed',
          hover:  '#f1f3f4',
          active: '#e8f0fe',
          text:   '#202124',
        },
      },
    },
  },
  plugins: [],
};

export default config;
