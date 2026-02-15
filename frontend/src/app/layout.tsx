import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Trading Assistant",
  description: "Agentic Trading Platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
