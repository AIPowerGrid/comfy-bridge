import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Power Grid - Model Manager",
  description: "Select and download AI models for your ComfyUI Bridge worker",
  icons: {
    icon: '/favicon.ico',
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased aipg-grid">
        <div className="relative z-10">
          {children}
        </div>
      </body>
    </html>
  );
}

