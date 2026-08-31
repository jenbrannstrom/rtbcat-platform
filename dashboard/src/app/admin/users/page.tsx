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
  CheckCircle,
  KeyRound,
  UserCheck,
} from "lucide-react";
import { HelpLink } from "@/components/docs/help-link";
import {
  getAdminUsers,
  changeAdminUserPassword,
  createUser,
  deactivateUser,
  getSeats,
  getUserPermissions,
  getUserSeatPermissions,
  grantPermission,
  grantUserSeatPermission,
  revokePermission,
  revokeUserSeatPermission,
  getServiceAccounts,
  updateAdminUser,
  type AdminUser,
  type CreateUserRequest,
  type ServiceAccount,
  type UserPermission,
  type UserSeatPermission,
} from "@/lib/api";
import { withAdminAuth } from "@/contexts/auth-context";
import { useTranslation } from "@/contexts/i18n-context";
import { cn } from "@/lib/utils";
import { availableLanguages } from "@/lib/i18n";
import type { BuyerSeat } from "@/types/api";

function UsersPage() {
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const { t, language } = useTranslation();

  const [showCreateModal, setShowCreateModal] = useState(
    searchParams.get("action") === "create"
  );
  const [permissionsUser, setPermissionsUser] = useState<AdminUser | null>(null);
  const [passwordUser, setPasswordUser] = useState<AdminUser | null>(null);
  const [activeDropdown, setActiveDropdown] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [permissionError, setPermissionError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);
  const [createSeatPermissions, setCreateSeatPermissions] = useState<Record<string, string>>({});
  const [createRole, setCreateRole] = useState<"read" | "admin" | "sudo">("read");
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

  const { data: seats } = useQuery({
    queryKey: ["buyer-seats", { activeOnly: true }],
    queryFn: () => getSeats({ active_only: true }),
    enabled: !!permissionsUser || showCreateModal,
  });

  const { data: serviceAccounts } = useQuery({
    queryKey: ["service-accounts", { activeOnly: true }],
    queryFn: () => getServiceAccounts(true).then((res) => res.accounts),
    enabled: !!permissionsUser,
  });

  const { data: userPermissions } = useQuery({
    queryKey: ["user-permissions", permissionsUser?.id],
    queryFn: () =>
      permissionsUser ? getUserPermissions(permissionsUser.id) : Promise.resolve([] as UserPermission[]),
    enabled: !!permissionsUser,
  });

  const { data: userSeatPermissions, isLoading: seatPermissionsLoading } = useQuery({
    queryKey: ["user-seat-permissions", permissionsUser?.id],
    queryFn: () =>
      permissionsUser
        ? getUserSeatPermissions(permissionsUser.id)
        : Promise.resolve([] as UserSeatPermission[]),
    enabled: !!permissionsUser,
  });

  const permissionMap = (userPermissions || []).reduce<Record<string, string>>((acc, perm) => {
    acc[perm.service_account_id] = perm.permission_level;
    return acc;
  }, {});

  const seatPermissionMap = (userSeatPermissions || []).reduce<Record<string, string>>((acc, perm) => {
    acc[perm.buyer_id] = perm.access_level;
    return acc;
  }, {});
  const permissionsUserIsSudo = permissionsUser?.role === "sudo";

  const createMutation = useMutation({
    mutationFn: createUser,
  });

  const resetCreateModalState = () => {
    setShowCreateModal(false);
    setCreateSeatPermissions({});
    setCreateRole("read");
    setCreateAuthMethod("local-password");
    setError(null);
  };

  const deactivateMutation = useMutation({
    mutationFn: deactivateUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      queryClient.invalidateQueries({ queryKey: ["admin-stats"] });
      setActiveDropdown(null);
      setActionNotice({ type: "success", message: t.admin.userDeactivated });
    },
    onError: (err) => {
      setActionNotice({
        type: "error",
        message: err instanceof Error ? err.message : t.common.failed,
      });
    },
  });

  const activateMutation = useMutation({
    mutationFn: (userId: string) => updateAdminUser(userId, { is_active: true }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      queryClient.invalidateQueries({ queryKey: ["admin-stats"] });
      setActiveDropdown(null);
      setActionNotice({ type: "success", message: t.admin.userActivated });
    },
    onError: (err) => {
      setActionNotice({
        type: "error",
        message: err instanceof Error ? err.message : t.common.failed,
      });
    },
  });

  const changePasswordMutation = useMutation({
    mutationFn: (params: { userId: string; password: string }) =>
      changeAdminUserPassword(params.userId, params.password),
    onSuccess: () => {
      setPasswordUser(null);
      setError(null);
      setActionNotice({ type: "success", message: t.admin.passwordChanged });
    },
  });

  const grantPermissionMutation = useMutation({
    mutationFn: (params: { userId: string; serviceAccountId: string; level: string }) =>
      grantPermission(params.userId, params.serviceAccountId, params.level),
    onSuccess: () => {
      setPermissionError(null);
      queryClient.invalidateQueries({ queryKey: ["user-permissions", permissionsUser?.id] });
    },
    onError: (err) => {
      setPermissionError(err instanceof Error ? err.message : t.common.failed);
    },
  });

  const revokePermissionMutation = useMutation({
    mutationFn: (params: { userId: string; serviceAccountId: string }) =>
      revokePermission(params.userId, params.serviceAccountId),
    onSuccess: () => {
      setPermissionError(null);
      queryClient.invalidateQueries({ queryKey: ["user-permissions", permissionsUser?.id] });
    },
    onError: (err) => {
      setPermissionError(err instanceof Error ? err.message : t.common.failed);
    },
  });

  const grantSeatPermissionMutation = useMutation({
    mutationFn: (params: { userId: string; buyerId: string; level: "read" | "admin" }) =>
      grantUserSeatPermission(params.userId, params.buyerId, params.level),
    onSuccess: () => {
      setPermissionError(null);
      queryClient.invalidateQueries({ queryKey: ["user-seat-permissions", permissionsUser?.id] });
    },
    onError: (err) => {
      setPermissionError(err instanceof Error ? err.message : t.common.failed);
    },
  });

  const revokeSeatPermissionMutation = useMutation({
    mutationFn: (params: { userId: string; buyerId: string }) =>
      revokeUserSeatPermission(params.userId, params.buyerId),
    onSuccess: () => {
      setPermissionError(null);
      queryClient.invalidateQueries({ queryKey: ["user-seat-permissions", permissionsUser?.id] });
    },
    onError: (err) => {
      setPermissionError(err instanceof Error ? err.message : t.common.failed);
    },
  });

  const bulkSeatPermissionMutation = useMutation({
    mutationFn: async (params: { userId: string; mode: "read" | "none" }) => {
      if (params.mode === "read") {
        await Promise.all(
          (seats || []).map((seat: BuyerSeat) =>
            grantUserSeatPermission(params.userId, seat.buyer_id, "read")
          )
        );
        return;
      }
      await Promise.all(
        (userSeatPermissions || []).map((permission) =>
          revokeUserSeatPermission(params.userId, permission.buyer_id)
        )
      );
    },
    onSuccess: () => {
      setPermissionError(null);
      queryClient.invalidateQueries({ queryKey: ["user-seat-permissions", permissionsUser?.id] });
    },
    onError: (err) => {
      setPermissionError(err instanceof Error ? err.message : t.common.failed);
    },
  });

  const makeReadOnlyAllSeatsMutation = useMutation({
    mutationFn: async (userId: string) => {
      await Promise.all(
        (seats || []).map((seat: BuyerSeat) =>
          grantUserSeatPermission(userId, seat.buyer_id, "read")
        )
      );
      return updateAdminUser(userId, { role: "read" });
    },
    onSuccess: (updatedUser) => {
      setPermissionError(null);
      setPermissionsUser(updatedUser);
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      queryClient.invalidateQueries({ queryKey: ["admin-stats"] });
      queryClient.invalidateQueries({ queryKey: ["user-seat-permissions", updatedUser.id] });
    },
    onError: (err) => {
      setPermissionError(err instanceof Error ? err.message : t.common.failed);
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
      const seatGrants = Object.entries(createSeatPermissions)
        .filter(([, level]) => level !== "none")
        .map(([buyerId, level]) =>
          grantUserSeatPermission(created.user_id, buyerId, level as "read" | "admin")
        );
      if (seatGrants.length > 0) {
        await Promise.all(seatGrants);
      }
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      queryClient.invalidateQueries({ queryKey: ["admin-stats"] });
      resetCreateModalState();
    } catch (err) {
      setError(err instanceof Error ? err.message : t.admin.createUserFailed);
    }
  };

  const handleChangePassword = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!passwordUser) return;

    setError(null);
    const formData = new FormData(e.currentTarget);
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

    try {
      await changePasswordMutation.mutateAsync({ userId: passwordUser.id, password });
    } catch (err) {
      setError(err instanceof Error ? err.message : t.common.failed);
    }
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "-";
    return new Date(dateStr).toLocaleDateString(language, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  const getRoleLabel = (role: string): string => {
    if (role === "sudo") return t.admin.sudoRole;
    if (role === "admin") return t.admin.adminRole;
    return t.admin.readRole;
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">{t.admin.users} <HelpLink chapter="16-user-admin" /></h1>
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
            setCreateSeatPermissions({});
            setCreateRole("read");
            setCreateAuthMethod("local-password");
            setError(null);
          }}
          className="inline-flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
        >
          <Plus className="h-5 w-5 mr-2" />
          {t.admin.createUser}
        </button>
      </div>

      {actionNotice && (
        <div
          className={cn(
            "mb-4 flex items-start justify-between gap-3 rounded-lg border px-4 py-3",
            actionNotice.type === "success"
              ? "border-green-200 bg-green-50 text-green-800"
              : "border-red-200 bg-red-50 text-red-800"
          )}
          role={actionNotice.type === "error" ? "alert" : "status"}
        >
          <div className="flex items-start gap-2 text-sm">
            {actionNotice.type === "success" ? (
              <CheckCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
            ) : (
              <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
            )}
            <span>{actionNotice.message}</span>
          </div>
          <button
            type="button"
            onClick={() => setActionNotice(null)}
            className="rounded p-0.5 hover:bg-black/5"
            aria-label={t.common.close}
          >
            <XCircle className="h-4 w-4" />
          </button>
        </div>
      )}

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
                            user.role === "sudo"
                              ? "bg-purple-100"
                              : user.role === "admin"
                                ? "bg-blue-100"
                              : "bg-gray-100"
                          )}
                        >
                          {user.role === "read" ? (
                            <User className="h-5 w-5 text-gray-500" />
                          ) : (
                            <Shield
                              className={cn(
                                "h-5 w-5",
                                user.role === "sudo" ? "text-purple-600" : "text-blue-600"
                              )}
                            />
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
                        user.role === "sudo"
                          ? "bg-purple-100 text-purple-800"
                          : user.role === "admin"
                            ? "bg-blue-100 text-blue-800"
                          : "bg-gray-100 text-gray-800"
                      )}
                    >
                      {getRoleLabel(user.role)}
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
                        <div className="absolute right-0 mt-2 w-56 bg-white rounded-md shadow-lg ring-1 ring-black ring-opacity-5 z-10">
                          <div className="py-1">
                            <button
                              onClick={() => {
                                setPermissionsUser(user);
                                setPermissionError(null);
                                setActiveDropdown(null);
                              }}
                              className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                            >
                              <Shield className="h-4 w-4 mr-3 text-gray-400" />
                              {t.admin.managePermissions}
                            </button>
                            <button
                              onClick={() => {
                                setPasswordUser(user);
                                setError(null);
                                setActiveDropdown(null);
                              }}
                              className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                            >
                              <KeyRound className="h-4 w-4 mr-3 text-gray-400" />
                              {t.admin.changePassword}
                            </button>
                            {user.is_active && (
                              <button
                                onClick={() => {
                                  if (
                                    window.confirm(
                                      t.admin.deactivateConfirm.replace("{email}", user.email)
                                    )
                                  ) {
                                    setActionNotice(null);
                                    deactivateMutation.mutate(user.id);
                                  }
                                }}
                                disabled={deactivateMutation.isPending}
                                className="flex items-center w-full px-4 py-2 text-sm text-red-600 hover:bg-red-50"
                              >
                                <XCircle className="h-4 w-4 mr-3" />
                                {t.admin.deactivate}
                              </button>
                            )}
                            {!user.is_active && (
                              <button
                                onClick={() => {
                                  setActionNotice(null);
                                  activateMutation.mutate(user.id);
                                }}
                                disabled={activateMutation.isPending}
                                className="flex items-center w-full px-4 py-2 text-sm text-green-700 hover:bg-green-50"
                              >
                                <UserCheck className="h-4 w-4 mr-3" />
                                {t.admin.activate}
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
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full mx-4 max-h-[90vh] flex flex-col">
            <div className="flex-shrink-0 px-6 pt-6 pb-4">
              <h2 className="text-xl font-semibold text-gray-900">
                {t.admin.createNewUser}
              </h2>
            </div>

            {error && (
              <div className="mx-6 mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
                <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
                <p className="text-sm text-red-700">{error}</p>
              </div>
            )}

            <form onSubmit={handleCreateUser} className="flex flex-col flex-1 min-h-0">
              <div className="overflow-y-auto flex-1 px-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t.admin.emailAddress}
                </label>
                <input
                  type="email"
                  name="email"
                  required
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  placeholder={t.admin.emailPlaceholder}
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
                  placeholder={t.admin.displayNamePlaceholder}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t.admin.role}
                </label>
                <select
                  name="role"
                  value={createRole}
                  onChange={(e) => {
                    const role = e.target.value as "read" | "admin" | "sudo";
                    setCreateRole(role);
                    if (role === "sudo") setCreateSeatPermissions({});
                  }}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                >
                  <option value="read">{t.admin.readRole}</option>
                  <option value="admin">{t.admin.adminRole}</option>
                  <option value="sudo">{t.admin.sudoRole}</option>
                </select>
              </div>
              <p className="text-xs text-gray-500 -mt-2">{t.admin.roleHelp}</p>
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
              {createRole === "sudo" ? (
                <div className="p-3 bg-purple-50 border border-purple-200 rounded-lg flex items-start gap-2">
                  <Shield className="h-5 w-5 text-purple-600 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-purple-800">{t.admin.sudoAccessHelp}</p>
                </div>
              ) : (
              <div className="space-y-2">
                <p className="text-sm font-medium text-gray-700">{t.admin.seatAccess}</p>
                <div className="space-y-2 max-h-40 overflow-y-auto border border-gray-200 rounded-lg p-2">
                  {(seats || []).map((seat: BuyerSeat) => {
                    const currentLevel = createSeatPermissions[seat.buyer_id] || "none";
                    return (
                      <div key={seat.buyer_id} className="flex items-center justify-between gap-3">
                        <div className="min-w-0">
                          <p className="text-sm text-gray-900 truncate">
                            {seat.display_name || seat.buyer_id}
                          </p>
                          <p className="text-xs text-gray-500 truncate">
                            {t.admin.buyerIdLabel.replace("{buyerId}", seat.buyer_id)}
                            {seat.bidder_id
                              ? ` • ${t.admin.bidderLabel.replace("{bidderId}", seat.bidder_id)}`
                              : ""}
                          </p>
                        </div>
                        <select
                          value={currentLevel}
                          onChange={(e) => {
                            const level = e.target.value;
                            setCreateSeatPermissions((prev) => ({
                              ...prev,
                              [seat.buyer_id]: level,
                            }));
                          }}
                          className="px-2 py-1 border border-gray-300 rounded text-sm"
                        >
                          <option value="none">{t.admin.noAccess}</option>
                          <option value="read">{t.admin.readAccess}</option>
                          <option value="admin">{t.admin.adminAccess}</option>
                        </select>
                      </div>
                    );
                  })}
                  {!seats?.length && (
                    <div className="text-sm text-gray-500">{t.admin.noSeatsConfigured}</div>
                  )}
                </div>
                <p className="text-xs text-gray-500">{t.admin.seatAccessHelp}</p>
              </div>
              )}
              <p className="text-sm text-gray-500">
                {createAuthMethod === "local-password"
                  ? t.admin.localPasswordHelp
                  : t.admin.oauthInviteNote}
              </p>
              </div>
              <div className="flex-shrink-0 px-6 pb-6 pt-4 border-t flex gap-3">
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

      {/* Change Password Modal */}
      {passwordUser && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full mx-4">
            <div className="px-6 pt-6 pb-4 flex items-start justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold text-gray-900">
                  {t.admin.changePasswordFor.replace("{email}", passwordUser.email)}
                </h2>
                <p className="mt-1 text-sm text-gray-500">{t.admin.changePasswordHelp}</p>
              </div>
              <button
                type="button"
                onClick={() => {
                  setPasswordUser(null);
                  setError(null);
                }}
                className="text-gray-400 hover:text-gray-600"
                aria-label={t.common.close}
              >
                <XCircle className="h-5 w-5" />
              </button>
            </div>

            {error && (
              <div className="mx-6 mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
                <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
                <p className="text-sm text-red-700">{error}</p>
              </div>
            )}

            <form onSubmit={handleChangePassword}>
              <div className="px-6 space-y-4">
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
                    autoFocus
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
                </div>
              </div>
              <div className="px-6 pb-6 pt-5 mt-5 border-t flex gap-3">
                <button
                  type="button"
                  onClick={() => {
                    setPasswordUser(null);
                    setError(null);
                  }}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
                >
                  {t.common.cancel}
                </button>
                <button
                  type="submit"
                  disabled={changePasswordMutation.isPending}
                  className="flex-1 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
                >
                  {changePasswordMutation.isPending ? t.common.loading : t.admin.changePassword}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Permissions Modal */}
      {permissionsUser && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] flex flex-col">
            <div className="flex-shrink-0 px-6 pt-6 pb-4 flex items-center justify-between">
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

            <div className="overflow-y-auto flex-1 px-6 space-y-3">
              {permissionError && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2" role="alert">
                  <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-red-700">{permissionError}</p>
                </div>
              )}

              {permissionsUserIsSudo ? (
                <div className="p-3 bg-purple-50 border border-purple-200 rounded-lg flex items-start justify-between gap-3">
                  <div className="flex items-start gap-2">
                    <Shield className="h-5 w-5 text-purple-600 flex-shrink-0 mt-0.5" />
                    <p className="text-sm text-purple-800">{t.admin.sudoAccessHelp}</p>
                  </div>
                  {!!seats?.length && (
                    <button
                      type="button"
                      onClick={() => makeReadOnlyAllSeatsMutation.mutate(permissionsUser.id)}
                      disabled={makeReadOnlyAllSeatsMutation.isPending}
                      className="flex-shrink-0 px-2.5 py-1.5 text-xs font-medium text-purple-800 bg-white border border-purple-300 rounded-md hover:bg-purple-100 disabled:opacity-50"
                    >
                      {t.admin.makeReadOnlyAllSeats}
                    </button>
                  )}
                </div>
              ) : !seatPermissionsLoading && (userSeatPermissions || []).length === 0 ? (
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg flex items-start gap-2">
                  <AlertCircle className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-amber-800">{t.admin.noSeatAccessWarning}</p>
                </div>
              ) : null}

              <div className="flex items-center justify-between border border-gray-200 rounded-lg p-3">
                <div>
                  <p className="text-sm font-medium text-gray-900">{t.admin.role}</p>
                  <p className="text-xs text-gray-500 max-w-md">{t.admin.roleHelp}</p>
                </div>
                <select
                  value={permissionsUser.role}
                  onChange={(e) => {
                    const role = e.target.value;
                    setPermissionError(null);
                    updateAdminUser(permissionsUser.id, { role })
                      .then((updatedUser) => {
                        queryClient.invalidateQueries({ queryKey: ["admin-users"] });
                        queryClient.invalidateQueries({ queryKey: ["admin-stats"] });
                        setPermissionsUser(updatedUser);
                      })
                      .catch((err) => {
                        setPermissionError(err instanceof Error ? err.message : t.common.failed);
                      });
                  }}
                  className="ml-4 px-3 py-2 border border-gray-300 rounded-lg text-sm"
                >
                  <option value="read">{t.admin.readRole}</option>
                  <option value="admin">{t.admin.adminRole}</option>
                  <option value="sudo">{t.admin.sudoRole}</option>
                </select>
              </div>

              <div className="flex items-center justify-between border border-gray-200 rounded-lg p-3">
                <div>
                  <p className="text-sm font-medium text-gray-900">{t.admin.defaultLanguage}</p>
                  <p className="text-xs text-gray-500">{t.admin.defaultLanguageHelp}</p>
                </div>
                <select
                  value={permissionsUser.default_language || "en"}
                  onChange={(e) => {
                    const value = e.target.value;
                    setPermissionError(null);
                    updateAdminUser(permissionsUser.id, { default_language: value })
                      .then((updatedUser) => {
                        queryClient.invalidateQueries({ queryKey: ["admin-users"] });
                        setPermissionsUser(updatedUser);
                      })
                      .catch((err) => {
                        setPermissionError(err instanceof Error ? err.message : t.common.failed);
                      });
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
              <div className="border border-gray-200 rounded-lg p-3">
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div>
                    <p className="text-sm font-medium text-gray-900">{t.admin.seatAccess}</p>
                    <p className="text-xs text-gray-500 mt-1">{t.admin.seatAccessManageHelp}</p>
                  </div>
                  {!permissionsUserIsSudo && !!seats?.length && (
                    <div className="flex flex-wrap justify-end gap-2">
                      <button
                        type="button"
                        onClick={() =>
                          bulkSeatPermissionMutation.mutate({
                            userId: permissionsUser.id,
                            mode: "read",
                          })
                        }
                        disabled={bulkSeatPermissionMutation.isPending}
                        className="px-2.5 py-1.5 text-xs font-medium text-primary-700 bg-primary-50 border border-primary-200 rounded-md hover:bg-primary-100 disabled:opacity-50"
                      >
                        {t.admin.setAllSeatsRead}
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          bulkSeatPermissionMutation.mutate({
                            userId: permissionsUser.id,
                            mode: "none",
                          })
                        }
                        disabled={
                          bulkSeatPermissionMutation.isPending ||
                          (userSeatPermissions || []).length === 0
                        }
                        className="px-2.5 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
                      >
                        {t.admin.removeAllSeatAccess}
                      </button>
                    </div>
                  )}
                </div>
                <div className="space-y-2">
                  {(seats || []).map((seat: BuyerSeat) => {
                    const currentLevel = seatPermissionMap[seat.buyer_id] || "none";
                    return (
                      <div
                        key={seat.buyer_id}
                        className="flex items-center justify-between border border-gray-200 rounded-lg p-3"
                      >
                        <div>
                          <p className="text-sm font-medium text-gray-900">
                            {seat.display_name || seat.buyer_id}
                          </p>
                          <p className="text-xs text-gray-500">
                            {t.admin.buyerIdLabel.replace("{buyerId}", seat.buyer_id)}
                            {seat.bidder_id
                              ? ` • ${t.admin.bidderLabel.replace("{bidderId}", seat.bidder_id)}`
                              : ""}
                          </p>
                        </div>
                        <select
                          value={permissionsUserIsSudo ? "sudo" : currentLevel}
                          disabled={permissionsUserIsSudo}
                          onChange={(e) => {
                            const level = e.target.value;
                            if (level === "none") {
                              if (currentLevel !== "none") {
                                revokeSeatPermissionMutation.mutate({
                                  userId: permissionsUser.id,
                                  buyerId: seat.buyer_id,
                                });
                              }
                            } else {
                              grantSeatPermissionMutation.mutate({
                                userId: permissionsUser.id,
                                buyerId: seat.buyer_id,
                                level: level as "read" | "admin",
                              });
                            }
                          }}
                          className="ml-4 px-3 py-2 border border-gray-300 rounded-lg text-sm disabled:bg-purple-50 disabled:text-purple-800"
                        >
                          {permissionsUserIsSudo && (
                            <option value="sudo">{t.admin.sudoRole} · {t.admin.adminAccess}</option>
                          )}
                          <option value="none">{t.admin.noAccess}</option>
                          <option value="read">{t.admin.readAccess}</option>
                          <option value="admin">{t.admin.adminAccess}</option>
                        </select>
                      </div>
                    );
                  })}
                  {!seats?.length && (
                    <div className="text-sm text-gray-500">{t.admin.noSeatsConfigured}</div>
                  )}
                </div>
              </div>

              <div className="border border-gray-200 rounded-lg p-3">
                <p className="text-sm font-medium text-gray-900">{t.admin.legacyServiceAccountAccess}</p>
                <p className="text-xs text-gray-500 mt-1 mb-3">{t.admin.legacyServiceAccountAccessHelp}</p>
                <div className="space-y-2">
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
                          value={permissionsUserIsSudo ? "sudo" : currentLevel}
                          disabled={permissionsUserIsSudo}
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
                          className="ml-4 px-3 py-2 border border-gray-300 rounded-lg text-sm disabled:bg-purple-50 disabled:text-purple-800"
                        >
                          {permissionsUserIsSudo && (
                            <option value="sudo">{t.admin.sudoRole} · {t.admin.adminAccess}</option>
                          )}
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
              </div>
            </div>

            <div className="flex-shrink-0 px-6 pb-6 pt-4 border-t flex justify-end">
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
