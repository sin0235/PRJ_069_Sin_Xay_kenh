import ContentVideoProduction from "./_components/content_video_production";

export default async function ContentVideoProductionPage({
  params,
  searchParams,
}: {
  params: Promise<{ projectId: string }>;
  searchParams: Promise<{ plan?: string | string[]; run?: string | string[]; new?: string | string[] }>;
}) {
  const [{ projectId }, query] = await Promise.all([params, searchParams]);
  const planId = Array.isArray(query.plan) ? query.plan[0] : query.plan;
  const runId = Array.isArray(query.run) ? query.run[0] : query.run;
  const startNew = (Array.isArray(query.new) ? query.new[0] : query.new) === "1";
  return <ContentVideoProduction projectId={projectId} planId={planId} runId={runId} startNew={startNew} />;
}
