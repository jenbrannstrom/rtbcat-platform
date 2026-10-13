import { MutationObserver, QueryClient } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { syncPretargetingConfigs } from '@/lib/api/settings';
import { refreshPretargetingAfterMutation, type PretargetingPushResult } from '@/lib/pretargeting-refresh';

vi.mock('@/lib/api/settings', () => ({ syncPretargetingConfigs: vi.fn() }));

const applied = { message: 'Applied 1 changes, 0 failed', changes_applied: 1, changes_failed: 0 };

describe('pretargeting mutation feedback', () => {
  beforeEach(() => vi.resetAllMocks());

  it('keeps a successful push successful and invalidates stale data when sync fails', async () => {
    vi.mocked(syncPretargetingConfigs).mockRejectedValue(new Error('Sync unavailable'));
    const queryClient = new QueryClient();
    const keys = [
      ['pretargeting-detail', 'billing-B'], ['pretargeting-configs', 'buyer-B'],
      ['pretargeting-publishers', 'billing-B'], ['pretargeting-history', 'billing-B'],
      ['pretargeting-snapshots', 'billing-B'], ['config-breakdown', 'billing-B', 7],
      ['snapshots', 'billing-B'], ['pretargeting-history', 30, 'billing-B'],
    ];
    keys.forEach(queryKey => queryClient.setQueryData(queryKey, { maximum_qps: 10000 }));
    const onError = vi.fn();
    const feedback: PretargetingPushResult[] = [];
    const observer = new MutationObserver(queryClient, {
      mutationFn: async () => applied,
      onSuccess: async result => {
        feedback.push(await refreshPretargetingAfterMutation(queryClient, 'billing-B', result));
      },
      onError,
    });

    await observer.mutate(undefined);

    expect(observer.getCurrentResult().status).toBe('success');
    expect(onError).not.toHaveBeenCalled();
    expect(syncPretargetingConfigs).toHaveBeenCalledWith({ billing_id: 'billing-B' });
    keys.forEach(key => expect(queryClient.getQueryState(key)?.isInvalidated).toBe(true));
    expect(feedback[0]).toMatchObject({ success: true, warning: true });
    expect(feedback[0].message).toContain(applied.message);
    expect(feedback[0].message).toContain('Sync');
  });

  it.each([[1, 1, true], [0, 2, false]])(
    'does not show complete success for %i applied and %i failed changes',
    async (changes_applied, changes_failed, warning) => {
      vi.mocked(syncPretargetingConfigs).mockResolvedValue({ status: 'success', configs_synced: 1, bidder_id: 'bidder-B' });
      const result = await refreshPretargetingAfterMutation(new QueryClient(), 'billing-B', {
        message: `Applied ${changes_applied} changes, ${changes_failed} failed`, changes_applied, changes_failed,
      });
      expect(result).toMatchObject({ success: false, warning });
    },
  );

  it('shows success after sync recovers a failed server refresh', async () => {
    vi.mocked(syncPretargetingConfigs).mockResolvedValue({ status: 'success', configs_synced: 1, bidder_id: 'bidder-B' });
    const result = await refreshPretargetingAfterMutation(new QueryClient(), 'billing-B', applied);
    expect(result).toEqual({ success: true, warning: false, message: applied.message });
  });

  it('does not turn a cache reload failure into a failed Google operation', async () => {
    vi.mocked(syncPretargetingConfigs).mockResolvedValue({ status: 'success', configs_synced: 1, bidder_id: 'bidder-B' });
    const queryClient = new QueryClient();
    vi.spyOn(queryClient, 'invalidateQueries').mockRejectedValue(new Error('Reload failed'));
    await expect(refreshPretargetingAfterMutation(queryClient, 'billing-B', applied))
      .resolves.toMatchObject({ success: true, warning: true });
  });
});
