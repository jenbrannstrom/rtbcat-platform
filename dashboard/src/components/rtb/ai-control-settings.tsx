'use client';

import { useState, useEffect } from 'react';
import { Bot, Settings, Zap, Shield, Info } from 'lucide-react';
import { cn } from '@/lib/utils';

export type AIControlMode = 'manual' | 'assisted' | 'autonomous';

interface AIControlSettingsProps {
  initialMode?: AIControlMode;
  onModeChange?: (mode: AIControlMode) => void;
  compact?: boolean;
}

const MODE_OPTIONS: {
  value: AIControlMode;
  label: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
}[] = [
  {
    value: 'manual',
    label: 'Manual only',
    description: "I'll make all changes myself",
    icon: Settings,
  },
  {
    value: 'assisted',
    label: 'AI proposes',
    description: 'AI suggests, I approve',
    icon: Bot,
  },
  {
    value: 'autonomous',
    label: 'Auto-optimize',
    description: 'AI optimizes within limits',
    icon: Zap,
    badge: 'Coming Soon',
  },
];

export function AIControlSettings({
  initialMode = 'assisted',
  onModeChange,
  compact = false,
}: AIControlSettingsProps) {
  const [mode, setMode] = useState<AIControlMode>(initialMode);

  // Load from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem('ai-control-mode') as AIControlMode | null;
    if (saved && ['manual', 'assisted', 'autonomous'].includes(saved)) {
      setMode(saved);
    }
  }, []);

  const handleModeChange = (newMode: AIControlMode) => {
    if (newMode === 'autonomous') return; // Disabled for now
    setMode(newMode);
    localStorage.setItem('ai-control-mode', newMode);
    onModeChange?.(newMode);
  };

  if (compact) {
    return (
      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-500">AI Mode:</span>
        <div className="flex rounded-lg border border-gray-200 overflow-hidden">
          {MODE_OPTIONS.map((option) => {
            const Icon = option.icon;
            const isDisabled = option.value === 'autonomous';
            return (
              <button
                key={option.value}
                onClick={() => handleModeChange(option.value)}
                disabled={isDisabled}
                className={cn(
                  'flex items-center gap-1 px-2 py-1 text-xs font-medium transition-colors',
                  mode === option.value
                    ? 'bg-blue-600 text-white'
                    : isDisabled
                    ? 'bg-gray-50 text-gray-400 cursor-not-allowed'
                    : 'bg-white text-gray-700 hover:bg-gray-50'
                )}
                title={option.description}
              >
                <Icon className="h-3 w-3" />
                {option.label.split(' ')[0]}
              </button>
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
      <div className="flex items-center gap-2 mb-3">
        <Shield className="h-4 w-4 text-blue-600" />
        <span className="font-medium text-gray-900">AI Control Settings</span>
      </div>

      <div className="space-y-2">
        {MODE_OPTIONS.map((option) => {
          const Icon = option.icon;
          const isDisabled = option.value === 'autonomous';
          const isSelected = mode === option.value;

          return (
            <label
              key={option.value}
              className={cn(
                'flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-all',
                isSelected
                  ? 'border-blue-300 bg-blue-50'
                  : isDisabled
                  ? 'border-gray-200 bg-gray-100 cursor-not-allowed opacity-60'
                  : 'border-gray-200 bg-white hover:border-gray-300'
              )}
            >
              <input
                type="radio"
                name="ai-control-mode"
                value={option.value}
                checked={isSelected}
                onChange={() => handleModeChange(option.value)}
                disabled={isDisabled}
                className="mt-0.5"
              />
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <Icon
                    className={cn(
                      'h-4 w-4',
                      isSelected ? 'text-blue-600' : 'text-gray-500'
                    )}
                  />
                  <span
                    className={cn(
                      'font-medium',
                      isSelected ? 'text-blue-900' : 'text-gray-900'
                    )}
                  >
                    {option.label}
                  </span>
                  {option.badge && (
                    <span className="px-1.5 py-0.5 bg-gray-200 text-gray-600 text-xs rounded">
                      {option.badge}
                    </span>
                  )}
                </div>
                <p className="text-sm text-gray-600 mt-0.5">{option.description}</p>
              </div>
            </label>
          );
        })}
      </div>

      {mode === 'assisted' && (
        <div className="mt-3 p-2 bg-blue-50 rounded border border-blue-200 text-xs text-blue-700 flex items-start gap-2">
          <Info className="h-3 w-3 mt-0.5 flex-shrink-0" />
          <span>
            AI will analyze your data and suggest optimizations. You review and approve
            each change before it's applied.
          </span>
        </div>
      )}
    </div>
  );
}

// Hook to get current AI mode
export function useAIControlMode(): AIControlMode {
  const [mode, setMode] = useState<AIControlMode>('assisted');

  useEffect(() => {
    const saved = localStorage.getItem('ai-control-mode') as AIControlMode | null;
    if (saved && ['manual', 'assisted', 'autonomous'].includes(saved)) {
      setMode(saved);
    }

    // Listen for changes
    const handleStorage = (e: StorageEvent) => {
      if (e.key === 'ai-control-mode' && e.newValue) {
        setMode(e.newValue as AIControlMode);
      }
    };
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, []);

  return mode;
}
