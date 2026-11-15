import * as Dialog from "@radix-ui/react-dialog";
import type { ReactNode } from "react";

export function Drawer({ open, onClose, title, children, width = "max-w-[760px]" }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; width?: string }) {
  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-ink/30" />
        <Dialog.Content className={`fixed right-0 top-0 z-50 flex h-full w-full ${width} flex-col bg-white shadow-2xl outline-none`}>
          <div className="flex items-start justify-between gap-4 border-b border-line px-6 py-4">
            <Dialog.Title className="m-0 font-display text-xl font-semibold">{title}</Dialog.Title>
            <Dialog.Close className="btn-ghost px-3 py-1.5" aria-label="Close (Esc)">
              Close <kbd>Esc</kbd>
            </Dialog.Close>
          </div>
          <Dialog.Description className="sr-only">Details</Dialog.Description>
          <div className="flex-1 overflow-auto px-6 py-5">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
