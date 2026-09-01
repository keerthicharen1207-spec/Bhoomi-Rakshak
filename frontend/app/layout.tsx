import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "NER Risk Monitor",
  description: "Early warning and landslide risk monitoring for Northeast India",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
