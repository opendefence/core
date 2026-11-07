"use client";

import { createFileRoute } from "@tanstack/react-router";
import { useRequireSuperadmin } from "@/hooks/auth/useRequireSuperadmin";
import { Forbidden } from "@/components/Forbidden";
import { useNavigate } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { Users, Shield, FileText, type LucideIcon } from "lucide-react";

type AdminToolsSearch = {
  type?: "users" | "services" | "all";
};

export const Route = createFileRoute("/admin-tools")({
  component: AdminToolsPage,
  validateSearch: (search: Record<string, unknown>): AdminToolsSearch => {
    const validTypes = ["users", "services", "all"];
    return {
      type: validTypes.includes(search.type as string)
        ? (search.type as "users" | "services" | "all")
        : undefined,
    };
  },
});

interface MenuItem {
  icon: LucideIcon;
  titleKey?: string;
  descKey?: string;
  title?: string;
  description?: string;
  action:
    | { type: "navigate"; to: string; search?: Record<string, unknown> }
    | { type: "external"; url: string };
}

interface MenuSection {
  titleKey: string;
  items: MenuItem[];
}

interface AdminToolCardProps {
  item: MenuItem;
  onAction: (item: MenuItem) => void;
}

function AdminToolCard({ item, onAction }: AdminToolCardProps) {
  const { t } = useTranslation();
  const Icon = item.icon;
  const title = item.title ?? (item.titleKey ? t(item.titleKey) : "");
  const description = item.description ?? (item.descKey ? t(item.descKey) : "");

  const cardKey = item.titleKey ?? item.title ?? "unknown";

  const content = (
    <>
      <div className="p-4 rounded-xl bg-primary/10 group-hover:bg-primary/20 transition-colors flex items-center justify-center">
        <Icon className="w-8 h-8 text-primary" />
      </div>
      <div className="flex flex-col">
        <h3 className="font-semibold text-xl mb-1">{title}</h3>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
    </>
  );

  const className =
    "group flex items-center gap-6 p-6 w-full border border-border rounded-2xl bg-card hover:border-primary hover:shadow-lg hover:bg-card/80 transition-all duration-300 cursor-pointer";

  if (item.action.type === "external") {
    return (
      <a
        data-testid="admin-tool-card"
        data-admin-tool-key={cardKey}
        data-admin-tool-action="external"
        href={item.action.url}
        target="_blank"
        rel="noopener noreferrer"
        className={className}
      >
        {content}
      </a>
    );
  }

  return (
    <a
      data-testid="admin-tool-card"
      data-admin-tool-key={cardKey}
      data-admin-tool-action={item.action.type}
      onClick={() => onAction(item)}
      className={className}
    >
      {content}
    </a>
  );
}

function AdminToolsPage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { isLoading: userTypeLoading, allowed } = useRequireSuperadmin({
    noCallsign: "approveUsers.noCallsignFound",
    forbidden: "adminTools.forbiddenAdminAccess",
  });
  const { type } = Route.useSearch();

  const typeSelectorItems: MenuItem[] = [
    {
      icon: Users,
      titleKey: "common.userManagement",
      descKey: "adminTools.userManagementDesc",
      action: {
        type: "navigate",
        to: "/admin-tools",
        search: { type: "users" },
      },
    },
  ];

  const menuSections: MenuSection[] = [
    {
      titleKey: "common.userManagement",
      items: [
        {
          icon: Users,
          titleKey: "common.manageUsers",
          descKey: "adminTools.manageUsersDesc",
          action: { type: "navigate", to: "/manage-users" },
        },
        {
          icon: FileText,
          titleKey: "common.addUsers",
          descKey: "adminTools.addUsersDesc",
          action: { type: "navigate", to: "/add-users" },
        },
        {
          icon: Shield,
          titleKey: "common.approveUsers",
          descKey: "adminTools.approveUsersDesc",
          action: { type: "navigate", to: "/approve-users" },
        },
      ],
    },
  ];

  const handleAction = (item: MenuItem) => {
    if (item.action.type === "navigate") {
      navigate({ to: item.action.to, search: item.action.search });
    }
  };

  const showUserTools = type === "users" || type === "all";
  const showTypeSelector = !type;

  if (!userTypeLoading && !allowed) {
    return (
      <Forbidden
        testid="admin-tools-forbidden"
        className="w-full max-w-2xl"
        message={t("adminTools.forbiddenAdminAccess")}
      />
    );
  }

  if (userTypeLoading) {
    return (
      <div
        data-testid="admin-tools-loading"
        className="w-full max-w-2xl mx-auto space-y-6"
      >
        <h1 className="text-3xl font-bold">{t("adminTools.navLink")}</h1>
        <div className="flex items-center justify-center py-12">
          <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  if (showTypeSelector) {
    return (
      <div
        data-testid="admin-tools-type-selector"
        className="w-full max-w-2xl mx-auto"
      >
        <div className="space-y-8">
          <div className="space-y-3 pt-8 text-center">
            <h1 className="text-4xl font-bold">{t("adminTools.navLink")}</h1>
            <p className="text-sm text-muted-foreground leading-relaxed">
              {t("adminTools.description")}
            </p>
          </div>

          <div data-testid="admin-tools-grid" className="grid gap-4">
            {typeSelectorItems.map((item) => (
              <AdminToolCard
                key={item.titleKey}
                item={item}
                onAction={handleAction}
              />
            ))}
          </div>
        </div>
      </div>
    );
  }

  const visibleSections = showUserTools ? menuSections : [];

  return (
    <div
      data-testid="admin-tools-page"
      data-admin-tools-type={type ?? "none"}
      className="w-full max-w-2xl mx-auto"
    >
      <div className="space-y-8">
        {visibleSections.map((section) => (
          <div
            data-testid="admin-tools-section-group"
            data-section-key={section.titleKey}
            key={section.titleKey}
            className="space-y-4"
          >
            <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              {t(section.titleKey)}
            </h2>

            <div data-testid="admin-tools-grid" className="grid gap-4">
              {section.items.map((item) => (
                <AdminToolCard
                  key={item.titleKey ?? item.title}
                  item={item}
                  onAction={handleAction}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
