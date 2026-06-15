"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { api, errorMessage } from "@/lib/api/client";

export default function UploadPage() {
  const router = useRouter();
  const fileInput = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [dragOver, setDragOver] = useState(false);

  const pickFile = (f: File | null) => {
    setError("");
    if (f && !f.name.toLowerCase().endsWith(".pdf")) {
      setError("Only PDF files are accepted");
      return;
    }
    setFile(f);
  };

  const upload = async () => {
    if (!file) return;
    setUploading(true);
    setError("");
    setNotice("");
    setProgress("Uploading file...");

    try {
      const { data } = await api.uploadTender(file);
      const jobId = data.job_id;

      // No background worker available: file is stored but won't be analyzed.
      if (!jobId || data.status === "stored") {
        setProgress("");
        setNotice(
          data.message ||
            "Tender stored, but background processing is unavailable. Start the worker stack (Redis + Celery + OpenAI/Qdrant) to analyze it."
        );
        setUploading(false);
        return;
      }

      setProgress("Processing tender (extracting, embedding)...");

      // Poll job status
      const poll = setInterval(async () => {
        try {
          const status = (await api.getJobStatus(jobId)).data;
          if (status.status === "SUCCESS") {
            clearInterval(poll);
            setProgress("Done! Redirecting...");
            router.push(`/dashboard/tenders/${data.tender_id}`);
          } else if (status.status === "FAILURE") {
            try {
              const tender = (await api.getTenderStatus(data.tender_id)).data;
              if (tender.status === "completed") {
                clearInterval(poll);
                setProgress("Done! Redirecting...");
                router.push(`/dashboard/tenders/${data.tender_id}`);
                return;
              }
              clearInterval(poll);
              setError(tender.error_message || status.error || "Processing failed. Please try again.");
            } catch {
              clearInterval(poll);
              setError(status.error || "Processing failed. Please try again.");
            }
            setUploading(false);
          } else if (status.progress) {
            setProgress(`Processing... ${status.progress}%`);
          }
        } catch {
          // keep polling
        }
      }, 3000);
    } catch (err: any) {
      setError(errorMessage(err, "Upload failed"));
      setUploading(false);
    }
  };

  return (
    <div className="p-8 max-w-2xl">
      <h1 className="text-2xl font-bold text-slate-900">Upload Tender</h1>
      <p className="mt-1 text-slate-500">
        Upload a tender PDF to extract details and get a bid score
      </p>

      {error && (
        <div className="mt-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">
          {error}
        </div>
      )}

      {notice && (
        <div className="mt-4 p-3 bg-amber-50 text-amber-800 rounded-lg text-sm">
          ✓ {notice}{" "}
          <button
            onClick={() => router.push("/dashboard")}
            className="underline font-medium"
          >
            View tenders
          </button>
        </div>
      )}

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          pickFile(e.dataTransfer.files[0]);
        }}
        onClick={() => fileInput.current?.click()}
        className={`mt-6 p-12 border-2 border-dashed rounded-xl text-center cursor-pointer transition ${
          dragOver ? "border-brand-500 bg-brand-50" : "border-slate-300 bg-white"
        }`}
      >
        <input
          ref={fileInput}
          type="file"
          accept=".pdf"
          className="hidden"
          onChange={(e) => pickFile(e.target.files?.[0] || null)}
        />
        {file ? (
          <div>
            <p className="text-slate-900 font-medium">{file.name}</p>
            <p className="text-sm text-slate-500 mt-1">
              {(file.size / 1024 / 1024).toFixed(2)} MB
            </p>
          </div>
        ) : (
          <div>
            <p className="text-slate-600">
              Drag & drop a PDF here, or click to browse
            </p>
            <p className="text-sm text-slate-400 mt-1">Max 50 MB</p>
          </div>
        )}
      </div>

      {progress && (
        <div className="mt-4 p-3 bg-blue-50 text-blue-700 rounded-lg text-sm">
          {progress}
        </div>
      )}

      <button
        onClick={upload}
        disabled={!file || uploading}
        className="mt-6 px-6 py-2.5 bg-brand-600 text-white rounded-lg font-medium hover:bg-brand-700 disabled:opacity-50"
      >
        {uploading ? "Processing..." : "Upload & Analyze"}
      </button>
    </div>
  );
}
