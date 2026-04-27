import ChartSharePageClient from "./ChartSharePageClient";

export default async function ChartSharePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <ChartSharePageClient token={token} />;
}
