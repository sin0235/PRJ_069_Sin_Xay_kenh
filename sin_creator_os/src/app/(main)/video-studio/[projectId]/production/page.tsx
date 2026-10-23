import ContentVideoProduction from "./_components/content_video_production";

export default async function ContentVideoProductionPage({
  params,
  searchParams,
}: {
  params: Promise<{ projectId: string }>;
  searchParams: Promise<{ plan?: string | string[]; run?: string | string[] }>;
}) {
  const [{ projectId }, query] = await Promise.all([params, searchParams]);
  const planId = Array.isArray(query.plan) ? query.plan[0] : query.plan;
  const runId = Array.isArray(query.run) ? query.run[0] : query.run;
  return <ContentVideoProduction projectId={projectId} planId={planId} runId={runId} />;
}
