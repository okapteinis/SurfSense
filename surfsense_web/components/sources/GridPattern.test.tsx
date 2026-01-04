import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { GridPattern } from './GridPattern';

describe('GridPattern', () => {
  it('renders correctly', () => {
    const { container } = render(<GridPattern />);
    
    // Check if the main container exists
    const mainDiv = container.firstChild as HTMLElement;
    expect(mainDiv).toHaveClass('flex-wrap');
    
    // Check if it renders the expected number of grid cells (41 * 11 = 451)
    const cells = mainDiv.querySelectorAll('div');
    expect(cells.length).toBe(451);
  });
});
