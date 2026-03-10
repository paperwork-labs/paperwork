"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Camera, RotateCcw, Check, X, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface DocumentCameraProps {
  onCapture: (file: File) => void;
  onError?: (error: string) => void;
  onClose?: () => void;
  documentType?: string;
}

type CameraState = "initializing" | "ready" | "captured" | "error";

export function DocumentCamera({
  onCapture,
  onError,
  onClose,
  documentType = "W-2",
}: DocumentCameraProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const [state, setState] = useState<CameraState>("initializing");
  const [capturedImage, setCapturedImage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const startCamera = useCallback(async () => {
    setState("initializing");
    setErrorMessage(null);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: "environment" },
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
      });

      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        setState("ready");
      }
    } catch (err) {
      const message =
        err instanceof DOMException && err.name === "NotAllowedError"
          ? "Camera access denied. Please allow camera access in your browser settings."
          : "Could not access camera. Try uploading an image instead.";

      setErrorMessage(message);
      setState("error");
      onError?.(message);
    }
  }, [onError]);

  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
  }, []);

  useEffect(() => {
    startCamera();
    return stopCamera;
  }, [startCamera, stopCamera]);

  const capture = useCallback(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext("2d")!;
    ctx.drawImage(video, 0, 0);

    const dataUrl = canvas.toDataURL("image/jpeg", 0.92);
    setCapturedImage(dataUrl);
    setState("captured");
    stopCamera();
  }, [stopCamera]);

  const retake = useCallback(() => {
    setCapturedImage(null);
    startCamera();
  }, [startCamera]);

  const confirm = useCallback(() => {
    if (!capturedImage) return;

    const byteString = atob(capturedImage.split(",")[1]);
    const mimeType = capturedImage.split(":")[1].split(";")[0];
    const ab = new ArrayBuffer(byteString.length);
    const ia = new Uint8Array(ab);
    for (let i = 0; i < byteString.length; i++) {
      ia[i] = byteString.charCodeAt(i);
    }
    const file = new File([ab], `${documentType.toLowerCase()}-capture.jpg`, {
      type: mimeType,
    });
    onCapture(file);
  }, [capturedImage, documentType, onCapture]);

  return (
    <div className="relative mx-auto w-full max-w-lg overflow-hidden rounded-xl border border-border/50 bg-black">
      <canvas ref={canvasRef} className="hidden" />

      <div className="relative aspect-[3/4]">
        <AnimatePresence mode="wait">
          {state === "initializing" && (
            <motion.div
              key="init"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 flex flex-col items-center justify-center gap-3"
            >
              <Loader2 className="h-8 w-8 animate-spin text-violet-500" />
              <p className="text-sm text-muted-foreground">
                Starting camera...
              </p>
            </motion.div>
          )}

          {state === "error" && (
            <motion.div
              key="error"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 flex flex-col items-center justify-center gap-4 px-6"
            >
              <div className="rounded-full bg-destructive/10 p-3">
                <X className="h-6 w-6 text-destructive" />
              </div>
              <p className="text-center text-sm text-muted-foreground">
                {errorMessage}
              </p>
              <Button variant="outline" size="sm" onClick={onClose}>
                Close
              </Button>
            </motion.div>
          )}

          {(state === "ready" || state === "captured") && (
            <motion.div
              key="camera"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0"
            >
              <video
                ref={videoRef}
                playsInline
                muted
                className={cn(
                  "h-full w-full object-cover",
                  state === "captured" && "hidden",
                )}
              />

              {state === "captured" && capturedImage && (
                <img
                  src={capturedImage}
                  alt="Captured document"
                  className="h-full w-full object-cover"
                />
              )}

              {state === "ready" && (
                <div className="pointer-events-none absolute inset-0">
                  <div className="absolute inset-6 rounded-lg border-2 border-white/30" />
                  <div className="absolute bottom-8 left-0 right-0 text-center">
                    <p className="text-sm font-medium text-white drop-shadow-lg">
                      Position your {documentType} within the frame
                    </p>
                  </div>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <div className="flex items-center justify-center gap-4 bg-background/80 p-4 backdrop-blur">
        {state === "ready" && (
          <>
            {onClose && (
              <Button variant="ghost" size="icon" onClick={onClose}>
                <X className="h-5 w-5" />
              </Button>
            )}
            <Button
              size="lg"
              className="h-14 w-14 rounded-full bg-white hover:bg-white/90"
              onClick={capture}
            >
              <Camera className="h-6 w-6 text-black" />
            </Button>
            <div className="w-10" />
          </>
        )}

        {state === "captured" && (
          <>
            <Button variant="outline" onClick={retake}>
              <RotateCcw className="mr-2 h-4 w-4" />
              Retake
            </Button>
            <Button
              className="bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500"
              onClick={confirm}
            >
              <Check className="mr-2 h-4 w-4" />
              Use Photo
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
