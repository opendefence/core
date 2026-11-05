"use client";

import { createFileRoute } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { Forbidden } from "@/components/Forbidden";
import { GroupDetail, GroupTree } from "@/components/manage-groups";
import { useGroupManagement } from "@/hooks/useGroupManagement";

export const Route = createFileRoute("/manage-groups")({
  component: ManageGroupsPage,
});

function ManageGroupsPage() {
  const { t } = useTranslation();
  const {
    tree,
    selectedGroup,
    parent,
    inherited,
    selectGroup,
    isLoading,
    userTypeLoading,
    allowed,
  } = useGroupManagement();

  if (!userTypeLoading && !allowed) {
    return (
      <Forbidden
        testid="manage-groups-forbidden"
        message={t("manageGroups.forbidden")}
      />
    );
  }

  if (isLoading || userTypeLoading) {
    return (
      <div className="max-w-4xl mx-auto space-y-6">
        <h1 className="text-3xl font-bold">{t("manageGroups.title")}</h1>
        <div className="flex items-center justify-center py-12">
          <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  return (
    <div
      className="max-w-4xl mx-auto space-y-6"
      data-testid="manage-groups-page"
    >
      <div className="space-y-2 mt-4">
        <h1 className="text-3xl font-bold">{t("manageGroups.title")}</h1>
        <p className="text-sm text-muted-foreground">
          {t("manageGroups.description")}
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
        <div className="p-4 bg-card border-2 border-border rounded-xl">
          <GroupTree
            tree={tree}
            selectedId={selectedGroup?.id}
            onSelect={selectGroup}
          />
        </div>
        <div className="p-5 bg-card border-2 border-border rounded-xl">
          <GroupDetail
            group={selectedGroup}
            parent={parent}
            inherited={inherited}
          />
        </div>
      </div>
    </div>
  );
}
