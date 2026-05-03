export type StartupPhase =
  | "booting"
  | "beamGrow"
  | "beamRelax"
  | "brandReveal"
  | "brandHold"
  | "brandLift"
  | "ctaReveal"
  | "idle"
  | "qrVisible"
  | "enterShell";

export type RootScene = "startup" | "transitioning" | "shell";
export type ShellEntryMode = "shell-enter-home" | "steady";

export type StartupQrStatus =
  | "idle"
  | "ready"
  | "waiting-scan"
  | "waiting-confirm"
  | "success"
  | "expired";

export interface StartupPayload {
  connection: {
    mode: string;
    apiStatus: string;
    cookieStatus: string;
    accountNickname: string;
  };
  qr: {
    status: StartupQrStatus;
    url: string;
    imageDataUrl: string;
  };
  diagnostics: {
    logs: string[];
    lastError: string;
  };
  startup: {
    isAuthenticated: boolean;
    canAutoEnter: boolean;
    hasQr: boolean;
  };
  shell: any;
}
