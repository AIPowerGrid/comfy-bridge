import type { Metadata } from "next";
import "./globals.css";
import { Web3Provider } from "@/lib/web3";

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
        <Web3Provider>
          <div className="relative z-10">
            {children}
          </div>
        </Web3Provider>
      </body>
    </html>
  );
}

