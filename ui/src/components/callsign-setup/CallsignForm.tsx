import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription } from "@/components/ui/alert";

interface CallsignFormProps {
  onSubmit: (callsign: string) => void;
  onBack: () => void;
  errorMessage?: string;
  onErrorClear?: () => void;
  isLoading?: boolean;
}

export function CallsignForm({
  onSubmit,
  onBack,
  errorMessage,
  onErrorClear,
  isLoading = false,
}: CallsignFormProps) {
  const { t } = useTranslation();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({ mode: "onChange", defaultValues: { callsign: "" } });

  // Sent as typed: CALLSIGN_PATTERN is ^[A-Za-z0-9][A-Za-z0-9_]{2,29}$, unique without regard to case.
  const submit = handleSubmit(({ callsign }) => onSubmit(callsign));

  return (
    <form
      className="space-y-4"
      onSubmit={submit}
      noValidate
      data-testid="callsign-form"
    >
      <div className="space-y-2">
        <Label htmlFor="callsign">{t("callsignSetup.yourCallsignLabel")}</Label>
        <Input
          id="callsign"
          type="text"
          autoComplete="off"
          placeholder={t("callsignSetup.callsignPlaceholder")}
          className="font-mono"
          data-testid="callsign-input"
          {...register("callsign", {
            required: t("callsignSetup.validation.required"),
            pattern: {
              value: /^[A-Za-z0-9_]+$/,
              message: t("callsignSetup.validation.pattern"),
            },
            validate: {
              firstChar: (value) =>
                /^[A-Za-z0-9]/.test(value) ||
                t("callsignSetup.validation.firstChar"),
            },
            minLength: { value: 3, message: t("callsignSetup.validation.min") },
            maxLength: {
              value: 30,
              message: t("callsignSetup.validation.max"),
            },
            onChange: () => onErrorClear?.(),
          })}
        />
        {errors.callsign && (
          <p
            className="text-sm text-destructive"
            data-testid="callsign-validation-error"
          >
            {errors.callsign.message}
          </p>
        )}
        {errorMessage && (
          <Alert variant="destructive" data-testid="callsign-error-alert">
            <AlertCircle className="h-4" />
            <AlertDescription>{errorMessage}</AlertDescription>
          </Alert>
        )}
      </div>

      <div className="flex gap-2">
        <Button
          type="button"
          variant="outline"
          onClick={onBack}
          disabled={isLoading}
          data-testid="callsign-back-button"
        >
          {t("callsignSetup.buttons.back")}
        </Button>
        <Button
          type="submit"
          variant={"outline"}
          className="flex-1 bg-primary-light hover:bg-primary-light/90"
          disabled={isLoading}
          data-testid="callsign-submit-button"
        >
          {isLoading
            ? t("callsignSetup.buttons.settingUp")
            : t("callsignSetup.buttons.continue")}
        </Button>
      </div>
    </form>
  );
}
