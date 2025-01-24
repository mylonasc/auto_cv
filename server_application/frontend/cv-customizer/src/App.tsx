import React, { useState } from "react";
import axios from "axios";

const App: React.FC = () => {
  const [text, setText] = useState("");
  const [pdfBlob, setPdfBlob] = useState<Blob | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleGeneratePDF = async () => {
    setError(null); // Reset error state
    try {
      const response = await axios.post(
        "http://127.0.0.1:8000/generate-pdf",
        { text },
        { responseType: "blob" } // Expecting a binary response (PDF)
      );
      setPdfBlob(response.data); // Save the Blob to state
    } catch (err: any) {
      console.error("Error generating PDF:", err);
      setError("Failed to generate PDF. Please try again.");
    }
  };

  const handleDownloadPDF = () => {
    if (pdfBlob) {
      const url = window.URL.createObjectURL(pdfBlob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "generated.pdf"; // The filename for download
      link.click();
      window.URL.revokeObjectURL(url); // Clean up the object URL
    }
  };

  return (
    <div style={{ padding: "20px" }}>
      <h1>Text to PDF Generator</h1>
      <textarea
        rows={10}
        cols={50}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Paste your text here..."
        style={{ display: "block", marginBottom: "10px" }}
      ></textarea>
      <button onClick={handleGeneratePDF} style={{ marginBottom: "20px" }}>
        Generate PDF
      </button>
      {error && <p style={{ color: "red" }}>{error}</p>}
      {pdfBlob && (
        <div>
          <h2>Generated PDF:</h2>
          {/* Render the PDF */}
          <iframe
            src={window.URL.createObjectURL(pdfBlob)}
            width="100%"
            height="500px"
            style={{ border: "1px solid #ccc", marginBottom: "10px" }}
          ></iframe>
          {/* Download Button */}
          <button onClick={handleDownloadPDF} style={{ marginTop: "10px" }}>
            Download PDF
          </button>
        </div>
      )}
    </div>
  );
};

export default App;