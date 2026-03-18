"use client";

import { useState, forwardRef, type ChangeEvent } from "react";
import { Eye, EyeOff, Lock } from "lucide-react";
import { Input, cn } from "@paperwork-labs/ui";

interface SSNInputProps {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  className?: string;
}

function formatSSN(raw: string): string {
  const digits = raw.replace(/\D/g, "").slice(0, 9);
  if (digits.length <= 3) return digits;
  if (digits.length <= 5) return `${digits.slice(0, 3)}-${digits.slice(3)}`;
  return `${digits.slice(0, 3)}-${digits.slice(3, 5)}-${digits.slice(5)}`;
}

export const SSNInput = forwardRef<HTMLInputElement, SSNInputProps>(
  function SSNInput({ value, onChange, disabled, className }, ref) {
    const [visible, setVisible] = useState(false);

    function handleChange(e: ChangeEvent<HTMLInputElement>) {
      const formatted = formatSSN(e.target.value);
      onChange(formatted);
    }

    return (
      <div className={cn("relative", className)}>
        <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          ref={ref}
          type={visible ? "text" : "password"}
          inputMode="numeric"
          value={value}
          onChange={handleChange}
          disabled={disabled}
          className="pl-9 pr-10 font-mono"
          placeholder="XXX-XX-XXXX"
          maxLength={11}
        />
        <button
          type="button"
          onClick={() => setVisible(!visible)}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          aria-label={visible ? "Hide SSN" : "Show SSN"}
          aria-pressed={visible}
        >
          {visible ? (
            <EyeOff className="h-4 w-4" />
          ) : (
            <Eye className="h-4 w-4" />
          )}
        </button>
      </div>
    );
  }
);
