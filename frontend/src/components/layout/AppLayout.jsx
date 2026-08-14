import Sidebar from "./Sidebar";
import Topbar from "./Topbar";

export default function AppLayout({ children }) {
  return (
    <div className="app-shell">
      <Sidebar />

      <div className="app-content">
        <Topbar />

        <main className="page-content">
          {children}
        </main>
      </div>
    </div>
  );
}