import useSourceHealthStore from "../store/sourceHealthStore";

export function useHarvestHealth() {
  const sources = useSourceHealthStore((state) => state.sources);

  return {
    sources,
    status: "advisory",
  };
}
