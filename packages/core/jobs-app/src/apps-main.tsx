import React from "react"
import { createRoot } from "react-dom/client"
import "./index.css"
import { AppsPage } from "./AppsPage"
createRoot(document.getElementById("root")!).render(<AppsPage initial={(window as any).__INITIAL__} />)
