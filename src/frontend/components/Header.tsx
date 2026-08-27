/**
 * 页面头部横幅组件
 * 用于所有页面的统一头部设计
 */

import { useRouter } from "next/navigation";

interface HeaderProps {
  title: string;
  subtitle?: string;
  showBackButton?: boolean;
  onBack?: () => void;
}

export default function Header({
  title,
  subtitle,
  showBackButton = true,
  onBack,
}: HeaderProps) {
  const router = useRouter();

  const handleBack = () => {
    if (onBack) {
      onBack();
    } else {
      router.back();
    }
  };

  return (
    <section className="gradient-bg text-white header-banner">
      <div className="max-w-6xl mx-auto">
        <div className="header-content py-6">
          <div className="flex items-center gap-4 mb-4">
            {showBackButton && (
              <button
                onClick={handleBack}
                className="back-btn flex items-center gap-2 px-4 py-2 rounded-full bg-white/20 hover:bg-white/30 transition-colors"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
                <span className="text-sm font-medium">返回</span>
              </button>
            )}
          </div>

          <h1 className="text-3xl md:text-4xl font-bold mb-2">{title}</h1>
          {subtitle && <p className="text-lg opacity-90">{subtitle}</p>}
        </div>
      </div>
    </section>
  );
}
