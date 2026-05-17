export function connectLiveWs(path: string): WebSocket {
  const base = process.env.NEXT_PUBLIC_WS_BASE_URL ?? "ws://localhost:8000";
  return new WebSocket(`${base}${path}`);
}

