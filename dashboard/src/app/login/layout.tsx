import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Login - Cat-Scan",
  description: "Sign in to Cat-Scan Dashboard",
};

export default function LoginLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Login page doesn't need the sidebar or account provider
  return <>{children}</>;
}
