export const downloadBlob = (blob: Blob, filename: string) => {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
};

export const downloadResponseBlob = (data: BlobPart, filename: string, type?: string) => {
  downloadBlob(new Blob([data], type ? { type } : undefined), filename);
};

export const fetchAndDownload = async (url: string, filename: string, token?: string | null) => {
  const response = await fetch(url, {
    headers: { Authorization: `Bearer ${token ?? ''}` },
  });
  const blob = await response.blob();
  downloadBlob(blob, filename);
};
