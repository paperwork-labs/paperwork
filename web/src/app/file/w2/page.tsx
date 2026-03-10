"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Camera, Upload, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FileUploadZone } from "@/components/upload/file-upload-zone";
import { useFilingStore, type W2Data } from "@/stores/filing-store";
import { slideInUp } from "@/lib/motion";
import api from "@/lib/api";

function formatCents(cents: number): string {
  return `$${(cents / 100).toLocaleString("en-US", { minimumFractionDigits: 2 })}`;
}

export default function W2Page() {
  const router = useRouter();
  const { w2s, addW2, removeW2, setCurrentStep } = useFilingStore();
  const [isProcessing, setIsProcessing] = useState(false);

  async function handleFile(file: File) {
    setIsProcessing(true);
    try {
      const formData = new FormData();
      formData.append("file", file);

      const { data } = await api.post("/api/v1/documents/demo-upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      const fields = data.data.fields;
      const w2: W2Data = {
        employer_name: fields.employer_name || "",
        employer_ein: fields.employer_ein || "",
        employer_address: fields.employer_address || "",
        employee_name: fields.employee_name || "",
        employee_address: fields.employee_address || "",
        ssn_last_four: fields.ssn_last_four || "",
        wages: fields.wages || 0,
        federal_tax_withheld: fields.federal_tax_withheld || 0,
        social_security_wages: fields.social_security_wages || 0,
        social_security_tax: fields.social_security_tax || 0,
        medicare_wages: fields.medicare_wages || 0,
        medicare_tax: fields.medicare_tax || 0,
        state: fields.state || "",
        state_wages: fields.state_wages || 0,
        state_tax_withheld: fields.state_tax_withheld || 0,
        confidence: data.data.confidence,
      };

      addW2(w2);
      toast.success("W-2 scanned successfully!");
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Failed to process W-2";
      toast.error(message);
    } finally {
      setIsProcessing(false);
    }
  }

  function handleContinue() {
    setCurrentStep(1);
    router.push("/file/confirm");
  }

  return (
    <motion.div
      className="space-y-6"
      initial="hidden"
      animate="visible"
      variants={slideInUp}
    >
      <div>
        <h2 className="text-2xl font-bold text-foreground">
          Upload your W-2
        </h2>
        <p className="mt-1 text-muted-foreground">
          Take a photo or upload an image of your W-2 form. Our AI will extract
          the data automatically.
        </p>
      </div>

      {w2s.map((w2, index) => (
        <Card key={index} className="border-border/50">
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <CardTitle className="text-base">
              {w2.employer_name || `W-2 #${index + 1}`}
            </CardTitle>
            <button
              onClick={() => removeW2(index)}
              className="text-muted-foreground hover:text-destructive transition"
              aria-label="Remove W-2"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <span className="text-muted-foreground">Wages (Box 1)</span>
                <p className="font-medium">{formatCents(w2.wages)}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Federal Withheld (Box 2)</span>
                <p className="font-medium">{formatCents(w2.federal_tax_withheld)}</p>
              </div>
              <div>
                <span className="text-muted-foreground">SSN</span>
                <p className="font-medium">
                  XXX-XX-{w2.ssn_last_four || "????"}
                </p>
              </div>
              <div>
                <span className="text-muted-foreground">EIN</span>
                <p className="font-medium">{w2.employer_ein || "—"}</p>
              </div>
              {w2.confidence !== undefined && (
                <div className="col-span-2">
                  <span className="text-muted-foreground">Confidence</span>
                  <div className="mt-1 flex items-center gap-2">
                    <div className="h-1.5 flex-1 rounded-full bg-muted">
                      <div
                        className={`h-full rounded-full transition-all ${
                          w2.confidence >= 0.9
                            ? "bg-green-500"
                            : w2.confidence >= 0.7
                              ? "bg-yellow-500"
                              : "bg-red-500"
                        }`}
                        style={{ width: `${w2.confidence * 100}%` }}
                      />
                    </div>
                    <span className="text-xs font-medium">
                      {Math.round(w2.confidence * 100)}%
                    </span>
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      ))}

      {w2s.length === 0 ? (
        <FileUploadZone
          onFileAccepted={handleFile}
          isProcessing={isProcessing}
          className="min-h-[240px]"
        />
      ) : (
        <button
          onClick={() => {
            const input = document.createElement("input");
            input.type = "file";
            input.accept = "image/jpeg,image/png,image/webp,image/heic";
            input.onchange = (e) => {
              const file = (e.target as HTMLInputElement).files?.[0];
              if (file) handleFile(file);
            };
            input.click();
          }}
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-border/50 p-4 text-sm text-muted-foreground hover:text-foreground hover:border-border transition"
        >
          <Plus className="h-4 w-4" />
          Add another W-2
        </button>
      )}

      {w2s.length > 0 && (
        <Button
          onClick={handleContinue}
          className="w-full h-12 bg-gradient-to-r from-violet-600 to-purple-600 text-white border-0 hover:from-violet-500 hover:to-purple-500 text-base font-semibold"
        >
          Continue to Review
        </Button>
      )}
    </motion.div>
  );
}
