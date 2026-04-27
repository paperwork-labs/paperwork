import { redirect } from "next/navigation";

/**
 * Vite `StrategiesManager` redirected to the strategies list under `/market/strategies`.
 * The Next list lives at `/strategies`.
 */
export default function StrategiesManagePage() {
  redirect("/strategies");
}
