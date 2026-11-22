"use client";

import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";

import { useApproveUser, useRevokeUser, useUsers } from "@/api/users";
import { useRequireSuperadmin } from "@/hooks/auth/useRequireSuperadmin";
import { Forbidden } from "@/components/Forbidden";

import {
  QRScanner,
  ApproveUserDialog,
  WaitingUsersList,
  HowItWorksSection,
} from "@/components/approve-users";

export const Route = createFileRoute("/approve-users")({
  component: ApproveUsersPage,
});

/** The user being approved: the id acts, the callsign shows. */
interface Waiting {
  id: string;
  callsign: string;
}

function ApproveUsersPage() {
  const [howItWorksOpen, setHowItWorksOpen] = useState(false);
  const [waitingUsersOpen, setWaitingUsersOpen] = useState(true);
  const [approveDialogOpen, setApproveDialogOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<Waiting | null>(null);
  const [approvalCode, setApprovalCode] = useState("");

  const { t } = useTranslation();
  const { isLoading: userTypeLoading, allowed } = useRequireSuperadmin({
    noCallsign: "approveUsers.noCallsignFound",
    forbidden: "approveUsers.forbidden",
  });

  const {
    data: waitingUsers = [],
    isLoading,
    refetch,
  } = useUsers("pending", 5000);

  const approveUserMutation = useApproveUser({
    onSuccess: () => {
      toast.success(
        t("approveUsers.userApprovedSuccessfully", {
          callsign: selectedUser?.callsign,
        }),
      );
      setApproveDialogOpen(false);
      setApprovalCode("");
      setSelectedUser(null);
      refetch();
    },
    onError: (error) => {
      toast.error(t("approveUsers.failedToApprove", { error: error.message }));
    },
  });

  const rejectUserMutation = useRevokeUser({
    onSuccess: () => {
      toast.error(
        t("approveUsers.userRejected", { callsign: selectedUser?.callsign }),
      );
      setApproveDialogOpen(false);
      setApprovalCode("");
      setSelectedUser(null);
      refetch();
    },
    onError: (error) => {
      toast.error(t("approveUsers.failedToReject", { error: error.message }));
    },
  });

  const handleApproveClick = (user: Waiting) => {
    setSelectedUser(user);
    setApproveDialogOpen(true);
  };

  const handleApprove = () => {
    if (!approvalCode.trim()) {
      toast.error(t("approveUsers.enterApprovalCodeMessage"));
      return;
    }
    if (!selectedUser) return;
    approveUserMutation.mutate({ userId: selectedUser.id, approvalCode });
  };

  const handleReject = () => {
    if (!selectedUser) return;
    rejectUserMutation.mutate(selectedUser.id);
  };

  const handleQRRead = (data: string) => {
    let url: URL;
    try {
      url = new URL(data);
    } catch {
      // Not a link, so a bare approval code
      setApprovalCode(data);
      toast.success(t("approveUsers.approvalCodeScanned"));
      return true;
    }
    const id = url.searchParams.get("user");
    const callsign = url.searchParams.get("callsign");
    const code = url.searchParams.get("approvalcode");
    if (!id || !callsign || !code) {
      toast.error(t("approveUsers.invalidQRFormat"));
      return false;
    }
    setSelectedUser({ id, callsign });
    setApprovalCode(code);
    setApproveDialogOpen(true);
    toast.success(t("approveUsers.qrScannedSuccessfully"));
    return true;
  };

  if (!userTypeLoading && !allowed) {
    return <Forbidden message={t("approveUsers.forbidden")} />;
  }

  if (isLoading || userTypeLoading) {
    return (
      <div className="max-w-4xl mx-auto space-y-6">
        <h1 className="text-3xl font-bold">{t("approveUsers.title")}</h1>
        <div className="flex items-center justify-center py-12">
          <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between mt-4">
        <h1 className="text-3xl font-bold">{t("approveUsers.title")}</h1>
      </div>

      <div className="space-y-4">
        <p className="text-muted-foreground">
          {t("approveUsers.usersAwaiting")}
        </p>

        <HowItWorksSection
          open={howItWorksOpen}
          onOpenChange={setHowItWorksOpen}
        />

        <WaitingUsersList
          users={waitingUsers}
          open={waitingUsersOpen}
          onOpenChange={setWaitingUsersOpen}
          onUserClick={handleApproveClick}
        />
      </div>

      <div className="flex gap-3">
        <QRScanner
          onRead={handleQRRead}
          trigger={t("approveUsers.scanQRCode")}
          title={t("approveUsers.scanApprovalQR")}
          description={t("approveUsers.pointCamera")}
        />
      </div>

      <ApproveUserDialog
        open={approveDialogOpen}
        onOpenChange={setApproveDialogOpen}
        selectedUser={selectedUser?.callsign ?? null}
        approvalCode={approvalCode}
        onApprovalCodeChange={setApprovalCode}
        onApprove={handleApprove}
        onReject={handleReject}
        isApproving={approveUserMutation.isPending}
        isRejecting={rejectUserMutation.isPending}
      />
    </div>
  );
}
