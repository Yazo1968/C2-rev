import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import Login from "./pages/Login";
import Projects from "./pages/Projects";
import Upload from "./pages/Upload";
import Query from "./pages/Query";
import Audit from "./pages/Audit";
import { RequireAuth } from "./lib/auth";

const queryClient = new QueryClient();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<RequireAuth><App /></RequireAuth>}>
            <Route index element={<Navigate to="/projects" replace />} />
            <Route path="/projects" element={<Projects />} />
            <Route path="/project/:projectId/upload" element={<Upload />} />
            <Route path="/project/:projectId/query" element={<Query />} />
            <Route path="/project/:projectId/audit" element={<Audit />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
