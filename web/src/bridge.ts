declare global {
  interface Window {
    QWebChannel?: new (
      transport: unknown,
      callback: (channel: { objects: Record<string, any> }) => void
    ) => void;
    qt?: {
      webChannelTransport?: unknown;
    };
    pybridge?: Record<string, any>;
    __shadowReload?: () => Promise<void> | void;
  }
}

let bridgePromise: Promise<Record<string, any>> | null = null;

export async function initBridge(): Promise<Record<string, any>> {
  if (window.pybridge) {
    return window.pybridge;
  }
  if (bridgePromise) {
    return bridgePromise;
  }
  bridgePromise = new Promise((resolve, reject) => {
    let attempts = 0;
    const boot = () => {
      attempts += 1;
      if (window.pybridge) {
        resolve(window.pybridge);
        return;
      }
      if (window.QWebChannel && window.qt?.webChannelTransport) {
        new window.QWebChannel(window.qt.webChannelTransport, (channel) => {
          window.pybridge = channel.objects.pybridge;
          resolve(window.pybridge);
        });
        return;
      }
      if (attempts > 120) {
        reject(new Error("未能连接到 Qt WebChannel。"));
        return;
      }
      window.setTimeout(boot, 50);
    };
    boot();
  });
  return bridgePromise;
}

export async function invokeBridge<T = any>(method: string, ...args: any[]): Promise<T> {
  const bridge = await initBridge();
  const fn = bridge[method];
  if (typeof fn !== "function") {
    throw new Error(`Bridge 方法不存在：${method}`);
  }
  return new Promise<T>((resolve, reject) => {
    fn(...args, (raw: string) => {
      try {
        const payload = JSON.parse(raw);
        if (payload?.ok) {
          resolve(payload.data as T);
          return;
        }
        reject(new Error(String(payload?.error || "Bridge 调用失败。")));
      } catch (error) {
        reject(error instanceof Error ? error : new Error("Bridge 返回值无法解析。"));
      }
    });
  });
}
