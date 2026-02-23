"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import {
  Users,
  Plus,
  Shield,
  User,
  MoreVertical,
  XCircle,
  AlertCircle,
} from "lucide-react";
import {
  getAdminUsers,
  createUser,
  deactivateUser,
  getUserPermissions,
  grantPermission,
  revokePermission,
  getServiceAccounts,
  updateAdminUser,
  type AdminUser,
  type CreateUserRequest,
  type ServiceAccount,
  type UserPermission,
} from "@/lib/api";
import { withAdminAuth } from "@/contexts/auth-context";
import { useTranslation } from "@/contexts/i18n-context";
import { cn } from "@/lib/utils";
import { availableLanguages } from "@/lib/i18n";

function UsersPage() {
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const { t } = useTranslation();

  const [showCreateModal, setShowCreateModal] = useState(
    searchParams.get("action") === "create"
  );
  const [permissionsUser, setPermissionsUser] = useState<AdminUser | null>(null);
  const [activeDropdown, setActiveDropdown] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [createPermissions, setCreatePermissions] = useState<Record<string, string>>({});
  const [createAuthMethod, setCreateAuthMethod] = useState<"local-password" | "oauth-precreate">(
    "local-password"
  );

  // Filters from URL params
  const activeOnly = searchParams.get("active_only") === "true";
  const roleFilter = searchParams.get("role") || undefined;

  const { data: users, isLoading } = useQuery({
    queryKey: ["admin-users", { activeOnly, roleFilter }],
    queryFn: () => getAdminUsers({ active_only: activeOnly, role: roleFilter }),
  });

  const { data: serviceAccounts } = useQuery({
    queryKey: ["service-accounts", { activeOnly: true }],
    queryFn: () => getServiceAccounts(true).then((res) => res.accounts),
    enabled: !!permissionsUser || showCreateModal,
  });

  const { data: userPermissions } = useQuery({
    queryKey: ["user-permissions", permissionsUser?.id],
    queryFn: () =>
      permissionsUser ? getUserPermissions(permissionsUser.id) : Promise.resolve([] as UserPermission[]),
    enabled: !!permissionsUser,
  });

  const permissionMap = (userPermissions || []).reduce<Record<string, string>>((acc, perm) => {
    acc[perm.service_account_id] = perm.permission_level;
    return acc;
  }, {});

  const createMutation = useMutation({
    mutationFn: createUser,
  });

  const resetCreateModalState = () => {
    setShowCreateModal(false);
    setCreatePermissions({});
    setCreateAuthMethod("local-password");
    setError(null);
  };

  const deactivateMutation = useMutation({
    mutationFn: deactivateUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      queryClient.invalidateQueries({ queryKey: ["admin-stats"] });
      setActiveDropdown(null);
    },
  });

  const grantPermissionMutation = useMutation({
    mutationFn: (params: { userId: string; serviceAccountId: string; level: string }) =>
      grantPermission(params.userId, params.serviceAccountId, params.level),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user-permissions", permissionsUser?.id] });
    },
  });

  const revokePermissionMutation = useMutation({
    mutationFn: (params: { userId: string; serviceAccountId: string }) =>
      revokePermission(params.userId, params.serviceAccountId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user-permissions", permissionsUser?.id] });
    },
  });

  const handleCreateUser = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    const formData = new FormData(e.currentTarget);
    const request: CreateUserRequest = {
      email: formData.get("email") as string,
      display_name: (formData.get("display_name") as string) || undefined,
      role: formData.get("role") as string,
      default_language: (formData.get("default_language") as string) || "en",
    };
    const authMethod = (formData.get("auth_method") as "local-password" | "oauth-precreate") || "local-password";
    request.auth_method = authMethod;
    if (authMethod === "local-password") {
      const password = (formData.get("password") as string) || "";
      const confirmPassword = (formData.get("confirm_password") as string) || "";
      if (password.length < 8) {
        setError(t.admin.passwordMinLengthHelp);
        return;
      }
      if (password !== confirmPassword) {
        setError(t.admin.passwordMismatch);
        return;
      }
      request.password = password;
    }
    try {
      const created = await createMutation.mutateAsync(request);
      const grants = Object.entries(createPermissions)
        .filter(([, level]) => level !== "none")
        .map(([serviceAccountId, level]) =>
          grantPermission(created.user_id, serviceAccountId, level)
        );
      if (grants.length > 0) {
        await Promise.all(grants);
      }
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      queryClient.invalidateQueries({ queryKey: ["admin-stats"] });
      resetCreateModalState();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create user");
    }
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "-";
    return new Date(dateStr).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t.admin.users}</h1>
          <p className="mt-1 text-gray-600">
            {users?.length !== 1
              ? t.admin.usersCountPlural.replace("{count}", String(users?.length ?? 0))
              : t.admin.usersCount.replace("{count}", String(users?.length ?? 0))}
            {activeOnly && ` ${t.admin.activeOnly}`}
            {roleFilter && ` ${t.admin.withRole.replace("{role}", roleFilter)}`}
          </p>
        </div>
        <button
          onClick={() => {
            setShowCreateModal(true);
            setCreatePermissions({});
            setCreateAuthMethod("local-password");
            setError(null);
          }}
          className="inline-flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
        >
          <Plus className="h-5 w-5 mr-2" />
          {t.admin.createUser}
        </button>
      </div>

      {/* Users Table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center">
            <div className="w-8 h-8 border-4 border-primary-600 border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="mt-4 text-gray-600">{t.admin.loadingUsers}</p>
          </div>
        ) : users?.length === 0 ? (
          <div className="p-12 text-center">
            <Users className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-600">{t.admin.noUsersFound}</p>
          </div>
        ) : (
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t.admin.user}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t.admin.role}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t.admin.status}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t.admin.lastLogin}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {t.admin.created}
                </th>
                <th className="relative px-6 py-3">
                  <span className="sr-only">{t.common.actions}</span>
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {users?.map((user) => (
                <tr key={user.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <div className="h-10 w-10 flex-shrink-0">
                        <div
                          className={cn(
                            "h-10 w-10 rounded-full flex items-center justify-center",
                            user.role === "admin"
                              ? "bg-purple-100"
                              : "bg-gray-100"
                          )}
                        >
                          {user.role === "admin" ? (
                            <Shield className="h-5 w-5 text-purple-600" />
                          ) : (
                            <User className="h-5 w-5 text-gray-500" />
                          )}
                        </div>
                      </div>
                      <div className="ml-4">
                        <div className="text-sm font-medium text-gray-900">
                          {user.display_name || user.email.split("@")[0]}
                        </div>
                        <div className="text-sm text-gray-500">{user.email}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span
                      className={cn(
                        "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium capitalize",
                        user.role === "admin"
                          ? "bg-purple-100 text-purple-800"
                          : "bg-gray-100 text-gray-800"
                      )}
                    >
                      {user.role}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span
                      className={cn(
                        "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium",
                        user.is_active
                          ? "bg-green-100 text-green-800"
                          : "bg-red-100 text-red-800"
                      )}
                    >
                      {user.is_active ? t.admin.active : t.admin.inactive}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {formatDate(user.last_login_at)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {formatDate(user.created_at)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <div className="relative">
                      <button
                        onClick={() =>
                          setActiveDropdown(
                            activeDropdown === user.id ? null : user.id
                          )
                        }
                        className="text-gray-400 hover:text-gray-600 p-1 rounded-md hover:bg-gray-100"
                      >
                        <MoreVertical className="h-5 w-5" />
                      </button>
                      {activeDropdown === user.id && (
                        <div className="absolute right-0 mt-2 w-48 bg-white rounded-md shadow-lg ring-1 ring-black ring-opacity-5 z-10">
                          <div className="py-1">
                            <button
                              onClick={() => {
                                setPermissionsUser(user);
                                setActiveDropdown(null);
                              }}
                              className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                            >
                              <Shield className="h-4 w-4 mr-3 text-gray-400" />
                              {t.admin.managePermissions}
                            </button>
                            {user.is_active && (
                              <button
                                onClick={() => deactivateMutation.mutate(user.id)}
                                className="flex items-center w-full px-4 py-2 text-sm text-red-600 hover:bg-red-50"
                              >
                                <XCircle className="h-4 w-4 mr-3" />
                                {t.admin.deactivate}
                              </button>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Create User Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full mx-4 p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">
              {t.admin.createNewUser}
            </h2>

            {error && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
                <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
                <p className="text-sm text-red-700">{error}</p>
              </div>
            )}

            <form onSubmit={handleCreateUser} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t.admin.emailAddress}
                </label>
                <input
                  type="email"
                  name="email"
                  required
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  placeholder="user@example.com"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t.admin.displayNameOptional}
                </label>
                <input
                  type="text"
                  name="display_name"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  placeholder="John Doe"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t.admin.role}
                </label>
                <select
                  name="role"
                  defaultValue="user"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                >
                  <option value="user">{t.admin.userRole}</option>
                  <option value="admin">{t.admin.adminRole}</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t.admin.authMethod}
                </label>
                <select
                  name="auth_method"
                  value={createAuthMethod}
                  onChange={(e) =>
                    setCreateAuthMethod(e.target.value as "local-password" | "oauth-precreate")
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                >
                  <option value="local-password">{t.admin.localPasswordAuth}</option>
                  <option value="oauth-precreate">{t.admin.oauthPrecreateAuth}</option>
                </select>
                <p className="mt-1 text-xs text-gray-500">
                  {createAuthMethod === "local-password"
                    ? t.admin.localPasswordHelp
                    : t.admin.oauthPrecreateHelp}
                </p>
              </div>
              {createAuthMethod === "local-password" && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {t.admin.password}
                    </label>
                    <input
                      type="password"
                      name="password"
                      required
                      minLength={8}
                      autoComplete="new-password"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    />
                    <p className="mt-1 text-xs text-gray-500">{t.admin.passwordMinLengthHelp}</p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {t.admin.confirmPassword}
                    </label>
                    <input
                      type="password"
                      name="confirm_password"
                      required
                      minLength={8}
                      autoComplete="new-password"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    />
                    <p className="mt-1 text-xs text-gray-500">{t.admin.confirmPasswordHelp}</p>
                  </div>
                </>
              )}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t.admin.defaultLanguage}
                </label>
                <select
                  name="default_language"
                  defaultValue="en"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                >
                  {availableLanguages.map((lang) => (
                    <option key={lang.code} value={lang.code}>
                      {lang.nativeName}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <p className="text-sm font-medium text-gray-700">{t.admin.seatAccess}</p>
                <div className="space-y-2 max-h-40 overflow-y-auto border border-gray-200 rounded-lg p-2">
                  {(serviceAccounts || []).map((account: ServiceAccount) => {
                    const currentLevel = createPermissions[account.id] || "none";
                    return (
                      <div key={account.id} className="flex items-center justify-between gap-3">
                        <div className="min-w-0">
                          <p className="text-sm text-gray-900 truncate">
                            {account.display_name || account.client_email}
                          </p>
                          <p className="text-xs text-gray-500 truncate">{account.client_email}</p>
                        </div>
                        <select
                          value={currentLevel}
                          onChange={(e) => {
                            const level = e.target.value;
                            setCreatePermissions((prev) => ({
                              ...prev,
                              [account.id]: level,
                            }));
                          }}
                          className="px-2 py-1 border border-gray-300 rounded text-sm"
                        >
                          <option value="none">{t.admin.noAccess}</option>
                          <option value="read">{t.admin.readAccess}</option>
                          <option value="write">{t.admin.writeAccess}</option>
                          <option value="admin">{t.admin.adminAccess}</option>
                        </select>
                      </div>
                    );
                  })}
                  {!serviceAccounts?.length && (
                    <div className="text-sm text-gray-500">{t.admin.noServiceAccounts}</div>
                  )}
                </div>
                <p className="text-xs text-gray-500">{t.admin.seatAccessHelp}</p>
              </div>
              <p className="text-sm text-gray-500">
                {createAuthMethod === "local-password"
                  ? t.admin.localPasswordHelp
                  : t.admin.oauthInviteNote}
              </p>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={resetCreateModalState}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
                >
                  {t.common.cancel}
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="flex-1 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
                >
                  {createMutation.isPending ? t.admin.creating : t.admin.createUser}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Permissions Modal */}
      {permissionsUser && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full mx-4 p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-xl font-semibold text-gray-900">
                  {t.admin.permissionsFor.replace("{email}", permissionsUser.email)}
                </h2>
                <p className="text-sm text-gray-500">{t.admin.permissionsHelp}</p>
              </div>
              <button
                onClick={() => setPermissionsUser(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                <XCircle className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-3 max-h-[420px] overflow-y-auto">
              <div className="flex items-center justify-between border border-gray-200 rounded-lg p-3">
                <div>
                  <p className="text-sm font-medium text-gray-900">{t.admin.defaultLanguage}</p>
                  <p className="text-xs text-gray-500">{t.admin.defaultLanguageHelp}</p>
                </div>
                <select
                  value={permissionsUser.default_language || "en"}
                  onChange={(e) => {
                    const value = e.target.value;
                    updateAdminUser(permissionsUser.id, { default_language: value })
                      .then(() => {
                        queryClient.invalidateQueries({ queryKey: ["admin-users"] });
                        setPermissionsUser((prev) =>
                          prev ? { ...prev, default_language: value } : prev
                        );
                      })
                      .catch(() => {});
                  }}
                  className="ml-4 px-3 py-2 border border-gray-300 rounded-lg text-sm"
                >
                  {availableLanguages.map((lang) => (
                    <option key={lang.code} value={lang.code}>
                      {lang.nativeName}
                    </option>
                  ))}
                </select>
              </div>
              {(serviceAccounts || []).map((account: ServiceAccount) => {
                const currentLevel = permissionMap[account.id] || "none";
                return (
                  <div
                    key={account.id}
                    className="flex items-center justify-between border border-gray-200 rounded-lg p-3"
                  >
                    <div>
                      <p className="text-sm font-medium text-gray-900">
                        {account.display_name || account.client_email}
                      </p>
                      <p className="text-xs text-gray-500">{account.client_email}</p>
                    </div>
                    <select
                      value={currentLevel}
                      onChange={(e) => {
                        const level = e.target.value;
                        if (level === "none") {
                          if (currentLevel !== "none") {
                            revokePermissionMutation.mutate({
                              userId: permissionsUser.id,
                              serviceAccountId: account.id,
                            });
                          }
                        } else {
                          grantPermissionMutation.mutate({
                            userId: permissionsUser.id,
                            serviceAccountId: account.id,
                            level,
                          });
                        }
                      }}
                      className="ml-4 px-3 py-2 border border-gray-300 rounded-lg text-sm"
                    >
                      <option value="none">{t.admin.noAccess}</option>
                      <option value="read">{t.admin.readAccess}</option>
                      <option value="write">{t.admin.writeAccess}</option>
                      <option value="admin">{t.admin.adminAccess}</option>
                    </select>
                  </div>
                );
              })}
              {!serviceAccounts?.length && (
                <div className="text-sm text-gray-500">{t.admin.noServiceAccounts}</div>
              )}
            </div>

            <div className="pt-4 flex justify-end">
              <button
                onClick={() => setPermissionsUser(null)}
                className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
              >
                {t.common.done}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Click outside to close dropdown */}
      {activeDropdown && (
        <div
          className="fixed inset-0 z-0"
          onClick={() => setActiveDropdown(null)}
        />
      )}
    </div>
  );
}

export default withAdminAuth(UsersPage);
