"use client";

import { Suspense } from "react";
import { redirect } from "next/navigation";

// The Waste Optimizer is the core value of the app - make it the home page
export default function HomePage() {
  redirect("/waste-analysis");
}
