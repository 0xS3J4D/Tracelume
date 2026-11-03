import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import "./index.css";
import Layout from "./components/Layout";
import CasesPage from "./pages/CasesPage";
import CasePage from "./pages/CasePage";
import JobPage from "./pages/JobPage";
import SettingsPage from "./pages/SettingsPage";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<CasesPage />} />
          <Route path="/cases/:caseId/:tab?" element={<CasePage />} />
          <Route path="/jobs/:jobId" element={<JobPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
);
