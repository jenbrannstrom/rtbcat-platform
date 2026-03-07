"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, Filter, ChevronDown } from "lucide-react";
import { getAuditLogs } from "@/lib/api";
import { withAdminAuth } from "@/contexts/auth-context";
import { useTranslation } from "@/contexts/i18n-context";
import { cn } from "@/lib/utils";

const ACTION_COLORS: Record<string, string> = {
  login: "bg-green-100 text-green-800",
  logout: "bg-gray-100 text-gray-800",
  login_failed: "bg-red-100 text-red-800",
  login_blocked: "bg-red-100 text-red-800",
  create_user: "bg-blue-100 text-blue-800",
  update_user: "bg-yellow-100 text-yellow-800",
  deactivate_user: "bg-red-100 text-red-800",
  reset_password: "bg-purple-100 text-purple-800",
  change_password: "bg-purple-100 text-purple-800",
  grant_permission: "bg-blue-100 text-blue-800",
  revoke_permission: "bg-orange-100 text-orange-800",
  update_setting: "bg-yellow-100 text-yellow-800",
  create_initial_admin: "bg-green-100 text-green-800",
};

function AuditLogPage() {
  const { t, language } = useTranslation();
  const [days, setDays] = useState(7);
  const [actionFilter, setActionFilter] = useState<string | undefined>();
  const [showFilters, setShowFilters] = useState(false);

  const { data: logs, isLoading } = useQuery({
    queryKey: ["audit-logs", { days, action: actionFilter }],
    queryFn: () =>
      getAuditLogs({
        days,
        action: actionFilter,
        limit: 500,
      }),
  });

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "-";
    const date = new Date(dateStr);
    return date.toLocaleString(language, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const formatActionLabel = (action: string) => {
    const labels: Record<string, string> = {
      login: t.admin.auditActionLogin,
      logout: t.admin.auditActionLogout,
      login_failed: t.admin.auditActionLoginFailed,
      login_blocked: t.admin.auditActionLoginBlocked,
      create_user: t.admin.auditActionCreateUser,
      update_user: t.admin.auditActionUpdateUser,
      deactivate_user: t.admin.auditActionDeactivateUser,
      reset_password: t.admin.auditActionResetPassword,
      change_password: t.admin.auditActionChangePassword,
      grant_permission: t.admin.auditActionGrantPermission,
      revoke_permission: t.admin.auditActionRevokePermission,
      update_setting: t.admin.auditActionUpdateSetting,
      create_initial_admin: t.admin.auditActionCreateInitialAdmin,
    };
    return labels[action] || action.replace(/_/g, " ");
  };

  const parseDetails = (details: string | null) => {
    if (!details) return null;
    try {
      return JSON.parse(details);
    } catch {
      return details;
    }
  };

  const uniqueActions = logs
    ? [...new Set(logs.map((log) => log.action))].sort()
    : [];

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t.admin.auditLog}</h1>
          <p className="mt-1 text-gray-600">
            {logs?.length !== 1
              ? t.admin.eventsCountPlural.replace("{count}", String(logs?.length ?? 0))
              : t.admin.eventsCount.replace("{count}", String(logs?.length ?? 0))}{" "}
            {days !== 1
              ? t.admin.inLastDays.replace("{days}", String(days))
              : t.admin.inLastDay}
          </p>
        </div>
        <button
          onClick={() => setShowFilters(!showFilters)}
          className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
        >
          <Filter className="h-5 w-5 mr-2 text-gray-500" />
          {t.admin.filters}
          <ChevronDown
            className={cn(
              "h-4 w-4 ml-2 text-gray-500 transition-transform",
              showFilters && "rotate-180"
            )}
          />
        </button>
      </div>

      {/* Filters */}
      {showFilters && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {t.admin.timeRange}
              </label>
              <select
                value={days}
                onChange={(e) => setDays(Number(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              >
                <option value={1}>{t.admin.last24Hours}</option>
                <option value={7}>{t.admin.last7Days}</option>
                <option value={30}>{t.admin.last30Days}</option>
                <option value={60}>{t.admin.last60Days}</option>
                <option value={90}>{t.admin.last90Days}</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {t.admin.actionType}
              </label>
              <select
                value={actionFilter || ""}
                onChange={(e) => setActionFilter(e.target.value || undefined)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              >
                <option value="">{t.admin.allActions}</option>
                {uniqueActions.map((action) => (
                  <option key={action} value={action}>
                    {formatActionLabel(action)}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      )}

      {/* Audit Log Table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center">
            <div className="w-8 h-8 border-4 border-primary-600 border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="mt-4 text-gray-600">{t.admin.loadingAuditLogs}</p>
          </div>
        ) : logs?.length === 0 ? (
          <div className="p-12 text-center">
            <Activity className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-600">{t.admin.noAuditLogs}</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    {t.admin.timestamp}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    {t.admin.action}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    {t.admin.resource}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    {t.admin.details}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    {t.admin.ipAddress}
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {logs?.map((log) => {
                  const details = parseDetails(log.details);
                  return (
                    <tr key={log.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {formatDate(log.created_at)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span
                          className={cn(
                            "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium",
                            ACTION_COLORS[log.action] ||
                              "bg-gray-100 text-gray-800"
                          )}
                        >
                          {formatActionLabel(log.action)}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {log.resource_type ? (
                          <span>
                            {log.resource_type}
                            {log.resource_id && (
                              <span className="text-gray-400">
                                /{log.resource_id.slice(0, 8)}...
                              </span>
                            )}
                          </span>
                        ) : (
                          "-"
                        )}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500 max-w-xs truncate">
                        {details ? (
                          typeof details === "object" ? (
                            <code className="text-xs bg-gray-100 px-2 py-1 rounded">
                              {Object.entries(details)
                                .map(([k, v]) => `${k}: ${v}`)
                                .join(", ")}
                            </code>
                          ) : (
                            details
                          )
                        ) : (
                          "-"
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        <code className="text-xs bg-gray-100 px-2 py-1 rounded">
                          {log.ip_address || "-"}
                        </code>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default withAdminAuth(AuditLogPage);
