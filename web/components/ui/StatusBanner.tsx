import type { ReactNode } from "react";

// 门禁结论横幅:全站「能否交易」的唯一权威呈现,消除多处重复。
export default function StatusBanner({
  status,
  title,
  detail,
}: {
  status: "ready" | "blocked";
  title: ReactNode;
  detail?: ReactNode;
}) {
  const ready = status === "ready";
  return (
    <div
      className={`rounded-[12px] border px-5 py-4 flex items-start gap-3 ${
        ready ? "border-ok/30 bg-ok/5" : "border-danger/30 bg-danger/5"
      }`}
    >
      <span
        className={`mt-1 inline-block w-2.5 h-2.5 rounded-full shrink-0 ${
          ready ? "bg-ok animate-pulse" : "bg-danger"
        }`}
      />
      <div className="min-w-0">
        <div className={`text-base font-semibold ${ready ? "text-ok" : "text-danger"}`}>{title}</div>
        {detail && <div className="text-[12px] text-subink mt-1 leading-relaxed">{detail}</div>}
      </div>
    </div>
  );
}
