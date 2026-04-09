import "./globals.css";
import "../../ui-components/index.css";
import { ThemeProvider } from "../../ui-components/hooks/useTheme";
import FluentClientProvider from "@/component/FluentClientProvider";

export const metadata = {
  title: "Airi",
  description: "Airi",
};

export default async function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><text y='26' font-size='28' font-family='serif' fill='%230078D4'>A</text></svg>" />
      <body
        className="antialiased"
        style={{ fontFamily: 'var(--font-body)' }}
      >
        {/* Blocking script: apply dark class before first paint to avoid flash */}
        <script dangerouslySetInnerHTML={{ __html: `
          (function(){
            try {
              var t = localStorage.getItem('theme');
              if (!t) t = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'Night' : 'Day';
              if (t === 'Night') document.documentElement.classList.add('dark');
              else document.documentElement.classList.remove('dark');
            } catch(e){}
          })();
        `}} />
        <ThemeProvider>
          <FluentClientProvider>
            {children}
          </FluentClientProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
