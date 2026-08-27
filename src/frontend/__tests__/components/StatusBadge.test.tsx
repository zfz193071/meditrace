import { render, screen } from '@testing-library/react';
import StatusBadge from '../../components/StatusBadge';

describe('StatusBadge', () => {
  it('renders confirmed status correctly', () => {
    render(<StatusBadge status="confirmed" />);
    expect(screen.getByText('已上链')).toBeInTheDocument();
    expect(screen.getByText('✓')).toBeInTheDocument();
  });

  it('renders pending status correctly', () => {
    render(<StatusBadge status="pending" />);
    expect(screen.getByText('待上链')).toBeInTheDocument();
    expect(screen.getByText('⏳')).toBeInTheDocument();
  });

  it('renders failed status correctly', () => {
    render(<StatusBadge status="failed" />);
    expect(screen.getByText('上链失败')).toBeInTheDocument();
    expect(screen.getByText('✗')).toBeInTheDocument();
  });

  it('applies custom className', () => {
    render(<StatusBadge status="confirmed" className="custom-class" />);
    const badge = screen.getByText('已上链').parentElement;
    expect(badge).toHaveClass('custom-class');
  });
});
