import { getInfrastructureStatus } from "@/lib/command-center";
import InfraClient from "./infra-client";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function InfrastructurePage() {
  const services = await getInfrastructureStatus();
  const checkedAt = new Date().toISOString();

  return <InfraClient initialServices={services} initialCheckedAt={checkedAt} />;
}
