import type { QueryClient } from '@tanstack/react-query';
import { syncPretargetingConfigs } from '@/lib/api/settings';

export type PretargetingPushResult = {
  success: boolean;
  warning?: boolean;
  message: string;
};

/** Keep a confirmed Google write separate from failures refreshing the page. */
export async function refreshPretargetingAfterMutation(
  queryClient: QueryClient,
  billingId: string,
  result: { message: string; changes_applied?: number; changes_failed?: number },
): Promise<PretargetingPushResult> {
  let refreshFailed = false;
  try {
    await syncPretargetingConfigs({ billing_id: billingId });
  } catch {
    refreshFailed = true;
  }

  // Reload even if sync failed: the apply endpoint may already have saved the
  // new config, and applied changes must disappear from the pending list.
  const reloaded = await Promise.allSettled([
    ['pretargeting-detail', billingId],
    ['pretargeting-configs'],
    ['pretargeting-publishers', billingId],
    ['pretargeting-history'],
    ['pretargeting-snapshots', billingId],
    ['snapshots', billingId],
    ['config-breakdown', billingId],
  ].map(queryKey => queryClient.invalidateQueries({ queryKey }, { throwOnError: true })));
  refreshFailed ||= reloaded.some(result => result.status === 'rejected');

  const success = (result.changes_failed ?? 0) === 0;
  const partial = !success && (result.changes_applied ?? 0) > 0;
  return {
    success,
    warning: partial || (success && refreshFailed),
    message: refreshFailed
      ? `${result.message} The page could not refresh the latest settings. Use Sync to retry the refresh.`
      : result.message,
  };
}
