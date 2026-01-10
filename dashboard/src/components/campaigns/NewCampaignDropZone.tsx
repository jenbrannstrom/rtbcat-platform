'use client';

import { useDroppable } from '@dnd-kit/core';
import { cn } from '@/lib/utils';
import { useTranslation } from '@/contexts/i18n-context';

interface NewCampaignDropZoneProps {
  onClick: () => void;
}

/**
 * Droppable zone to create a new campaign on drop (Grid view)
 */
export function NewCampaignDropZone({ onClick }: NewCampaignDropZoneProps) {
  const { t } = useTranslation();
  const { setNodeRef, isOver } = useDroppable({
    id: 'new-campaign',
  });

  return (
    <div
      ref={setNodeRef}
      onClick={onClick}
      className={cn(
        "min-h-[200px] rounded-xl border-2 border-dashed flex flex-col items-center justify-center gap-2 transition-colors cursor-pointer",
        isOver
          ? "border-blue-500 bg-blue-50 text-blue-600"
          : "border-gray-300 text-gray-400 hover:border-blue-400 hover:text-blue-500"
      )}
    >
      <span className="text-4xl">+</span>
      <span>{isOver ? t.campaigns.dropToCreateCampaign : t.campaigns.newCampaign}</span>
      {isOver && (
        <span className="text-sm text-blue-500">{t.campaigns.releaseToCreate}</span>
      )}
    </div>
  );
}

/**
 * Droppable zone to create a new campaign on drop (List view)
 */
export function NewCampaignDropZoneList({ onClick }: NewCampaignDropZoneProps) {
  const { t } = useTranslation();
  const { setNodeRef, isOver } = useDroppable({
    id: 'new-campaign',
  });

  return (
    <div
      ref={setNodeRef}
      onClick={onClick}
      className={cn(
        "w-80 flex-shrink-0 rounded-lg border-2 border-dashed flex flex-col items-center justify-center gap-2 transition-colors cursor-pointer",
        isOver
          ? "border-blue-500 bg-blue-50 text-blue-600"
          : "border-gray-300 bg-gray-50 text-gray-400 hover:border-blue-400 hover:text-blue-500"
      )}
      style={{ maxHeight: '70vh', minHeight: '200px' }}
    >
      <span className="text-4xl">+</span>
      <span className="text-sm">{isOver ? t.campaigns.dropToCreate : t.campaigns.newCampaign}</span>
      {isOver && (
        <span className="text-xs text-blue-500">{t.campaigns.releaseToCreateShort}</span>
      )}
    </div>
  );
}
