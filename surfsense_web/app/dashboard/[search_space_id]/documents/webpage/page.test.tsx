import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import WebpageCrawler from './page';
import { server } from '@/vitest.setup';
import { http, HttpResponse } from 'msw';

// Mock the TagInput component from emblor as it's complex to test in JSDOM
vi.mock('emblor', () => ({
  TagInput: ({ tags, setTags, onAddTag }: any) => (
    <div data-testid="mock-tag-input">
      <input 
        data-testid="url-input" 
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            onAddTag((e.target as HTMLInputElement).value);
            (e.target as HTMLInputElement).value = '';
          }
        }} 
      />
      {tags.map((tag: any) => (
        <span key={tag.id}>{tag.text}</span>
      ))}
    </div>
  ),
}));

describe('WebpageCrawler', () => {
  it('renders correctly', () => {
    render(<WebpageCrawler />);
    expect(screen.getByText(/add_webpage\.title/)).toBeInTheDocument();
    expect(screen.getByText(/Space 1/)).toBeInTheDocument();
  });

  it('validates URLs and adds tags', async () => {
    render(<WebpageCrawler />);
    const input = screen.getByTestId('url-input');
    
    fireEvent.keyDown(input, { key: 'Enter', target: { value: 'https://example.com' } });
    
    expect(screen.getByText('https://example.com')).toBeInTheDocument();
  });

  it('submits URLs successfully', async () => {
    render(<WebpageCrawler />);
    const input = screen.getByTestId('url-input');
    
    fireEvent.keyDown(input, { key: 'Enter', target: { value: 'https://example.com' } });
    
    const submitButton = screen.getByText('add_webpage.submit');
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('add_webpage.submitting')).toBeInTheDocument();
    });
  });

  it('handles submission error', async () => {
    const baseUrl = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL;
    server.use(
      http.post(`${baseUrl}/api/v1/documents`, () => {
        return new HttpResponse(JSON.stringify({ detail: 'Backend error' }), { 
          status: 500,
          headers: { 'Content-Type': 'application/json' }
        });
      })
    );

    render(<WebpageCrawler />);
    const input = screen.getByTestId('url-input');
    fireEvent.keyDown(input, { key: 'Enter', target: { value: 'https://example.com' } });
    
    const submitButton = screen.getByText('add_webpage.submit');
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('Backend error')).toBeInTheDocument();
    });
  });
});
