"use client";

import { useQuery } from "@tanstack/react-query";
import { Users, Shield, Activity, Settings } from "lucide-react";
import Link from "next/link";
import { getAdminStats, getSystemSettings } from "@/lib/api";
import { useAuth, withAdminAuth } from "@/contexts/auth-context";
import { useTranslation } from "@/contexts/i18n-context";

function AdminDashboard() {
  const { user } = useAuth();
  const { t } = useTranslation();

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["admin-stats"],
    queryFn: getAdminStats,
  });

  const { data: settings, isLoading: settingsLoading } = useQuery({
    queryKey: ["system-settings"],
    queryFn: getSystemSettings,
  });

  const isLoading = statsLoading || settingsLoading;

  const statCards = [
    {
      name: t.admin.totalUsers,
      value: stats?.total_users ?? 0,
      icon: Users,
      href: "/admin/users",
      color: "bg-blue-500",
    },
    {
      name: t.admin.activeUsers,
      value: stats?.active_users ?? 0,
      icon: Activity,
      href: "/admin/users?active_only=true",
      color: "bg-green-500",
    },
    {
      name: t.admin.adminUsers,
      value: stats?.admin_users ?? 0,
      icon: Shield,
      href: "/admin/users?role=admin",
      color: "bg-purple-500",
    },
  ];

  const retentionOptions = [
    { value: "0", label: t.admin.unlimited },
    { value: "30", label: "30 " + t.dashboard.days },
    { value: "60", label: "60 " + t.dashboard.days },
    { value: "90", label: "90 " + t.dashboard.days },
    { value: "120", label: "120 " + t.dashboard.days },
  ];

  const currentRetention = settings?.audit_retention_days ?? "60";
  const multiUserEnabled = settings?.multi_user_enabled === "1";

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">{t.admin.dashboard}</h1>
        <p className="mt-1 text-gray-600">
          {t.admin.manageUsers}
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        {statCards.map((stat) => (
          <Link
            key={stat.name}
            href={stat.href}
            className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow"
          >
            <div className="flex items-center">
              <div className={`${stat.color} rounded-lg p-3`}>
                <stat.icon className="h-6 w-6 text-white" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-600">{stat.name}</p>
                <p className="text-2xl font-bold text-gray-900">
                  {isLoading ? "..." : stat.value}
                </p>
              </div>
            </div>
          </Link>
        ))}
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        {/* User Management */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            {t.admin.userManagement}
          </h2>
          <div className="space-y-3">
            <Link
              href="/admin/users"
              className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <div className="flex items-center">
                <Users className="h-5 w-5 text-gray-500 mr-3" />
                <span className="text-gray-700">Manage Users</span>
              </div>
              <span className="text-gray-400">&rarr;</span>
            </Link>
            <Link
              href="/admin/users?action=create"
              className="flex items-center justify-between p-3 bg-primary-50 rounded-lg hover:bg-primary-100 transition-colors"
            >
              <div className="flex items-center">
                <Shield className="h-5 w-5 text-primary-600 mr-3" />
                <span className="text-primary-700">Create New User</span>
              </div>
              <span className="text-primary-400">&rarr;</span>
            </Link>
            <Link
              href="/admin/audit-log"
              className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <div className="flex items-center">
                <Activity className="h-5 w-5 text-gray-500 mr-3" />
                <span className="text-gray-700">View Audit Log</span>
              </div>
              <span className="text-gray-400">&rarr;</span>
            </Link>
          </div>
        </div>

        {/* System Settings */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            {t.admin.systemSettings}
          </h2>
          <div className="space-y-4">
            {/* Multi-User Mode */}
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <div>
                <p className="font-medium text-gray-700">Multi-User Mode</p>
                <p className="text-sm text-gray-500">
                  {multiUserEnabled
                    ? "Multiple users can access the system"
                    : "Single-user mode (open-source)"}
                </p>
              </div>
              <span
                className={`px-3 py-1 text-sm font-medium rounded-full ${
                  multiUserEnabled
                    ? "bg-green-100 text-green-700"
                    : "bg-gray-200 text-gray-600"
                }`}
              >
                {multiUserEnabled ? "Enabled" : "Disabled"}
              </span>
            </div>

            {/* Audit Log Retention */}
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <div>
                <p className="font-medium text-gray-700">Audit Log Retention</p>
                <p className="text-sm text-gray-500">
                  How long to keep audit logs
                </p>
              </div>
              <span className="px-3 py-1 text-sm font-medium rounded-full bg-blue-100 text-blue-700">
                {retentionOptions.find((o) => o.value === currentRetention)
                  ?.label ?? `${currentRetention} days`}
              </span>
            </div>

            {/* Link to settings page */}
            <Link
              href="/admin/settings"
              className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <div className="flex items-center">
                <Settings className="h-5 w-5 text-gray-500 mr-3" />
                <span className="text-gray-700">All Settings</span>
              </div>
              <span className="text-gray-400">&rarr;</span>
            </Link>
          </div>
        </div>
      </div>

      {/* Current User Info */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Your Account
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <p className="text-sm text-gray-500">Email</p>
            <p className="font-medium text-gray-900">{user?.email}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Display Name</p>
            <p className="font-medium text-gray-900">
              {user?.display_name || "-"}
            </p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Role</p>
            <p className="font-medium text-gray-900 capitalize">{user?.role}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Status</p>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
              Active
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default withAdminAuth(AdminDashboard);
