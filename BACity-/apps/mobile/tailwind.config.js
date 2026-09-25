/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,jsx,ts,tsx}",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  presets: [require("nativewind/preset")],
  theme: {
    extend: {
      colors: {
        primary: "#FF7F86",
        "primary-foreground": "#FFFFFF",
        secondary: "#FFF0EE",
        "secondary-foreground": "#272329",
        background: "#FFF8F5",
        foreground: "#272329",
        card: "#FFFFFF",
        "card-foreground": "#272329",
        muted: "#FFF0EE",
        "muted-foreground": "#7C7379",
        accent: "#FF9DA1",
        "accent-foreground": "#272329",
        destructive: "#D95763",
        border: "#F1D8D5",
        input: "#F1D8D5",
        ring: "#FF7F86",
      },
    },
  },
  plugins: [],
};
