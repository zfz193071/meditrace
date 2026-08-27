/**
 * 加载动画组件
 * 用于显示加载状态
 */

interface LoadingSpinnerProps {
  size?: "sm" | "md" | "lg";
  text?: string;
  className?: string;
}

export default function LoadingSpinner({
  size = "md",
  text = "加载中...",
  className = "",
}: LoadingSpinnerProps) {
  const sizeClasses = {
    sm: "w-4 h-4 border-2",
    md: "w-8 h-8 border-3",
    lg: "w-12 h-12 border-4",
  };

  return (
    <div className={`flex flex-col items-center justify-center ${className}`}>
      <div
        className={`${sizeClasses[size]} border-gray-300 border-t-green-500 rounded-full animate-spin`}
      ></div>
      {text && <p className="mt-3 text-gray-600 font-medium">{text}</p>}
    </div>
  );
}
