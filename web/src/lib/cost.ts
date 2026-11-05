import type { Cost, ModelEntry } from "@/lib/api";
import { tr } from "@/lib/i18n";

/** Cost labels are English source strings; render them with t(COST_LABEL[cost]) or tr(). */
export const COST_LABEL: Record<Cost, string> = { member: "Member", free: "Free", paid: "Paid", local: "Local" };

/** Paid models bill per use, so they are only used after the user says yes. Returns true when it is fine to go on. */
export function confirmPaid(m: Pick<ModelEntry, "label" | "cost">, action: "use" | "test" = "use"): boolean {
  if (m.cost !== "paid") return true;
  const what = action === "use" ? tr("every question you ask after switching is billed") : tr("a test is billed too");
  return window.confirm(
    tr("“{label}” is a pay-per-use model (billed to your OpenRouter balance), and {what}.", { label: m.label, what }) +
      "\n\n" +
      tr("Do you want to continue?"),
  );
}
