import { render, screen } from '@testing-library/react';
import LoadingSpinner from '../../components/LoadingSpinner';

describe('LoadingSpinner', () => {
  it('renders with default text', () => {
    render(<LoadingSpinner />);
    expect(screen.getByText('加载中...')).toBeInTheDocument();
  });

  it('renders with custom text', () => {
    render(<LoadingSpinner text="处理中..." />);
    expect(screen.getByText('处理中...')).toBeInTheDocument();
  });

  it('renders spinner element', () => {
    render(<LoadingSpinner />);
    const spinner = screen.getByText('加载中...').parentElement;
    expect(spinner).toBeInTheDocument();
    expect(spinner?.querySelector('div')).toHaveClass('animate-spin');
  });

  it('applies custom className', () => {
    render(<LoadingSpinner className="custom-class" />);
    const container = screen.getByText('加载中...').parentElement;
    expect(container).toHaveClass('custom-class');
  });

  it('renders different sizes', () => {
    const { rerender } = render(<LoadingSpinner size="sm" />);
    expect(screen.getByText('加载中...').parentElement?.querySelector('div')).toHaveClass('w-4');

    rerender(<LoadingSpinner size="md" />);
    expect(screen.getByText('加载中...').parentElement?.querySelector('div')).toHaveClass('w-8');

    rerender(<LoadingSpinner size="lg" />);
    expect(screen.getByText('加载中...').parentElement?.querySelector('div')).toHaveClass('w-12');
  });
});
