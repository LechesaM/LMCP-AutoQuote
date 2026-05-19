export function createPollingController(fetcher, intervalMs = 30000) {
  let timer = null;
  let running = false;

  const start = () => {
    if (running) {
      return;
    }
    running = true;
    timer = setInterval(() => {
      Promise.resolve(fetcher()).catch(() => {});
    }, intervalMs);
  };

  const stop = () => {
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
    running = false;
  };

  const refresh = async () => fetcher();

  return {
    start,
    stop,
    refresh,
    get running() {
      return running;
    },
  };
}
