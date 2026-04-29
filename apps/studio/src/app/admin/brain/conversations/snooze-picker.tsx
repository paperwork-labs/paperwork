"use client";

import { useEffect, useRef, useState } from "react";

interface Props {
  onSelect: (until: Date) => void;
  onClose: () => void;
}

function nextMonday9am(): Date {
  const d = new Date();
  const day = d.getDay(); // 0=Sun,1=Mon,...,6=Sat
  const daysUntilMonday = day === 0 ? 1 : 8 - day;
  d.setDate(d.getDate() + daysUntilMonday);
  d.setHours(9, 0, 0, 0);
  return d;
}

function tomorrow9am(): Date {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  d.setHours(9, 0, 0, 0);
  return d;
}

function eod(): Date {
  const d = new Date();
  d.setHours(18, 0, 0, 0);
  return d;
}

function inHours(n: number): Date {
  return new Date(Date.now() + n * 60 * 60 * 1000);
}

const SMART_DEFAULTS = [
  { label: "1 hour", until: () => inHours(1) },
  { label: "4 hours", until: () => inHours(4) },
  { label: "End of day", until: eod },
  { label: "Tomorrow 9am", until: tomorrow9am },
  { label: "Next Monday 9am", until: nextMonday9am },
];

export function SnoozePicker({ onSelect, onClose }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [customDate, setCustomDate] = useState("");

  useEffect(() => {
    const handle = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, [onClose]);

  const handleCustom = () => {
    if (!customDate) return;
    onSelect(new Date(customDate));
  };

  return (
    <div
      ref={ref}
      className="absolute right-0 top-8 z-30 w-52 rounded-xl border border-zinc-800 bg-zinc-950 p-2 shadow-xl"
    >
      <p className="mb-1.5 px-2 text-[10px] font-semibold uppercase tracking-widest text-zinc-600">
        Snooze until
      </p>
      {SMART_DEFAULTS.map((d) => (
        <button
          key={d.label}
          onClick={() => onSelect(d.until())}
          className="block w-full rounded-lg px-3 py-1.5 text-left text-sm text-zinc-300 transition hover:bg-zinc-800 hover:text-zinc-100"
        >
          {d.label}
        </button>
      ))}
      <div className="mt-2 border-t border-zinc-800 pt-2 px-2">
        <p className="mb-1 text-[10px] text-zinc-600">Custom date &amp; time</p>
        <input
          type="datetime-local"
          value={customDate}
          onChange={(e) => setCustomDate(e.target.value)}
          className="w-full rounded border border-zinc-800 bg-zinc-900 px-2 py-1 text-xs text-zinc-300"
        />
        <button
          onClick={handleCustom}
          disabled={!customDate}
          className="mt-1.5 w-full rounded-lg bg-zinc-800 py-1.5 text-xs text-zinc-300 transition hover:bg-zinc-700 disabled:opacity-40"
        >
          Set
        </button>
      </div>
    </div>
  );
}
