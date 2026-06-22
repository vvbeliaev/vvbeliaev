export const SITE = {
  title: "Vladimir Beliaev",
  tagline: "AI Full Stack Engineer · Product Lead · Analytics Engineer",
  description:
    "Personal site and long-form blog by Vladimir Beliaev — notes on AI, product and analytics.",
  author: "Vladimir Beliaev",
  // TODO: set the final domain
  url: "https://vbeliaev.dev",
  locale: "en-US",
} as const;

export const NAV = [
  { label: "Home", href: "/" },
  { label: "Blog", href: "/blog" },
] as const;
