import { http, HttpResponse } from 'msw';

const baseUrl = process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL || 'http://localhost:8000';

export const handlers = [
  // Mock file upload
  http.post(`${baseUrl}/api/v1/documents/fileupload`, async ({ request }) => {
    const data = await request.formData();
    const files = data.getAll('files');
    const searchSpaceId = data.get('search_space_id');

    if (!files.length || !searchSpaceId) {
      return new HttpResponse(null, { status: 400 });
    }

    return HttpResponse.json({ message: 'Files uploaded for processing' });
  }),

  // Mock document crawl (POST /api/v1/documents)
  http.post(`${baseUrl}/api/v1/documents`, async ({ request }) => {
    const body = await request.json() as any;
    
    if (body.document_type === 'CRAWLED_URL' && body.content && body.search_space_id) {
      return HttpResponse.json({ message: 'Documents processed successfully' });
    }

    return new HttpResponse(null, { status: 400 });
  }),
  
  // Mock health check
  http.get(`${baseUrl}/api/health`, () => {
    return HttpResponse.json({ status: 'healthy' });
  }),
];
