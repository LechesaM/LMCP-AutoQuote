export function SkeletonLine({ className = "" }) {
  return <div className={`animate-pulse rounded-lg bg-slate-800/80 ${className}`} />;
}

export function SkeletonCard({ lines = 3 }) {
  return (
    <div className="space-y-3">
      <SkeletonLine className="h-4 w-2/3" />
      {Array.from({ length: lines }).map((_, index) => (
        <SkeletonLine key={index} className={`h-4 ${index === lines - 1 ? "w-1/2" : "w-full"}`} />
      ))}
    </div>
  );
}
