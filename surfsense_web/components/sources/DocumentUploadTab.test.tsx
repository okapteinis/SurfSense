import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { DocumentUploadTab } from './DocumentUploadTab';
import { server } from '@/vitest.setup';
import { http, HttpResponse } from 'msw';

// Mock motion to disable animations
vi.mock('motion/react', () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

// Mock useDropzone
vi.mock('react-dropzone', () => ({
  useDropzone: ({ onDrop }: any) => ({
    getRootProps: () => ({}),
    getInputProps: () => ({
      'data-testid': 'dropzone-input',
      type: 'file',
      multiple: true,
      onChange: (e: any) => {
        onDrop(Array.from(e.target.files || []));
      },
    }),
    isDragActive: false,
  }),
}));

describe('DocumentUploadTab', () => {
  it('renders correctly', () => {
    render(<DocumentUploadTab searchSpaceId="1" />);
    expect(screen.getByText(/upload_documents\.drag_drop/)).toBeInTheDocument();
  });

  it('handles file selection', async () => {
    const user = userEvent.setup();
    render(<DocumentUploadTab searchSpaceId="1" />);
    const input = screen.getByTestId('dropzone-input') as HTMLInputElement;
    
    const file = new File(['hello'], 'hello.pdf', { type: 'application/pdf' });
    await user.upload(input, file);

    expect(await screen.findByText(/hello\.pdf/)).toBeInTheDocument();
  });

  it('uploads files successfully', async () => {
    const user = userEvent.setup();
    render(<DocumentUploadTab searchSpaceId="1" />);
    const input = screen.getByTestId('dropzone-input') as HTMLInputElement;
    
    const file = new File(['hello'], 'hello.pdf', { type: 'application/pdf' });
    await user.upload(input, file);

    const uploadButton = await screen.findByText(/upload_documents\.upload_button/);
    await user.click(uploadButton);

    await waitFor(() => {
      const uploadingElements = screen.getAllByText(/upload_documents\.uploading/);
      expect(uploadingElements.length).toBeGreaterThan(0);
    });
  });

  it('handles upload failure', async () => {
    const user = userEvent.setup();
    const baseUrl = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL;
    server.use(
      http.post(`${baseUrl}/api/v1/documents/fileupload`, () => {
        return new HttpResponse(JSON.stringify({ detail: 'Upload error' }), { 
          status: 400,
          headers: { 'Content-Type': 'application/json' }
        });
      })
    );

    render(<DocumentUploadTab searchSpaceId="1" />);
    const input = screen.getByTestId('dropzone-input') as HTMLInputElement;
    const file = new File(['hello'], 'hello.pdf', { type: 'application/pdf' });
    await user.upload(input, file);

    const uploadButton = await screen.findByText(/upload_documents\.upload_button/);
    await user.click(uploadButton);

    await waitFor(() => {
      expect(screen.queryByText(/upload_documents\.uploading/)).not.toBeInTheDocument();
    });
  });
});
