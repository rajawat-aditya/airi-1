import "./globals.css";
import { AppSidebar } from "@/components/app-sidebar"
import {
  SidebarProvider,
} from "@/components/ui/sidebar"

export const metadata = {
  title: "Airi | Ai Desktop Assistant Agent",
  description: "Airi | Ai Desktop Assistant Agent",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <link rel="icon" href="/logo.ico" />
      <body
        className={`antialiased`}
      >
        <SidebarProvider>
          <AppSidebar />
          {children}
        </SidebarProvider>
      </body>
    </html>
  );
}
