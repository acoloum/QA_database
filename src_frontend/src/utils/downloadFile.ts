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
