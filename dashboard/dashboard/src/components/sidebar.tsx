"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Image,
  FolderKanban,
  Download,
  Settings,
  ExternalLink,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navigation = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "Creatives", href: "/creatives", icon: Image },
  { name: "Campaigns", href: "/campaigns", icon: FolderKanban },
  { name: "Collect", href: "/collect", icon: Download },
  { name: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <div className="flex flex-col w-64 bg-white border-r border-gray-200">
      <div className="flex items-center h-16 px-4 border-b border-gray-200">
        <img
          src="/cat-scanning-stats.webp"
          alt="RTBcat"
          className="h-10 w-10 rounded-lg mr-3"
        />
        <span className="text-xl font-bold text-primary-600">RTBcat</span>
      </div>
      <nav className="flex-1 px-4 py-4 space-y-1">
        {navigation.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors",
                isActive
                  ? "bg-primary-50 text-primary-700"
                  : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
              )}
            >
              <item.icon
                className={cn(
                  "mr-3 h-5 w-5",
                  isActive ? "text-primary-600" : "text-gray-400"
                )}
              />
              {item.name}
            </Link>
          );
        })}
      </nav>
      <div className="px-4 py-4 border-t border-gray-200">
        <a
          href="https://rtb.cat"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center px-3 py-2 text-sm font-medium text-gray-600 hover:text-primary-600 rounded-md hover:bg-gray-50 transition-colors"
        >
          <ExternalLink className="mr-3 h-5 w-5 text-gray-400" />
          Docs
        </a>
        <p className="mt-2 px-3 text-xs text-gray-500">v0.1.0</p>
      </div>
    </div>
  );
}
