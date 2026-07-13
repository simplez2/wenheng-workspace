export const createAuthenticatedEventStream = (url) => {
  const controller = new AbortController();
  const listeners = new Map();
  const stream = {
    readyState: 0,
    onmessage: null,
    onerror: null,
    addEventListener(type, handler) {
      const handlers = listeners.get(type) || new Set();
      handlers.add(handler);
      listeners.set(type, handlers);
    },
    close() {
      if (stream.readyState === 2) return;
      stream.readyState = 2;
      controller.abort();
    },
  };

  const dispatch = (type, data) => {
    const event = { data };
    if (type === 'message' && stream.onmessage) {
      stream.onmessage(event);
    }
    for (const handler of listeners.get(type) || []) {
      handler(event);
    }
  };

  const fail = (error) => {
    if (stream.readyState === 2) return;
    if (stream.onerror) stream.onerror(error);
    if (stream.readyState !== 2) stream.readyState = 2;
  };

  queueMicrotask(async () => {
    try {
      const cardKey = localStorage.getItem('cardKey');
      const response = await fetch(url, {
        headers: cardKey ? { 'X-Card-Key': cardKey } : {},
        cache: 'no-store',
        signal: controller.signal,
      });
      if (!response.ok || !response.body) {
        throw new Error(`SSE request failed with status ${response.status}`);
      }

      stream.readyState = 1;
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (stream.readyState !== 2) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
        const frames = buffer.split(/\r?\n\r?\n/);
        buffer = frames.pop() || '';

        for (const frame of frames) {
          let eventType = 'message';
          const dataLines = [];
          for (const line of frame.split(/\r?\n/)) {
            if (line.startsWith('event:')) eventType = line.slice(6).trim();
            if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart());
          }
          if (dataLines.length) dispatch(eventType, dataLines.join('\n'));
        }

        if (done) break;
      }

      if (stream.readyState !== 2) fail(new Error('SSE connection closed'));
    } catch (error) {
      if (error?.name !== 'AbortError') fail(error);
    }
  });

  return stream;
};
