import workstreamsJson from "@/data/workstreams.json";
import { buildCalendarEventsByDay } from "@/lib/calendar-events";
import { loadTrackerIndex } from "@/lib/tracker";
import { WorkstreamsFileSchema } from "@/lib/workstreams/schema";

import { CalendarClient } from "./calendar-client";

export const dynamic = "force-static";

export const metadata = { title: "Calendar — Studio" };

export default function AdminCalendarPage() {
  const parsed = WorkstreamsFileSchema.parse(workstreamsJson);
  const { sprints } = loadTrackerIndex();
  const eventsByDay = buildCalendarEventsByDay(parsed, sprints);

  return <CalendarClient eventsByDay={eventsByDay} />;
}
