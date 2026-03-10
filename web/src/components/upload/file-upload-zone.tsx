"use client";

import { useCallback, useState } from "react";
import { useDropzone, type FileRejection } from "react-dropzone";
import { Upload, FileImage, AlertCircle, Loader2 } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

interface FileUploadZoneProps {
  onFileAccepted: (file: File) => void;
  isProcessing?: boolean;
  accept?: Record<string, string[]>;
  maxSize?: number;
  className?: string;
}

const DEFAULT_ACCEPT = {
  "image/jpeg": [".jpg", ".jpeg"],
  "image/png": [".png"],
  "image/webp": [".webp"],
  "image/heic": [".heic"],
  "image/heif": [".heif"],
};

export function FileUploadZone({
  onFileAccepted,
  isProcessing = false,
  accept = DEFAULT_ACCEPT,
  maxSize = 10 * 1024 * 1024,
  className,
}: FileUploadZoneProps) {
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(
    (accepted: File[], rejected: FileRejection[]) => {
      setError(null);

      if (rejected.length > 0) {
        const err = rejected[0].errors[0];
        if (err.code === "file-too-large") {
          setError("File is too large. Maximum size is 10MB.");
        } else if (err.code === "file-invalid-type") {
          setError("Invalid file type. Please upload a JPG, PNG, or WEBP image.");
        } else {
          setError(err.message);
        }
        return;
      }

      if (accepted.length > 0) {
        onFileAccepted(accepted[0]);
      }
    },
    [onFileAccepted],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept,
    maxSize,
    multiple: false,
    disabled: isProcessing,
  });

  return (
    <div className={className}>
      <div
        {...getRootProps()}
        className={cn(
          "group relative flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 transition-all duration-200",
          isDragActive
            ? "border-violet-500 bg-violet-500/10"
            : "border-border/50 bg-card/30 hover:border-violet-500/50 hover:bg-card/50",
          isProcessing && "pointer-events-none opacity-60",
        )}
      >
        <input {...getInputProps()} />

        <AnimatePresence mode="wait">
          {isProcessing ? (
            <motion.div
              key="processing"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              className="flex flex-col items-center gap-3"
            >
              <Loader2 className="h-10 w-10 animate-spin text-violet-500" />
              <p className="text-sm text-muted-foreground">Processing image...</p>
            </motion.div>
          ) : isDragActive ? (
            <motion.div
              key="drag"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              className="flex flex-col items-center gap-3"
            >
              <FileImage className="h-10 w-10 text-violet-500" />
              <p className="text-sm font-medium text-violet-500">
                Drop your image here
              </p>
            </motion.div>
          ) : (
            <motion.div
              key="idle"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex flex-col items-center gap-3"
            >
              <div className="rounded-full bg-violet-500/10 p-3 transition-colors group-hover:bg-violet-500/20">
                <Upload className="h-6 w-6 text-violet-500" />
              </div>
              <div className="text-center">
                <p className="text-sm font-medium text-foreground">
                  Drag & drop your W-2 image
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  or click to browse &middot; JPG, PNG, WEBP &middot; max 10MB
                </p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className="mt-2 flex items-center gap-2 text-sm text-destructive"
          >
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
