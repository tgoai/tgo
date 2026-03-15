"use client";
import { TgoSection } from "@/components/home/tgo-section";
import { CoreCapabilities } from "@/components/home/core-capabilities";
import { GetStarted } from "@/components/home/get-started";
import Footer from "@/components/Footer";

export default function HomePage() {
  return (
    <div className="min-h-screen text-gray-900 dark:text-gray-100">
      <main>
        <TgoSection />
        <CoreCapabilities />
        <GetStarted />
      </main>
      <Footer />
    </div>
  );
}
