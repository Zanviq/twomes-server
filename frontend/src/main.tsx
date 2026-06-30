import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";
import { useTheme, attachThemeListener } from "./store/theme";

// 저장된 테마 적용 + 시스템 변경 구독
useTheme.getState().apply();
attachThemeListener();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
