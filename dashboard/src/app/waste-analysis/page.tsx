import { redirect } from "next/navigation";

// Redirect /waste-analysis to / for backwards compatibility
// The Waste Optimizer is now the homepage
export default function WasteAnalysisRedirect() {
  redirect("/");
}
