import type { Metadata } from "next";
import "./styles.css";
import { QueryProvider } from "./query-provider";

export const metadata: Metadata = {
  title: "Synthetic Data Studio",
  description: "Production interface for NVIDIA NeMo Data Designer",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
