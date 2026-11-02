import type { BoardState, Column, TaskTeam } from "./types";

export const columns = [
  { id: "ideas", title: "Ideas" },
  { id: "planned", title: "Planned" },
  { id: "building", title: "Building" },
  { id: "qa", title: "QA" },
  { id: "shipped", title: "Shipped" },
] as const satisfies readonly Column[];

export const columnIds = columns.map((column) => column.id);

export const tagTones: Record<TaskTeam, string> = {
  Backend: "bg-blue-500/10 text-blue-700 dark:text-blue-300",
  Data: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  Design: "bg-sky-500/10 text-sky-700 dark:text-sky-300",
  Docs: "bg-indigo-500/10 text-indigo-700 dark:text-indigo-300",
  "Finance Ops": "bg-teal-500/10 text-teal-700 dark:text-teal-300",
  Platform: "bg-cyan-500/10 text-cyan-700 dark:text-cyan-300",
  Product: "bg-orange-500/10 text-orange-700 dark:text-orange-300",
  QA: "bg-red-500/10 text-red-700 dark:text-red-300",
  Security: "bg-teal-500/10 text-teal-700 dark:text-teal-300",
};

export const initialBoard: BoardState = {
  ideas: [],
  planned: [],
  building: [],
  qa: [],
  shipped: [],
};
