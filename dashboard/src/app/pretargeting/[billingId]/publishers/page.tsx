'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import { PretargetingSettingsEditor } from '@/components/rtb/pretargeting-settings-editor';
import { useAccount } from '@/contexts/account-context';
import { toBuyerScopedPath } from '@/lib/buyer-routes';

export default function PublisherListPage() {
  const { selectedBuyerId } = useAccount();
  const params = useParams();
  const billingId = typeof params?.billingId === 'string' ? params.billingId : '';
  const buyerIdFromParams = typeof params?.buyerId === 'string' ? params.buyerId : null;
  const backHref = toBuyerScopedPath('/', buyerIdFromParams || selectedBuyerId);

  if (!billingId) {
    return (
      <div className="p-6">
        <div className="rounded border bg-white p-6 text-sm text-gray-500">
          Missing billing ID.
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-3">
        <Link
          href={backHref}
          className="inline-flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to configs
        </Link>
      </div>
      <PretargetingSettingsEditor
        billing_id={billingId}
        initialTab="publishers"
        hideTabs
      />
    </div>
  );
}
