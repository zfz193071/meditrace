/**
 * 状态徽章组件
 * 用于显示诊断记录的上链状态
 */

interface StatusBadgeProps {
  status: "pending" | "confirmed" | "failed";
  className?: string;
}

export default function StatusBadge({ status, className = "" }: StatusBadgeProps) {
  const statusConfig = {
    pending: {
      label: "待上链",
      bgClass: "bg-yellow-100",
      textClass: "text-yellow-800",
      icon: "⏳",
    },
    confirmed: {
      label: "已上链",
      bgClass: "bg-green-100",
      textClass: "text-green-800",
      icon: "✓",
    },
    failed: {
      label: "上链失败",
      bgClass: "bg-red-100",
      textClass: "text-red-800",
      icon: "✗",
    },
  };

  const config = statusConfig[status];

  return (
    <span
      className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm font-medium ${config.bgClass} ${config.textClass} ${className}`}
    >
      <span>{config.icon}</span>
      <span>{config.label}</span>
    </span>
  );
}
