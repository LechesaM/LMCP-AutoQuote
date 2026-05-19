import useQueueStore from "../store/queueStore";

export function useReviewQueue() {
  const items = useQueueStore((state) => state.items);
  const summary = useQueueStore((state) => state.summary);

  return {
    items,
    summary,
  };
}
