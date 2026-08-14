import {
  BrainCircuit,
  ShieldCheck,
  History,
  Database,
  BookOpen,
  ReceiptText,
} from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import keymanageIcon from "../../assets/keymanage-ai-robot-logo-transparent.png";

const items = [
  {
    hidden: true,
    label: "Dashboard",
    icon: BrainCircuit,
    path: "/dashboard",
    children: [
      { label: "KPI globaux", hash: "#kpi-globaux" },
      { label: "Alertes IA", hash: "#alertes-ia" },
      { label: "Activite recente", hash: "#activite-recente" },
      { label: "Niveau de confiance", hash: "#niveau-confiance" },
      {
        label: "Repartition Auto OK / Validation",
        hash: "#repartition-auto-validation",
      },
      { label: "Metiers a risque", hash: "#metiers-a-risque" },
    ],
  },
  {
    label: "Analyse IA",
    icon: BrainCircuit,
    path: "/analysis",
  },
  {
    label: "Validation humaine",
    icon: ShieldCheck,
    path: "/validation",
  },
  {
    label: "Historique",
    icon: History,
    path: "/history",
  },
  {
    label: "Écritures Validées",
    icon: ReceiptText,
    path: "/ecritures-validees",
  },
  {
    label: "Performance & mémoire IA",
    icon: Database,
    path: "/memory",
  },
  {
    label: "Bases metiers",
    icon: BookOpen,
    path: "/bases-metiers",
  },
];

export default function Sidebar() {
  const location = useLocation();
  const visibleItems = items.filter((item) => !item.hidden);
  const [expandedPath, setExpandedPath] = useState("/analysis");

  const toggleSection = (path) => {
    setExpandedPath((currentPath) =>
      currentPath === path ? null : path,
    );
  };

  useEffect(() => {
    const activeItem =
      items.find((item) =>
        item.path === "/dashboard"
          ? location.pathname === "/dashboard"
          : location.pathname.startsWith(item.path),
      ) ?? visibleItems[0];

    setExpandedPath(activeItem.path);
  }, [location.pathname]);

  return (
    <aside className="sidebar">
      <div>
        <div className="logo">
          <span className="logo-mark-shell">
            <img
              src={keymanageIcon}
              alt="KeyManage AI"
              className="logo-mark"
            />
          </span>

          <div>
            <h2>KeyManage AI</h2>
            <p>Accounting Engine</p>
          </div>
        </div>

        <nav className="sidebar-nav">
          {visibleItems.map((item) => {
            const Icon = item.icon;
            const isExpanded = expandedPath === item.path;
            const isExpandable = Boolean(item.children?.length);

            return (
              <div
                key={item.path}
                className={`sidebar-item-group${
                  isExpanded ? " expanded" : ""
                }`}
              >
                <div className="sidebar-link-row">
                  <NavLink
                    to={item.path}
                    end={item.path === "/dashboard"}
                    className={({ isActive }) =>
                      isActive
                        ? "sidebar-link active sidebar-link-main"
                        : "sidebar-link sidebar-link-main"
                    }
                    onClick={() => setExpandedPath(item.path)}
                  >
                    <Icon size={18} />

                    <span className="sidebar-link-copy">
                      {item.label}
                    </span>
                  </NavLink>

                  {isExpandable ? (
                    <button
                      type="button"
                      className="sidebar-chevron-btn"
                      aria-label={
                        isExpanded
                          ? `Replier ${item.label}`
                          : `Deplier ${item.label}`
                      }
                      onClick={(event) => {
                        event.preventDefault();
                        event.stopPropagation();
                        toggleSection(item.path);
                      }}
                    >
                      <span
                        className={`sidebar-chevron-glyph${
                          isExpanded ? " open" : ""
                        }`}
                        aria-hidden="true"
                      >
                        {">"}
                      </span>
                    </button>
                  ) : null}
                </div>

                {isExpanded && isExpandable ? (
                  <div className="sidebar-subnav">
                    {item.children.map((child) => (
                      <NavLink
                        key={`${item.path}${child.hash}`}
                        to={{
                          pathname: item.path,
                          hash: child.hash,
                        }}
                        end={false}
                        className={({ isActive }) => {
                          const hashActive =
                            isActive &&
                            location.hash === child.hash;

                          return hashActive
                            ? "sidebar-sublink active"
                            : "sidebar-sublink";
                        }}
                      >
                        <span>{child.label}</span>
                      </NavLink>
                    ))}
                  </div>
                ) : null}
              </div>
            );
          })}
        </nav>
      </div>

    </aside>
  );
}






