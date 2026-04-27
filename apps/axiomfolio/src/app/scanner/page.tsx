import { redirect } from "next/navigation";

export default function ScannerPage() {
  redirect("/market/tracked?mode=scan");
}
