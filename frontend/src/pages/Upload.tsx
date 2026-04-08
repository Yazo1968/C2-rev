import { useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../lib/api";

// Heuristic: presence of /Font in the raw bytes is a strong indicator of a
// digital PDF. We sample the first 256KB to keep this cheap. If we don't see
// any font dictionary entry, we assume it's scanned and surface the EU OCR
// banner before triggering ingestion.
async function looksScanned(file: File): Promise<boolean> {
  const slice = await file.slice(0, 256 * 1024).arrayBuffer();
  const text = new TextDecoder("latin1").decode(slice);
  return !text.includes("/Font");
}

export default function Upload() {
  const { projectId } = useParams();
  const [file, setFile] = useState<File | null>(null);
  const [layer, setLayer] = useState("L1");
  const [documentType, setDocumentType] = useState("CONTRACT");
  const [scannedWarning, setScannedWarning] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  async function handleFile(f: File) {
    setFile(f);
    setScannedWarning(await looksScanned(f));
  }

  async function submit() {
    if (!file || !projectId) return;
    setStatus("Requesting signed upload URL…");
    // Phase 5.3 simplification: assume the API supplies a signed URL endpoint.
    // For now we POST a placeholder gcs_uri the operator pre-uploads.
    const gcsUri = prompt("Paste the gs:// URI for the uploaded file:") || "";
    if (!gcsUri) {
      setStatus(null);
      return;
    }
    setStatus("Triggering ingestion…");
    try {
      const resp = await api.post("/api/v1/ingest", {
        project_id: projectId,
        layer,
        document_type: documentType,
        gcs_uri: gcsUri,
        file_name: file.name,
      });
      setStatus(`Ingested. document_id=${resp.data.document_id}, chunks=${resp.data.chunk_count}`);
    } catch (err) {
      setStatus(`Error: ${(err as Error).message}`);
    }
  }

  return (
    <div className="max-w-xl space-y-4">
      <h1 className="text-xl font-semibold">Upload document</h1>
      <input
        type="file"
        accept="application/pdf"
        onChange={(e) => e.target.files && handleFile(e.target.files[0])}
      />
      <div className="flex gap-3">
        <label className="text-sm">
          Layer
          <select value={layer} onChange={(e) => setLayer(e.target.value)} className="block border rounded px-2 py-1">
            <option value="L1">L1 — Project documents</option>
            <option value="L2A">L2A — Project policies</option>
          </select>
        </label>
        <label className="text-sm">
          Type
          <select value={documentType} onChange={(e) => setDocumentType(e.target.value)} className="block border rounded px-2 py-1">
            <option value="CONTRACT">Contract</option>
            <option value="CORRESPONDENCE">Correspondence</option>
            <option value="PROGRAMME">Programme</option>
            <option value="POLICY">Policy</option>
            <option value="DRAWING">Drawing</option>
          </select>
        </label>
      </div>
      {scannedWarning && (
        <div className="border-l-4 border-amber-500 bg-amber-50 p-3 text-sm">
          This document appears to be scanned. It will be processed via the
          Document AI <strong>EU endpoint</strong>. Construction document
          content will leave GCC temporarily for text extraction. Continue
          only if your project authorises external OCR.
        </div>
      )}
      <button type="button" className="border rounded px-4 py-2" onClick={submit} disabled={!file}>
        Ingest
      </button>
      {status && <div className="text-sm">{status}</div>}
    </div>
  );
}
