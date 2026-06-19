import { useState } from "react";
import ExtractionApp from "./ExtractionApp";
import ReviewerApp from "./reviewer/ReviewerApp";
import EstimateReport from "./reviewer/EstimateReport";
import ActivityFeed from "./reviewer/ActivityFeed";
import UploadScreen from "./reviewer/UploadScreen";
import DrawbackTypeStep from "./reviewer/DrawbackTypeStep";
import HowItsCalculated from "./reviewer/HowItsCalculated";
import BomEntry from "./reviewer/BomEntry";
import Journey from "./reviewer/Journey";
import "./App.css";

type Tab =
  | "upload"
  | "drawbackType"
  | "journey"
  | "extraction"
  | "reviewer"
  | "estimate"
  | "activity"
  | "howCalculated"
  | "bom";

export default function App() {
  const [tab, setTab] = useState<Tab>("reviewer");
  const [drawbackType, setDrawbackType] = useState("unused_substitution");

  return (
    <div className="app-root">
      <nav className="app-nav">
        <button
          type="button"
          className={tab === "upload" ? "nav-active" : ""}
          onClick={() => setTab("upload")}
        >
          Upload
        </button>
        <button
          type="button"
          className={tab === "journey" ? "nav-active" : ""}
          onClick={() => setTab("journey")}
        >
          Guided Journey
        </button>
        <button
          type="button"
          className={tab === "extraction" ? "nav-active" : ""}
          onClick={() => setTab("extraction")}
        >
          7501 Extraction
        </button>
        <button
          type="button"
          className={tab === "reviewer" ? "nav-active" : ""}
          onClick={() => setTab("reviewer")}
        >
          Match Reviewer
        </button>
        <button
          type="button"
          className={tab === "estimate" ? "nav-active" : ""}
          onClick={() => setTab("estimate")}
        >
          Recovery Estimate
        </button>
        <button
          type="button"
          className={tab === "activity" ? "nav-active" : ""}
          onClick={() => setTab("activity")}
        >
          Pipeline Run
        </button>
        <button
          type="button"
          className={tab === "howCalculated" ? "nav-active" : ""}
          onClick={() => setTab("howCalculated")}
        >
          How It's Calculated
        </button>
        <button
          type="button"
          className={tab === "bom" ? "nav-active" : ""}
          onClick={() => setTab("bom")}
        >
          Bill of Materials
        </button>
      </nav>
      {tab === "upload" && <UploadScreen onRun={() => setTab("drawbackType")} />}
      {tab === "drawbackType" && (
        <DrawbackTypeStep
          onContinue={(choice) => {
            setDrawbackType(choice.drawback_type);
            setTab(choice.needs_bom ? "bom" : "activity");
          }}
        />
      )}
      {tab === "journey" && <Journey onBom={() => setTab("bom")} />}
      {tab === "extraction" && <ExtractionApp />}
      {tab === "reviewer" && <ReviewerApp />}
      {tab === "estimate" && <EstimateReport />}
      {tab === "activity" && <ActivityFeed drawbackType={drawbackType} />}
      {tab === "howCalculated" && <HowItsCalculated />}
      {tab === "bom" && <BomEntry />}
    </div>
  );
}
