import type { Metadata } from "next";
import "./globals.css";
import { Nav } from "@/components/Nav";
import { LiveStream } from "@/components/LiveStream";
import styles from "./layout.module.css";

export const metadata: Metadata = {
  title: "Market Viceroy — Command Deck",
  description: "The fund in a glass box.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className={styles.shell}>
          <Nav />
          <main className={styles.main}>{children}</main>
        </div>
        <LiveStream />
      </body>
    </html>
  );
}
