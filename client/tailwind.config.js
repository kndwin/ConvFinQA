const oklchColor = (token) => `oklch(from var(--${token}) l c h / <alpha-value>)`;
const oklchColorWithSourceAlpha = (token) =>
  `oklch(from var(--${token}) l c h / calc(alpha * <alpha-value>))`;

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        border: oklchColorWithSourceAlpha("border"),
        input: oklchColorWithSourceAlpha("input"),
        ring: oklchColor("ring"),
        background: oklchColor("background"),
        foreground: oklchColor("foreground"),
        card: oklchColor("card"),
        "card-foreground": oklchColor("card-foreground"),
        popover: oklchColor("popover"),
        "popover-foreground": oklchColor("popover-foreground"),
        primary: oklchColor("primary"),
        "primary-foreground": oklchColor("primary-foreground"),
        secondary: oklchColor("secondary"),
        "secondary-foreground": oklchColor("secondary-foreground"),
        muted: oklchColor("muted"),
        "muted-foreground": oklchColor("muted-foreground"),
        accent: oklchColor("accent"),
        "accent-foreground": oklchColor("accent-foreground"),
        destructive: oklchColor("destructive"),
        "destructive-foreground": oklchColor("destructive-foreground"),
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
