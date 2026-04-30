"use client";

import { useCallback, useEffect, type ReactNode } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import Link from "@tiptap/extension-link";
import { Markdown } from "@tiptap/markdown";
import {
  Bold,
  ChevronDown,
  Code2,
  Heading2,
  Heading3,
  Italic,
  Link2,
  List,
  ListOrdered,
} from "lucide-react";

export type MarkdownEditorProps = {
  value: string;
  onChange: (markdown: string) => void;
};

function ToolbarButton({
  pressed,
  disabled,
  title,
  children,
  onClick,
}: {
  pressed?: boolean;
  disabled?: boolean;
  title: string;
  children: ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      title={title}
      disabled={disabled}
      onMouseDown={(e) => e.preventDefault()}
      onClick={() => onClick()}
      className={`rounded-md border px-2 py-1.5 text-xs font-medium transition disabled:opacity-40 ${
        pressed
          ? "border-sky-500/50 bg-sky-500/15 text-sky-100"
          : "border-zinc-700 bg-zinc-900 text-zinc-300 hover:border-zinc-600 hover:bg-zinc-800"
      }`}
    >
      {children}
    </button>
  );
}

function ToolbarSep() {
  return <div className="mx-0.5 hidden h-6 w-px bg-zinc-800 sm:block" aria-hidden />;
}

/**
 * TipTap editor with Markdown I/O and a zinc-styled formatting toolbar.
 */
export function MarkdownEditor({ value, onChange }: MarkdownEditorProps) {
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
        link: false,
      }),
      Markdown,
      Placeholder.configure({
        placeholder: "Write documentation body (markdown)…",
      }),
      Link.configure({
        openOnClick: false,
        autolink: true,
        HTMLAttributes: {
          class: "text-sky-400 underline underline-offset-2",
        },
      }),
    ],
    content: value,
    contentType: "markdown",
    immediatelyRender: false,
    editorProps: {
      attributes: {
        class:
          "min-h-[280px] prose prose-invert prose-sm max-w-none focus:outline-none px-3 py-2 text-zinc-200 prose-headings:text-zinc-50 prose-p:my-2 prose-li:my-0.5 prose-code:text-amber-300 prose-pre:bg-zinc-950 prose-pre:border prose-pre:border-zinc-800",
      },
    },
    onUpdate: ({ editor: ed }) => {
      onChange(ed.getMarkdown());
    },
  });

  const setLink = useCallback(() => {
    if (!editor) return;
    const prev = editor.getAttributes("link").href as string | undefined;
    const next = window.prompt("Link URL", prev ?? "https://");
    if (next === null) return;
    if (next === "") {
      editor.chain().focus().unsetLink().run();
      return;
    }
    editor.chain().focus().extendMarkRange("link").setLink({ href: next }).run();
  }, [editor]);

  useEffect(() => {
    if (!editor) return;
    const current = editor.getMarkdown();
    if (current === value) return;
    editor.commands.setContent(value, { contentType: "markdown" });
  }, [editor, value]);

  if (!editor) {
    return (
      <div
        data-testid="admin-markdown-editor"
        className="rounded-lg border border-zinc-800 bg-zinc-950/50 p-8 text-sm text-zinc-500"
      >
        Loading editor…
      </div>
    );
  }

  return (
    <div
      data-testid="admin-markdown-editor"
      className="flex flex-col overflow-hidden rounded-lg border border-zinc-800 bg-zinc-950/40"
    >
      <div className="flex flex-wrap items-center gap-1 border-b border-zinc-800 bg-zinc-900/60 px-2 py-1.5">
        <ToolbarButton
          title="Bold"
          pressed={editor.isActive("bold")}
          onClick={() => editor.chain().focus().toggleBold().run()}
        >
          <Bold className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton
          title="Italic"
          pressed={editor.isActive("italic")}
          onClick={() => editor.chain().focus().toggleItalic().run()}
        >
          <Italic className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarSep />
        <ToolbarButton
          title="Heading 2"
          pressed={editor.isActive("heading", { level: 2 })}
          onClick={() =>
            editor.chain().focus().toggleHeading({ level: 2 }).run()
          }
        >
          <Heading2 className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton
          title="Heading 3"
          pressed={editor.isActive("heading", { level: 3 })}
          onClick={() =>
            editor.chain().focus().toggleHeading({ level: 3 }).run()
          }
        >
          <Heading3 className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarSep />
        <ToolbarButton
          title="Bulleted list"
          pressed={editor.isActive("bulletList")}
          onClick={() => editor.chain().focus().toggleBulletList().run()}
        >
          <List className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton
          title="Ordered list"
          pressed={editor.isActive("orderedList")}
          onClick={() => editor.chain().focus().toggleOrderedList().run()}
        >
          <ListOrdered className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarSep />
        <ToolbarButton
          title="Code block"
          pressed={editor.isActive("codeBlock")}
          onClick={() => editor.chain().focus().toggleCodeBlock().run()}
        >
          <Code2 className="h-4 w-4" />
        </ToolbarButton>
        <ToolbarButton title="Insert link" onClick={setLink}>
          <Link2 className="h-4 w-4" />
        </ToolbarButton>
        <div className="ml-auto hidden items-center gap-1 text-[10px] text-zinc-600 sm:flex">
          <ChevronDown className="h-3 w-3" aria-hidden />
          Markdown · TipTap
        </div>
      </div>

      <div data-testid="admin-markdown-editor-body" className="min-h-0 flex-1 overflow-y-auto">
        <EditorContent editor={editor} />
      </div>
    </div>
  );
}
