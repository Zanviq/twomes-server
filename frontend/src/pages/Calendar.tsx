import { useCallback, useRef, useState } from "react";
import FullCalendar from "@fullcalendar/react";
import dayGridPlugin from "@fullcalendar/daygrid";
import timeGridPlugin from "@fullcalendar/timegrid";
import interactionPlugin from "@fullcalendar/interaction";
import type { DateClickArg } from "@fullcalendar/interaction";
import type { DatesSetArg, EventClickArg } from "@fullcalendar/core";
import { Shell } from "../components/layout/Shell";
import { EventDialog, GCAL_COLORS } from "../components/calendar/EventDialog";
import { api, CalEvent } from "../lib/api";
import { toast } from "../store/toast";

export function Calendar() {
  const [events, setEvents] = useState<CalEvent[]>([]);
  const [dialog, setDialog] = useState<Partial<CalEvent> | null>(null);
  const [source, setSource] = useState("internal");
  const range = useRef<{ from?: string; to?: string }>({});

  const reload = useCallback(async () => {
    try {
      setEvents(await api.calEvents(range.current.from, range.current.to));
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "이벤트 로드 실패");
    }
  }, []);

  const onDatesSet = (arg: DatesSetArg) => {
    range.current = { from: arg.start.toISOString(), to: arg.end.toISOString() };
    reload();
    api.calSource().then((s) => setSource(s.source)).catch(() => {});
  };

  const onDateClick = (arg: DateClickArg) => {
    setDialog({ start: `${arg.dateStr}T09:00:00`, end: `${arg.dateStr}T10:00:00`, allDay: arg.allDay });
  };

  const onEventClick = (arg: EventClickArg) => {
    const ev = events.find((e) => e.id === arg.event.id);
    if (ev) setDialog(ev);
  };

  const save = async (e: Partial<CalEvent>) => {
    try {
      if (e.id) await api.calUpdate(e.id, e);
      else await api.calCreate(e);
      setDialog(null);
      toast.ok("저장됨");
      reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "저장 실패");
    }
  };

  const del = async (id: string) => {
    try {
      await api.calDelete(id);
      setDialog(null);
      toast.ok("삭제됨");
      reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "삭제 실패");
    }
  };

  const fcEvents = events.map((e) => ({
    id: e.id,
    title: e.title,
    start: e.start,
    end: e.end,
    allDay: e.allDay,
    backgroundColor: GCAL_COLORS[e.color] ?? GCAL_COLORS["2"],
    borderColor: GCAL_COLORS[e.color] ?? GCAL_COLORS["2"],
  }));

  return (
    <Shell
      title="캘린더"
      actions={
        <span className="badge">{source === "google" ? "Google 동기화" : "내부 저장"}</span>
      }
    >
      <div className="card fc-twoems p-4">
        <FullCalendar
          plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
          initialView="dayGridMonth"
          locale="ko"
          headerToolbar={{
            left: "prev,next today",
            center: "title",
            right: "dayGridMonth,timeGridWeek,timeGridDay",
          }}
          buttonText={{ today: "오늘", month: "월", week: "주", day: "일" }}
          events={fcEvents}
          datesSet={onDatesSet}
          dateClick={onDateClick}
          eventClick={onEventClick}
          dayMaxEvents={3}
          height="auto"
          nowIndicator
        />
      </div>
      <EventDialog
        open={!!dialog}
        initial={dialog}
        onClose={() => setDialog(null)}
        onSave={save}
        onDelete={del}
      />
    </Shell>
  );
}
