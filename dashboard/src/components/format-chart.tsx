"use client";

import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from "recharts";
import { useTranslation } from "@/contexts/i18n-context";

interface FormatChartProps {
  data: Record<string, number>;
}

const COLORS = {
  HTML: "#3b82f6",
  VIDEO: "#8b5cf6",
  NATIVE: "#22c55e",
  IMAGE: "#f97316",
  UNKNOWN: "#6b7280",
};

export function FormatChart({ data }: FormatChartProps) {
  const { t } = useTranslation();
  const chartData = Object.entries(data).map(([name, value]) => ({
    name,
    value,
  }));

  if (chartData.length === 0) {
    return (
      <div className="flex items-center justify-center h-[300px] text-gray-500">
        {t.creatives.noData}
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <PieChart>
        <Pie
          data={chartData}
          cx="50%"
          cy="50%"
          labelLine={false}
          outerRadius={80}
          fill="#8884d8"
          dataKey="value"
          label={({ name, percent }) =>
            `${name} ${(percent * 100).toFixed(0)}%`
          }
        >
          {chartData.map((entry) => (
            <Cell
              key={`cell-${entry.name}`}
              fill={COLORS[entry.name as keyof typeof COLORS] || COLORS.UNKNOWN}
            />
          ))}
        </Pie>
        <Tooltip
          formatter={(value: number) => [value, t.creatives.title]}
        />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  );
}
