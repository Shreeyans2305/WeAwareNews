/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Kanit', 'Geist', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        display: ['Kanit', 'Geist', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
