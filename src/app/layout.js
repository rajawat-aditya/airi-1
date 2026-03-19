import "./globals.css";

import { auth0 } from "@/lib/auth0";

export const metadata = {
  title: "Airi | Ai Desktop Assistant Agent",
  description: "Airi | Ai Desktop Assistant Agent",
};

export default async function RootLayout({ children }) {
  // Check if user is authenticated
  const session = await auth0.getSession();
  // /auth/login?screen_hint=signup
  return (
    <html lang="en">
      <link rel="icon" href="/logo.ico" />
      <body
        className={`antialiased`}
      >
          {children}
      </body>
    </html>
  );
}
