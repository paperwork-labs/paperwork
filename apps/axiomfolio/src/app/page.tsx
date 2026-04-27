import { RequireAuthClient } from "@/components/auth/RequireAuthClient";
import HomeClient from "@/components/home/HomeClient";

export default function HomePage() {
  return (
    <RequireAuthClient>
      <HomeClient />
    </RequireAuthClient>
  );
}
