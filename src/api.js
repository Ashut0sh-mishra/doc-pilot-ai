const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function request(path, options = {}, role = 'patient') {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'X-User-Role': role,
      ...(options.body instanceof Blob || options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...options.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${response.status})`);
  }
  return response.status === 204 ? null : response.json();
}

export const api = {
  health: () => request('/health'),
  createPatient: (data) => request('/v1/patients', { method: 'POST', body: JSON.stringify(data) }),
  getPatient: (id) => request(`/v1/patients/${id}`),
  records: (id) => request(`/v1/patients/${id}/records`),
  medications: (id) => request(`/v1/patients/${id}/medications`),
  summary: (id) => request(`/v1/patients/${id}/clinical-summary`, {}, 'doctor'),
  getJob: (jobId) => request(`/v1/jobs/${jobId}`),
  retryJob: (jobId, role = 'patient') => request(`/v1/jobs/${jobId}/retry`, { method: 'POST' }, role),
  getOcr: (recordId) => request(`/v1/records/${recordId}/ocr`),
  saveOcrCorrection: (recordId, payload, role = 'patient') =>
    request(`/v1/records/${recordId}/ocr`, { method: 'PUT', body: JSON.stringify(payload) }, role),
  async getRecordFileUrl(recordId, role = 'patient') {
    // The file endpoint requires the role header, so fetch bytes and hand
    // the UI a same-origin blob URL for preview.
    const response = await fetch(`${API_URL}/v1/records/${recordId}/file`, { headers: { 'X-User-Role': role } });
    if (!response.ok) throw new Error(`Document download failed (${response.status})`);
    return URL.createObjectURL(await response.blob());
  },
  async uploadRecord(patientId, file) {
    const initiated = await request(`/v1/patients/${patientId}/records/upload`, {
      method: 'POST',
      body: JSON.stringify({
        filename: file.name,
        content_type: file.type || 'application/octet-stream',
        source_type: file.type.startsWith('image/') ? 'medicine_photo' : 'other',
      }),
    });
    const transfer = await fetch(initiated.upload_url, {
      method: 'PUT',
      headers: { 'Content-Type': file.type || 'application/octet-stream', 'X-User-Role': 'patient' },
      body: file,
    });
    if (!transfer.ok) throw new Error('File transfer failed');
    const job = await request(`/v1/records/${initiated.record_id}/complete`, { method: 'POST' });
    return { ...initiated, job };
  },
};
