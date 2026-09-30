/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        display: ['Newsreader', 'Georgia', 'serif'],
        serif: ['Newsreader', 'Source Serif 4', 'Georgia', 'serif'],
        bodyserif: ['Source Serif 4', 'Georgia', 'serif'],
      },
    },
  },
  plugins: [],
}
