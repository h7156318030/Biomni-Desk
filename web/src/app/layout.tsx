import type { Metadata } from "next";
import { Rail } from "@/components/rail";
import { ThemeSync } from "@/components/theme-sync";
import { I18nProvider } from "@/lib/i18n";
import "./globals.css";

export const metadata: Metadata = {
  title: "Biomni-Desk workspace",
  description: "Local biomedical research agent workspace",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // Browser extensions and auto-translate edit the DOM before React loads; that is not an app error.
    <html lang="en" className="h-full antialiased" suppressHydrationWarning>
      <body className="flex h-full" suppressHydrationWarning>
        <I18nProvider>
          <ThemeSync />
          <Rail />
          <div className="h-full min-w-0 flex-1">{children}</div>
        </I18nProvider>
      </body>
    </html>
  );
}
