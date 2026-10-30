export function decodeBase64ToFloat32(b64?: string | null): Float32Array {
  if (!b64) return new Float32Array(0);
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return new Float32Array(bytes.buffer);
}

export function decodeBase64ToUint32(b64?: string | null): Uint32Array {
  if (!b64) return new Uint32Array(0);
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return new Uint32Array(bytes.buffer);
}

export function decodeBase64ToUint8(b64?: string | null): Uint8Array {
  if (!b64) return new Uint8Array(0);
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}
