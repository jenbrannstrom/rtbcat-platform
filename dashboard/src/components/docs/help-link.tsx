"use client";

import { HelpCircle } from "lucide-react";

export const DOCS_MAP: Record<string, string> = {
  "/": "03-qps-funnel",
  "/qps/geo": "04-analyzing-waste",
  "/qps/publisher": "04-analyzing-waste",
  "/qps/size": "04-analyzing-waste",
  "/creatives": "05-managing-creatives",
  "/campaigns": "05-managing-creatives",
  "/history": "06-pretargeting",
  "/import": "09-data-import",
  "/settings/accounts": "17-integrations",
  "/settings/retention": "14-database",
  "/settings/system": "13-health-monitoring",
  "/admin/users": "16-user-admin",
  "/admin/audit-log": "16-user-admin",
};

interface HelpLinkProps {
  chapter: string;
  className?: string;
}

export function HelpLink({ chapter, className = "" }: HelpLinkProps) {
  return (
    <a
      href={`/docs/${chapter}`}
      target="_blank"
      rel="noopener noreferrer"
      className={`inline-flex items-center justify-center p-1 text-gray-400 hover:text-primary-600 rounded-md hover:bg-gray-100 transition-colors ${className}`}
      title="Open documentation"
    >
      <HelpCircle className="h-4 w-4" />
    </a>
  );
}
