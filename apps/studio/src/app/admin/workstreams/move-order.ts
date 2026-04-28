import { arrayMove } from "@dnd-kit/sortable";

/** Pure reorder step used by the board and Vitest (DnD semantics without DOM). */
export function moveOrderedIds(
  orderedIds: readonly string[],
  activeId: string,
  overId: string | undefined | null,
): string[] | null {
  if (!overId || activeId === overId) return null;
  const oldIndex = orderedIds.indexOf(activeId);
  const newIndex = orderedIds.indexOf(overId);
  if (oldIndex === -1 || newIndex === -1) return null;
  return arrayMove([...orderedIds], oldIndex, newIndex);
}
